# Civic Engagement App

A content pipeline that ingests municipal government meeting documents —
agendas, minutes, staff reports — from heterogeneous city platforms,
extracts structured facts from them with an LLM, will validate that
output against an eval suite, and publish digests that pass automated
quality checks.

**The problem:** municipal governments publish meeting records in wildly
inconsistent formats, across dozens of different platform vendors, with
no shared schema. A resident trying to track a specific issue — a zoning
change, a budget line, a vote — has to manually dig through PDFs and
platform-specific web UIs, city by city. This project's job is to
normalize that into one structured, queryable form, and to catch bad
output (hallucinated facts, miscategorized items, sloppy summaries)
before a reader ever sees it.

**Current status: early.** The ingestion layer — connectors that turn a
platform's calendar page into a normalized, schema-validated `Meeting`
— works and is tested, with a content-addressed document fetch/cache,
PDF text extraction with scan detection, and an LLM extraction module
that turns one agenda item's document text into a schema-validated,
provenance-verified `AgendaItem`. That extraction module has been run
against the live Anthropic API and scored by a real eval harness — a
44-case hand-annotated gold set, precision/recall/F1 per field, zero
measured hallucinations, and confidence calibration — with the honest
result that the model is overconfident (see [`docs/evals.md`](docs/evals.md)
for the full numbers). Extractions below a per-field confidence
threshold are held back from publication and routed to a human review
queue (`python -m civic_scraper.review`), and accepted review decisions
feed back into the gold set — see [`docs/review.md`](docs/review.md).
None of the pipeline is wired into the connectors/runners automatically
yet, and the digest layer that makes this a genuinely quality-controlled
system end to end is not built at all. See
[Current limitations](#current-limitations) and
[Roadmap](#roadmap) below.

## Architecture

```
 Municipal platform (Legistar, CivicPlus, ...)
            |
            v
   Platform Connector          <- only place that knows platform-specific HTML/DOM
            |
            v
   Pydantic models              <- Meeting, LegistarAgendaEntry, LegislationDetails, Attachment
            |
            v
   data/processed/<city>/*.json <- current persistence layer (flat JSON, no DB)
            |
            v
   Document fetch + text        <- data/raw/<city>/, content-addressed;
   extraction                       PDF text extraction with scan detection
            |
            v
   LLM extraction (llm.py,      <- forced tool use -> AgendaItem, provenance-verified;
   extraction/agenda_item.py)      run against the live API, scored by evals/ (not wired to a runner yet)
            |
            v
   Eval harness (evals/)         <- 44-case gold set; precision/recall/F1, hallucination rate,
                                     and confidence calibration per field; CI regression gate
            |
            v
   Review queue (review/)         <- extractions below a per-field confidence threshold are
                                      held back; python -m civic_scraper.review resolves them;
                                      accepted decisions feed back into the gold set above
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
   downstream depends only on the `Meeting` model in
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

Stated plainly:

- **No validation gate, eval, or digest layers yet.** Everything past
  "get a schema-validated `Meeting`, fetch/extract its documents, and
  extract one `AgendaItem` from a document on request" — the actual
  quality-controlled content system described above — is unbuilt. See
  [Roadmap](#roadmap).
- **Nothing is wired together automatically.** `fetch_and_extract()` in
  `document_text.py` and `extract_agenda_item()` in
  `extraction/agenda_item.py` both work standalone, and confidence
  routing/review (`review/routing.py`, `python -m civic_scraper.review`)
  exists as a standalone step too, but nothing calls any of this on a
  scraped `Meeting`'s `agenda_url`/`minutes_url` automatically — that
  plumbing is still ahead.
- **Extraction quality is uneven across fields, and the model is
  overconfident.** Against the 44-case gold set: motions F1 0.87,
  amounts F1 0.87, people F1 0.81, but locations F1 only 0.60 (a
  matching-granularity problem more than an extraction problem, and
  locations also over-trigger on a document's own self-referential city
  name — see [`docs/evals.md`](docs/evals.md) and
  [`docs/review.md`](docs/review.md)). Hallucination rate is 0% and
  schema validity is 100%, but confidence calibration is not
  trustworthy as-is (ECE 0.14) — this is exactly why extraction now
  routes below-threshold values to human review rather than publishing
  or dropping them outright.
- **The eval harness doesn't check everything that matters.** Motion
  matching doesn't verify *who* moved or seconded, only that the outcome
  and text/tally match; location matching is text-similarity only, with
  no address-normalization, so distinct-but-related places can
  under/over-match. Documented in full in
  [`docs/evals.md`](docs/evals.md#known-limitations-and-what-a-v2-harness-should-fix).
- **`cities.yaml` has 481 cities registered, most of them scraped at
  least once — this overshoots the project's actual near-term scope.**
  The near-term plan is to prove the pipeline well on a small, deliberate
  set of cities across two different platforms rather than spread thin
  across many — two platforms proven well is worth more than dozens
  proven shallowly. The registry is left as-is (useful for future
  breadth) but isn't the near-term priority.
- **The CivicPlus connector has no test coverage.** Header-mapping,
  Pydantic model validation, document fetch/caching, and PDF text
  extraction all do (`tests/`); `CivicPlusConnector` itself doesn't yet.
- **Scan detection is a heuristic, not a real classifier.** A PDF page is
  flagged `ocr_required` when extracted text is implausibly sparse for
  its page count (`document_text.MIN_CHARS_PER_PAGE`) — good enough to
  catch genuinely text-free scans, not rigorously validated against a
  labeled set of real scanned municipal PDFs.
- **Two `data/processed/` directories exist** because the runners
  resolve output paths relative to the current working directory, not
  the repo root. Known, not yet fixed — see
  [`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md#output-layout).
- **No database.** Output is JSON files on disk, overwritten on every
  run — no history, no query interface beyond reading files directly.

## Roadmap

Rough shape of what comes after the current ingestion layer, in the
order it's planned:

1. **Schema migration and document fetch — done.** `models.py` is now a
   validated Pydantic schema with mandatory provenance (source text +
   offset) and per-field confidence on every extracted value
   (`Extracted[T]`), plus connector hardening (the Legistar video-link
   `onclick`-popup fix, `LegistarAgendaEntry.title` now required rather
   than silently nullable) and content-addressed document fetch/caching
   with PDF text extraction and scan detection
   (`document_fetch.py`, `document_text.py`). Not done: wiring fetch into
   the connectors/runners automatically.
2. **Extraction layer — built and validated against the live API.**
   `extraction/agenda_item.py` extracts one agenda item's motions,
   people, locations, and dollar amounts via forced Claude tool use
   against `AgendaItem`'s own JSON schema — no free-text parsing.
   Provenance gets verified deterministically (`verify_provenance()`
   checks the cited span actually appears in the source document) as a
   hallucination check, and every Claude call routes through `llm.py`,
   cached on `(prompt_version, model, input)`. What's missing: wiring
   into a runner, and the review-queue layer below.
3. **Eval harness — done.** A hand-annotated gold set (44 cases and
   growing via the review flywheel below), scored for precision/recall/F1,
   hallucination rate, schema validity, and confidence calibration per
   field type, with a CI regression gate (`.github/workflows/eval.yml`,
   no-ops without an `ANTHROPIC_API_KEY` secret so it never forces
   spend). The first real run found and fixed two genuine bugs — one in
   gold-set completeness, one in the person-name matcher — and surfaced
   honest weaknesses (weak location matching, overconfident calibration)
   that are documented, not hidden. Full methodology and results:
   [`docs/evals.md`](docs/evals.md).
4. **Confidence routing and review queue — done.** Extractions below a
   per-field-type confidence threshold don't publish — they're written
   to `data/review_queue/` and resolved one at a time by a person via
   `python -m civic_scraper.review` (accept, edit, or reject). Accepted
   or edited decisions are exported into new gold cases, closing the
   loop: human review makes the eval suite stronger over time. The first
   real review session resolved 10 real queued values from a fresh
   meeting the gold set had never seen — 6 accepted, 4 correctly
   rejected — growing the gold set from 38 to 44 cases and surfacing a
   real gold-set-partial-annotation scoring bug in the process. Full
   writeup: [`docs/review.md`](docs/review.md).
5. **Digest generation and style enforcement.** Plain-language meeting
   summaries generated from validated extractions, checked against a
   written style guide by both deterministic rules and an LLM judge.
6. **Metrics and drift detection.** Per-city health metrics over time,
   flagging when a city's template changes enough to degrade extraction
   quality (connector rot).
7. **A second platform.** One more connector on a platform Legistar
   doesn't share anything with, run through the same eval suite, with
   results reported honestly — including where they're worse.

## Documentation

| Doc | Covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Connector framework, header-driven parsing, document fetch, the city registry, directory layout |
| [`docs/data-model.md`](docs/data-model.md) | Every field on every model — scrape output, extraction output, and document fetch output |
| [`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md) | Runners, phases, `cities.yaml` format, output layout |
| [`docs/evals.md`](docs/evals.md) | Eval harness methodology, the gold set, matching rules, and the first real run's results (bugs found, calibration read) |
| [`docs/review.md`](docs/review.md) | Confidence routing, the review CLI, the gold-set flywheel, and the first real review session's results |
| [`docs/engineering-log.md`](docs/engineering-log.md) | How the connector architecture and header-mapping approach were actually arrived at |

## Project layout

```
docs/                   architecture, data model, pipeline, eval methodology, engineering log
prompts/                versioned LLM prompts (never inline in code)
services/workers/civic_scraper/
    models.py             canonical Pydantic schema
    connectors/           one module per platform + shared interface
    llm.py                 single cached Claude wrapper - every LLM call goes through this
    extraction/            LLM-based structured extraction (agenda items, staff reports)
    document_fetch.py      content-addressed document download/cache
    document_text.py       PDF text extraction + scan detection
    cities.yaml            the city registry
    run_all.py             multi-connector ingestion runner
    review/                confidence routing, review queue, gold-set flywheel
evals/                  eval harness: gold set, scoring metrics, orchestration, baseline
tests/                  pytest coverage of parsing, models, fetch, text extraction, LLM extraction, evals, and review
data/processed/         sample output (JSON, one file per city per period)
data/raw/               fetched agenda/minutes documents, content-addressed
data/review_queue/      below-threshold extractions awaiting human review
.cache/llm/             Claude response cache, keyed on (prompt_version, model, input hash)
```

Full breakdown in [`docs/architecture.md`](docs/architecture.md#directory-layout-current).
