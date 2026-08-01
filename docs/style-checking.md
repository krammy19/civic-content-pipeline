# Style checker: methodology and results

`checks/style_check.py` is scored the same way `extraction/agenda_item.py`
is in [`docs/evals.md`](evals.md): a hand-labeled set of cases with known
answers, precision/recall computed against those labels, and a committed
baseline CI gates against. A style checker nobody has measured is a style
checker nobody should trust — this document is the measurement, and an
honest read of what it actually found.

## What gets measured, and against what

`checks/style_check.py` has two tiers (see
[`docs/architecture.md`](architecture.md) for how they fit into the
pipeline; see [`docs/style-guide.md`](style-guide.md) for the rules
themselves):

- **Deterministic** (`check_deterministic()`): required structure,
  citation presence and validity, banned constructions, sentence/
  paragraph length ceilings, reading level, and first-reference titles.
  Pure pattern matching — no model call, no network.
- **LLM judge** (`judge_style()`): forced tool use against a digest and
  the validated facts it was built from, checking three things pattern
  matching structurally cannot: voice/register conformance, unsupported
  claims, and political-outcome editorializing.

Both tiers return the same `Finding(rule, severity, message, excerpt)`
shape, so `evals/run_style_eval.py` scores them identically: for every
case in `evals/style_cases/*.json`, it runs both tiers, collects the set
of rule names that fired, and compares that set against the case's
labeled `expected_findings`.

## Matching: how "the checker got it right" is decided

A case is scored by **which rules fired, not how many times**.
`evals/style_metrics.py`'s `score_case()` treats `expected_findings` and
the actual set of fired rule names as sets: a rule in both is a true
positive, a rule only in the actual set is a false positive, a rule only
in `expected_findings` is a false negative. Precision, recall, and F1 are
then pooled per rule across every case (not averaged per case — the same
convention `evals/metrics.py` uses), plus one overall number across every
rule combined.

Exact-count matching was deliberately rejected. "This digest has a
banned construction" is a label this hand-built set can support
honestly; "this digest has exactly one banned construction, located at
this exact span" is not, once a real checker might reasonably report two
adjacent problems in the same sentence as two findings instead of one.
Set-membership per rule name is the honest granularity for a
hand-labeled set this size.

## The style_cases set

`scripts/build_style_cases.py` builds 20 cases into `evals/style_cases/`,
in two groups:

- **Deterministic-isolated cases** (16): each digest is built to trip
  exactly one deterministic rule and nothing else — checked, while
  writing it, against every other rule so a case doesn't accidentally
  earn a second, unlabeled violation. Two are clean baselines
  (`clean-ceremonial`, `clean-consent`) with zero expected findings at
  all — a checker that fires on clean input is exactly as broken as one
  that misses a real violation, and an eval set with no clean cases
  can't tell you that.
- **Judge-only cases** (4, plus one hard case): each digest is
  deterministically clean by construction, isolating the judge's own
  behavior. The last one, `wrong-item-citation`, is the reason this
  checker has two tiers at all: it cites a real, existing item number,
  just the wrong one — the fact attached to it belongs to a different
  item. The deterministic `unknown_citation` check has nothing to flag,
  because the citation isn't to a nonexistent item, it's to the wrong
  real one. Only a judge that can see the per-item facts, not just a set
  of valid item numbers, can catch this.

Every case's `facts_block` is meant to be the complete, honest ground
truth for its digest — see "Two real bugs" below for what happened the
first time that wasn't actually true.

## Deterministic thresholds, precisely

- **Sentence ceiling**: 40 words. **Paragraph ceiling**: 150 words.
  Round numbers chosen to catch genuinely sprawling sentences/paragraphs
  without nitpicking ordinary compound sentences — not derived from a
  corpus study of real digests, because none existed yet when this was
  built.
- **Reading level**: Flesch-Kincaid grade level, target ceiling **12.0**.
  Computed with a vowel-cluster syllable-counting heuristic
  (`flesch_kincaid_grade()`), not a dictionary lookup — accurate enough
  to flag real jargon-heavy prose, not precise to the decimal. Municipal
  writing (ordinance numbers, legal citations, department names) is
  inherently denser than casual prose; 12.0 is a real ceiling that real
  civic digests will sometimes brush up against, which is the honest
  cost of writing for a general audience about specialized government
  process.
