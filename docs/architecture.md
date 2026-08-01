# Architecture

This describes the system as it exists today: a connector-based
ingestion layer that normalizes municipal meeting data into a validated
schema, a document-fetch/text-extraction stage on top of it, an
LLM-based extraction layer that can turn one agenda item's document text
into a schema-validated `AgendaItem`, an eval harness that scores that
extraction layer against a hand-annotated gold set, and a confidence-based
review queue that holds back uncertain extractions for a human decision
and feeds that decision back into the gold set. It does not describe the
digest layer still planned (see the [README](../README.md#roadmap)) —
that doesn't exist yet. This doc will be updated as it lands.

## Overview

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
   data/processed/<city>/*.json <- current persistence layer
            |
            v
   Document fetch + text        <- data/raw/<city>/, content-addressed;
   extraction (document_fetch.py,   PDF text extraction with scan detection
   document_text.py)
            |
            v
   LLM extraction                <- extraction/agenda_item.py, via llm.py (cached)
   (not wired to a runner yet)      forced tool use -> AgendaItem, provenance-verified
            |
            v
   Eval harness (evals/)          <- 44-case gold set; precision/recall/F1, hallucination
                                      rate, calibration per field; gates CI on regression
            |
            v
   Review queue (review/)         <- below-threshold extractions held back; a person
                                      accepts/edits/rejects via the review CLI; accepted
                                      decisions feed back into the gold set above
```

See [`data-model.md`](data-model.md) for the full field reference on
every model, and [`ingestion-pipeline.md`](ingestion-pipeline.md) for
how a run actually executes end to end.

## Guiding principles

- **Normalize immediately after scraping.** A connector's public methods
  never return raw HTML, `BeautifulSoup` elements, or dicts shaped like
  the source platform's DOM — only the Pydantic models in
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
- **Preserve source URLs for traceability.** Every model that
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

A related, separately-discovered issue: several link columns —
consistently the `Video` column, confirmed live on Oakland's and San
Francisco's Legistar calendars — don't use a real `href` at all. The
anchor is `href="#"` with the actual target hidden in a JS popup
handler: `onclick="window.open('Video.aspx?Mode=Granicus&ID1=...','video')"`.
A plain `cell.find("a")["href"]` extraction silently produces a useless
`.../#` URL in this case rather than failing — which is exactly what
shipped for a while (visible in older committed sample data).
`_extract_link()` now falls back to parsing the `onclick` handler when
the `href` is empty or `"#"`.

Rows with no resolvable `title` are now skipped outright in
`_parse_agenda_items()`, rather than constructing an agenda entry with a
missing title — `LegistarAgendaEntry.title` is a required field under
Pydantic, so this used to be a validation error rather than a graceful
skip.

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
Near-term scope is deliberately Legistar plus exactly one second city on
a different platform — see the README's
[current limitations](../README.md#current-limitations) — so building
out every detected platform is explicitly not the near-term goal.

## Document fetch and text extraction

Two small, single-purpose modules sit downstream of the connector layer:

- **`document_fetch.py`** — `fetch_document(url, jurisdiction)` downloads
  a URL to `data/raw/<jurisdiction-slug>/<hash-of-url><ext>`. The cache
  key is a hash of the URL itself, not the response body, so
  "has this already been fetched" is a directory glob, not a network
  round trip. Content-Type (falling back to the URL's own suffix)
  decides the file extension.
- **`document_text.py`** — `extract_pdf_text(path)` runs `pdfplumber`
  with `layout=True` (preserves visual column/whitespace structure
  rather than collapsing it) and flags `ocr_required=True` when the
  extracted text is implausibly sparse for the page count — the proxy
  for "this PDF is a scan with no embedded text layer." Municipal
  agenda/minutes PDFs are frequently exactly that. `fetch_and_extract()`
  combines both steps and returns a `FetchedDocument` (see
  [`data-model.md`](data-model.md#document-fetch-output)).

Neither module is wired into the connectors or runners yet — nothing
calls `fetch_and_extract()` on a `Meeting`'s `agenda_url`/`minutes_url`
automatically. That wiring is still on the [roadmap](../README.md#roadmap).

## LLM extraction layer

`llm.py` is the only place in the codebase that touches
`anthropic.Anthropic()`. Every Claude call — the new agenda-item
extraction below and the older staff-report extraction — routes through
its one function, `call_with_tool()`, which:

1. Forces tool use (`tool_choice={"type": "tool", "name": ...}`), never
   free-text parsing.
2. Caches the response to `.cache/llm/` (gitignored), keyed on a hash of
   `(prompt_version, model, messages, tools, tool_choice, max_tokens,
   thinking)`. A cache hit returns before an Anthropic client is even
   constructed — re-running extraction against inputs already seen costs
   zero tokens.

**`extraction/agenda_item.py`** builds its tool's `input_schema` directly
from `AgendaItem.model_json_schema()` — the Pydantic schema itself is
what Claude is asked to fill in, so a successful tool call produces
something `AgendaItem.model_validate()` can construct without a
hand-written parser in between. The prompt lives in
[`prompts/extract_agenda_item.v1.md`](../prompts/extract_agenda_item.v1.md),
not inline in code, so a prompt change is a diff an eval run can be
attributed to later.

**Provenance verification is the hallucination check, and it's
deterministic.** Every `Extracted[T]` the model returns carries a
`provenance.source_text` — the verbatim span it claims supports the
extraction. `verify_provenance()` checks that span is actually a
substring of the source document. Anything that fails is dropped before
the `AgendaItem` is returned; nothing downstream ever sees an
unverified extraction. This is a plain string containment check, not
another LLM call, specifically so the check itself can't hallucinate.
`provenance.source_document` is also overwritten with the real, known
document identifier after the fact, rather than trusted from the
model's own output — there's no reason to let it guess something the
caller already knows.

**`extraction/staff_report.py`** predates the schema-driven approach
above and extracts free-form structured JSON from a whole staff report
(fiscal impacts, timelines, stakeholders, cited laws) rather than a
validated `AgendaItem` for one specific item — no provenance
verification is applied to its output. Both modules route through the
same `llm.py`, which is what actually matters for the caching guarantee
and for having exactly one place that touches the Anthropic client.

Nothing calls `extract_agenda_item()` automatically yet — it's built,
tested against a mocked Anthropic client for the plumbing (caching,
schema construction, provenance filtering), and separately scored
against the live API by the eval harness below. It's ready to be wired
into a runner once the review-queue layer around it exists.

## Eval harness

[`evals/`](../evals/) measures what `extraction/agenda_item.py` actually
produces from a real model, not just what it's plumbed to do. Full
methodology, matching rules, and the first real run's results (including
two real bugs the harness caught) are in
[`docs/evals.md`](evals.md) — this section covers only how the pieces
fit together architecturally:

- **`evals/gold/*.json`** — 38 hand-annotated cases, each pairing real
  verbatim government-document text with hand-determined expected
  motions/people/locations/amounts. Built by
  [`scripts/build_gold_set.py`](../scripts/build_gold_set.py), a
  one-time generator (not re-run automatically — editing gold means
  editing the JSON or the generator directly).
- **`evals/metrics.py`** — pure scoring functions with no network or
  Pydantic dependency: per-field-type matchers, greedy one-to-one
  matching, precision/recall/F1, hallucination-rate and calibration
  (Expected Calibration Error) computation. Fully unit-tested against
  synthetic inputs (`tests/evals/test_metrics.py`), independent of
  whether a real API call ever runs.
- **`evals/run_eval.py`** — orchestration: loads gold cases, calls
  `extract_agenda_item_raw()` (the unfiltered, pre-provenance-check
  output — scoring the filtered output alone would show 0%
  hallucinations by construction and hide what the model actually
  attempts), scores both raw and filtered output, and checks the result
  against `evals/baseline.json` with a regression gate (fails if any
  field's F1 drops more than 0.03 below baseline).
- **Cost safety** — because every extraction call routes through
  `llm.py`'s cache, running the eval twice against the same gold set and
  model costs nothing the second time. `.github/workflows/eval.yml`
  additionally no-ops (exit 0) when no `ANTHROPIC_API_KEY` secret is
  configured, so the CI job never forces spend on a fork or an
  unconfigured environment.

## Confidence routing and the review queue

[`review/`](../services/workers/civic_scraper/review/) sits downstream of
extraction and answers a question the eval harness surfaced but doesn't
itself resolve: what should happen to an extraction the model wasn't
confident about? Full methodology, the review CLI's usage, and the first
real review session's results are in [`docs/review.md`](review.md); this
section covers how the pieces fit together:

- **`routing.py`** — `route_agenda_item()` takes an already-verified
  `AgendaItem` and, per field type, either keeps a value (confidence at
  or above that field type's threshold) or moves it into a
  `ReviewQueueItem` (below threshold). Thresholds are a plain dict
  (`DEFAULT_THRESHOLDS`), not a single global constant, specifically so a
  field type with its own measured calibration profile can move
  independently once that data exists.
- **`models.py` (review-scoped) / `queue.py`** — `ReviewQueueItem` is the
  file format for `data/review_queue/*.json`: the proposed value, its
  provenance, and full item/meeting context, plus a `status` a reviewer
  moves from `pending` to `accepted`/`edited`/`rejected`. `queue.py`
  reads and writes these files and reports queue volume by status.
- **`cli.py`** (`python -m civic_scraper.review`) — the interactive
  decision loop: one item at a time, its provenance span and surrounding
  source context, accept/edit/reject/skip.
- **`gold_export.py`** — turns an accepted or edited item into a new
  `evals/gold/*.json` case, closing the loop between human review and
  the eval harness. Because a review item only has ground truth for the
  one field type it covers, the exported case carries an explicit
  `annotated_fields` list restricting scoring to that field - see
  `docs/review.md` for the real regression this fixed the first time it
  came up.

## Directory layout (current)

```
civic-engagement-app/
├── docs/                          architecture, data model, pipeline, engineering log
├── prompts/                        versioned LLM prompts, never inline in code
│   ├── extract_agenda_item.v1.md
│   └── extract_civic_data.v1.md
├── scripts/
│   └── scrape_meetings.py         early prototype, kept for reference
├── services/workers/
│   ├── civic_scraper/
│   │   ├── models.py              canonical Pydantic schema
│   │   ├── connectors/            one module per platform + the shared ABC
│   │   ├── llm.py                  single cached Claude wrapper
│   │   ├── extraction/             LLM-based structured extraction (agenda items, staff reports)
│   │   ├── review/                 confidence routing, review queue, gold-set flywheel
│   │   ├── document_fetch.py      content-addressed document download/cache
│   │   ├── document_text.py       PDF text extraction + scan detection
│   │   ├── cities.yaml            city registry
│   │   ├── generate_cities_yaml.py
│   │   ├── detect_platforms.py
│   │   ├── discover_civicplus.py
│   │   ├── run_legistar.py        Legistar-only runner (superseded by run_all.py)
│   │   └── run_all.py             multi-connector ingestion runner
│   └── data/processed/            sample output when run from services/workers/
├── evals/                         gold set, scoring metrics, orchestration, committed baseline
├── data/processed/                sample output when run from repo root
├── data/raw/                      fetched agenda/minutes documents, content-addressed
├── data/review_queue/             below-threshold extractions awaiting human review
├── .cache/llm/                    Claude response cache, keyed on (prompt_version, model, input hash)
└── tests/                         pytest coverage of parsing, models, fetch, text extraction, LLM extraction, evals, and review
```

`data/processed/` exists in two places because the runners resolve their
output path relative to the current working directory rather than the
repo root — a known inconsistency, not yet fixed.

See the [README's roadmap](../README.md#roadmap) for what's still ahead
(wiring fetch and extraction into a runner, a validation gate, an eval
harness, digest generation) and the order it's being built in.
