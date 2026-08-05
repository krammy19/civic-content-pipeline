# The end-to-end runner

`civic run` is the wiring every prior milestone built as a standalone,
independently-tested stage but never connected: one command that takes a
real meeting from a city's live calendar to a style-checked digest and a
recorded health metric. See
[`docs/architecture.md`](architecture.md) for how each stage it calls
works on its own; this document is only about the wiring, its two
different failure-handling rules, and what the first live run against it
found.

## Usage

```bash
uv run civic run --city "San Jose" --meeting 8/11/2026
uv run civic run --city "San Jose" --meeting 8/11/2026 --dry-run
```

`--city` is a substring match against `cities.yaml`, the same convention
`civic ingest --city` already uses. `--meeting` is a substring match
against a meeting's own `date` field, as scraped from the live calendar —
there's no separate meeting-ID lookup, since the calendar itself is the
only source of truth for what's actually on it right now. `--dry-run`
resolves the city and the meeting, fetches the real agenda-item list and
the real source document, and prints the plan — city, meeting, document
URL and size, item count — without calling the extraction API at all.

## What it walks, in order

1. **Calendar** (`resolve_city`, `resolve_meeting`) — the same Phase 1
   connector call `civic ingest` uses, filtered to the one meeting whose
   date matches `--meeting`.
2. **Agenda items** (`fetch_agenda_items`) — Phase 2, Legistar only. A
   city using the CivicPlus connector is rejected immediately with a
   clear reason, not a confusing downstream failure — `get_meeting_details()`
   doesn't exist on `CivicPlusConnector` yet (see
   [`docs/ingestion-pipeline.md`](ingestion-pipeline.md)).
3. **The meeting's own source document** (`fetch_meeting_document`) —
   `minutes_url` if it's been published, else `agenda_url`. A scanned
   PDF (`ocr_required=True`) halts here rather than feeding an empty
   string into extraction.
4. **Extraction, provenance verification, and confidence routing**
   (`extract_and_route`) — one `extract_agenda_item_raw()` call per
   agenda item, against the *whole* fetched document, then
   `drop_unverified()` and `route_agenda_item()` exactly as the
   standalone stages already work. Queued (below-threshold) values are
   written to `data/review_queue/` the same way a manual review batch
   already does.
5. **Digest generation** (`generate_digest`) — from only the published
   `AgendaItem`s, never raw document text, same as every other digest
   this project has ever produced.
6. **Style check** (`checks.style_check`) — both tiers, printed but not
   gating: `civic run`'s job is to report what a real run actually
   produced, warts included, not to block on them. `civic check` is the
   separate, CI-facing gate for that.
7. **Run metrics** (`compute_run_metrics`, `save_run_metrics`) — one
   `RunMetrics` record per run, written to `data/metrics/`, ready for
   `civic metrics --city` to compare against trailing history.

## Two failure rules, on purpose

A stage the run cannot recover from at all — the calendar won't load,
the requested meeting isn't in it, the meeting has no document to
fetch — raises `StageError` and halts the whole run with the stage name
and cause printed plainly (`RUN FAILED at stage 'document': ...`).
There is no partial output in this case; a run either has a real
document to extract from or it doesn't proceed.

A single agenda item failing extraction does **not** halt the run. It's
caught, printed, and counted as a schema failure — the exact thing
`RunMetrics.schema_failures` already exists to track (see
[`docs/metrics.md`](metrics.md)) — and the run continues with the
remaining items. Halting an entire 30-item meeting because one item's
extraction call had a transient schema hiccup would throw away 29 good
results to protect against one bad one; scoring it instead is what the
metrics layer is for. This mirrors exactly how `evals/run_eval.py`
already treats one gold case's schema failure as a scored outcome, not
a crash.

## The first live run, and a real, unflattering finding

Run against San Jose's real live calendar (`uv run civic run --city
"San Jose" --meeting 8/11/2026`, limited to the first 3 of 30 real
agenda items to keep the live-validation cost small — see the
engineering log for the full transcript). Every stage wired correctly
end to end against real data: a real calendar fetch, a real 30-item
agenda list, a real 111,598-character source document, real extraction
calls, a real generated digest, real style-check findings, and a real
`RunMetrics` record written to disk.

**The result was also a genuinely bad one, and it's reported as such.**
`hallucination_rate` on this run was **1.0** — every raw extraction
attempted on these three items failed provenance verification, so
nothing published. The cause isn't a bug in extraction or in this
runner; it's a document-type mismatch this pipeline hasn't had to
confront before. Every prior milestone's gold set, prompt, and live
validation was built exclusively against **minutes** — the post-meeting
record, with resolved language like "Action: ... was adopted ...
(11-0-0)." This meeting is three days in the future as of the run, so
no minutes exist yet; `fetch_meeting_document` correctly fell back to
the **agenda** — the pre-meeting proposal, which states what's being
asked for, not what happened. `extract_agenda_item`'s prompt looks for
resolved-action language that simply isn't present in agenda text, so
the model's attempts didn't verify. The digest generated from zero
published facts was, unsurprisingly, thin, and the style checker
correctly flagged a real high-severity finding on it (an uncited
factual claim) — the whole pipeline behaved exactly as designed given a
bad input, which is a better outcome than looking artificially clean on
a case it was never built to handle.

**This is a real, currently-open gap, not something quietly patched
around:** the extraction prompt and gold set need an agenda-aware
variant (or this runner needs to skip extraction entirely when only an
agenda is available) before `civic run` produces a trustworthy digest
for a not-yet-held meeting. Today, `civic run` against a future meeting
will reliably fetch and wire correctly; it will not reliably extract
anything real from it. Running it against a meeting whose minutes are
already published does not have this problem, since that's exactly the
document type every other stage in this project was built and measured
against.

## Known limitations

- **Legistar only.** `CivicPlusConnector` has no `get_meeting_details()`
  yet, so `civic run` rejects a CivicPlus city immediately rather than
  failing confusingly partway through.
- **One full document fetched and re-sent per agenda item, not once per
  meeting.** A 30-item meeting means the same ~110K-character document
  text is included in 30 separate extraction prompts. This works and
  was validated live, but it is not the cheapest or fastest possible
  design — a single extraction call scoped to the whole meeting, or a
  cheaper way to slice a document per item, is the obvious next
  optimization and hasn't been built.
- **Agenda-only documents produce unreliable extraction**, as the live
  run above found directly. There is no document-type-aware prompt
  variant yet.
- **Style-check findings are reported, not gated.** A run with a real
  high-severity finding still completes and writes its digest and
  metrics; `civic run`'s exit code reflects it (non-zero if any
  high-severity finding exists), but nothing stops the digest from
  being written to stdout regardless.
