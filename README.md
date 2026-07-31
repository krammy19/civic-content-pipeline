# Civic Engagement App

A content pipeline that ingests municipal government meeting documents —
agendas, minutes, staff reports — from heterogeneous city platforms,
will extract structured facts from them with an LLM, validate that
output against a schema and an eval suite, and publish digests that pass
automated quality checks.

**The problem:** municipal governments publish meeting records in wildly
inconsistent formats, across dozens of different platform vendors, with
no shared schema. A resident trying to track a specific issue — a zoning
change, a budget line, a vote — has to manually dig through PDFs and
platform-specific web UIs, city by city. This project's job is to
normalize that into one structured, queryable form, and to catch bad
output (hallucinated facts, miscategorized items, sloppy summaries)
before a reader ever sees it.

**Current status: early.** The ingestion layer — connectors that turn a
platform's calendar page into a normalized `Meeting` object — works and
is tested. The extraction, validation, and eval layers that make this a
genuinely quality-controlled system are not built yet. See
[Current limitations](#current-limitations) below and
[`SPEC.md`](SPEC.md) for the build plan.

## Architecture

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
   data/processed/<city>/*.json <- current persistence layer (flat JSON, no DB)
```

Full writeup, including why parsing is header-driven rather than
positional: [`docs/architecture.md`](docs/architecture.md). Field-level
schema: [`docs/data-model.md`](docs/data-model.md). How a scrape run
actually executes: [`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md).

## Quickstart

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/krammy19/civic-engagement-app.git
cd civic-engagement-app
uv sync

# Scrape this month's meetings for every connectorized city
PYTHONPATH=services/workers uv run python services/workers/civic_scraper/run_all.py

# Or just one city
PYTHONPATH=services/workers uv run python services/workers/civic_scraper/run_all.py --city Oakland

# Run the test suite
uv run pytest

# Lint
uv run ruff check .
```

Output lands in `data/processed/<city-slug>/`. Legistar's calendar
search is JS-driven, so that connector drives a headless Chrome via
Selenium — a Chrome/Chromium install is required. CivicPlus is plain
HTTP and needs nothing extra.

## How to add a connector

1. Create `services/workers/civic_scraper/connectors/<platform>.py`
   implementing `CivicConnector` (see
   [`connectors/base.py`](services/workers/civic_scraper/connectors/base.py)
   — one method required: `list_meetings()`, returning `list[Meeting]`).
2. Never let platform-specific parsing leak outside that file. Everything
   downstream depends only on the `Meeting` dataclass in
   [`models.py`](services/workers/civic_scraper/models.py).
3. Parse by semantic column/field name, not position — see
   [`docs/architecture.md#header-driven-parsing-legistar`](docs/architecture.md#header-driven-parsing-legistar)
   for why positional parsing doesn't survive contact with real
   municipal websites.
4. Wire it into `make_connector()` in
   [`run_all.py`](services/workers/civic_scraper/run_all.py), and add a
   `connector: <platform>` entry to
   [`cities.yaml`](services/workers/civic_scraper/cities.yaml) once a
   city has everything the connector needs (see
   [`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md#the-city-registry-citiesyaml)).
5. Add tests under `tests/connectors/` covering the same class of
   failure the Legistar tests cover: malformed/missing columns, pager or
   non-data rows, and any platform-specific quirk you had to work around.

## Current limitations

Stated plainly, per [`SPEC.md`](SPEC.md)'s priority on honesty over
feature count:

- **No extraction, validation, eval, or digest layers yet.** Everything
  past "get a normalized `Meeting` object onto disk" — the actual
  quality-controlled content system described above — is unbuilt. It's
  the subject of [`SPEC.md`](SPEC.md)'s milestones M1 through M5.
- **`cities.yaml` has 481 cities registered, most of them scraped at
  least once — this overshoots the project's actual near-term scope.**
  [`SPEC.md`](SPEC.md#2-decisions-already-made) narrows scope
  deliberately to San Jose plus exactly one second city on a different
  platform, on the reasoning that two platforms proven well is worth
  more than dozens proven shallowly. The registry is left as-is (useful
  for future breadth) but isn't the near-term priority.
- **Header-mapping logic is unit-tested; the rest of the pipeline
  mostly isn't.** `tests/connectors/test_legistar.py` covers the
  resilient-parsing logic in detail. Document fetch, agenda/minutes PDF
  handling, and the CivicPlus connector do not have equivalent coverage
  yet.
- **Two `data/processed/` directories exist** because the runners
  resolve output paths relative to the current working directory, not
  the repo root. Known, not yet fixed — see
  [`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md#output-layout).
- **No database.** Output is JSON files on disk, overwritten on every
  run — no history, no query interface beyond reading files directly.
- **Storage model still uses plain dataclasses, not the Pydantic schema
  in [`SPEC.md`](SPEC.md#4-data-model).** Provenance and per-field
  confidence — required for the eval harness this project is ultimately
  meant to demonstrate — don't exist in the current model at all.

## Documentation

| Doc | Covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Connector framework, header-driven parsing, the city registry, directory layout |
| [`docs/data-model.md`](docs/data-model.md) | Every field on `Meeting`, `AgendaItem`, `LegislationDetails`, `Attachment` |
| [`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md) | Runners, phases, `cities.yaml` format, output layout |
| [`docs/engineering-log.md`](docs/engineering-log.md) | How the connector architecture and header-mapping approach were actually arrived at |
| [`SPEC.md`](SPEC.md) | The build plan this project is currently being developed against |

## Project layout

```
docs/                   architecture, data model, pipeline, engineering log
services/workers/civic_scraper/
    models.py             canonical dataclasses
    connectors/           one module per platform + shared interface
    extractors/           early AI-powered document extraction (staff reports)
    cities.yaml            the city registry
    run_all.py             multi-connector ingestion runner
tests/                  pytest coverage of the header-mapping logic
data/processed/         sample output (JSON, one file per city per period)
```

Full breakdown in [`docs/architecture.md`](docs/architecture.md#directory-layout-current).
