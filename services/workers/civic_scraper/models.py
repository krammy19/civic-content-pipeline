"""Canonical Pydantic schema every connector and downstream stage is written against.

Two families of model live here:

  - Scrape output: Meeting, Attachment, LegislationDetails, LegistarAgendaEntry.
    What a connector directly reads off a platform's own HTML — no inference,
    no LLM involved.
  - Extraction output: Provenance, Extracted[T], Person, VoteRecord, Motion,
    Location, MonetaryAmount, AgendaItem. What the LLM extraction layer
    (extraction/agenda_item.py) produces from a fetched document. Every value
    an extraction step emits is wrapped in Extracted[T] and carries mandatory
    provenance — an extraction with no provenance is invalid by construction,
    not by a validation step someone has to remember to run.

AgendaItem here is deliberately NOT what LegistarConnector.get_meeting_details()
returns — that's LegistarAgendaEntry, Legistar's own agenda-listing row (File #,
Title, Action, Result), which exists independently of any LLM extraction.
AgendaItem is the extraction-layer output that lives on Meeting.agenda_items.

Every field below carries a Field(description=...) rather than a trailing
comment - descriptions are runtime-introspectable, which is what lets
checks/docs_drift.py regenerate docs/data-model.md directly from this file
instead of a hand-maintained copy that can silently drift from it. They also
show up in model_json_schema(), which is the tool schema Claude is asked to
fill in during extraction - one description serves both purposes.
"""

from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T")


class Provenance(BaseModel):
    """Where an extracted value came from, so it can be checked against the source."""

    source_document: str = Field(
        description="Path or URL of the document the value was drawn from."
    )
    source_text: str = Field(
        description=(
            "Verbatim span the value was extracted from. Checked against the "
            "source document by string match — an extraction whose source_text "
            "doesn't actually appear in the document is presumptively a fabrication."
        )
    )
    char_start: int | None = Field(
        default=None, description="Start offset of source_text in the document, when known."
    )
    char_end: int | None = Field(
        default=None, description="End offset of source_text in the document, when known."
    )


class Extracted(BaseModel, Generic[T]):
    """Wraps any extracted value with the confidence and provenance it must carry."""

    value: T = Field(
        description="The extracted value itself — a Motion, Person, Location, or MonetaryAmount."
    )
    confidence: float = Field(
        description=(
            "0.0-1.0. Calibration (does a stated 0.6 mean ~60% correct) is an "
            "eval-harness concern, not enforced here."
        )
    )
    provenance: Provenance = Field(description="Required, not optional.")


class Person(BaseModel):
    raw_name: str = Field(description="Exactly as written in the source document.")
    canonical_name: str | None = Field(
        default=None,
        description=(
            "Resolved against a per-jurisdiction roster, when a match is found. "
            "Unresolved is expected, not an error — officials change."
        ),
    )
    role: Literal["mayor", "councilmember", "staff", "applicant", "public", "unknown"] = Field(
        description="Role as identified from context, not guessed beyond what the text supports."
    )


class VoteRecord(BaseModel):
    person: Person = Field(description="Who cast this vote.")
    position: Literal["aye", "no", "abstain", "absent", "recused"] = Field(
        description="This person's recorded vote position."
    )


class Motion(BaseModel):
    text: str = Field(description="The motion as stated/recorded.")
    moved_by: Person | None = Field(default=None, description="Who made the motion, if recorded.")
    seconded_by: Person | None = Field(
        default=None, description="Who seconded the motion, if recorded."
    )
    outcome: Literal["passed", "failed", "tabled", "withdrawn", "continued", "no_action"] = Field(
        description="What ultimately happened to the motion."
    )
    votes: list[VoteRecord] = Field(
        default_factory=list,
        description="Itemized roll call, if one was recorded. A motion can pass without one.",
    )
    tally: str | None = Field(
        default=None,
        description=(
            'Vote tally as printed, e.g. "7-2-1". Kept as a string rather than '
            "parsed, since formats vary."
        ),
    )


class Location(BaseModel):
    raw_text: str = Field(description="Address/location text exactly as it appears in the source.")
    normalized_address: str | None = Field(
        default=None, description="Normalized postal address, if resolved."
    )
    parcel_id: str | None = Field(
        default=None, description="Assessor's parcel number, if identified."
    )
    lat: float | None = Field(default=None, description="Latitude, if geocoded.")
    lon: float | None = Field(default=None, description="Longitude, if geocoded.")


class MonetaryAmount(BaseModel):
    raw_text: str = Field(description='Amount as written, e.g. "$6.0 million" or "up to $500,000".')
    amount_usd: Decimal | None = Field(
        default=None,
        description="Parsed numeric value, when unambiguous. Decimal, not float — this is money.",
    )
    kind: Literal["contract", "grant", "budget", "fee", "fine", "unknown"] = Field(
        description="What kind of monetary figure this is."
    )


