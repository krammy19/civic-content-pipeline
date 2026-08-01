"""Tests for the review CLI's decision loop. review_session() is driven
directly against an in-memory item list with a fake input() - no real
terminal, and no dependency on the queue directory beyond a tmp_path."""

from unittest.mock import patch

from civic_scraper.models import Provenance
from civic_scraper.review import queue
from civic_scraper.review.cli import _context_snippet, review_session
from civic_scraper.review.models import ReviewQueueItem


def _item(field_type: str = "people", **overrides) -> ReviewQueueItem:
    base = dict(
        queue_id="case-people-0",
        field_type=field_type,
        value={"raw_name": "Doan", "canonical_name": None, "role": "councilmember"},
        confidence=0.6,
        provenance=Provenance(source_document="doc", source_text="Councilmember Doan"),
        jurisdiction="San Jose",
        body="City Council",
        meeting_date="2026-01-01",
        item_number="4.2",
        item_title="Approve the contract",
        document_text="Councilmember Doan moved to approve the contract.",
        source_document="doc",
        status="pending",
    )
    base.update(overrides)
    return ReviewQueueItem(**base)


class TestContextSnippet:
    def test_includes_surrounding_text(self):
        text = "The quick brown fox jumps over the lazy dog in the park today."
        snippet = _context_snippet(text, "jumps over", radius=10)
        assert "jumps over" in snippet
        assert "fox" in snippet

    def test_falls_back_to_the_span_when_not_found(self):
        assert _context_snippet("no match here", "missing span") == "missing span"


class TestReviewSession:
    def test_accept_persists_status_and_tallies(self, tmp_path):
        item = _item()
        with patch("builtins.input", return_value="a"):
            tally = review_session([item], tmp_path)

        assert tally == {"accepted": 1, "edited": 0, "rejected": 0, "skipped": 0}
        saved = queue.load_items(tmp_path)
        assert saved[0].status == "accepted"

    def test_edit_replaces_the_primary_field_and_saves_resolved_value(self, tmp_path):
        item = _item()
        with patch("builtins.input", side_effect=["e", "Bien Doan"]):
            tally = review_session([item], tmp_path)

        assert tally["edited"] == 1
        saved = queue.load_items(tmp_path)[0]
        assert saved.status == "edited"
        assert saved.resolved_value["raw_name"] == "Bien Doan"
        # Everything else on the value is preserved, only the primary field changed.
        assert saved.resolved_value["role"] == "councilmember"

    def test_reject_records_optional_notes(self, tmp_path):
        item = _item()
        with patch("builtins.input", side_effect=["r", "not a real person"]):
            tally = review_session([item], tmp_path)

        assert tally["rejected"] == 1
        saved = queue.load_items(tmp_path)[0]
        assert saved.status == "rejected"
        assert saved.reviewer_notes == "not a real person"

    def test_skip_leaves_item_pending_and_unsaved(self, tmp_path):
        item = _item()
        with patch("builtins.input", return_value="s"):
            tally = review_session([item], tmp_path)

        assert tally["skipped"] == 1
        assert queue.load_items(tmp_path) == []

    def test_quit_stops_before_processing_remaining_items(self, tmp_path):
        first = _item(queue_id="a")
        second = _item(queue_id="b")
        with patch("builtins.input", return_value="q"):
            tally = review_session([first, second], tmp_path)

        assert tally == {"accepted": 0, "edited": 0, "rejected": 0, "skipped": 0}
        assert queue.load_items(tmp_path) == []

    def test_invalid_input_is_reprompted(self, tmp_path):
        item = _item()
        with patch("builtins.input", side_effect=["bogus", "a"]):
            tally = review_session([item], tmp_path)

        assert tally["accepted"] == 1
