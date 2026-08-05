"""Confidence-based publish/review routing.

By the time an AgendaItem reaches this module it's already been through
provenance verification (extraction.agenda_item.drop_unverified) - every
remaining field value is a real, verifiable extraction, not a
fabrication. What's left to decide is whether each individual value is
confident enough to publish on its own. Confidence is per-field, not
per-document (models.Extracted is deliberately shaped that way), so
routing operates field value by field value: a high-confidence vote
tally shouldn't be held back because a neighboring field in the same
item is murky, and a low-confidence name shouldn't publish just because
everything else in the item looks solid.
"""

from dataclasses import dataclass

from civic_scraper.models import AgendaItem

from .models import FieldType, ReviewQueueItem

FIELD_TYPES: tuple[FieldType, ...] = ("motions", "people", "locations", "amounts")

# Derived from evals/baseline.json's per-field calibration curve by
# evals/derive_review_thresholds.py, not hand-picked: for each field,
# the lower edge of the lowest-confidence bucket (with at least 10
# points) whose measured accuracy clears 90%. Locations has no bucket
# that clears that bar with enough data yet, so it keeps the original
# uniform 0.9 - a real, stated gap, not an oversight. See
# docs/review.md's "From one uniform threshold to four derived ones"
# for the full table and the two honest caveats (locations' missing
# data, amounts' non-monotonic top bucket). Re-run
# derive_review_thresholds.py and compare against that table whenever
# the gold set or the extraction prompt changes materially - a
# calibration curve is a snapshot, not a constant.
DEFAULT_THRESHOLDS: dict[FieldType, float] = {
    "motions": 0.85,
    "people": 0.95,
    "locations": 0.9,
    "amounts": 0.85,
}


@dataclass
class ItemContext:
    """Everything about the source item a ReviewQueueItem needs to be
    reviewable on its own, and later convertible into a gold case."""

    case_id: str
    jurisdiction: str
    body: str
    meeting_date: str
    source_document: str
    document_text: str


@dataclass
class RoutingResult:
    published: AgendaItem
    queued: list[ReviewQueueItem]


def route_agenda_item(
    item: AgendaItem,
    *,
    context: ItemContext,
    thresholds: dict[FieldType, float] = DEFAULT_THRESHOLDS,
) -> RoutingResult:
    """Split `item`'s fields into what clears its field type's confidence
    threshold (published) and what doesn't (queued for review).

    `item` is assumed already hallucination-filtered - this function makes
    a publish/hold decision, it does not re-verify provenance.
    """
    published_fields: dict[str, list] = {}
    queued: list[ReviewQueueItem] = []

    for field_type in FIELD_TYPES:
        threshold = thresholds[field_type]
        kept = []
        for index, extracted in enumerate(getattr(item, field_type)):
            if extracted.confidence >= threshold:
                kept.append(extracted)
                continue
            queued.append(
                ReviewQueueItem(
                    queue_id=f"{context.case_id}-{field_type}-{index}",
                    field_type=field_type,
                    value=extracted.value.model_dump(mode="json"),
                    confidence=extracted.confidence,
                    provenance=extracted.provenance,
                    jurisdiction=context.jurisdiction,
                    body=context.body,
                    meeting_date=context.meeting_date,
                    item_number=item.item_number,
                    item_title=item.title,
                    document_text=context.document_text,
                    source_document=context.source_document,
                )
            )
        published_fields[field_type] = kept

    published = item.model_copy(update=published_fields)
    return RoutingResult(published=published, queued=queued)
