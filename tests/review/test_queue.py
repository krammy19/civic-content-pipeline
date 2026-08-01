"""Tests for review-queue file persistence and volume tracking."""

from civic_scraper.models import Provenance
from civic_scraper.review import queue
from civic_scraper.review.models import ReviewQueueItem


def _item(queue_id: str = "case-people-0", status: str = "pending", **overrides) -> ReviewQueueItem:
    base = dict(
        queue_id=queue_id,
        field_type="people",
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
        status=status,
    )
    base.update(overrides)
    return ReviewQueueItem(**base)


class TestSaveAndLoad:
    def test_save_then_load_round_trips(self, tmp_path):
        item = _item()
        queue.save_item(item, tmp_path)

        loaded = queue.load_items(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].queue_id == "case-people-0"
        assert loaded[0].value["raw_name"] == "Doan"

    def test_save_overwrites_same_queue_id(self, tmp_path):
        item = _item()
        queue.save_item(item, tmp_path)

        item.status = "accepted"
        queue.save_item(item, tmp_path)

        loaded = queue.load_items(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].status == "accepted"

    def test_load_filters_by_status(self, tmp_path):
        queue.save_item(_item("a", status="pending"), tmp_path)
        queue.save_item(_item("b", status="accepted"), tmp_path)

        pending = queue.load_items(tmp_path, status="pending")
        assert [item.queue_id for item in pending] == ["a"]

    def test_load_from_missing_directory_is_empty(self, tmp_path):
        assert queue.load_items(tmp_path / "does-not-exist") == []


class TestSummarize:
    def test_counts_by_status(self, tmp_path):
        queue.save_item(_item("a", status="pending"), tmp_path)
        queue.save_item(_item("b", status="accepted"), tmp_path)
        queue.save_item(_item("c", status="rejected"), tmp_path)
        queue.save_item(_item("d", status="pending"), tmp_path)

        counts = queue.summarize(tmp_path)

        assert counts == {"pending": 2, "accepted": 1, "edited": 0, "rejected": 1, "total": 4}

    def test_empty_queue_is_all_zero(self, tmp_path):
        counts = queue.summarize(tmp_path / "does-not-exist")
        assert counts == {"pending": 0, "accepted": 0, "edited": 0, "rejected": 0, "total": 0}
