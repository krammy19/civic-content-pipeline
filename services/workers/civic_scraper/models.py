"""Canonical Pydantic schema every connector and downstream stage is written against.

Two families of model live here:

  - Scrape output: Meeting, Attachment, LegislationDetails, LegistarAgendaEntry.
    What a connector directly reads off a platform's own HTML — no inference,
    no LLM involved.
  - Extraction output: Provenance, Extracted[T], Person, VoteRecord, Motion,
    Location, MonetaryAmount, AgendaItem. What the (not-yet-built) LLM
    extraction layer produces from a fetched document. Every value an
    extraction step emits is wrapped in Extracted[T] and carries mandatory
    provenance — an extraction with no provenance is invalid by construction,
    not by a validation step someone has to remember to run.

AgendaItem here is deliberately NOT what LegistarConnector.get_meeting_details()
returns — that's LegistarAgendaEntry, Legistar's own agenda-listing row (File #,
Title, Action, Result), which exists independently of any LLM extraction.
AgendaItem is the extraction-layer output that lives on Meeting.agenda_items,
populated only once the extraction layer exists.
"""

from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T")


class Provenance(BaseModel):
    """Where an extracted value came from, so it can be checked against the source."""

    source_document: str  # path or URL
    source_text: str  # verbatim span the value was drawn from
    char_start: int | None = None
    char_end: int | None = None


class Extracted(BaseModel, Generic[T]):
    """Wraps any extracted value with the confidence and provenance it must carry."""

    value: T
    confidence: float
    provenance: Provenance


class Person(BaseModel):
    raw_name: str  # exactly as written in the document
    canonical_name: str | None = None  # resolved to a known roster entry
    role: Literal["mayor", "councilmember", "staff", "applicant", "public", "unknown"]


class VoteRecord(BaseModel):
    person: Person
    position: Literal["aye", "no", "abstain", "absent", "recused"]


class Motion(BaseModel):
    text: str
    moved_by: Person | None = None
    seconded_by: Person | None = None
    outcome: Literal["passed", "failed", "tabled", "withdrawn", "continued", "no_action"]
    votes: list[VoteRecord] = Field(default_factory=list)
    tally: str | None = None  # e.g. "7-2-1" as printed


class Location(BaseModel):
    raw_text: str
    normalized_address: str | None = None
    parcel_id: str | None = None
    lat: float | None = None
    lon: float | None = None


class MonetaryAmount(BaseModel):
    raw_text: str
    amount_usd: Decimal | None = None
    kind: Literal["contract", "grant", "budget", "fee", "fine", "unknown"]


class AgendaItem(BaseModel):
    """Extraction-layer output for one agenda item. See module docstring."""

    item_number: str | None = None
    title: str
    item_type: Literal[
        "consent",
        "public_hearing",
        "action",
        "report",
        "closed_session",
        "ceremonial",
        "unknown",
    ]
    motions: list[Extracted[Motion]] = Field(default_factory=list)
    people: list[Extracted[Person]] = Field(default_factory=list)
    locations: list[Extracted[Location]] = Field(default_factory=list)
    amounts: list[Extracted[MonetaryAmount]] = Field(default_factory=list)


class Attachment(BaseModel):
    name: str
    url: str


class LegislationDetails(BaseModel):
    legislation_url: str
    status: str | None = None
    text: str | None = None
    recommendations: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)


class LegistarAgendaEntry(BaseModel):
    """One row of Legistar's own agenda-item listing, scraped directly from a
    meeting-detail page. Not the extraction-layer AgendaItem above — this is
    what Legistar's HTML already told us, with no LLM involved.
    """

    file_number: str | None = None
    title: str
    type: str | None = None
    agenda_note: str | None = None
    legislation_url: str | None = None
    action: str | None = None
    result: str | None = None
    version: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_consent(self) -> bool:
        return bool(self.type and "consent" in self.type.lower())


class Meeting(BaseModel):
    source: str
    jurisdiction: str
    body: str
    date: str
    time: str | None = None
    location: str | None = None
    meeting_details_url: str | None = None
    agenda_url: str | None = None
    minutes_url: str | None = None
    video_url: str | None = None
    agenda_items: list[AgendaItem] = Field(default_factory=list)
    extraction_run_id: str | None = None


class FetchedDocument(BaseModel):
    """A cached local copy of a fetched agenda/minutes document, with extracted text."""

    source_url: str
    local_path: str
    text: str
    page_count: int
    ocr_required: bool
