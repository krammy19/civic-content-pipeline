# Digest Style Guide

This is the standard every generated meeting digest is written to, and
the standard `checks/style_check.py` enforces automatically. It exists
because a digest is the one artifact in this pipeline a resident actually
reads without ever looking at the source minutes — if it's wrong, vague,
or quietly opinionated, nothing downstream catches that. Everything below
is a rule a digest can actually fail, not a statement of good intentions.

If a rule here and a rule in `docs/evals.md` or `docs/review.md` ever
conflict, this document governs digest text specifically; the others
govern extraction and review.

## Who this is for

A resident who did not attend the meeting, has three minutes, and wants
to know two things: what the city actually decided, and whether anything
in it affects them. They are not a city-hall regular. They do not know
what a "consent calendar" is until the digest tells them. They are not
looking for a take.

## Voice and register

Write like a competent city reporter on a wire desk, not like a press
release and not like a court transcript.

- **Plain language over institutional language.** "The Council approved
  a $250,000 increase to a consulting contract" beats "Council action
  was taken to authorize an amendment increasing compensation under the
  existing agreement." If a sentence needs the phrase "actions related
  to," rewrite it around the actual action.
- **Active voice, named actor.** "The Council voted 9-2 to adopt the
  ordinance" — not "the ordinance was adopted." A digest that hides who
  did something is halfway to hiding what they did.
- **Precise, not padded.** Every sentence should be doing work. Cut
  throat-clearing ("It should be noted that," "Notably,") and cut
  restatement ("In other words,"). If a sentence can lose ten words
  without losing meaning, it should.
- **Neutral, not clinical.** Neutral means not taking a side on whether a
  decision was good. It does not mean flattening a $12 million contract
  award and a proclamation into the same tone. Scale and stakes can show
  up in what gets explained, not in adjectives.
- **No direct address, no rhetorical questions, no exclamation points.**
  This is a record, not a newsletter. "Here's what you need to know!"
  and "So what does this mean for you?" are both banned in practice by
  the construction rules below, but the underlying principle is: the
  reader is being informed, not sold to.

## Required structure

A digest has, in this order, only the sections a given meeting actually
has content for:

1. **Header.** Body name, meeting date, and (if the source record has
   one) a link or citation to the source minutes/agenda. No summary text
   in the header itself.
2. **Overview.** Two to four sentences stating the scope of the meeting
   in plain terms — how many items, and a bare-facts pointer to what
   mattered most (the largest dollar figure, the only non-unanimous
   vote, the one public hearing). This is a table of contents in prose
   form, not a verdict. It does not contain opinion words (see Banned
   constructions) and it does not contain any claim that isn't repeated,
   cited, in a body section below.
3. **Body sections, in this fixed order, each present only if the
   meeting had at least one item of that type:**
   - Ceremonial Items
   - Consent Calendar
   - Public Hearings
   - Other Actions
   - Reports
   Fixed order matters more than it looks like it should: a resident
   skimming ten digests over ten weeks should be able to jump to
   "Public Hearings" without re-learning the layout each time.
4. **Notable Votes and Financial Actions.** A compact recap of every
   motion that did not pass unanimously and every dollar figure over
   $100,000, each still carrying its item-number citation. This section
   exists because the body sections walk through items in the order
   the agenda presented them, which is not the order of what a reader
   would call important. Omit this section entirely if the meeting had
   no split votes and no amount over that threshold — an empty section
   with "None" in it is worse than no section.
5. **Closing line.** One sentence, purely mechanical: where to find the
   full agenda and minutes. Never a summary judgment, never "stay tuned,"
   never anything that implies the digest is the last word.

Closed-session items are never described in a digest, in any section,
beyond noting a closed session occurred if the agenda says so — the
substance of closed session is not public record and this pipeline has
no business inferring it.

## Every factual claim cites its item number

This is the single rule the deterministic checker enforces most
aggressively, because it is the rule that makes the rest of this
document auditable. A claim is anything that could be wrong: a vote
result, a dollar amount, a name attached to an action, a decision, a
date, an outcome. Every one of them ends with a citation in the form
`(Item 2.8)`.

**Correct:**

> The Council approved a $250,000 increase to the city's consulting
> contract with CSG Advisors, raising the total to $1,000,000 (Item 2.8).

**Incorrect — claim with no citation:**

> The Council approved a $250,000 increase to the city's consulting
> contract with CSG Advisors.

**Incorrect — citation present but claim is broader than the source:**

> The Council significantly increased spending on outside consultants
> (Item 2.8).

The second example fails because "significantly increased spending on
outside consultants" is a characterization the source item doesn't
support — it describes one contract, not a spending pattern. A citation
does not license a broader claim than the cited item actually makes;
see Expressing uncertainty below.

A sentence with more than one claim needs a citation for each claim it
introduces, not just the last one. Two short cited sentences beat one
long sentence with a citation bolted onto the end.

## Expressing uncertainty

The digest is generated from **validated extractions only** — facts that
survived provenance verification and cleared their confidence threshold
(see `docs/evals.md` and `docs/review.md`). A digest never states
something the underlying extraction didn't actually assert, and never
upgrades a soft fact into a hard one.

- If an item's motion outcome is `continued`, `tabled`, or `no_action`,
  say so plainly: "The Council continued this item to a future meeting
  (Item 2.10)." Do not omit an item just because nothing was decided —
  "nothing was decided" is itself the fact worth reporting.
- If a fact was withheld pending human review (see `docs/review.md`) and
  never made it into the validated set, the digest simply doesn't
  mention it. Do not write around a gap with a hedge like "it appears"
  or "reportedly" — a digest has no business guessing at something the
  extraction layer wasn't confident enough to assert outright.
