"""Tests for the end-to-end pipeline runner (civic_scraper.runner). Every
external boundary - the connector, extraction, digest generation, the
style checker, metrics storage - is mocked; the thing under test is the
wiring and the failure-handling split between StageError (halts the
run) and a per-item schema failure (counted, doesn't halt). No live API
calls anywhere in this file."""

from unittest.mock import MagicMock, patch

import pytest
from civic_scraper import runner
from civic_scraper.models import AgendaItem, FetchedDocument, LegistarAgendaEntry, Meeting


def _meeting(**overrides) -> Meeting:
    base = dict(
        source="legistar",
        jurisdiction="San Jose",
        body="City Council",
        date="12/09/2025",
        meeting_details_url="https://sanjose.legistar.com/MeetingDetail.aspx?ID=1",
        minutes_url="https://sanjose.legistar.com/minutes.pdf",
    )
    base.update(overrides)
    return Meeting(**base)


def _entry(**overrides) -> dict:
    base = {"name": "San Jose", "connector": "legistar", "legistar_url": "https://x"}
    base.update(overrides)
    return base


def _document(**overrides) -> FetchedDocument:
    base = dict(
        source_url="https://sanjose.legistar.com/minutes.pdf",
        local_path="/tmp/x.pdf",
        text="The Council approved the contract. (Item 2.8)",
        page_count=3,
        ocr_required=False,
    )
    base.update(overrides)
    return FetchedDocument(**base)


