"""Tests for CivicPlusConnector.

CivicPlus has no dynamic column layout the way Legistar's RadGrid does,
so the failure modes here are a different shape but the same class of
problem: rows that don't carry the data cells a parser assumes
(catAgendaRow rows with no <strong aria-label>, no agenda link, no
minutes/media cell), a category-discovery step that has to fall back
gracefully across differently-worded body names site to site, and a
title-parsing regex that has to survive real inconsistent phrasing. No
network calls anywhere in this file - requests.get is always mocked.
"""

from datetime import date as real_date
from unittest.mock import MagicMock, patch

from civic_scraper.connectors import civicplus as civicplus_module

from tests.html_builders import (
    civicplus_agenda_row,
    civicplus_category_checkboxes,
    civicplus_non_data_row,
    civicplus_search_results,
)


class TestExtractBodyFromTitle:
    def test_strips_agenda_for_the_date_prefix_and_meeting_suffix(self, civicplus_connector):
        title = "Agenda for the May 6, 2025 City Council Meeting."
        assert civicplus_connector._extract_body_from_title(title, "fallback") == "City Council"

    def test_handles_missing_the(self, civicplus_connector):
        title = "Agenda for May 6, 2025 Planning Commission Meeting."
        assert (
            civicplus_connector._extract_body_from_title(title, "fallback") == "Planning Commission"
        )

    def test_handles_missing_trailing_period(self, civicplus_connector):
        title = "Agenda for the May 6, 2025 City Council Meeting"
        assert civicplus_connector._extract_body_from_title(title, "fallback") == "City Council"

    def test_falls_back_when_title_does_not_match_expected_shape(self, civicplus_connector):
        assert civicplus_connector._extract_body_from_title("Packet.pdf", "fallback") == "fallback"

    def test_empty_title_falls_back(self, civicplus_connector):
        assert civicplus_connector._extract_body_from_title("", "fallback") == "fallback"


class TestThisMonthRange:
    def test_returns_first_and_last_day_of_the_current_month(
        self, civicplus_connector, monkeypatch
    ):
        class _FrozenDate:
            @staticmethod
            def today():
                return real_date(2024, 2, 15)  # 2024 is a leap year - exercises the 29-day case

            replace = real_date.replace

        monkeypatch.setattr(civicplus_module, "date", _FrozenDate)
        start, end = civicplus_module._this_month_range()
        assert start == "02/01/2024"
        assert end == "02/29/2024"


class TestSearchUrl:
    def test_this_month_uses_computed_date_range(self, civicplus_connector, monkeypatch):
        monkeypatch.setattr(
            civicplus_module, "_this_month_range", lambda: ("05/01/2025", "05/31/2025")
        )
        url = civicplus_connector._search_url("This Month", "12")
        assert "startDate=05/01/2025" in url
        assert "endDate=05/31/2025" in url
        assert "CIDs=12" in url

    def test_known_relative_period_maps_to_its_date_selector(self, civicplus_connector):
        url = civicplus_connector._search_url("Last Month", "12")
        assert "dateSelector=2" in url

    def test_unknown_period_falls_back_to_selector_3(self, civicplus_connector):
        url = civicplus_connector._search_url("Whenever", "12")
        assert "dateSelector=3" in url

    def test_none_period_searches_everything(self, civicplus_connector):
        url = civicplus_connector._search_url(None, "12")
        assert "dateSelector=3" in url
        assert "startDate=&endDate=" in url

    def test_period_matching_is_case_insensitive(self, civicplus_connector):
        url = civicplus_connector._search_url("LAST WEEK", "12")
        assert "dateSelector=1" in url


