# Evals

This is the component the rest of the project's claims rest on. Anyone
can write a prompt that produces plausible-looking JSON; the question
that actually matters is whether the extractions are *right*, how often
they're not, and — the harder question — whether the model's own stated
confidence can be trusted to tell you which is which. This document
covers the methodology, how to extend it, and an honest read of the
first real run's results, including where the model is overconfident.

## What gets measured, and against what

`evals/run_eval.py` runs `extraction.agenda_item.extract_agenda_item_raw()`
against every hand-annotated case in `evals/gold/`, scores the result
with the pure functions in `evals/metrics.py`, and prints a scorecard.
Two different outputs from the same call get scored against different
things, on purpose:

- **Precision / recall / F1** are computed against the **filtered**
  output — what `extract_agenda_item()` actually returns to a caller,
  after `drop_unverified()` has already removed anything whose
  provenance didn't check out. This is "how good is the system," not
  "how good is the model before its own safety net runs."
- **Hallucination rate** and **calibration** are computed against the
  **raw**, pre-filter output — what the model actually said before
  anything got removed. Scoring hallucination rate on the filtered
  output would read 0% by construction, since filtering exists
  specifically to remove exactly those cases. Measuring it requires
  seeing what didn't survive.

Per field type (motions, people, locations, amounts), the scorecard
reports:

- **Precision, recall, F1** — pooled true/false positives/negatives
  across the whole gold set, not averaged per case. A case with ten
  gold facts and a case with one don't get equal weight in the result;
  the ten-fact case's mistakes count ten times as much, which is the
  correct behavior for "how good is the system overall."
- **Hallucination rate** — the fraction of raw extractions whose
  `provenance.source_text` doesn't actually appear in the source
  document. This is the one metric in the suite that isn't a judgment
  call: it's a plain substring check (`evals.metrics.is_verified()`,
  which mirrors `verify_provenance()` in production code), and it's
  the same check that drives `drop_unverified()` in the real pipeline.
- **Schema validity rate** — the fraction of calls where Claude's
  tool-use output actually validated against `AgendaItem` at all. With
  forced tool use this should be at or near 100%; if it isn't, that's
  a signal something is wrong with the tool schema or the model
  choice, not with any individual extraction.
- **Mean confidence** and **calibration** — see below.

## Matching: how "the model got it right" is decided

There's no ground truth for "these two JSON blobs mean the same thing"
that doesn't involve some judgment call, so here's exactly what
`evals/metrics.py` does, and where it's weaker than it should be:

- **Motions** match on `outcome` (exact) plus either an exact-after-
  normalization `tally` match or text similarity above 0.5
  ([`difflib.SequenceMatcher`](https://docs.python.org/3/library/difflib.html),
  not embeddings — deliberately simple and inspectable). It does **not**
  check `moved_by`/`seconded_by` identity. A model that gets the right
  outcome with the wrong mover would still count as a match today —
  a real gap, not an oversight; fixing it means teaching the motion
  matcher to call the person matcher recursively on two optional
  nested fields, which didn't make the cut for this pass.
- **People** match on `raw_name` similarity above 0.8, with known
  titles (`mayor`, `councilmember`, `director`, etc.) stripped from
  both sides before comparing — added after the first real run showed
  why: the model extracts "Mayor Mahan" as one unit when a sentence
  lists titled names in a series ("co-authored by Mayor Mahan,
  Councilmember Tordillos, ...") but extracts a bare surname when the
  title and name are used more conversationally ("Vice Mayor Pam Foley
  motioned..."). Both are defensible readings of "exactly as written";
  the matcher normalizes the difference away instead of asking gold to
  guess which form a given sentence will produce.
- **Locations** match on `raw_text` similarity above 0.5 alone. This is
  the weakest matcher in the suite — see [Known limitations](#known-limitations-and-what-a-v2-harness-should-fix).
- **Amounts** match on parsed `amount_usd` equality when both sides
  have one; text similarity is only a fallback when a numeric value is
  missing on either side. This was a real bug in the first draft: text
  similarity alone judged `"$1,000,000"` and `"$2,000,000"` as a match,
  because the two strings share every character except one digit. A
  unit test written before ever touching the live API caught it.

## The gold set

38 hand-annotated cases in `evals/gold/`, one JSON file per agenda
item — short of the 40–50 originally targeted, and that's stated
plainly rather than padded to a round number with easy filler cases.
37 are excerpted verbatim from real San José City Council and Planning
Commission minutes fetched during the M1 live-validation pass
(`data/raw/san-jose/`); one (`sj-cc-synthetic-amount-in-words`) is
explicitly synthetic and labeled as such, built because no real
document in this corpus happened to spell a dollar amount out in words
and that's an explicit target case below. `scripts/build_gold_set.py`
is the full record of how every case was built, string quotes and all.

Every gold case carries `document_text` (the real excerpt) and
`expected` (motions/people/locations/amounts determined by reading that
excerpt directly, not by running the model and eyeballing the result).
A validation pass confirms every `source_text` value gold claims is a
verbatim substring of its own `document_text` — the same standard
`verify_provenance()` holds the model to.

Deliberate hard cases, because an eval set of only easy cases proves
nothing:

- **A continued item with no vote at all**
  (`sj-cc-2025-12-09-2.15`, re-appearing deferred a second time as
  `sj-cc-2025-12-16-2.28`) — administratively deferred before any
  motion was made, `motions` must be `[]`, not a fabricated "continued"
  motion with no real mover to cite. Contrasted with
  `sj-cc-2025-12-09-10.1a`, where a deferral **is** a real voted motion
  — the two should not be scored identically.
- **A consent calendar passed in bulk**
  (`sj-cc-2025-12-09-2.4`, `sj-pc-2025-12-10-4`) — the only real motion
  in the text covers the whole calendar, not the individual item; the
  extraction has to attribute the shared motion rather than inventing
  a per-item one.
- **A name with no roster match** — not a special case at all, since
  roster resolution (`canonical_name`) doesn't exist yet; every person
  in every case is annotated with `canonical_name: null`. What *did*
  turn out to need a real decision: Planning Commissioners have no
  matching `Person.role` value in the current schema (not mayor,
  councilmember, staff, applicant, or public) — annotated `unknown`
  throughout `sj-pc-*`, and flagged here as a real schema gap this
  hand-annotation pass surfaced, not something to route around quietly.
- **A dollar amount written in words** — synthetic, as noted above.
- **An item with three-plus motions** — `sj-pc-2025-12-10-5a-cisco`,
  `-apple`, and `-google` are three sub-motions of the same public
  hearing item (each with its own mover, seconder, and recusal
  pattern), split into separate gold files since each has independent
  ground truth. One of the three (`-google`) has a 6-1-0-4 tally with
  four commissioners recused — annotated `passed` since a simple
  majority of votes cast is what the source text supports, flagged in
  its own `notes` field as a genuine judgment call a real annotator (or
  a model) could reasonably land on differently.
- **Non-unanimous and multi-part vote tallies** —
  `sj-cc-2025-12-09-6.1` (`10-0-1; Absent: Ortiz`),
  `sj-pc-2025-12-10-4` (`8-0-2-1`, an absence and an abstention in the
  same tally).
- **Organizations that must not be extracted as people** — franchise
  applicants and contractors (Compactor Management Company, VNH
  Builders, Gillig LLC) appear throughout; none should show up in
  `people`.

## Calibration: how it's computed and how to read it

Every raw extraction is placed into a confidence bucket
(`evals.metrics.CALIBRATION_BUCKETS`: `[0, 0.5)`, `[0.5, 0.7)`,
`[0.7, 0.85)`, `[0.85, 0.95)`, `[0.95, 1.0]`) and marked correct only if
it's **both** verified (real provenance) **and** matched to a real gold
fact — a verified-but-wrong extraction (the right kind of fact, citing
real text, about the wrong person) counts against calibration exactly
like a fabrication does, because both mean the stated confidence didn't
predict correctness.

For each bucket, the scorecard reports the bucket's mean stated
confidence against its actual accuracy (fraction correct). A
well-calibrated 0.6 should be right about 60% of the time. The
**Expected Calibration Error (ECE)** is the count-weighted mean absolute
gap between confidence and accuracy across all five buckets — 0.0 is
perfect, higher means confidence and correctness have drifted apart.

The scorecard below reports this in aggregate, across every field type
pooled together — that was the only view available when M4's review
queue needed a threshold and no per-field breakdown existed yet.
`evals.metrics.calibration_points_by_field` now computes the same curve
broken out by field type, and `evals/derive_review_thresholds.py` turns
that into an actual per-field publish threshold; see
[`docs/review.md`](review.md#from-one-uniform-threshold-to-four-derived-ones)
for the current numbers and two honest limitations of the method.

## First real run: results and an honest read

Run against `claude-sonnet-5`, 38 gold cases, zero mocking — every
number below came from real API calls (`.cache/llm/` holds all 38
responses; a second run against the same gold set is free, and was
used twice while fixing the two bugs described below).

| Field | Precision | Recall | F1 |
|---|---|---|---|
| Motions | 0.825 | 0.943 | **0.880** |
| People | 0.706 | 1.000 | **0.828** |
| Locations | 0.452 | 0.875 | **0.596** |
| Amounts | 0.767 | 1.000 | **0.868** |

Schema validity: **100%**. Hallucination rate: **0%** — across every
raw extraction in this run, every claimed `source_text` really was a
verbatim substring of the source document. That's a genuinely good
result and also a small sample size; it should not be read as "this
model doesn't hallucinate," only as "it didn't in these 38 cases."

**Recall is strong across the board (0.87–1.00); precision is the
problem, concentrated in locations and, before a fix, in people too.**
Two rounds of hand-inspecting false positives during this run found two
distinct, genuinely different causes:

1. **A real bug in the matcher, now fixed.** People precision started
   at 0.529 (F1 0.635). Inspecting the false positives showed the model
   correctly extracting people the gold annotation had simply missed —
   e.g. a joint memorandum naming five co-authors where the first gold
   pass had only captured one, because the model rendered four of them
   as `"Mayor Mahan"`/`"Councilmember Tordillos"` (title fused to the
   name) against gold's bare surnames, and the 0.8 similarity threshold
   didn't bridge the gap. Stripping known titles before comparing (see
   [Matching](#matching-how-the-model-got-it-right-is-decided) above)
   raised people to precision 0.706, F1 0.828, with zero cost to re-run
   since every case was already cached. This is the harness catching
   its own bug, which is the entire point of writing one.
2. **A real, unresolved matching-granularity mismatch, left as-is.**
   Locations precision (0.452) mostly reflects something the person-title
   fix doesn't touch: gold frequently combines an address and its
   Council District into one composite string
   (`"0 Suncrest Avenue, Council District 4"`), while the model treats
   each as its own `Location` entry. Both are reasonable decompositions
   of the same real information, and today's single-string similarity
   match can't reconcile them — a location split into two model entries
   scores as one false negative and two false positives instead of one
   correct match. A smaller number of these are genuine model
   over-extraction: mentions of "San José" or "City of San José" that
   are trivially true of every single item and don't carry location
   information worth flagging. This is called out here rather than
   patched, because the honest fix is a better matcher (one that can
   recombine or partially credit split entries), not more gold
   annotation chasing today's specific granularity choice.

**Calibration is the most interesting number in this suite, and the
model is overconfident.** ECE across the full run: **0.135** (down from
0.228 before the people-matcher fix — a genuine improvement, not
noise, since the same 38 cached responses were rescored both times).

| Confidence range | n | Mean stated confidence | Actual accuracy |
|---|---|---|---|
| [0.00, 0.50) | 1 | 0.400 | 0.000 |
| [0.50, 0.70) | 14 | 0.593 | 0.071 |
| [0.70, 0.85) | 24 | 0.750 | 0.208 |
| [0.85, 0.95) | 90 | 0.887 | 0.833 |
| [0.95, 1.00] | 74 | 0.956 | 0.932 |

Read plainly: in the two lowest non-trivial buckets, the model is
dramatically overconfident — extractions it scores around 0.59–0.75
confidence are right only 7–21% of the time, not the 59–75% the
number implies. The gap narrows sharply at high confidence (0.887 vs.
0.833, 0.956 vs. 0.932) but never closes. Practically, this means a
downstream confidence threshold (M4's planned review queue) **cannot
take these numbers at face value** — a naive "route anything under 0.8
to human review" rule would let through a meaningful share of wrong
extractions sitting just above that line, while correctly catching most
of what's actually bad below it. The threshold that would need
calibrating is closer to "anything under 0.9," based on this run, and
that threshold itself should be re-checked every time the gold set or
prompt changes materially — a single run's calibration curve is a
snapshot, not a constant.

## Known limitations and what a v2 harness should fix

Stated plainly, matching the project's own standard for itself:

- **38 cases, not 40–50.** Reported honestly above rather than padded.
- **Motion matching doesn't check mover/seconder identity.** A model
  could get an item's outcome right while attributing it to the wrong
  councilmember and this suite would not catch it.
- **Location matching can't reconcile different decomposition choices**
  between gold and the model, as discussed above — the largest concrete
  gap in this run's numbers.
- **Calibration and hallucination rate are measured on 38 cases'
  worth of raw extractions (203 across all fields).** The five-bucket
  calibration table has as few as 1 point in its lowest bucket — real
  signal in the two largest buckets (90 and 74 points), thin at the
  edges. Don't over-read the `[0.00, 0.50)` row specifically.
- **One real gold-annotation methodology gap, found and partially
  fixed live:** the first annotation pass wasn't exhaustive about every
  person/location mentioned in a case, only the ones that felt salient
  while reading. Two concrete instances were found and corrected
  (`sj-cc-2025-12-09-8.1`, `sj-cc-2025-12-09-3.6`) by comparing real
  model output against gold and fixing gold where the model was
  actually right. The remaining 30 people-field and 17 location-field
  false positives in the current run have not all been individually
  audited this way — some are likely further gaps of the same kind,
  some are likely genuine model over-extraction. Distinguishing the two
  for every remaining false positive is the most valuable next unit of
  work on this harness, ahead of adding more gold cases.

## A second platform: Alhambra, CA (CivicPlus)

Every result above is San José, one city on one platform. SPEC's M7 and
the generalization question it's meant to answer — does this pipeline
work anywhere, or does it only work on the one city it was tuned
against — needed a second, structurally different source. Alhambra runs
CivicPlus's AgendaCenter, not Legistar: different HTML entirely
(`connectors/civicplus.py`, tested in
`tests/connectors/test_civicplus.py`), different PDF minutes layout,
different city, different council.

**15 real gold cases** (`evals/gold_civicplus/`, built by
`scripts/build_gold_set_civicplus.py`), hand-annotated from two real
regular City Council meetings fetched live via `CivicPlusConnector` +
`document_text.fetch_and_extract()` during this session — February 9
and February 23, 2026. Scored **separately** from San José's gold set,
never pooled: `uv run python evals/run_eval.py --gold-dir
evals/gold_civicplus` writes its own `evals/baseline_civicplus.json`,
compared only against itself on later runs (`baseline_path_for()` maps
each `gold_<name>/` directory to its own baseline file specifically so
this never gets silently diffed against San José's numbers as if it
were the same suite regressing).

**The prompt was not touched to close any gap found here.** That's not
an oversight; it's the actual point of building a second gold set — a
prompt tuned until it also scores well on Alhambra would no longer be
testing whether the original approach generalizes, only whether it can
be made to pass a second exam it's seen the answers to.

| Field | Precision | Recall | F1 | vs. San José F1 |
|---|---|---|---|---|
| Motions | 0.929 | 0.867 | **0.897** | 0.868 (+0.029) |
| People | 0.377 | 0.935 | **0.537** | 0.815 (−0.278) |
| Locations | 0.583 | 1.000 | **0.737** | 0.696 (+0.041) |
| Amounts | 0.455 | 0.909 | **0.606** | 0.868 (−0.262) |

Schema validity: **93.3%** (14/15 — one real schema failure, below).
Hallucination rate: **0%**. Calibration: **ECE 0.323**, roughly 2.5x
worse than San José's 0.126 — Alhambra's confidence numbers track
correctness far less reliably.

**Two fields got worse, two got (slightly) better — the honest read is
narrower than "CivicPlus is worse."** Motions and locations held up or
improved. People and amounts collapsed, and both collapses were traced
to a real, verified cause, not left as a guess:

1. **People: the model extracts every named vote-caster, not just the
   mover and seconder.** Alhambra's minutes name the full five-member
   roll call on *every single item* (`Ayes: MAZA, ANDRADE-STADLER, LEE,
   WANG, MALONEY`), not just a tally like San José's `(11-0-0)`. Pulling
   raw extraction for one real case confirmed it directly: the model
   returned `ANDRADE-STADLER` and `MAZA` (correctly, as mover/seconder)
   *and* `LEE`, `WANG`, `MALONEY` (from the Ayes list) as four
   additional `people` facts — all five real, all verified, none
   hallucinated. Gold only credits mover/seconder as meaningful
   `people` facts, mirroring the convention San José's gold set already
   uses. That convention was never tested against a document that names
   every voter every time; Alhambra is the first one that does, and 48
   of the field's 77 raw extractions are exactly this pattern. This is
   an annotation-convention question the eval never had to answer
   before ("does every named roll-call vote count as a person fact?"),
   not a hallucination and not a prompt bug.
2. **Amounts: the model extracts background dollar figures, not just
   the one actually acted on.** Alhambra's minutes narrate the bidding
   process before stating the award (`bids ranged from $444,760.00 to
   ... $726,250`), and pulling raw extraction for a real contract-award
   case confirmed the model extracts the losing high bid
   (`$726,250`, confidence 0.85) as its own `amounts` fact alongside the
   actually-awarded `$444,760.00`. San José's minutes rarely narrate a
   multi-bid process inline this way, so this over-extraction mode had
   little material to trigger on there. Predicted in this gold set's
   own annotation notes (items `alhambra-cc-2026-02-23-6` and `-7`)
   before the eval was ever run, then confirmed by real model output —
   not a post-hoc excuse.

**The one schema failure is itself informative.** `alhambra-cc-2026-02-23-13`'s
raw tool call came back missing the required `title` and `item_type`
fields entirely — a real API/schema miss, not a provenance failure (it
never got that far). This case has a genuine, minor document defect of
its own (`$200,00.00`, a source PDF typo missing a digit, corrected to
`$200,000.00` in the same item's own Action Taken clause) — whether
that's related is unconfirmed, but it's exactly the kind of messier,
real-world input a second, independently-sourced platform was expected
to surface that a single well-worn gold set wouldn't.

**Locations and motions holding up is itself worth stating, not just
the fields that got worse.** Generalizing well on some fields and
poorly on others is a more credible result than either "it works
everywhere" or "it falls apart on a new platform" — the failure modes
found are specific and explained, not a uniform collapse.

## How to add a gold case

1. Find a real item in a fetched document (`data/raw/<jurisdiction>/`,
   or fetch a new one with `document_fetch.fetch_document()`).
2. Add a `case(...)` call to `scripts/build_gold_set.py` with the
   verbatim excerpt as `document_text` and your own reading of it as
   `expected` — every `source_text` you write must be a real substring
   of your own `document_text`, checked by re-running the script (it
   regenerates `evals/gold/` from scratch each time, so there's no
   drift between the generator and the committed files).
3. Prefer a case that's wrong in an interesting way over one that's
   correct in a boring way — see the hard cases above for the shape of
   "interesting."
4. Run `uv run python evals/run_eval.py` and read the new case's
   contribution before assuming it's right; a gold mistake looks
   exactly like a model mistake in the scorecard until someone checks.
5. Only run `--update-baseline` as its own commit with the score deltas
   in the message — per SPEC, updating the baseline is meant to be an
   explicit, reviewable decision, not a side effect of an unrelated
   change.
