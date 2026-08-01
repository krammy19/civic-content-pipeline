# Engineering Log

> This log was drafted with Claude during the initial build session and
> then edited by hand into the document below — cut down to the
> decisions and reasoning worth keeping, with environment-setup notes
> and other session noise removed. It is not hidden that AI assistance
> was part of building this project; the editing is the point. See the
> [README](../README.md) for the current state of the project and where
> it's headed, and this log for why the parts that already exist look
> the way they do.

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

## Where this was heading, and where the roadmap picks it up

The framing shift that mattered most during this phase: the project
stopped being thought of as "a scraper script" and became "a civic data
ingestion and normalization platform." The [README's roadmap](../README.md#roadmap)
carries that framing forward and sharpens it further — this is meant to
become a quality-controlled content system, where extraction is graded
against an eval suite and gated in CI, not just a normalization layer.
The connector architecture and the header-mapping discipline described
above are exactly what that next phase is built on top of.

## 2026-07-31 — Schema migration, a real connector bug, and document fetch

First step of the roadmap above: move `models.py` off dataclasses onto
Pydantic, and start on connector hardening and document fetch.

**The schema now enforces what used to be assumed.** Dataclasses never
validated anything at runtime — `AgendaItem(title=None, ...)` was
accepted silently. Pydantic rejects it, which immediately surfaced a
real gap: `LegistarConnector._parse_agenda_items()` could construct an
agenda entry with no title if that cell happened to be empty. Fixed by
skipping rows with no resolvable title, the same way rows with no
resolvable date already get skipped in `_parse_meetings()` — a missing
required field is now a parse-time skip decision, not something that
reaches a model constructor.

**The new schema also splits "scraped" from "extracted."** The old
`AgendaItem` (Legistar's own File #/Title/Action/Result row) and the
target schema's `AgendaItem` (motions, votes, people, locations, dollar
amounts — extraction-layer output) are not the same shape, and were
never going to be. Keeping one name for both would have made "does this
object hold real analysis or just a scraped listing" something you could
only tell by inspecting field values. Renamed the scraped version to
`LegistarAgendaEntry` and kept `AgendaItem` for the extraction-layer
model, populated by nothing yet — see `docs/data-model.md`'s "Why two
agenda item models" for the fuller version of this.

**Found a real bug by actually looking at production HTML instead of
guessing.** The design doc's own backlog had flagged "video URL
extraction unreliable" months ago without saying why. Fetching Oakland's
and San Francisco's live Legistar calendars (both with Selenium, to get
past-meeting rows with real video links) showed the actual mechanism:
Legistar's Video column renders `href="#"` with the real target hidden
in `onclick="window.open('Video.aspx?Mode=Granicus&ID1=...','video')"`.
Committed sample data already showed the symptom —
`https://oakland.legistar.com/#` as a "video URL" — which is exactly the
useless output that bug produces. `_extract_link()` now falls back to
parsing the `onclick` handler when `href` is empty or `"#"`.

Lesson worth naming: "this field is unreliable" sitting in a backlog for
months without a concrete cause is a sign nobody's actually looked at
the HTML recently. Fetching two real cities' live calendars took a few
minutes and turned a vague complaint into a three-line, tested fix.

**Document fetch and text extraction are new, standalone, and not wired
up yet.** `document_fetch.py` downloads a URL to
`data/raw/<jurisdiction>/<hash-of-url><ext>`, keyed by a hash of the URL
so a re-fetch is a directory glob, not a network call.
`document_text.py` extracts PDF text with `pdfplumber`'s layout-
preserving mode and flags `ocr_required` when extracted text is
implausibly sparse for the page count — the proxy for "this is a scan
with no text layer." Validated against 35 real San Jose agenda/minutes
PDFs (25 agendas + 10 minutes, all of 2025): all born-digital, zero
scans, zero failures. That's a clean result, not a thorough one — none
of San Jose's recent documents happened to be scans, so the OCR-flagging
path is proven correct against synthetic fixtures
(`tests/test_document_text.py`) but not yet against a real scanned
municipal PDF. Neither module is called automatically by any connector
or runner yet; that wiring is still ahead.

## 2026-07-31 (continued) — Extraction layer, and an honest gap

Second step of the roadmap: the LLM extraction layer itself.

**One wrapper, one place that touches the Anthropic client.** `llm.py`'s
`call_with_tool()` is now the only thing in the codebase that constructs
`anthropic.Anthropic()`. Everything else — the new
`extraction/agenda_item.py` and the older `extraction/staff_report.py`
(moved and refactored to match, its previously-inline instructions
pulled out to `prompts/extract_civic_data.v1.md` in the process) — calls
through it. Caching is keyed on a hash of the full request
(`prompt_version`, model, messages, tools, tool_choice), so a re-run
against something already seen costs nothing and hits no network.

