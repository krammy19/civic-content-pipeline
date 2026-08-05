# Civic Engagement App

Turns municipal meeting records into structured, verifiable data, and
into plain-language digests that can't publish until they pass an
automated quality gate.

**Why it exists.** Cities publish meeting records in dozens of
incompatible formats with no shared schema. Tracking a zoning change or
a budget line means digging through PDFs one city at a time. This
project normalizes that into one structured, queryable form, and holds
back bad output — hallucinated facts, miscategorized items, sloppy
summaries — before a reader ever sees it.

**What's proven.** Extraction scores against a 44-case hand-annotated
gold set: 0% hallucination, 100% schema validity, F1 0.70–0.87
depending on field. The model is measurably overconfident (ECE 0.13),
which is why below-threshold values route to human review rather than
publishing. → [`docs/evals.md`](docs/evals.md)

**What isn't.** `civic run` wires every stage end to end, but only for
Legistar cities with already-published minutes. A second platform is
scored, not equally good — two fields measurably worse, for verified
reasons. → [Current limitations](#current-limitations)

## Results at a glance

Against the 44-case gold set ([`evals/baseline.json`](evals/baseline.json)):

| Field | Precision | Recall | F1 |
|---|---|---|---|
| Motions | 0.83 | 0.92 | 0.87 |
| People | 0.69 | 0.99 | 0.82 |
| Locations | 0.55 | 0.94 | 0.70 |
| Amounts | 0.77 | 1.00 | 0.87 |

- Schema validity: 100% · Hallucination rate: 0% · Gold set size: 44 cases
- Expected calibration error: 0.13 — the model states confidence higher
  than it earns

Locations underperform for a documented matching-granularity reason, not
worse extraction — see [`docs/evals.md`](docs/evals.md#known-limitations-and-what-a-v2-harness-should-fix).

## Architecture

```
 Municipal platform (Legistar, CivicPlus, ...)
            |
            v
   Platform Connector          <- only place that knows platform-specific HTML/DOM
            |                                    `civic run` (services/workers/civic_scraper/runner.py)
            v                                     walks every stage below for one real meeting,
   Pydantic models              <- Meeting, ...   Legistar cities with published minutes only -
            |                                     see docs/end-to-end-runner.md
            v
   data/processed/<city>/*.json <- current persistence layer (flat JSON, no DB)
            |
            v
   Document fetch + text        <- data/raw/<city>/, content-addressed;
   extraction                       PDF text extraction with scan detection
            |
            v
   LLM extraction (llm.py,      <- forced tool use -> AgendaItem, provenance-verified;
   extraction/agenda_item.py)      run against the live API, scored by evals/
            |
            v
   Eval harness (evals/)         <- 44-case gold set; precision/recall/F1, hallucination rate,
                                     and confidence calibration per field; CI regression gate
            |
            v
   Review queue (review/)         <- extractions below a per-field confidence threshold are
                                      held back; civic review resolves them;
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
uv run civic ingest

# Or just one city
uv run civic ingest --city Oakland

# Run the test suite
uv run pytest

# Lint
uv run ruff check .
```

Output lands in `data/processed/<city-slug>/`. Legistar's calendar
search is JS-driven, so that connector drives a headless Chrome via
Selenium — a Chrome/Chromium install is required. CivicPlus is plain
HTTP and needs nothing extra. Every `civic` subcommand is documented in
[`docs/ingestion-pipeline.md`](docs/ingestion-pipeline.md); run
`uv run civic --help` for the full list.

## Examples

Real output from real runs, committed so you can see what this
produces without cloning the repo or supplying an API key:
[`examples/`](examples/). Start with a real generated digest
([`examples/digest-san-jose-2026-06-09.md`](examples/digest-san-jose-2026-06-09.md))
and the eval scorecard
([`examples/eval-scorecard.txt`](examples/eval-scorecard.txt)); a real
drift report and a review-session transcript are there too. See
[`examples/README.md`](examples/README.md) for what produced each one.

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
| [`docs/end-to-end-runner.md`](docs/end-to-end-runner.md) | `civic run`'s stage wiring, its two failure-handling rules, and what the first live run found |
| [`docs/engineering-log.md`](docs/engineering-log.md) | How the connector architecture and header-mapping approach were actually arrived at |

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

- **The end-to-end runner (`civic run`) is real, live-validated, and
  narrower than "wired everything."** It walks calendar → agenda items →
  document fetch → extraction → confidence routing → digest → style
  check → metrics for one real meeting, and a live run against San
  José's real calendar exercised every stage with real data. What it
  isn't: CivicPlus-capable (Phase 2 is Legistar-only), cheap at scale
  (it re-sends the full meeting document once per agenda item), or
  reliable against a not-yet-held meeting (extraction was built and
  measured against *minutes*, not the *agenda* text available before a
  meeting happens — the live run's own hallucination rate on an
  agenda-only document was a genuine 100%, reported as such rather than
  hidden). Full writeup: [`docs/end-to-end-runner.md`](docs/end-to-end-runner.md).
- **Digest generation has only been run against one meeting's worth of
  real data.** `docs/style-checking.md` documents that single real run
  in detail (including a real sentence-tokenization bug it found and
  fixed), but one meeting is a smoke test, not a validated sample size.
- **Extraction quality is uneven across fields, and the model is
  overconfident.** Against the 44-case gold set: motions F1 0.87,
  amounts F1 0.87, people F1 0.82, but locations F1 only 0.70 (a
  matching-granularity problem more than an extraction problem, and
  locations also over-trigger on a document's own self-referential city
  name — see [`docs/evals.md`](docs/evals.md) and
  [`docs/review.md`](docs/review.md)). Hallucination rate is 0% and
  schema validity is 100%, but confidence calibration is not
  trustworthy as-is (ECE 0.13) — this is exactly why extraction now
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
- **On the second platform (Alhambra, CivicPlus), people and amounts
  extraction is measurably worse, for two verified reasons, not a
  hallucination.** The model extracts every named vote-caster in
  Alhambra's per-item roll call, not just the mover/seconder gold
  credits (48 of 77 raw `people` extractions), and extracts background
  bid figures alongside the amount actually awarded. Motions and
  locations held up fine on the same 15-case set. Full breakdown:
  [`docs/evals.md`](docs/evals.md#a-second-platform-alhambra-ca-civicplus).
- **Scan detection is a heuristic, not a real classifier.** A PDF page is
  flagged `ocr_required` when extracted text is implausibly sparse for
  its page count (`document_text.MIN_CHARS_PER_PAGE`) — good enough to
  catch genuinely text-free scans, not rigorously validated against a
  labeled set of real scanned municipal PDFs.
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
   `civic review` (accept, edit, or reject). Accepted
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
7. **End-to-end wiring — done, with real scope limits.** `civic run`
   (`runner.py`) walks calendar → agenda items → document fetch →
   extraction → confidence routing → digest → style check → metrics for
   one real meeting, live-validated against San José's real calendar.
   It's Legistar-only (CivicPlus has no Phase 2 yet) and, more
   interestingly, only reliable against meetings with published
   minutes — the live run against a not-yet-held meeting (agenda text
   only) produced a genuine 100% raw hallucination rate, reported
   plainly rather than smoothed over, since the extraction prompt was
   built and measured entirely against minutes. Full writeup:
   [`docs/end-to-end-runner.md`](docs/end-to-end-runner.md).
8. **A second platform — done.** `CivicPlusConnector` (Alhambra, CA) got
   its own test suite (`tests/connectors/test_civicplus.py`) and its own
   15-case gold set (`evals/gold_civicplus/`), scored separately from
   San José's and never pooled with it. Motions and locations held up;
   people and amounts got measurably worse, and both regressions were
   traced to a real, verified cause by pulling raw model output, not
   left as a guess — the prompt was not tuned to close the gap, since
   doing so would defeat the point of testing generalization at all.
   Full writeup: [`docs/evals.md`](docs/evals.md#a-second-platform-alhambra-ca-civicplus).

## Project layout

```
docs/                   architecture, data model, pipeline, eval methodology, engineering log
examples/               real committed output: a generated digest, an eval scorecard, a drift report, a review session
prompts/                versioned LLM prompts (never inline in code)
services/workers/civic_scraper/
    models.py             canonical Pydantic schema
    paths.py              every data directory, anchored to the repo root
    cli.py                 the `civic` console command - thin argument parsing over everything below
    runner.py              `civic run` - wires every stage below for one real meeting end to end
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
