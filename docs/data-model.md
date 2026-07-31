# Data Model

Every connector, regardless of source platform, emits the same set of
dataclasses defined in
[`services/workers/civic_scraper/models.py`](../services/workers/civic_scraper/models.py).
This is the contract downstream code is written against — it never sees
platform-specific shapes.

> **Note:** this file is hand-maintained today. Once `models.py` migrates
> to a validated schema (see the [README's roadmap](../README.md#roadmap)),
> this file is intended to become generated output instead, with CI
> failing if the committed file diverges from the live models. Until
> then, keep it in sync by hand when a field changes.

## Meeting

One row in a platform's meeting calendar, normalized. Output of
`CivicConnector.list_meetings()`.

| Field | Type | Notes |
|---|---|---|
| `source` | `str` | Connector identifier: `"legistar"` or `"civicplus"`. |
| `jurisdiction` | `str` | City/agency name, matching the `name` field in `cities.yaml`. |
| `body` | `str` | Governing body, e.g. `"City Council"`. Falls back to the requested `body` filter when the platform doesn't expose it per-row. |
| `date` | `str` | Meeting date as rendered by the source site — format varies by platform and is not normalized. |
| `time` | `str | None` | Meeting time, if the platform publishes it. CivicPlus does not. |
| `location` | `str | None` | Free-text meeting location. CivicPlus does not publish this on the calendar view. |
| `meeting_details_url` | `str | None` | Link to the platform's per-meeting detail page, when one exists. Input to `get_meeting_details()`. |
| `agenda_url` | `str | None` | Direct link to the agenda document. |
| `minutes_url` | `str | None` | Direct link to the minutes document, once published. |
| `video_url` | `str | None` | Direct link to meeting video/media, when the platform publishes one. |

## AgendaItem

A single line item from a meeting's agenda. Currently only the Legistar
connector populates this, via `LegistarConnector.get_meeting_details()`.

| Field | Type | Notes |
|---|---|---|
| `file_number` | `str | None` | The platform's tracking ID for this item (Legistar "File #"). |
| `title` | `str` | Item title/description as it appears on the agenda. |
| `type` | `str | None` | Item category, e.g. `"Ordinance"`, `"Resolution"`, `"Consent Calendar"`. |
| `agenda_note` | `str | None` | Supplemental note attached to the agenda row, if present. |
| `legislation_url` | `str | None` | Link to the item's `LegislationDetail.aspx` page — input to `get_legislation_details()`. |
| `action` | `str | None` | Action taken on the item (e.g. `"Adopted"`). |
| `result` | `str | None` | Vote result, when recorded. |
| `version` | `str | None` | Legislation version/revision marker. |

`AgendaItem` also exposes a derived, non-field property: **`is_consent`**
(`bool`) — `True` when `type` contains the substring `"consent"`
(case-insensitive). Computed in `to_dict()`, not part of the schema.

## LegislationDetails

The expanded record behind a single `AgendaItem.legislation_url`, fetched
by `LegistarConnector.get_legislation_details()`.

| Field | Type | Notes |
|---|---|---|
| `legislation_url` | `str` | The source URL this record was fetched from. |
| `status` | `str | None` | Current legislative status, when the page publishes one. |
| `text` | `str | None` | Item text/description/synopsis — whichever label the source page uses. |
| `recommendations` | `str | None` | Staff recommendation or recommended action text. |
| `attachments` | `list[Attachment]` | Supporting documents linked from the page. Defaults to an empty list. |

## Attachment

A single supporting document linked from a `LegislationDetails` page.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Link text as shown on the source page (usually the document title). |
| `url` | `str` | Absolute URL to the document. |

## Design principle: flexible parsing, standardized output

Different cities on the same platform expose different columns.
Connectors absorb that variance internally (see
[`architecture.md`](architecture.md#connector-framework)) and always
return these five dataclasses. If a piece of data isn't available from a
given source, the field is `None` — connectors never invent placeholder
values, and never add platform-specific fields to the shared model.

## Where this is going

The planned schema migration (see the
[README's roadmap](../README.md#roadmap)) adds `Provenance` and
per-field `confidence` to every extracted value, plus new entities
(motions, votes, people, locations, monetary amounts) that don't exist
in the current dataclasses at all. That migration hasn't happened yet —
none of it is reflected above.
