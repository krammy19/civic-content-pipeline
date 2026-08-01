"""Turn an accepted or edited review-queue item into a new gold case.

This is the flywheel the review CLI exists for. Confidence routing sends
a value here specifically because the model wasn't sure about it; a
person's accept/edit decision resolves that uncertainty, and the result
becomes a permanent, versioned fact the eval suite is scored against from
then on. Human review makes the eval suite stronger over time - that's
the interesting part of M4, not the CLI itself. A rejected item is a
confirmed non-fact (or a fabrication provenance verification missed) and
is never exported; only a positive human decision belongs in gold.
"""

from .models import FieldType, ReviewQueueItem

_EMPTY_EXPECTED: dict[FieldType, list] = {
    "motions": [],
    "people": [],
    "locations": [],
    "amounts": [],
}


def review_item_to_gold_case(item: ReviewQueueItem) -> dict:
    """Build a gold case dict in the same shape as evals/gold/*.json.

    Only the field type this item covers gets a fact; every other field
    type is left empty. This case is meant to be additive to the gold
    set, not a complete annotation of every fact in the source item - a
    reviewer resolving one queued location doesn't also assert "and there
    are no motions here."
    """
    if item.status not in ("accepted", "edited"):
        raise ValueError(
            f"cannot export a gold case from a '{item.status}' item ({item.queue_id}) - "
            "only accepted or edited review decisions represent confirmed facts"
        )

    resolved_value = item.resolved_value if item.status == "edited" else item.value
    expected = {field: list(facts) for field, facts in _EMPTY_EXPECTED.items()}
    expected[item.field_type] = [{**resolved_value, "source_text": item.provenance.source_text}]

    return {
        "id": f"review-{item.queue_id}",
        "jurisdiction": item.jurisdiction,
        "body": item.body,
        "meeting_date": item.meeting_date,
        "source_document": item.source_document,
        "item_number": item.item_number,
        "item_title": item.item_title,
        "document_text": item.document_text,
        "expected": expected,
        # Only this one field type has real ground truth - see
        # evals/metrics.py's evaluate_case(annotated_fields=...). Without
        # this, the eval harness would treat every other field's empty
        # list as "confirmed no facts here" and score the model's other,
        # unrelated, possibly-correct extractions on this same document
        # as false positives.
        "annotated_fields": [item.field_type],
        "notes": (
            f"Promoted from the review queue ({item.queue_id}); a below-threshold "
            f"{item.field_type[:-1]} extraction (confidence {item.confidence:.2f}) was "
            f"human-{item.status} and fed back into the gold set. Only the "
            f"{item.field_type} field is asserted here - see module docstring."
        ),
    }