- **First-reference titles**: only checked for `role in {"mayor",
  "councilmember"}` — the two roles with one unambiguous, schema-known
  title word. `"staff"` covers real job titles (City Manager, Chief of
  Police, Housing Director) the schema doesn't capture beyond
  `role="staff"`, so there's no single correct title string to check
  for. This is a real, scoped-out gap, not an oversight: extending it
  would mean extending `Person` to capture an actual job title, which is
  outside what M2's extraction schema was built to do.

## First real run: two bugs, and an honest read of the rest

The first real run against the live API did not go well, and that was
useful. Overall precision came back at **0.360** — the judge tier was
firing on cases that were supposed to be clean. Two real bugs were
behind most of it, both in the eval fixtures, not the checker:

**Bug 1: facts_block didn't ground everything the digest claimed.**
`clean-consent`'s digest said "The Council raised its deal with CSG
Advisors... Councilmember Rosemary Kamei backed the motion" — but its
`facts_block` never mentioned CSG Advisors by name, and never recorded
that the motion actually passed. The judge was *right* to call these
unsupported: from what it was given, a reader has no way to know the
vendor's name or whether the motion succeeded. Fixed by making every
fully-grounded case's `facts_block` state literally everything its
digest asserts — vendor names, motion outcomes, seconders — not just the
figures. This is the same category of finding as M3's gold-annotation
gaps: the harness looked broken because the *labels* were incomplete,
not because the thing under test was wrong.

**Bug 2: ambiguous attribution in hand-written prose.**
`missing-first-reference-title`'s original sentence — "Kamei seconded
the motion to raise the contract by $250,000" — reads, on a careful
parse, as attributing the raise itself to the seconding, which the
underlying facts don't actually support (seconding a motion isn't the
same as it passing). Fixed by splitting the claim into an unambiguous
sentence: "The Council approved a $250,000 increase..., seconded by
Kamei." Small phrasing choices that seem harmless in isolation can read
as a stronger claim than intended — exactly the kind of thing a careful
judge should catch, and exactly why writing genuinely isolated test
cases is harder than it looks.

After both fixes, the **deterministic tier is perfect**: every one of
its eleven rules scores precision 1.0, recall 1.0 on this set. That's
expected and not very impressive on its own — it's pattern matching
against hand-written triggers built to match those exact patterns. The
real signal is what's left.

**The judge tier has perfect recall and weak precision, even after both
fixes**: `editorializing` 0.20, `unsupported_claim` 0.17, `voice_register`
0.10 — all at recall 1.0 (it never missed a planted violation), overall
F1 **0.576**. Investigating the remaining false positives (see
`evals/results/style_latest.json` for the raw findings) turned up a
genuine, reportable pattern rather than a third bug to fix:

