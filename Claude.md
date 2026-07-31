# Engineering Log

> This log was drafted with Claude during the initial build session and
> then edited by hand into the document below — cut down to the
> decisions and reasoning worth keeping, with environment-setup notes
> and other session noise removed. It is not hidden that AI assistance
> was part of building this project; the editing is the point. See
> [SPEC.md](../SPEC.md) for how work on this repo is directed going
> forward, and this log for why the parts that already exist look the
> way they do.

## Project origin

The goal, from the start: aggregate local government meeting data —
agendas, minutes, video, metadata — across multiple municipal platforms
(Legistar, Granicus, PrimeGov, CivicClerk), normalize it to one shape,
and build toward search, summarization, and AI analysis on top of it.
Phase 1 was narrowly scoped to robust ingestion and normalization,
starting with a single platform: Legistar, starting from San Jose's
calendar at `sanjose.legistar.com/Calendar.aspx`.

## Architectural decisions

**Connector-based scraping.** Each municipal platform gets its own
connector (`connectors/legistar.py`, and eventually `granicus.py`,
`primegov.py`, `civicclerk.py`). This keeps platform-specific
assumptions from leaking into the rest of the system — nothing outside
`connectors/` should ever need to know which platform a given city runs.

**Uniform output model.** Regardless of source platform, every connector
emits the same normalized `Meeting` object:

```python
@dataclass
class Meeting:
    source: str
    jurisdiction: str
    body: str
    date: str
    time: Optional[str]
    location: Optional[str]
    meeting_details_url: Optional[str]
    agenda_url: Optional[str]
    minutes_url: Optional[str]
    video_url: Optional[str]
```

The governing principle: **flexible parsing, standardized output.**
Different cities expose different Legistar columns; the model they parse
into must not.

## Legistar connector development

Initial findings from San Jose's calendar: the meeting list is
dynamically searchable and requires Selenium — pagination, year/body
filtering, and historical archive traversal are all JS-driven, so a
requests-only approach can't reach past meetings at all. The table
itself has up to 12 columns, several of them optional and city-dependent
(Accessible Agenda, Accessible Minutes, Agenda Packet, Video).

An older scraper project (`city-agenda-scraper`) was reviewed for
reference but not reused directly — its Selenium API usage was outdated,
it was tightly coupled to one site's layout, and it had no normalized
data model underneath it. `LegistarConnector` was written fresh, with
the explicit expectation that more connectors would follow it.

## Dynamic column mapping

This was the central discovery of the Phase 1 build. Hardcoded column
indexes broke almost immediately: different Legistar instances expose
different columns, column counts vary city to city, optional
accessibility columns shift every index after them, and some columns are
icon-only with no header text at all. Pager rows compounded it — parsed
as if they were data rows, they corrupted whatever column alignment the
parser assumed.

The failure mode was concrete, not theoretical:

```json
{
  "body": "12/31/2024",
  "date": "",
  "time": "Council Chambers CANCELLED"
}
```

Date landing in the body field, a cancellation note landing in time —
this is what a parser keyed on column *position* does the moment a city
enables or disables one optional column.

The fix: parse by header, never by position. Read the table's actual
header row, build a `{name: index}` map per parse call, and resolve
every field by looking up its canonical column name — falling back to a
small alias table for the few Legistar instances that label a column
differently. Pager rows are filtered out before mapping, not after, so
they never get a chance to misalign anything. This is now covered by
`tests/connectors/test_legistar.py`, including a regression test built
directly from the bad-output example above.

## Lessons

**Legistar HTML is not a stable API.** Hidden columns, dynamic
rendering, non-uniform per-city configuration, pager rows mixed into
data rows — the connector layer has to be adaptive by default, not
adaptive as an afterthought.

**Selenium is a real requirement, not a shortcut.** Historical archives,
pagination, and dropdown filtering all depend on it; a requests-only
connector cannot reach this data.

**Data normalization is the actual product.** The app should never
expose a platform's raw schema to anything downstream:

```text
Platform HTML → Connector Parser → Normalized Meeting Model → downstream AI / search / alerts
```

## Where this was heading, and where SPEC.md picks it up

The framing shift that mattered most during this phase: the project
stopped being thought of as "a scraper script" and became "a civic data
ingestion and normalization platform." [`SPEC.md`](../SPEC.md) carries
that framing forward and sharpens it further — this is a
quality-controlled content system, where extraction is graded against an
eval suite and gated in CI, not just a normalization layer. The
connector architecture and the header-mapping discipline described above
are exactly what that next phase is built on top of.
