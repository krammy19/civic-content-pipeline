# Data Model

Every model here is a Pydantic `BaseModel` defined in
[`services/workers/civic_scraper/models.py`](../services/workers/civic_scraper/models.py).
Unlike the dataclasses this replaced, these validate at construction —
required fields reject `None`, `Literal` fields reject unknown values.
That's deliberate: a connector or extraction step that produces
malformed data should fail loudly at the point it's constructed, not
downstream when something tries to use it.

Two families of model live in this one file, and the split matters:

- **Scrape output** — `Meeting`, `Attachment`, `LegislationDetails`,
  `LegistarAgendaEntry`. What a connector reads directly off a
  platform's own HTML. No inference, no LLM involved.
- **Extraction output** — `Provenance`, `Extracted[T]`, `Person`,
  `VoteRecord`, `Motion`, `Location`, `MonetaryAmount`, `AgendaItem`.
  What the (not yet built) LLM extraction layer produces from a fetched
  document. See [Extraction output](#extraction-output-not-populated-yet)
  below for why this half of the schema exists before anything populates
  it.

## Scrape output

### Meeting

One row in a platform's meeting calendar, normalized. Output of
`CivicConnector.list_meetings()`.

| Field | Type | Notes |
|---|---|---|
| `source` | `str` | Connector identifier: `"legistar"` or `"civicplus"`. |
| `jurisdiction` | `str` | City/agency name, matching the `name` field in `cities.yaml`. |
| `body` | `str` | Governing body, e.g. `"City Council"`. Falls back to the requested `body` filter when the platform doesn't expose it per-row. |
| `date` | `str` | Meeting date as rendered by the source site — format varies by platform and is not normalized. |
| `time` | `str \| None` | Meeting time, if the platform publishes it. CivicPlus does not. |
| `location` | `str \| None` | Free-text meeting location. CivicPlus does not publish this on the calendar view. |
| `meeting_details_url` | `str \| None` | Link to the platform's per-meeting detail page, when one exists. Input to `get_meeting_details()`. |
| `agenda_url` | `str \| None` | Direct link to the agenda document. |
| `minutes_url` | `str \| None` | Direct link to the minutes document, once published. |
| `video_url` | `str \| None` | Direct link to meeting video/media, when the platform publishes one. |
| `agenda_items` | `list[AgendaItem]` | **Extraction output**, defaults to empty. Not populated by any connector — see below. |
| `extraction_run_id` | `str \| None` | Identifies which extraction run (if any) populated `agenda_items`. `None` until the extraction layer exists. |

### Attachment

A single supporting document linked from a `LegislationDetails` page.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Link text as shown on the source page (usually the document title). |
| `url` | `str` | Absolute URL to the document. |

### LegislationDetails

The expanded record behind a single `LegistarAgendaEntry.legislation_url`,
fetched by `LegistarConnector.get_legislation_details()`.

| Field | Type | Notes |
|---|---|---|
| `legislation_url` | `str` | The source URL this record was fetched from. |
| `status` | `str \| None` | Current legislative status, when the page publishes one. |
| `text` | `str \| None` | Item text/description/synopsis — whichever label the source page uses. |
| `recommendations` | `str \| None` | Staff recommendation or recommended action text. |
| `attachments` | `list[Attachment]` | Supporting documents linked from the page. Defaults to an empty list. |

### LegistarAgendaEntry

One row of Legistar's own agenda-item listing, scraped directly from a
meeting-detail page via `LegistarConnector.get_meeting_details()`. This
is **not** the extraction-layer `AgendaItem` below — see
[Why two "agenda item" models](#why-two-agenda-item-models).

| Field | Type | Notes |
|---|---|---|
| `file_number` | `str \| None` | The platform's tracking ID for this item (Legistar "File #"). |
| `title` | `str` | Item title/description as it appears on the agenda. Required — rows with no title text are skipped by the parser rather than constructed with a missing title. |
| `type` | `str \| None` | Item category, e.g. `"Ordinance"`, `"Resolution"`, `"Consent Calendar"`. |
| `agenda_note` | `str \| None` | Supplemental note attached to the agenda row, if present. |
| `legislation_url` | `str \| None` | Link to the item's `LegislationDetail.aspx` page — input to `get_legislation_details()`. |
| `action` | `str \| None` | Action taken on the item (e.g. `"Adopted"`). |
| `result` | `str \| None` | Vote result, when recorded. |
| `version` | `str \| None` | Legislation version/revision marker. |

`LegistarAgendaEntry` also has a `@computed_field`: **`is_consent`**
(`bool`) — `True` when `type` contains the substring `"consent"`
(case-insensitive). Unlike the dataclass version this replaced, it's a
real Pydantic computed field, so it appears in `model_dump()` output
automatically rather than needing a custom serializer.

## Extraction output (not populated yet)

These models exist now, ahead of the extraction layer that will
populate them, because the schema is the contract the eval harness gets
built against — see the [README's roadmap](../README.md#roadmap).
Nothing in this repo constructs a real (non-test) `AgendaItem` yet.

### Provenance

Where an extracted value came from, so it can be checked against the
source document rather than trusted blindly.

| Field | Type | Notes |
|---|---|---|
| `source_document` | `str` | Path or URL of the document the value was drawn from. |
| `source_text` | `str` | Verbatim span the value was extracted from. Meant to be checked against the source document by string match — an extraction whose `source_text` doesn't actually appear in the document is presumptively a fabrication. |
| `char_start` | `int \| None` | Start offset of `source_text` in the document, when known. |
| `char_end` | `int \| None` | End offset of `source_text` in the document, when known. |

### Extracted[T]

A generic wrapper — every extracted value, whatever its type, carries a
confidence score and provenance alongside it. There is no path to
constructing an extracted fact without both.

| Field | Type | Notes |
|---|---|---|
| `value` | `T` | The extracted value itself — a `Motion`, `Person`, `Location`, or `MonetaryAmount` in this schema. |
| `confidence` | `float` | 0.0–1.0. Calibration (does a stated 0.6 mean ~60% correct) is an eval-harness concern, not enforced here. |
| `provenance` | `Provenance` | Required, not optional — see `Provenance` above. |

### Person

| Field | Type | Notes |
|---|---|---|
| `raw_name` | `str` | Exactly as written in the source document. |
| `canonical_name` | `str \| None` | Resolved against a per-jurisdiction roster, when a match is found. Unresolved is expected, not an error — officials change. |
| `role` | `Literal["mayor", "councilmember", "staff", "applicant", "public", "unknown"]` | |

### VoteRecord

| Field | Type | Notes |
|---|---|---|
| `person` | `Person` | |
| `position` | `Literal["aye", "no", "abstain", "absent", "recused"]` | |

### Motion

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | The motion as stated/recorded. |
| `moved_by` | `Person \| None` | |
| `seconded_by` | `Person \| None` | |
| `outcome` | `Literal["passed", "failed", "tabled", "withdrawn", "continued", "no_action"]` | |
| `votes` | `list[VoteRecord]` | Defaults to empty — a motion can be recorded without an itemized roll call. |
| `tally` | `str \| None` | Vote tally as printed, e.g. `"7-2-1"`. Kept as a string rather than parsed, since formats vary. |

### Location

| Field | Type | Notes |
|---|---|---|
| `raw_text` | `str` | Address/location text exactly as it appears in the source. |
| `normalized_address` | `str \| None` | |
| `parcel_id` | `str \| None` | |
| `lat` | `float \| None` | |
| `lon` | `float \| None` | |

### MonetaryAmount

| Field | Type | Notes |
|---|---|---|
| `raw_text` | `str` | Amount as written, e.g. `"$6.0 million"` or `"up to $500,000"`. |
| `amount_usd` | `Decimal \| None` | Parsed numeric value, when unambiguous. `Decimal`, not `float` — this is money. |
| `kind` | `Literal["contract", "grant", "budget", "fee", "fine", "unknown"]` | |

### AgendaItem

The extraction-layer record for one agenda item — everything an LLM
pass over a fetched document is meant to produce. See
[Why two "agenda item" models](#why-two-agenda-item-models).

| Field | Type | Notes |
|---|---|---|
| `item_number` | `str \| None` | |
| `title` | `str` | |
| `item_type` | `Literal["consent", "public_hearing", "action", "report", "closed_session", "ceremonial", "unknown"]` | |
| `motions` | `list[Extracted[Motion]]` | Defaults to empty. |
| `people` | `list[Extracted[Person]]` | Defaults to empty. |
| `locations` | `list[Extracted[Location]]` | Defaults to empty. |
| `amounts` | `list[Extracted[MonetaryAmount]]` | Defaults to empty. |

### Why two "agenda item" models

`LegistarAgendaEntry` and `AgendaItem` look like they should be the same
thing, and almost were — but they answer different questions.
`LegistarAgendaEntry` is "what did Legistar's own HTML table say about
this row" (File #, a type label, an action/result Legistar already
recorded). `AgendaItem` is "what did an LLM pass over the actual agenda
document conclude" (motions, named people, locations, dollar amounts,
each individually confidence-scored and provenance-checked). The first
is free — a byproduct of scraping a platform that happens to expose
structured HTML. The second requires document fetch and an LLM call and
doesn't exist yet. Naming them the same thing would have made "does this
Meeting have real extraction output or just a scraped listing" a
question you could only answer by inspecting field values instead of
the type.

## Document fetch output

### FetchedDocument

Output of `fetch_and_extract()` in
[`document_text.py`](../services/workers/civic_scraper/document_text.py) —
a cached local copy of a fetched agenda/minutes document plus its
extracted text.

| Field | Type | Notes |
|---|---|---|
| `source_url` | `str` | The URL the document was fetched from. |
| `local_path` | `str` | Path under `data/raw/{jurisdiction}/`, content-addressed by a hash of `source_url`. |
| `text` | `str` | Extracted text, layout-preserved for PDFs. Empty string if extraction found nothing — check `ocr_required` before treating that as "the document has no content." |
| `page_count` | `int` | |
| `ocr_required` | `bool` | `True` when extracted text is implausibly sparse for the page count — the heuristic proxy for "this PDF is a scan with no text layer." See `document_text.MIN_CHARS_PER_PAGE`. |

## Design principle: flexible parsing, standardized output

Different cities on the same platform expose different columns.
Connectors absorb that variance internally (see
[`architecture.md`](architecture.md#connector-framework)) and always
return the same scrape-output models. If a piece of data isn't
available from a given source, the field is `None` — connectors never
invent placeholder values, and never add platform-specific fields to
the shared model.