- The judge frequently flags **more than the one problem a case was
  built to isolate**. `sentence-too-long`'s deliberately padded sentence
  ("The Council took a long time... to talk about many small parts of
  the plan...") was written to hit the 40-word ceiling using only simple
  vocabulary, so it wouldn't also trip the reading-level check — but
  that same padding is real vague, unsupported filler by the judge's
  own three-category rubric, and it correctly says so. The fixture
  needed one violation; the digest actually has two, honestly.
- The judge sometimes **labels a real finding under an unexpected
  category**. On `section-order`, it correctly noticed the section
  order was wrong but reported it as a `voice_register` finding instead
  of describing a structural problem — the underlying observation was
  right, the label didn't match what a human would file it under.
- On `unknown-citation`, the judge treats "cites a real fact, but to an
  item number that doesn't exist" as an unsupported claim — which is
  defensible on its own terms, and is why that case's
  `expected_findings` explicitly lists both `unknown_citation` and
  `unsupported_claim` rather than treating the overlap as an error.

None of this makes the judge tier broken. **A style-quality gate that
never misses a real violation but occasionally over-flags is the safer
failure mode**: an extra finding costs a human a few seconds of review;
a missed one publishes an unsupported claim. But it does mean these
precision numbers should be read as *"the judge is stricter than a
one-violation-per-fixture label can capture,"* not as *"the judge is
unreliable."* Reporting 0.10 precision on `voice_register` without this
context would be a worse kind of dishonesty than not measuring it at
all — SPEC's own standard here (report scores honestly, including where
they're worse) cuts both ways: the raw number and the reason behind it
both matter.

## A third bug, found by real generated text the hand-built cases never hit

The 20 `style_cases` are hand-written prose, and hand-written prose
doesn't naturally produce the one thing real LLM-generated digests are
full of: abbreviations. `scripts/check_sample_digest.py` runs the whole
pipeline end to end — extract the real June 9, 2026 San José agenda
items from M4, route them through confidence thresholds, generate a real
digest, check it — and the first real digest it generated came back with
**eight high-severity `missing_citation` findings** on sentences that
plainly had a citation in them.

The cause: `_split_sentences()`'s sentence-boundary regex treated the
period in "Ordinance No. 31328" and "Blocka Construction Inc." as the
end of a sentence, severing the actual claim from the "(Item X.X)"
citation that appeared later in the same real sentence. Every one of the
eight false positives was one of these abbreviation splits. Fixed with a
set of negative lookbehinds for the common abbreviations municipal
writing is full of (`No.`, `Inc.`, `St.`, `Mr.`, `Dr.`, and similar) —
see `checks/style_check.py`'s `_ABBREVIATIONS`. Regression tests for both
the fixing case and a second abbreviation are in
`tests/checks/test_style_check.py`.

This is the same lesson as `docs/evals.md`'s and `docs/review.md`'s own
"found by real data, not by hand-written tests" stories, in a new
place: 20 carefully isolated cases proved every *rule* works; only a
real generated digest proved the sentence *tokenizer* underneath all of
them didn't handle real prose. A second, smaller finding from the same
run: the model put citations in the "Notable Votes and Financial
Actions" section as a leading `"Item X.X:"` label instead of the
required `(Item X.X)` parenthetical — a real prompt gap, not a checker
bug, fixed by making `prompts/generate_digest.v1.md` state explicitly
that the citation format is the same everywhere in the digest, including
that section.

After both fixes, the same real digest came back with **zero
high-severity findings** — six low/medium findings remained (a stray
`## Closing line` heading, two long sentences, a high reading-level
score, and two legitimate, minor judge nitpicks), which is the correct
outcome: a style gate that reports zero findings on real generated text
would be far more suspicious than one that reports a few low-severity
ones.

**The planted-violation proof.** Splicing one deliberately bad sentence
into that same clean, real digest — *"In a historic win for residents,
the Council approved a massive spending increase!"* — and re-running
both tiers produced **4 new high-severity findings** across three
different rules: `missing_citation` (no item number at all),
`editorializing` ("historic win... not supported by any cited fact"),
and `unsupported_claim` (generalizing the whole consent calendar as "a
massive spending increase"). Zero high-severity findings before, four
after, from one spliced-in sentence — this is the concrete version of
the M5 acceptance criterion: a digest with a planted violation is
caught, not sometimes, not eventually, but on the very sentence that
carries it.

## Known limitations and what a v2 harness should fix

- **Single-label-per-case doesn't fit a judge that reports multiple real
  angles on the same text.** A v2 version of this set would label
  digests with the *complete* set of defensible findings a careful human
  reviewer would file, not just the one violation the case was built to
  isolate — which would very likely raise the measured precision without
  the judge's actual behavior changing at all.
- **Twenty cases is enough to catch a broken rule, not enough to trust a
  precise precision number.** A single false positive on a rule with one
  true positive moves that rule's precision by 33+ points. The
  deterministic tier's perfect scores are more a statement about
  pattern-matching being deterministic than about the rules being
  well-calibrated against real digest variety.
- **The judge's category boundaries aren't perfectly crisp**
  (`section-order`'s finding landing under `voice_register` above). A v2
  scorer might credit a judge finding against *any* semantically
  matching expected rule rather than requiring an exact category match -
  at the cost of making the eval itself more subjective.
- **No real generated digest has been scored yet in this set** - every
  case here is hand-written specifically to isolate a rule. See
  `docs/review.md`'s precedent (the M4 review session used real,
  never-before-seen extraction output) for what a v2 pass should do:
  generate real digests from real validated extractions and add the
  genuine violations found there, the way M4's flywheel added real gold
  cases from real model output.

## How to add a style case

1. Write a `digest_markdown` and a `facts_block` that together are
   internally consistent — every claim the digest makes must be true
   given the facts, except the one deliberate gap a judge-tier case
   exists to test.
2. Run `check_deterministic()` on it by hand and confirm the rule set it
   returns matches your intended `expected_findings` before adding any
   judge-tier expectations - see `scripts/build_style_cases.py`'s
   docstring for the exact verification loop used to build this set.
3. Add the case via `scripts/build_style_cases.py`'s `case()` helper, not
   by hand-editing a JSON file directly - it's the record of how every
   case was built and why.
4. Run `uv run python evals/run_style_eval.py` and read the actual
   findings for your new case before assuming your `expected_findings`
   is right. As this document's own "two bugs" section shows, the
   fixture is at least as likely to be wrong as the checker.