class TestFindCategoryId:
    def test_prepopulated_category_id_skips_discovery_entirely(self, civicplus_connector):
        civicplus_connector._category_id = "99"
        with patch.object(civicplus_connector, "discover_categories") as discover:
            assert civicplus_connector._find_category_id() == "99"
        discover.assert_not_called()

    def test_exact_match(self, civicplus_connector):
        cats = {"city council": "1", "planning commission": "2"}
        with patch.object(civicplus_connector, "discover_categories", return_value=cats):
            assert civicplus_connector._find_category_id() == "1"

    def test_substring_match_when_no_exact_match(self, civicplus_connector):
        # Real sites label this "City Council Meetings" instead of "City Council".
        cats = {"city council meetings": "1"}
        with patch.object(civicplus_connector, "discover_categories", return_value=cats):
            assert civicplus_connector._find_category_id() == "1"

    def test_falls_back_to_any_category_containing_council(self, civicplus_connector):
        civicplus_connector.body = "Legislative Body"
        cats = {"town council": "1", "parks board": "2"}
        with patch.object(civicplus_connector, "discover_categories", return_value=cats):
            assert civicplus_connector._find_category_id() == "1"

    def test_no_match_at_all_raises_with_available_categories_listed(self, civicplus_connector):
        cats = {"parks board": "2"}
        with patch.object(civicplus_connector, "discover_categories", return_value=cats):
            try:
                civicplus_connector._find_category_id()
            except ValueError as exc:
                assert "parks board" in str(exc)
            else:
                raise AssertionError("expected ValueError for no matching category")

    def test_no_categories_discovered_at_all_raises(self, civicplus_connector):
        with patch.object(civicplus_connector, "discover_categories", return_value={}):
            try:
                civicplus_connector._find_category_id()
            except ValueError as exc:
                assert "AgendaCenter" in str(exc)
            else:
                raise AssertionError("expected ValueError when no categories exist")


class TestDiscoverCategories:
    def test_parses_checkbox_label_pairs_into_a_name_to_id_map(self, civicplus_connector):
        html = civicplus_category_checkboxes({"City Council": "1", "Planning Commission": "2"})
        fake_response = MagicMock(text=html)
        fake_response.raise_for_status.return_value = None
        with patch.object(civicplus_module.requests, "get", return_value=fake_response):
            cats = civicplus_connector.discover_categories()
        assert cats == {"city council": "1", "planning commission": "2"}

    def test_checkbox_with_no_matching_label_is_skipped(self, civicplus_connector):
        html = '<input type="checkbox" name="chkCategoryID" id="cat0" value="1">'
        fake_response = MagicMock(text=html)
        fake_response.raise_for_status.return_value = None
        with patch.object(civicplus_module.requests, "get", return_value=fake_response):
            assert civicplus_connector.discover_categories() == {}


