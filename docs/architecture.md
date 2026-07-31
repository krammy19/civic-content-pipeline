# Architecture

This describes the system as it exists today: a connector-based
ingestion layer that normalizes municipal meeting data into one schema.
It does not describe the extraction/eval/digest layers in
[`SPEC.md`](../SPEC.md) — those are the target architecture, not yet
built. Where this doc and SPEC.md's target layout disagree, SPEC.md
wins; this doc will be updated as each milestone lands.

## Overview

```
 Municipal platform (Legistar, CivicPlus, ...)
            |
            v
   Platform Connector          <- only place that knows platform-specific HTML/DOM
            |
            v
   Normalized dataclasses      <- Meeting, AgendaItem, LegislationDetails, Attachment
            |
            v
   data/processed/<city>/*.json <- current persistence layer
```

See [`data-model.md`](data-model.md) for the full field reference on
every dataclass, and [`ingestion-pipeline.md`](ingestion-pipeline.md) for
how a run actually executes end to end.

## Guiding principles

- **Normalize immediately after scraping.** A connector's public methods
  never return raw HTML, `BeautifulSoup` elements, or dicts shaped like
  the source platform's DOM — only the dataclasses in
  [`models.py`](../services/workers/civic_scraper/models.py).
- **Platform-specific behavior stays inside connectors.** If you find
  yourself writing an `if platform == "legistar"` branch anywhere outside
  `connectors/`, that's a sign the abstraction is leaking.
- **Prefer semantic parsing over positional parsing.** Legistar table
  columns shift between cities — see
  [Header-driven parsing](#header-driven-parsing-legistar) below for why
  index-based parsing doesn't survive contact with real data, and
  [`docs/engineering-log.md`](engineering-log.md) for how that was
  discovered.
- **Preserve source URLs for traceability.** Every dataclass that
  represents a fetched page keeps the URL it came from
  (`meeting_details_url`, `legislation_url`, etc.).
- **Build for dozens of municipalities, not one.** Config (`cities.yaml`),
  not code, is what changes when a new city is added to an already
  supported platform.

## Connector framework

Every connector implements
[`CivicConnector`](../services/workers/civic_scraper/connectors/base.py):

```python
class CivicConnector(ABC):
    @abstractmethod
    def list_meetings(
        self,
        period: str | None = None,
        body: str | None = None,
        limit: int | None = None,
    ) -> list[Meeting]: ...
```

That single method is the only thing the runners depend on to run
calendar scraping across every city. Two connectors exist today:

| Connector | Platform | Fetch strategy | Notes |
|---|---|---|---|
| `LegistarConnector` | Legistar | Selenium (calendar search is JS-driven and paginated) | Also implements `get_meeting_details()` and `get_legislation_details()`, which are `requests`-based since those pages don't require JS. |
| `CivicPlusConnector` | CivicPlus AgendaCenter | `requests` + `BeautifulSoup` | Resolves the target body to an `AgendaCenter` category ID first, either from a pre-populated `cities.yaml` entry or by probing at call time. |

Adding a new platform means adding a new class here — never adding a
special case to a runner script, `models.py`, or another connector.

### Header-driven parsing (Legistar)

Legistar's calendar table is not a stable API: different municipalities
enable different optional columns (`Accessible Agenda`, `Accessible
Minutes`, `Agenda Packet`, `Video`), and some use icon-only columns with
no header text at all. Early positional parsing broke on exactly this —
see `docs/engineering-log.md` for the specific bad output it produced.

`LegistarConnector` never assumes a column position:

1. `_extract_headers()` reads the actual `<th>` row from the table,
   expanding any `colspan` so header count lines up with cell count.
2. Headers are mapped to a `{name: index}` dict at parse time — rebuilt
   per table, never cached across cities.
3. `_resolve_col()` looks up a canonical column name, falling back to a
   small alias table (`_COLUMN_ALIASES`) for the handful of Legistar
   instances that label a column differently.
4. Pager rows (`class="rgPager"`) are filtered out before parsing, not
   after — they don't have the columns a real meeting row has and would
   otherwise corrupt the field mapping.

The same approach is reused in `_parse_agenda_items()` for the
per-meeting agenda table, which has a different column set entirely
(`File #`, `Ver.`, `Agenda Note`, `Type`, `Title`, `Action`, `Result`).
This logic is covered by `tests/connectors/test_legistar.py`.

## Platform detection and the city registry

[`cities.yaml`](../services/workers/civic_scraper/cities.yaml) is the
single source of truth for which cities are ingested and how. It's built
and maintained by three scripts, run in sequence, each safe to re-run:

1. **`generate_cities_yaml.py`** — one-time seed from a CSV of CA city
   websites.
2. **`detect_platforms.py`** — for every city without a known platform,
   fetches its `agenda_url` and pattern-matches the final URL + HTML
   against known platform signatures. Falls back to brute-forcing common
   Legistar subdomain slugs when the agenda page itself doesn't reveal
   the platform.
3. **`discover_civicplus.py`** — for CivicPlus cities, resolves the
   `AgendaCenter` category ID matching the target body.

A city only gets a `connector:` field (and is picked up by the
multi-city runner) once it has everything its connector needs — a
resolved `legistar_url`, or a resolved `civicplus_base_url` +
`civicplus_category_id`. Detected-but-unconnected platforms (Granicus,
CivicClerk, PrimeGov, IQM2) are recorded so the next connector to be
built has a ready-made target list, but they're inert until it exists.
Per [`SPEC.md`](../SPEC.md#2-decisions-already-made), scope for now is
Legistar plus exactly one second city on a different platform — building
out every detected platform is explicitly not the near-term goal.

## Directory layout (current)

```
civic-engagement-app/
├── docs/                          architecture, data model, pipeline, engineering log
├── scripts/
│   └── scrape_meetings.py         early prototype, kept for reference
├── services/workers/
│   ├── civic_scraper/
│   │   ├── models.py              canonical dataclasses
│   │   ├── connectors/            one module per platform + the shared ABC
│   │   ├── extractors/            early AI-powered document extraction (staff reports)
│   │   ├── cities.yaml            city registry
│   │   ├── generate_cities_yaml.py
│   │   ├── detect_platforms.py
│   │   ├── discover_civicplus.py
│   │   ├── run_legistar.py        Legistar-only runner (superseded by run_all.py)
│   │   └── run_all.py             multi-connector ingestion runner
│   └── data/processed/            sample output when run from services/workers/
├── data/processed/                sample output when run from repo root
└── tests/                         pytest coverage of the header-mapping logic
```

`data/processed/` exists in two places because the runners resolve their
output path relative to the current working directory rather than the
repo root — a known inconsistency, not yet fixed.

See [`SPEC.md`](../SPEC.md#3-target-architecture) for the target layout
this is migrating toward (Pydantic models, an extraction layer, an eval
harness, digest generation) and the milestone order it's being built in.
