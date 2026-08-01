"""Tests for the review-queue-to-gold-set flywheel."""

import pytest
from civic_scraper.models import Provenance
from civic_scraper.review.gold_export import review_item_to_gold_case
from civic_scraper.review.models import ReviewQueueItem


def _item(**overrides) -> ReviewQueueItem:
    base = dict(
        queue_id="sj-cc-2026-01-01-4.2-people-0",
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
        source_document="san-jose-city-council-2026-01-01-minutes",
        status="pending",
    )
    base.update(overrides)
    return ReviewQueueItem(**base)


class TestReviewItemToGoldCase:
    def test_accepted_item_exports_its_value_verbatim(self):
        item = _item(status="accepted")

        case = review_item_to_gold_case(item)

        assert case["id"] == "review-sj-cc-2026-01-01-4.2-people-0"
        assert case["jurisdiction"] == "San Jose"
        assert case["source_document"] == "san-jose-city-council-2026-01-01-minutes"
        assert case["expected"]["people"] == [
            {
                "raw_name": "Doan",
                "canonical_name": None,
                "role": "councilmember",
                "source_text": "Councilmember Doan",
            }
        ]
        assert case["expected"]["motions"] == []
        assert case["expected"]["locations"] == []
        assert case["expected"]["amounts"] == []
        assert case["annotated_fields"] == ["people"]

    def test_edited_item_exports_the_resolved_value_not_the_original(self):
        item = _item(
            status="edited",
            resolved_value={
                "raw_name": "Bien Doan",
                "canonical_name": None,
                "role": "councilmember",
            },
        )

        case = review_item_to_gold_case(item)

        assert case["expected"]["people"][0]["raw_name"] == "Bien Doan"

    def test_rejected_item_cannot_be_exported(self):
        item = _item(status="rejected")
        with pytest.raises(ValueError, match="rejected"):
            review_item_to_gold_case(item)

    def test_pending_item_cannot_be_exported(self):
        item = _item(status="pending")
        with pytest.raises(ValueError, match="pending"):
            review_item_to_gold_case(item)