class AgendaItem(BaseModel):
    """Extraction-layer output for one agenda item. See module docstring."""

    item_number: str | None = Field(
        default=None, description='Agenda item number as printed, e.g. "2.8".'
    )
    title: str = Field(description="Item title as stated in the source document.")
    item_type: Literal[
        "consent",
        "public_hearing",
        "action",
        "report",
        "closed_session",
        "ceremonial",
        "unknown",
    ] = Field(description="The single category that best fits this item.")
    motions: list[Extracted[Motion]] = Field(
        default_factory=list, description="Motions made on this item. Empty if none were recorded."
    )
    people: list[Extracted[Person]] = Field(
        default_factory=list, description="People named in connection with this item."
    )
    locations: list[Extracted[Location]] = Field(
        default_factory=list, description="Addresses, parcels, or places affected by this item."
    )
    amounts: list[Extracted[MonetaryAmount]] = Field(
        default_factory=list, description="Dollar figures tied to this item."
    )


class Attachment(BaseModel):
    name: str = Field(
        description="Link text as shown on the source page (usually the document title)."
    )
    url: str = Field(description="Absolute URL to the document.")


class LegislationDetails(BaseModel):
    legislation_url: str = Field(description="The source URL this record was fetched from.")
    status: str | None = Field(
        default=None, description="Current legislative status, when the page publishes one."
    )
    text: str | None = Field(
        default=None,
        description="Item text/description/synopsis — whichever label the source page uses.",
    )
    recommendations: str | None = Field(
        default=None, description="Staff recommendation or recommended action text."
    )
    attachments: list[Attachment] = Field(
        default_factory=list, description="Supporting documents linked from the page."
    )


class LegistarAgendaEntry(BaseModel):
    """One row of Legistar's own agenda-item listing, scraped directly from a
    meeting-detail page. Not the extraction-layer AgendaItem above — this is
    what Legistar's HTML already told us, with no LLM involved.
    """

    file_number: str | None = Field(
        default=None, description='The platform\'s tracking ID for this item (Legistar "File #").'
    )
    title: str = Field(
        description=(
            "Item title/description as it appears on the agenda. Required — rows with "
            "no title text are skipped by the parser rather than constructed with a "
            "missing title."
        )
    )
    type: str | None = Field(
        default=None,
        description='Item category, e.g. "Ordinance", "Resolution", "Consent Calendar".',
    )
    agenda_note: str | None = Field(
        default=None, description="Supplemental note attached to the agenda row, if present."
    )
    legislation_url: str | None = Field(
        default=None,
        description=(
            "Link to the item's LegislationDetail.aspx page — input to get_legislation_details()."
        ),
    )
    action: str | None = Field(
        default=None, description='Action taken on the item (e.g. "Adopted").'
    )
    result: str | None = Field(default=None, description="Vote result, when recorded.")
    version: str | None = Field(default=None, description="Legislation version/revision marker.")

    @computed_field(  # type: ignore[prop-decorator]
        description='True when `type` contains the substring "consent" (case-insensitive).'
    )
    @property
    def is_consent(self) -> bool:
        return bool(self.type and "consent" in self.type.lower())


class Meeting(BaseModel):
    source: str = Field(description='Connector identifier: "legistar" or "civicplus".')
    jurisdiction: str = Field(
        description="City/agency name, matching the name field in cities.yaml."
    )
    body: str = Field(
        description=(
            'Governing body, e.g. "City Council". Falls back to the requested body '
            "filter when the platform doesn't expose it per-row."
        )
    )
    date: str = Field(
        description="Meeting date as rendered by the source site — format varies by platform."
    )
    time: str | None = Field(
        default=None, description="Meeting time, if the platform publishes it."
    )
    location: str | None = Field(default=None, description="Free-text meeting location.")
    meeting_details_url: str | None = Field(
        default=None,
        description="Link to the platform's per-meeting detail page, when one exists.",
    )
    agenda_url: str | None = Field(default=None, description="Direct link to the agenda document.")
    minutes_url: str | None = Field(
        default=None, description="Direct link to the minutes document, once published."
    )
    video_url: str | None = Field(
        default=None,
        description="Direct link to meeting video/media, when the platform publishes one.",
    )
    agenda_items: list[AgendaItem] = Field(
        default_factory=list, description="Extraction-layer output. Empty until extraction runs."
    )
    extraction_run_id: str | None = Field(
        default=None,
        description="Identifies which extraction run (if any) populated agenda_items.",
    )


class FetchedDocument(BaseModel):
    """A cached local copy of a fetched agenda/minutes document, with extracted text."""

    source_url: str = Field(description="The URL the document was fetched from.")
    local_path: str = Field(
        description=(
            "Path under data/raw/{jurisdiction}/, content-addressed by a hash of source_url."
        )
    )
    text: str = Field(
        description=(
            "Extracted text, layout-preserved for PDFs. Empty string if extraction found "
            "nothing — check ocr_required before treating that as 'no content'."
        )
    )
    page_count: int = Field(description="Number of pages in the source document.")
    ocr_required: bool = Field(
        description=(
            "True when extracted text is implausibly sparse for the page count — the "
            "heuristic proxy for 'this PDF is a scan with no text layer.'"
        )
    )
