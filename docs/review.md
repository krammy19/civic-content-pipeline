# Review queue and the gold-set flywheel

This describes M4: confidence-based publish/review routing, the
interactive review CLI, and the mechanism that turns a human's review
decision into a permanent addition to the eval gold set. See
[`docs/evals.md`](evals.md) for the eval harness itself and
[`docs/architecture.md`](architecture.md#eval-harness) for how this fits
into the pipeline as a whole.

## Why this exists

Confidence is per-field, not per-document (`models.Extracted` is
deliberately shaped that way - see `docs/data-model.md`). A `AgendaItem`
with nine solid facts and one shaky one shouldn't have all ten held back,
and it shouldn't publish the shaky one just because its neighbors are
fine. Confidence routing (`civic_scraper/review/routing.py`) makes that
decision field value by field value: anything at or above its field
type's threshold publishes; anything below is written to
`data/review_queue/` instead of being silently dropped or silently
shipped.

A held-back value isn't a dead end. A person resolves it - accept,
correct, or reject - through `civic review`, and an
accepted or edited decision is exported into a brand new gold case
(`civic_scraper/review/gold_export.py`). That's the flywheel: the same
uncertainty that kept a value out of production becomes, once resolved by
a human, a permanent addition to the data the eval suite is scored
against. Human review makes the eval suite stronger over time - that's
the point of building this queue, not the CLI itself.

## Confidence routing

`route_agenda_item()` takes an already-verified `AgendaItem` (the output
of `extraction.agenda_item.extract_agenda_item()` - hallucinations are
already filtered out by that point) and a threshold per field type. The
starting thresholds are uniform - `0.9` for every field:

```python
DEFAULT_THRESHOLDS = {"motions": 0.9, "people": 0.9, "locations": 0.9, "amounts": 0.9}
```

One number for every field type, not four independently tuned ones, is a
deliberate choice: the M3 calibration baseline measured confidence
accuracy in aggregate, not broken out per field type, and found the model
overconfident even in its 0.85-0.95 bucket (about 83% actual accuracy
there - see `docs/evals.md`). Moving individual field thresholds without
per-field calibration data to justify it would look more precise than it
actually is. `thresholds` is a plain dict parameter specifically so this
can change once that data exists.

Routing produces a `RoutingResult`: `published` (an `AgendaItem` with
only the fields that cleared their threshold) and `queued` (a
`ReviewQueueItem` per held-back value, each carrying everything a
reviewer needs to judge it on its own - the proposed value, its
provenance span, and the full item/meeting context - without having to
go find the source document).

## The review CLI

```bash
uv run civic review
```

Presents one pending queue item at a time: the item it came from, the
proposed value, the exact provenance span, and about 80 characters of
surrounding source text so a reviewer isn't judging a fact in isolation.
Four choices:

- **accept** - the value was right as extracted.
- **edit** - correct the one text field a reviewer would actually retype
  (`raw_name` for people, `raw_text` for locations/amounts, `text` for
  motions) and the value publishes with that correction going forward.
- **reject** - not a fact worth keeping, with an optional free-text
  reason. Nothing further happens to a rejected item; it is not exported.
- **skip** - leave it pending for a later session.

Every decision is written back to the item's own file in
`data/review_queue/` immediately, so a session can be interrupted and
resumed without losing prior decisions. `queue.summarize()` reports
review-queue volume by status - a growing `pending` count run over run is
the signal that extraction quality is degrading; watching that trend
per city over time is M6's job (`data/metrics/`), not this one's.

## The flywheel: from review decision to gold case

`review_item_to_gold_case()` only accepts `accepted` or `edited` items -
a rejection is a confirmed non-fact and is never exported. The resulting
case has the same shape as every other file in `evals/gold/`, with one
important difference: it asserts a fact for only the one field type the
review item covered, and carries an explicit `annotated_fields` list
saying so:

```json
{
  "id": "review-sj-cc-2026-06-09-6.1-locations-0",
  "expected": {"motions": [], "people": [], "locations": [{"raw_text": "9885 Regional Wastewater Facility", ...}], "amounts": []},
  "annotated_fields": ["locations"]
}
```

**Why `annotated_fields` exists, and the bug it fixes.** The first
version of this export left `annotated_fields` out, on the assumption
that an empty `expected` list for an unannotated field type was
harmless. It wasn't: `evals/metrics.py`'s `evaluate_case()` scores every
field type against whatever gold provides, including fields with nothing
in them - so an empty list reads as "confirmed: no facts of this type
exist here," not "not checked." The first real run after adding six
review-derived cases reported a regression on **every field**, including
fields those six cases never touched. The cause: those same source
documents also contain real, correct amounts and people that the model
correctly extracted, and with no ground truth on file for those fields,
every one of those correct extractions was scored as a false positive.
`annotated_fields` fixes this at the root: `evaluate_case()` now accepts
an optional field-type subset and, when given one, scores and
calibrates only those fields for that case - the other fields contribute
nothing to that case's counts, positive or negative. Hand-annotated
cases from the original 38-case gold set have no `annotated_fields` key
at all and are scored on every field exactly as before; this is
backward compatible by construction, not by a version flag. The bug,
the fix, and why it matters are also in `docs/engineering-log.md`'s M4
entry - it's the same category of finding as M3's two real bugs: the
harness catching an honest mistake in its own scoring logic, which is
the entire reason to build one this carefully.

## The first live review session

Eight real agenda items from San José's June 9, 2026 City Council
meeting - a meeting date the gold set had never seen - were fetched via
the project's own `document_fetch`/`document_text` pipeline, extracted
with the live API, and routed through confidence thresholds
(`scripts/run_review_demo_batch.py`, kept in the repo as the record of
exactly how this batch was produced, the same way
`scripts/build_gold_set.py` records the original gold set). Routing
queued 10 field values for review out of 36 total extracted.

A real review session resolved all 10:

| Decision | Count | Examples |
|---|---|---|
| Accepted | 6 | Councilmember Kamei correctly identified as the consent-calendar seconder on four separate items; a correctly-attributed motion outcome; a specific facility name ("9885 Regional Wastewater Facility") |
| Rejected | 4 | "San José" / "City of San José" extracted as a *location* three times - technically present in the text, but not a meaningful fact worth keeping, since every item mentions the city it's about; a capital *fund* name ("San José-Santa Clara Treatment Plant Capital Fund") misclassified as a location |

The rejections are as important as the acceptances here. A review queue
that accepts everything isn't demonstrating judgment, it's a rubber
stamp - and the rejected items surfaced a genuine, previously
undocumented failure mode: the model treats a document's own
self-referential city name, and a fund's name, as extractable "locations"
often enough to be worth a known-limitations note (see below).

The six accepted/edited decisions were exported to `evals/gold/`,
growing the gold set from 38 to 44 cases. Re-running the eval suite
picked them up immediately (`Gold cases: 44`) with no regression once
`annotated_fields` was in place, and `evals/baseline.json` was updated to
the new 44-case scores as an explicit, reviewable commit, per SPEC's
requirement that baseline updates never happen silently.

## Known limitations

- **Edited values keep the original provenance span.** The CLI lets a
  reviewer correct one text field but doesn't ask for a new provenance
  quote - the correction is anchored to the same span the reviewer was
  looking at when they made the call. Fine for a small text fix (a
  misspelled name), not necessarily accurate if an edit substantially
  changes what's being asserted.
- **A gold case derived from a review item can trigger one new,
  billable API call the first time an eval run touches it**, even though
  its `document_text` was already extracted once during the original
  batch. The gold case's `item_title`/`item_number` come from the
  model's own extracted `AgendaItem` fields (so the case reads naturally
  on its own), not from whatever string happened to be passed into the
  original extraction call - and since both values are part of the
  prompt, a different `item_title` or `item_number` produces a different
  cache key. Harmless and cheap (it's still exactly one call, ever, per
  distinct prompt), but worth knowing before assuming a gold-set addition
  is automatically free on its first eval run.
- **Locations extraction over-triggers on self-referential and
  organizational names.** A document's own city name and fund/account
  names get proposed as "locations" at low-but-not-negligible confidence.
  Confidence routing catches some of this (all three false-city-name
  extractions were below the 0.9 threshold and got reviewed out), but
  it's a real precision problem in the extraction prompt or schema, not
  just a confidence-calibration problem - see `docs/evals.md`'s locations
  F1 (the weakest field) for the aggregate version of the same issue.
- **The review-queue-volume metric is a single snapshot, not a trend.**
  `queue.summarize()` reports current counts; comparing that against a
  trailing baseline per city over time, and flagging the drift, is M6's
  explicit scope.
