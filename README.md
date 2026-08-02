# Civic Engagement App

A content pipeline that ingests municipal government meeting documents —
agendas, minutes, staff reports — from heterogeneous city platforms,
extracts structured facts from them with an LLM, validates that output
against an eval suite, and generates plain-language digests that pass
automated, two-tier style checks.

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
Validated extractions can be turned into a plain-language, cited
Markdown digest (`digest/generate_digest.py`), checked against a
hand-written style guide by a two-tier checker — deterministic pattern
matching plus an LLM judge — that is itself scored for precision and
recall the same way extraction is, and that check runs in CI against a
real generated digest on every relevant pull request; see
[`docs/style-checking.md`](docs/style-checking.md). Every extraction run
can also be summarized into per-city health metrics and compared
against that city's own trailing history to flag "connector rot" —
a platform template change degrading extraction quality — with no gold
set required (see [`docs/metrics.md`](docs/metrics.md)), and
`docs/data-model.md` is generated directly from the Pydantic models so
it cannot go stale without failing CI. None of the pipeline is wired
into the connectors/runners automatically yet — every stage above works
standalone and has been run against real data, but nothing calls the
next stage on the previous one's output automatically. See
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
            |
            v
   Digest generation (digest/)     <- plain-language, cited Markdown from validated facts only
            |
            v
   Style check (checks/)           <- deterministic rules + LLM judge, scored against
                                      evals/style_cases/; CI fails on any high-severity finding
            |
            v
   Metrics + drift (metrics/)      <- per-run RunMetrics vs. trailing per-city baseline;
                                      flags connector rot; data/metrics/{city}/{run_id}.json
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

- **Every pipeline stage exists and has been run against real data, but
  none of them call each other automatically.** `fetch_and_extract()`,
  `extract_agenda_item()`, `route_agenda_item()`, `generate_digest()`,
  `check_deterministic()`/`judge_style()`, and `compute_run_metrics()`
  each work standalone and have all been exercised against real San Jose
  meeting data, but nothing calls the next stage on the previous one's
  output — a scraped `Meeting`'s `agenda_url` doesn't automatically flow
  through fetch, extraction, review, digest generation, style checking,
  and metrics recording end to end. That runner is still ahead. See
  [Roadmap](#roadmap).
- **Digest generation has only been run against one meeting's worth of
  real data.** `docs/style-checking.md` documents that single real run
  in detail (including a real sentence-tokenization bug it found and
  fixed), but one meeting is a smoke test, not a validated sample size.
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
- **The style checker's LLM-judge tier has strong recall and weak
  measured precision on its own eval set** — it never missed a planted
  violation (recall 1.0 on every judge rule) but frequently flags more
  than the one problem a hand-built test case was built to isolate.
  Reported honestly, with the reasoning for why that's an acceptable
  failure mode for a quality gate, in
  [`docs/style-checking.md`](docs/style-checking.md).
- **Drift-detection thresholds are a starting guess, not derived from
  real drift data.** There isn't enough real per-city run history yet
  to know what normal metric variance actually looks like, and the
  thresholds are flat/absolute rather than scaled to each field's own
  baseline rate — the live demo in
  [`docs/metrics.md`](docs/metrics.md) shows a real case (a 25-point
  population-rate collapse on an already-low-baseline field) that the
  current thresholds don't flag, stated plainly rather than tuned away.
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
5. **Digest generation and style enforcement — done.**
   `digest/generate_digest.py` turns a meeting's validated, published
   `AgendaItem`s (never raw document text) into a plain-language,
   fully-cited Markdown digest, using forced tool use so the output is
   never free-text-parsed. `checks/style_check.py` scores it against
   [`docs/style-guide.md`](docs/style-guide.md) — a hand-written style
   guide covering voice, structure, citation rules, and an explicit
   prohibition on editorializing — with a deterministic tier (structure,
   citations, banned constructions, length, reading level, first-
   reference titles) and an LLM-judge tier (voice/register, unsupported
   claims, editorializing). The checker is scored against its own
   20-case labeled eval set the same way extraction is scored against
   its gold set, and CI generates a real digest from real M4 data on
   every relevant PR, failing on any high-severity finding. The first
   real run found and fixed two genuine bugs (ungrounded eval fixtures,
   a sentence-tokenizer bug that severed citations from real
   abbreviation-heavy prose) and produced an honest, reported precision/
   recall split between the two tiers. Full methodology and results:
   [`docs/style-checking.md`](docs/style-checking.md).
6. **Metrics and drift detection — done.** `metrics/collect.py` computes
   per-run `RunMetrics` (rows parsed, schema failure rate, per-field
   population rates, mean confidence, hallucination rate, review-queue
   volume) for one jurisdiction; `metrics/drift.py` compares a run
   against the mean of that jurisdiction's own prior runs and flags
   deviations past a threshold — the actual "connector rot" signal, with
   no gold set or hand labels required, only a city's own history.
   `metrics/report.py` renders a Markdown health report as a CI
   artifact. Separately, `checks/docs_drift.py` regenerates
   `docs/data-model.md` directly from the Pydantic models' own
   `Field(description=...)` metadata and fails CI if the committed file
   doesn't match — editing a model without regenerating the doc is now a
   CI failure, not a silently stale file. The live validation extracted
   real M4 data as a baseline, then simulated a deliberately broken
   connector (a field silently going empty, no schema failures) and
   confirmed `detect_drift()` catches it — while also surfacing, and
   reporting honestly, a real case the current thresholds don't catch.
   Full methodology: [`docs/metrics.md`](docs/metrics.md).
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
| [`docs/style-guide.md`](docs/style-guide.md) | The hand-written editorial standard every digest is written and checked against |
| [`docs/style-checking.md`](docs/style-checking.md) | Style-checker methodology, its own measured precision/recall, and the real bugs the first live run found |
| [`docs/metrics.md`](docs/metrics.md) | Per-run health metrics, trailing-baseline drift detection, thresholds, and the live connector-rot demonstration |
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
    digest/                digest generation from validated extractions
    metrics/               per-run health metrics + trailing-baseline drift detection
checks/                 style_check.py (deterministic rules + LLM judge), docs_drift.py
evals/                  eval harness: gold set + style cases, scoring metrics, orchestration, baselines
tests/                  pytest coverage of parsing, models, fetch, text extraction, LLM extraction, evals, review, digest, checks, and metrics
data/processed/         sample output (JSON, one file per city per period)
data/raw/               fetched agenda/minutes documents, content-addressed
data/review_queue/      below-threshold extractions awaiting human review
data/metrics/           per-run, per-city health metrics
.cache/llm/             Claude response cache, keyed on (prompt_version, model, input hash)
```

Full breakdown in [`docs/architecture.md`](docs/architecture.md#directory-layout-current).