- Never infer motive, intent, or reasoning that isn't itself a cited
  fact. "The Council increased the contingency to cover likely cost
  overruns" is an inference unless the source item actually says that
  was the reason; if it does, cite it. If it doesn't, write what
  happened, not why: "The Council approved a 10% contingency of
  $1,167,800 (Item 6.1)."

## Banned constructions

Flagged automatically by the deterministic checker; each exists because
it's a specific way institutional or editorial language creeps in.

- **Passive voice that hides the actor.** "It was decided," "the motion
  was approved," "action was taken to." Name who did it: the Council,
  the Planning Commission, a named committee.
- **Value-judgment adjectives applied to outcomes or actions**:
  "historic," "landmark," "controversial," "disappointing," "welcome,"
  "long-overdue," "much-needed," "concerning." These smuggle in an
  opinion about whether a decision was good, rare, or right. If an
  outcome really is procedurally unusual (a veto override, a rare
  unanimous reversal), state the mechanism, not the adjective: "the
  Council overturned its April decision by a 7-4 vote" rather than "in a
  surprising reversal."
- **Hedge phrases that imply unconfirmed information**: "reportedly,"
  "it seems," "apparently," "sources suggest." A digest built from
  validated extractions has no unconfirmed information in the first
  place — anything not confirmed doesn't get written.
- **Throat-clearing and filler**: "It should be noted that," "It is
  worth mentioning," "Interestingly," "Notably," "Of course."
- **Direct address and rhetorical questions**: "you," "your
  neighborhood," "So what does this mean?" A digest states facts to an
  unaddressed reader.
- **Exclamation points**, anywhere, for any reason.
- **Speculation about motive or future intent** not itself a cited fact:
  "in an apparent effort to," "likely aiming to," "paving the way for."

## Political-outcome editorializing

This is the rule the LLM-judge tier of the style checker exists
specifically to catch, because it's the hardest one to enforce with
pattern matching. The line is: **describe what happened and how it
happened; never characterize whether it was right, whether it will work,
or who "won."**

**Not allowed:**

> The Council's decision to raise the parcel tax is a blow to homeowners
> already stretched thin by rising costs (Item 2.7).

**Allowed:**

> The Council raised the Library Parcel Tax rate by 2.48% for Fiscal
> Year 2026-2027 (Item 2.7).

The banned version isn't wrong about the tax going up — it's wrong
because "a blow to homeowners" is a value judgment the digest has no
standing to make, and it implies a stance on the policy in the passive
guise of describing an impact. If a decision has a genuine, source-cited
fiscal or scope impact worth stating (a rate change, a headcount, a
service level), state the number. Do not characterize what the number
*means* for anyone.

This also covers close or split votes. Report the tally as a fact
(Item X.X, 7-4) without narrating it as a fight, a rebuke, a mandate, or
a win for any named party, councilmember, or faction. "The Council
approved the item 7-4" is complete. "The Council narrowly approved the
item over the objections of Councilmember X" adds a frame the tally
alone doesn't support unless the objection itself is a separately cited
fact (a recorded no vote is not evidence of "objection" beyond the vote
itself).

## Names and titles

- **First reference in the digest**: full name and role exactly as the
  extraction recorded it — "Councilmember Rosemary Kamei," "Mayor Matt
  Mahan," "Planning Commissioner [Name]." The role comes from the
  extracted `Person.role`, not from guessing.
- **Every subsequent reference in the same digest**: surname only —
  "Kamei" — with one exception: **the Mayor is referred to as "Mayor
  [Surname]" on every reference**, not just the first, since the title
  itself is load-bearing information about who holds the meeting's
  presiding role.
- Never use a bare first name, and never invent a title the extraction
  didn't provide — if `role` is `"unknown"`, use the raw name as
  extracted without inventing "Councilmember" or any other title.
- A person quoted or named only as part of public comment (role
  `"public"`) is introduced by name alone, with their affiliation if the
  source recorded one (e.g., "resident Jane Doe" or "Jane Doe, speaking
  on behalf of [organization]") — never with a governmental title they
  don't hold.

## A worked example

**Source facts (Item 2.8, validated extraction):**
motion outcome `passed`, tally `11-0-0`; amount `$250,000` (kind
`contract`) and `$1,000,000` (kind `contract`); person Rosemary Kamei,
role `councilmember`, as seconder.

**Correctly styled:**

> The Council unanimously approved a $250,000 increase to the city's
> consulting agreement with CSG Advisors Incorporated, raising the
> contract's maximum value to $1,000,000 for housing finance and policy
> consulting services (Item 2.8).

**Incorrectly styled, and why:**

> In a move welcomed by housing advocates, the Council voted to
> significantly boost funding for its consulting partner, a decision
> that reflects the city's ongoing commitment to housing policy (Item
> 2.8).

This version fails on at least four separate rules: "welcomed by housing
advocates" and "reflects the city's ongoing commitment" are
uncited editorializing about motive and reception; "significantly boost"
replaces a precise, citable dollar figure with a vague intensifier; and
the passing mention of "housing advocates" implies a source (public
reaction) that was never itself extracted or cited.

## What this document does not cover

Deterministic sentence/paragraph length ceilings and the reading-level
target are enforced by `checks/style_check.py` with specific numeric
thresholds rather than prose guidance — see
[`docs/style-checking.md`](style-checking.md) for the exact numbers and
why they were chosen. This document is the *why*; that one is the
*how it's measured*.