**Used the Pydantic schema itself as the tool definition.**
`extract_agenda_item()` builds its tool's `input_schema` from
`AgendaItem.model_json_schema()` directly, rather than hand-writing a
parallel JSON schema next to the model (the way the older
`staff_report.py` extraction does, with its own hand-maintained
`_EXTRACT_TOOL` dict). One schema, one source of truth — a field added
to `AgendaItem` shows up in what Claude is asked to fill in
automatically, with no second place to remember to update.

**Provenance verification is a string search, not a model call.** The
one requirement in the spec worth being stubborn about: an extraction
whose `source_text` isn't actually in the document is a fabrication, and
that has to be checkable without trusting another model's judgment.
`verify_provenance()` is a plain substring test. Anything that fails it
gets dropped before the `AgendaItem` is returned — `tests/extraction/test_agenda_item.py`
has a fabricated-span case proving this, and a mixed-batch case proving
a fabrication doesn't take a legitimate extraction down with it.

**The honest gap: this hasn't run against a real model.** No
`ANTHROPIC_API_KEY` was available in this environment, so
"`extract_agenda_item()` works" currently means "works against a
FakeClient that returns whatever a test tells it to." That's real
coverage of the plumbing — caching, schema construction, provenance
filtering, the source_document override — but it says nothing about
whether Claude actually extracts good motions and votes from a real
agenda PDF's text, which is the part that will need an eval harness
(next) to even measure. Documented plainly rather than glossed over,
here and in the README - the difference between "tested" and "validated
against a real model" matters and this project's whole premise is not
blurring that line.

## 2026-07-31 (continued) — The eval harness, a real API key, and two real bugs

Third step of the roadmap: close the gap the last entry ended on. An
`ANTHROPIC_API_KEY` became available, switching everything from "tested
against a mock" to "measured against a live model" — the model default
also moved off the placeholder `claude-opus-4-7` to `claude-sonnet-5`
for cost, since a $5 budget and 38 gold cases don't leave room for a
frontier-tier model on a first pass.

**The harness was built before it was allowed to spend anything.**
`evals/metrics.py` — every matcher, the greedy matching algorithm,
precision/recall/F1, calibration — is pure functions with no network or
Pydantic dependency, and got 33 unit tests against hand-computed
synthetic cases before a single real API call was made. The point: if
the scoring logic itself were wrong, a good-looking number from a real
run would be meaningless, and there'd be no way to tell the difference
between "the model did well" and "the scorer is broken" after the fact.

**One call per gold case, ever, by construction.** `llm.py`'s cache
means the eval is only ever expensive once — re-running after a gold
fix or a matcher fix hits the cache, not the API. The 38 files in
`.cache/llm/` after the entire session, matching the gold set size
exactly, is the actual proof this held.

**The harness caught its own bugs, which is the point of writing one.**
The first real run scored badly enough (people F1 0.635, locations
weak, calibration error 0.228) to be worth hand-auditing rather than
accepting. That audit found two distinct root causes, fixed differently
on purpose:

1. Item `sj-cc-2025-12-09-8.1`'s gold annotation only captured 1 of 5
   people named in a joint memo — Claude had correctly extracted the
   other 4 (Mahan, Tordillos, Ortiz, Casey) and they were scoring as
   false positives for being *right*. Fixed by completing the gold
   annotation, not by touching the model or the matcher.
2. Separately, `match_person()` was failing on names Claude extracted
   with a fused title ("Mayor Mahan") against gold's bare surname
   ("Mahan") — a real matcher gap, not a gold gap. Fixed by adding
   `_strip_title()` before comparing, with regression tests
   (`test_match_person_ignores_a_title_fused_into_one_side`) proving
   the fix without loosening the matcher into falsely joining different
   people. A third case (`sj-cc-2025-12-09-3.6`, a missing "Madison,
   AL" location) was the same category-1 gap. After both fixes: people
   F1 0.828, calibration error 0.1345.

**A real bug found by a unit test, not the live API.** Writing
`test_match_amount_false_for_different_numbers` surfaced that the
text-similarity fallback in `match_amount()` would call `"$1,000,000"`
and `"$2,000,000"` a match — they differ by one character. Fixed by
making the numeric `amount_usd` comparison authoritative whenever both
sides have one, falling back to text similarity only when neither does.
This one cost nothing to find because it never needed a real API call
to expose — exactly the value of testing scoring logic in isolation.

**Final numbers, and what they actually mean.** Against the 38-case
gold set: motions F1 0.88, amounts F1 0.87, people F1 0.83, locations F1
0.60 (weakest field — a matching-granularity issue, not necessarily a
worse extraction; see `docs/evals.md`). Zero measured hallucinations,
100% schema validity. Calibration is the one number worth stating
plainly rather than softening: Expected Calibration Error 0.13, and the
0.85–0.95 confidence bucket is only right 83% of the time — the model
states confidence higher than it's earned. A downstream review-queue
threshold built on this would need to sit closer to "hold back anything
under 0.9," not the naive 0.8 line that would look reasonable without
this data. Full writeup, matching-rule caveats, and known limitations
for a v2 harness: [`docs/evals.md`](evals.md).

**CI is wired to gate on this without forcing spend.**
`.github/workflows/eval.yml` runs the same harness on any PR touching
`evals/`, `prompts/`, or the extraction/model code, but no-ops (exit 0,
not a failure) when no `ANTHROPIC_API_KEY` secret is configured — a fork
or an environment without the secret gets a skipped check, not a broken
one, and a merge that genuinely regresses a field's F1 by more than 0.03
against `evals/baseline.json` is what actually fails the gate.

## 2026-07-31 (continued) — Confidence routing, the review CLI, and a real scoring bug

Fourth step of the roadmap: M3 established that the model is
overconfident (ECE 0.13, and only 83% accurate in its own 0.85-0.95
bucket). M4 is what that finding is actually *for* - a mechanism to hold
back exactly the extractions that overconfidence finding says can't be
trusted, and a way to turn a human's resolution of that uncertainty back
into more gold data rather than a one-off correction that's forgotten
the moment it's made.

**Confidence routing is per-field-type, and deliberately uniform for
now.** `review/routing.py`'s `route_agenda_item()` splits an
already-verified `AgendaItem`'s fields at a threshold (0.9 for every
field type today) - not because every field type deserves the same
threshold, but because M3's calibration data was measured in aggregate,
not broken out per field. Four independently-set thresholds would look
more sophisticated than the data backing them actually is. `thresholds`
is a plain dict parameter specifically so this can change once
per-field calibration exists to justify it.