class TestResolveCity:
    def test_no_match_raises_stage_error_on_calendar(self):
        with (
            patch.object(runner, "load_cities", return_value=[]),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.resolve_city("Nowhere")
        assert exc.value.stage == "calendar"

    def test_multiple_matches_raises_stage_error(self):
        matches = [_entry(), _entry(name="San Jose 2")]
        with (
            patch.object(runner, "load_cities", return_value=matches),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.resolve_city("San Jose")
        assert exc.value.stage == "calendar"

    def test_non_legistar_connector_raises_stage_error_on_agenda(self):
        with (
            patch.object(runner, "load_cities", return_value=[_entry(connector="civicplus")]),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.resolve_city("San Jose")
        assert exc.value.stage == "agenda"

    def test_legistar_match_returns_entry(self):
        entry = _entry()
        with patch.object(runner, "load_cities", return_value=[entry]):
            assert runner.resolve_city("San Jose") == entry


class TestResolveMeeting:
    def test_connector_failure_raises_stage_error_on_calendar(self):
        fake_conn = MagicMock()
        fake_conn.list_meetings.side_effect = RuntimeError("selenium boom")
        with (
            patch.object(runner, "make_connector", return_value=fake_conn),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.resolve_meeting(_entry(), "12/09/2025")
        assert exc.value.stage == "calendar"

    def test_no_matching_meeting_raises_stage_error(self):
        fake_conn = MagicMock()
        fake_conn.list_meetings.return_value = [_meeting(date="01/01/2026")]
        with (
            patch.object(runner, "make_connector", return_value=fake_conn),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.resolve_meeting(_entry(), "12/09/2025")
        assert exc.value.stage == "calendar"

    def test_matching_meeting_returned(self):
        target = _meeting(date="12/09/2025")
        fake_conn = MagicMock()
        fake_conn.list_meetings.return_value = [_meeting(date="01/01/2026"), target]
        with patch.object(runner, "make_connector", return_value=fake_conn):
            result = runner.resolve_meeting(_entry(), "12/09/2025")
        assert result.date == "12/09/2025"

    def test_falls_back_to_last_month_when_this_month_has_no_details_url(self):
        no_url_meeting = _meeting(date="12/09/2025", meeting_details_url=None)
        with_url_meeting = _meeting(date="11/09/2025")
        fake_conn = MagicMock()
        fake_conn.list_meetings.side_effect = [[no_url_meeting], [with_url_meeting]]
        with patch.object(runner, "make_connector", return_value=fake_conn):
            result = runner.resolve_meeting(_entry(), "11/09/2025")
        assert result.date == "11/09/2025"
        assert fake_conn.list_meetings.call_count == 2


class TestFetchAgendaItems:
    def test_connector_failure_raises_stage_error_on_agenda(self):
        fake_conn = MagicMock()
        fake_conn.get_meeting_details.side_effect = RuntimeError("boom")
        with (
            patch.object(runner, "make_connector", return_value=fake_conn),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.fetch_agenda_items(_entry(), _meeting())
        assert exc.value.stage == "agenda"

    def test_empty_result_raises_stage_error(self):
        fake_conn = MagicMock()
        fake_conn.get_meeting_details.return_value = []
        with (
            patch.object(runner, "make_connector", return_value=fake_conn),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.fetch_agenda_items(_entry(), _meeting())
        assert exc.value.stage == "agenda"

    def test_items_returned(self):
        items = [LegistarAgendaEntry(title="Item one")]
        fake_conn = MagicMock()
        fake_conn.get_meeting_details.return_value = items
        with patch.object(runner, "make_connector", return_value=fake_conn):
            assert runner.fetch_agenda_items(_entry(), _meeting()) == items


class TestFetchMeetingDocument:
    def test_no_url_raises_stage_error_on_document(self):
        meeting = _meeting(minutes_url=None, agenda_url=None)
        with pytest.raises(runner.StageError) as exc:
            runner.fetch_meeting_document(meeting)
        assert exc.value.stage == "document"

    def test_fetch_failure_raises_stage_error(self):
        with (
            patch.object(runner, "fetch_and_extract", side_effect=RuntimeError("404")),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.fetch_meeting_document(_meeting())
        assert exc.value.stage == "document"

    def test_scanned_document_raises_stage_error(self):
        with (
            patch.object(runner, "fetch_and_extract", return_value=_document(ocr_required=True)),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.fetch_meeting_document(_meeting())
        assert exc.value.stage == "document"

    def test_prefers_minutes_url_over_agenda_url(self):
        meeting = _meeting(minutes_url="https://x/minutes.pdf", agenda_url="https://x/agenda.pdf")
        with patch.object(runner, "fetch_and_extract", return_value=_document()) as fetch:
            runner.fetch_meeting_document(meeting)
        fetch.assert_called_once_with("https://x/minutes.pdf", "San Jose")

    def test_falls_back_to_agenda_url(self):
        meeting = _meeting(minutes_url=None, agenda_url="https://x/agenda.pdf")
        with patch.object(runner, "fetch_and_extract", return_value=_document()) as fetch:
            runner.fetch_meeting_document(meeting)
        fetch.assert_called_once_with("https://x/agenda.pdf", "San Jose")


class TestExtractAndRoute:
    def test_untitled_entries_are_skipped(self):
        entries = [LegistarAgendaEntry(title="")]
        with patch.object(runner, "extract_agenda_item_raw") as raw:
            outcome = runner.extract_and_route(
                entries, meeting=_meeting(), document=_document(), model="m"
            )
        raw.assert_not_called()
        assert outcome.published == []
        assert outcome.schema_failures == 0

    def test_extraction_failure_is_counted_not_raised(self):
        entries = [LegistarAgendaEntry(title="Item one", file_number="1.1")]
        with patch.object(runner, "extract_agenda_item_raw", side_effect=ValueError("bad schema")):
            outcome = runner.extract_and_route(
                entries, meeting=_meeting(), document=_document(), model="m"
            )
        assert outcome.schema_failures == 1
        assert outcome.published == []
        assert outcome.raw_extractions == []

    def test_successful_extraction_is_routed_and_published(self):
        entries = [LegistarAgendaEntry(title="Item one", file_number="2.8")]
        raw_item = AgendaItem(title="Item one", item_type="action")
        document = _document()

        with (
            patch.object(runner, "extract_agenda_item_raw", return_value=raw_item),
            patch.object(runner, "drop_unverified", return_value=raw_item) as drop,
        ):
            outcome = runner.extract_and_route(
                entries, meeting=_meeting(), document=document, model="m"
            )

        drop.assert_called_once_with(raw_item, document.text, document.source_url)
        assert outcome.published == [raw_item]
        assert outcome.queued == []
        assert outcome.raw_extractions == [(raw_item, document.text)]
        assert outcome.schema_failures == 0

    def test_one_bad_item_does_not_stop_the_rest(self):
        entries = [
            LegistarAgendaEntry(title="Bad item", file_number="1.1"),
            LegistarAgendaEntry(title="Good item", file_number="1.2"),
        ]
        good_item = AgendaItem(title="Good item", item_type="action")

        with (
            patch.object(
                runner,
                "extract_agenda_item_raw",
                side_effect=[ValueError("boom"), good_item],
            ),
            patch.object(runner, "drop_unverified", return_value=good_item),
        ):
            outcome = runner.extract_and_route(
                entries, meeting=_meeting(), document=_document(), model="m"
            )

        assert outcome.schema_failures == 1
        assert outcome.published == [good_item]


class TestRun:
    def test_dry_run_never_calls_extraction_and_returns_a_plan(self):
        entry = _entry()
        meeting = _meeting()
        document = _document()

        with (
            patch.object(runner, "resolve_city", return_value=entry),
            patch.object(runner, "resolve_meeting", return_value=meeting),
            patch.object(
                runner, "fetch_agenda_items", return_value=[LegistarAgendaEntry(title="x")]
            ),
            patch.object(runner, "fetch_meeting_document", return_value=document),
            patch.object(runner, "extract_agenda_item_raw") as raw,
        ):
            result = runner.run(city="San Jose", meeting_selector="12/09/2025", dry_run=True)

        raw.assert_not_called()
        assert isinstance(result, dict)
        assert result["city"] == "San Jose"
        assert result["items_to_extract"] == 1
        assert result["document_url"] == document.source_url

    def test_a_stage_error_propagates_and_halts_the_run(self):
        with (
            patch.object(
                runner, "resolve_city", side_effect=runner.StageError("calendar", "no such city")
            ),
            pytest.raises(runner.StageError) as exc,
        ):
            runner.run(city="Nowhere", meeting_selector="1/1/2025")
        assert exc.value.stage == "calendar"

    def test_full_run_wires_every_stage_and_returns_an_outcome(self, tmp_path):
        entry = _entry()
        meeting = _meeting()
        document = _document()
        published_item = AgendaItem(title="Item one", item_type="action")
        extraction = runner.ExtractionOutcome(
            published=[published_item],
            queued=[],
            raw_extractions=[(published_item, document.text)],
            schema_failures=0,
        )
        run_metrics = MagicMock()
        metrics_path = tmp_path / "run.json"

        with (
            patch.object(runner, "resolve_city", return_value=entry),
            patch.object(runner, "resolve_meeting", return_value=meeting),
            patch.object(
                runner, "fetch_agenda_items", return_value=[LegistarAgendaEntry(title="x")]
            ),
            patch.object(runner, "fetch_meeting_document", return_value=document),
            patch.object(runner, "extract_and_route", return_value=extraction) as extract_and_route,
            patch.object(
                runner, "generate_digest", return_value="# Digest text"
            ) as generate_digest,
            patch.object(
                runner, "compute_run_metrics", return_value=run_metrics
            ) as compute_metrics,
            patch.object(runner, "save_run_metrics", return_value=metrics_path) as save_metrics,
            patch("checks.style_check.check_deterministic", return_value=[]),
            patch("checks.style_check.judge_style", return_value=[]),
        ):
            result = runner.run(city="San Jose", meeting_selector="12/09/2025")

        extract_and_route.assert_called_once()
        generate_digest.assert_called_once()
        compute_metrics.assert_called_once()
        save_metrics.assert_called_once_with(run_metrics)
        assert result.digest == "# Digest text"
        assert result.style_findings == []
        assert result.metrics is run_metrics
        assert result.metrics_path == str(metrics_path)
