"""Data model for the human review queue.

An extraction whose confidence falls below its field type's publish
threshold (see routing.py) doesn't ship - it becomes a ReviewQueueItem
and waits for a person to accept, edit, or reject it. That decision
either lets the value publish after all, corrects it, or throws it out -
and an accepted or edited decision feeds back into the gold set
(gold_export.py), which is the actual point of building this queue
rather than just logging low-confidence values and moving on.
"""

from typing import Literal

from pydantic import BaseModel

from civic_scraper.models import Provenance

FieldType = Literal["motions", "people", "locations", "amounts"]


class ReviewQueueItem(BaseModel):
    """One below-threshold Extracted[T] value, held back from publication.

    `value` and `resolved_value` are plain dicts - the JSON form of a
    Motion/Person/Location/MonetaryAmount - rather than a typed union.
    A reviewer only ever corrects one text field on the value (see
    cli.py's _PRIMARY_FIELD), and a strict Pydantic discriminated union
    would need a discriminator field this data doesn't carry.
    """

    queue_id: str
    field_type: FieldType
    value: dict
    confidence: float
    provenance: Provenance

    jurisdiction: str
    body: str
    meeting_date: str
    item_number: str | None
    item_title: str
    document_text: str
    source_document: str

    status: Literal["pending", "accepted", "edited", "rejected"] = "pending"
    resolved_value: dict | None = None
    reviewer_notes: str | None = None