**The review CLI is intentionally thin.** `python -m civic_scraper.review`
does exactly four things to a queued item: accept, edit one text field,
reject, or skip - each persisted immediately to the item's own JSON file
so a session can be interrupted without losing decisions. The interesting
part was never the CLI; it's what an accept or edit decision triggers
next.

**The flywheel: `gold_export.py`.** An accepted or edited review item
becomes a new `evals/gold/*.json` case, in the same shape as every other
gold case. Rejections are never exported - a rejection is a confirmed
non-fact, not ambiguous data worth keeping.

**A real, live test of the whole loop.** Eight real agenda items from
San José's June 9, 2026 City Council meeting - fetched with the
project's own `document_fetch`/`document_text` pipeline, a meeting date
the gold set had never seen - were extracted against the live API and
routed through confidence thresholds (`scripts/run_review_demo_batch.py`,
kept in the repo the same way `scripts/build_gold_set.py` records how
the original gold set was built). Ten field values landed in the review
queue. A real review session resolved all ten: six accepted (Kamei
correctly identified as the consent-calendar seconder across four
separate items, a correctly-attributed motion outcome, a specific
facility name), four rejected - and the rejections turned out to be the
more interesting result. Three of them were the model extracting a
document's own city name ("San José" / "City of San José") as a
"location," and one was a capital *fund* name misclassified as a
location. Real, previously-undocumented failure modes, caught by a
human applying actual judgment rather than a review session that rubber-
stamps everything - see `docs/review.md` for the full breakdown.

**The harness caught its own bug again - this time in the flywheel
itself.** The six accepted items were exported and the eval suite
re-run to confirm it picked them up (`Gold cases: 44`). It did - and
then reported a regression on *every field*, including fields none of
the six new cases even asserted anything about. The cause: each
review-derived case only has real ground truth for the one field type it
was queued for, but `evaluate_case()` was scoring every field against
whatever gold provided - and an empty list read as "confirmed: nothing
here," not "not checked." The source documents behind those six cases
also contain real, correct amounts and people the model correctly
extracted, and with no ground truth on file for those fields, every one
of those correct extractions scored as a false positive. Fixed by adding
an `annotated_fields` concept to `evaluate_case()`: a case can now
restrict scoring to a subset of field types, and gold cases from the
original hand-annotated 38 (which have no `annotated_fields` key at all)
are scored on every field exactly as before - backward compatible by
construction, not a version flag anyone has to remember to set. After
the fix: no regression, and `evals/baseline.json` was updated to the new
44-case scores as its own explicit, reviewable commit. This is the same
category of finding as M3's two bugs: the harness catching an honest
mistake in its own scoring logic before that mistake could quietly
become "the model got worse" in someone's mind. That's the entire
reason to build one this carefully, twice now.

**Cost note.** The whole M4 live test - eight new extractions plus
several eval re-runs over the growing gold set - added twelve entries to
`.cache/llm/` (fifty total, up from thirty-eight after M3). A few of
those came from a small, harmless side effect worth naming honestly: a
gold case's `item_title`/`item_number` are taken from the *model's own*
extracted `AgendaItem` fields (so the case reads naturally on its own),
not the exact string originally passed into the extraction call - and
since both are part of the prompt, a mismatch between the two produces a
new cache key the first time an eval run touches that case. Harmless and
cheap, and documented in `docs/review.md` rather than treated as a
mystery.