class TestParseMeetings:
    def test_minimal_row_extracts_date_and_agenda_url(self, civicplus_connector):
        html = civicplus_search_results([civicplus_agenda_row()])
        meetings = civicplus_connector._parse_meetings(html, limit=None)
        assert len(meetings) == 1
        m = meetings[0]
        assert m.date == "May 6, 2025 City Council Meeting."
        assert m.agenda_url == (
            "https://testville.civicplus.com/AgendaCenter/ViewFile/Agenda/_05062025-100?html=true"
        )
        assert m.meeting_details_url == m.agenda_url
        assert m.source == "civicplus"

    def test_non_data_row_is_skipped_not_crashed_on(self, civicplus_connector):
        # The equivalent of a Legistar pager row sharing the table with
        # real data - no <strong aria-label> at all.
        html = civicplus_search_results([civicplus_non_data_row(), civicplus_agenda_row()])
        meetings = civicplus_connector._parse_meetings(html, limit=None)
        assert len(meetings) == 1

    def test_row_with_no_agenda_link_has_none_urls_and_fallback_body(self, civicplus_connector):
        html = civicplus_search_results([civicplus_agenda_row(agenda_href=None)])
        meetings = civicplus_connector._parse_meetings(html, limit=None)
        m = meetings[0]
        assert m.agenda_url is None
        assert m.meeting_details_url is None
        assert m.body == "City Council"  # falls back to self.body with no title text to parse

    def test_row_with_no_minutes_cell_link_has_none_minutes_url(self, civicplus_connector):
        html = civicplus_search_results([civicplus_agenda_row(minutes_href=None)])
        meetings = civicplus_connector._parse_meetings(html, limit=None)
        assert meetings[0].minutes_url is None

    def test_row_with_minutes_link_is_resolved_to_an_absolute_url(self, civicplus_connector):
        html = civicplus_search_results(
            [civicplus_agenda_row(minutes_href="/AgendaCenter/ViewFile/Minutes/_05062025-100")]
        )
        meetings = civicplus_connector._parse_meetings(html, limit=None)
        assert meetings[0].minutes_url == (
            "https://testville.civicplus.com/AgendaCenter/ViewFile/Minutes/_05062025-100"
        )

    def test_row_with_no_video_link_has_none_video_url(self, civicplus_connector):
        html = civicplus_search_results([civicplus_agenda_row(video_href=None)])
        assert civicplus_connector._parse_meetings(html, limit=None)[0].video_url is None

    def test_body_is_parsed_from_the_agenda_link_title_text(self, civicplus_connector):
        html = civicplus_search_results(
            [
                civicplus_agenda_row(
                    agenda_text="Agenda for the May 6, 2025 Planning Commission Meeting."
                )
            ]
        )
        meetings = civicplus_connector._parse_meetings(html, limit=None)
        assert meetings[0].body == "Planning Commission"

    def test_limit_truncates_results(self, civicplus_connector):
        rows = [civicplus_agenda_row(date_label=f"Agenda for {i}") for i in range(5)]
        html = civicplus_search_results(rows)
        meetings = civicplus_connector._parse_meetings(html, limit=2)
        assert len(meetings) == 2

    def test_multiple_real_rows_all_parse_independently(self, civicplus_connector):
        rows = [
            civicplus_agenda_row(
                date_label="Agenda for May 6, 2025 City Council Meeting.",
                agenda_href="/AgendaCenter/ViewFile/Agenda/_05062025-100",
            ),
            civicplus_non_data_row(),
            civicplus_agenda_row(
                date_label="Agenda for June 3, 2025 City Council Meeting.",
                agenda_href="/AgendaCenter/ViewFile/Agenda/_06032025-101",
                minutes_href="/AgendaCenter/ViewFile/Minutes/_06032025-101",
            ),
        ]
        html = civicplus_search_results(rows)
        meetings = civicplus_connector._parse_meetings(html, limit=None)
        assert len(meetings) == 2
        assert meetings[0].minutes_url is None
        assert meetings[1].minutes_url is not None


class TestListMeetings:
    def test_full_call_chain_with_a_prepopulated_category_id(self, civicplus_connector):
        civicplus_connector._category_id = "12"
        html = civicplus_search_results([civicplus_agenda_row()])
        fake_response = MagicMock(text=html)
        fake_response.raise_for_status.return_value = None
        with patch.object(civicplus_module.requests, "get", return_value=fake_response) as get:
            meetings = civicplus_connector.list_meetings(period="Last Month", limit=5)
        assert len(meetings) == 1
        called_url = get.call_args[0][0]
        assert "CIDs=12" in called_url
        assert "dateSelector=2" in called_url

    def test_passing_a_new_body_forces_category_rediscovery(self, civicplus_connector):
        civicplus_connector._category_id = "12"  # City Council's id from cities.yaml
        html = civicplus_search_results([civicplus_agenda_row()])
        fake_response = MagicMock(text=html)
        fake_response.raise_for_status.return_value = None
        with (
            patch.object(civicplus_module.requests, "get", return_value=fake_response),
            patch.object(
                civicplus_connector,
                "discover_categories",
                return_value={"planning commission": "7"},
            ),
        ):
            civicplus_connector.list_meetings(body="Planning Commission")
        assert civicplus_connector._category_id == "7"
