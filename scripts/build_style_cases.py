"""
One-time generator for evals/style_cases/*.json - the labeled violation
set the style checker's own precision/recall is scored against (see
evals/run_style_eval.py and docs/style-checking.md).

Every digest here is hand-written specifically to isolate one rule at a
time: each case is checked, while writing it, against every other rule
in checks/style_check.py to make sure it doesn't accidentally trip a
second one and mislabel the case. This includes the LLM-judge rules,
not just the deterministic ones - the first real run of this set found
that several "clean" facts_block fixtures didn't actually ground every
claim in their digest (a vendor name, a seconder's role, an item count),
which the judge correctly flagged as unsupported. Every fact a digest
states here is now deliberately present in its facts_block unless a
case exists specifically to test that gap - see docs/style-checking.md
for that story in full.

A handful of cases exist specifically to show why two tiers are needed
at all - see the "hard case" at the bottom, where a citation points at
a real item number that just doesn't support the claim attached to it,
which no deterministic pattern match can catch.

Run once: `uv run python scripts/build_style_cases.py`. Re-running
overwrites evals/style_cases/ with the same content (safe, idempotent).
"""

import json
from pathlib import Path

STYLE_CASES_DIR = Path(__file__).resolve().parent.parent / "evals" / "style_cases"

CASES = []

# Fully-grounded facts for the recurring CSG Advisors contract item, used
# by every case whose digest mentions the vendor name, the amount, and/or
# Kamei seconding the motion - deliberately complete so a digest built
# from a subset of these facts never over-claims.
_CSG_FACTS = (
    "## Consent Calendar\n\nItem 2.8: Contract amendment with CSG Advisors\n"
    "  - Amount: $250,000 (contract)\n"
    "  - Motion: outcome: passed, seconded by Rosemary Kamei\n"
    "  - Person: Rosemary Kamei (councilmember)"
)

# Fully-grounded facts for the recurring Independence Day proclamation
# item.
_PROCLAMATION_FACTS = (
    "## Ceremonial Items\n\nItem 1.1: Proclamation for Independence Day\n"
    "  - Person: George Casey (councilmember) - presented the proclamation"
)


def case(id, digest_markdown, known_item_numbers, people, facts_block, expected_findings, notes):
    CASES.append(
        {
            "id": id,
            "digest_markdown": digest_markdown,
            "known_item_numbers": known_item_numbers,
            "people": people,
            "facts_block": facts_block,
            "expected_findings": expected_findings,
            "notes": notes,
        }
    )


# --------------------------------------------------------------------------
# Clean baselines - a checker that fires on clean input is as broken as one
# that misses real violations.
# --------------------------------------------------------------------------

case(
    id="clean-ceremonial",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard one item today.

## Ceremonial Items

Councilmember George Casey presented a proclamation for Independence Day (Item 1.1).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["1.1"],
    people=[{"raw_name": "George Casey", "role": "councilmember"}],
    facts_block=_PROCLAMATION_FACTS,
    expected_findings=[],
    notes="A clean, minimal ceremonial-only digest. No violations of any kind.",
)

case(
    id="clean-consent",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item, raising a contract by $250,000.

## Consent Calendar

The Council approved a $250,000 increase to its contract with CSG \
Advisors, seconded by Councilmember Rosemary Kamei (Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[{"raw_name": "Rosemary Kamei", "role": "councilmember"}],
    facts_block=_CSG_FACTS,
    expected_findings=[],
    notes="Clean consent-calendar digest with a cited amount and a correctly titled name.",
)

# --------------------------------------------------------------------------
# Deterministic tier: one isolated violation per case.
# --------------------------------------------------------------------------

case(
    id="missing-header",
    digest_markdown="""## Overview

The Council heard 1 item, raising a contract by $250,000.

## Consent Calendar

The Council approved a $250,000 increase to its contract with CSG \
Advisors, seconded by Councilmember Rosemary Kamei (Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[{"raw_name": "Rosemary Kamei", "role": "councilmember"}],
    facts_block=_CSG_FACTS,
    expected_findings=["missing_header"],
    notes="Otherwise identical to clean-consent, with the level-1 header line removed.",
)

case(
    id="missing-overview",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Consent Calendar

The Council met today. The Council approved a $250,000 increase to its \
contract with CSG Advisors, seconded by Councilmember Rosemary Kamei \
(Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[{"raw_name": "Rosemary Kamei", "role": "councilmember"}],
    facts_block=_CSG_FACTS,
    expected_findings=["missing_overview"],
    notes="No '## Overview' section at all.",
)

case(
    id="section-order",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 2 items.

## Reports

City Manager Jennifer Maguire gave a verbal update (Item 3.1).

## Ceremonial Items

Councilmember George Casey presented a proclamation for Independence Day (Item 1.1).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["1.1", "3.1"],
    people=[
        {"raw_name": "George Casey", "role": "councilmember"},
        {"raw_name": "Jennifer Maguire", "role": "staff"},
    ],
    facts_block=(
        "## Reports\n\nItem 3.1: Verbal report from City Manager Jennifer Maguire\n\n"
        + _PROCLAMATION_FACTS
    ),
    expected_findings=["section_order"],
    notes="'Reports' appears before 'Ceremonial Items', violating the required fixed order.",
)

case(
    id="unexpected-section",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Ceremonial Items

Councilmember George Casey presented a proclamation for Independence Day (Item 1.1).

## Closing Remarks

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["1.1"],
    people=[{"raw_name": "George Casey", "role": "councilmember"}],
    facts_block=_PROCLAMATION_FACTS,
    expected_findings=["unexpected_section"],
    notes="'## Closing Remarks' is not one of the style guide's recognized section headings.",
)

case(
    id="missing-citation",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

The Council approved a $250,000 increase to its contract with CSG Advisors.

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["missing_citation"],
    notes="A dollar claim with no '(Item X.X)' citation at all.",
)

case(
    id="unknown-citation",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

The Council approved a $250,000 increase to its contract with CSG Advisors (Item 9.9).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["unknown_citation", "unsupported_claim"],
    notes=(
        "Citing a nonexistent item number is caught by the deterministic "
        "check, and the judge reasonably treats a citation to a nonexistent "
        "item as an unsupported claim too - the two tiers overlap here rather "
        "than partition cleanly, which is expected, not a bug."
    ),
)

case(
    id="banned-construction-passive",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

The motion was approved to raise the CSG Advisors contract by $250,000 (Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["banned_construction"],
    notes="Passive construction that hides who took the action.",
)

case(
    id="banned-construction-adjective",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

The Council approved a historic $250,000 increase to its CSG Advisors contract (Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["banned_construction"],
    notes="'historic' is a value-judgment adjective about the outcome.",
)

case(
    id="banned-construction-exclamation",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

The Council approved the $250,000 CSG Advisors contract increase (Item 2.8)!

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["banned_construction"],
    notes="An exclamation point, banned unconditionally.",
)

case(
    id="banned-construction-direct-address",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

You should know the Council approved a $250,000 increase to its CSG Advisors contract (Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["banned_construction"],
    notes=(
        "Direct address ('you should know') added without inventing any new "
        "claim, so this isolates the direct-address rule from unsupported_claim."
    ),
)

case(
    id="sentence-too-long",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Other Actions

The Council took a long time this evening to talk about many small \
parts of the plan to change how cars can park downtown before it \
chose to wait and put off any real vote on the matter until a later \
meeting date (Item 4.2).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["4.2"],
    people=[],
    facts_block=(
        "## Other Actions\n\nItem 4.2: Downtown parking regulations\n"
        "  - Motion: outcome: continued to a future meeting"
    ),
    expected_findings=["sentence_too_long"],
    notes=(
        "One sentence well past the 40-word ceiling, written in plain short "
        "words specifically so it doesn't also trip the reading-level check - "
        "word count and grade level are correlated but not the same thing."
    ),
)

case(
    id="paragraph-too-long",
    digest_markdown=(
        "# San Jose City Council -- June 9, 2026\n\n"
        "## Overview\n\n"
        "The Council heard a staff report today.\n\n"
        "## Reports\n\n"
        + " ".join(
            f"The report noted routine activity in area {i} of the operations plan."
            for i in range(20)
        )
        + "\n\nFull agenda and minutes are available from the City Clerk.\n"
    ),
    known_item_numbers=[],
    people=[],
    facts_block=(
        "## Reports\n\nItem 3.1: Quarterly operations report covering routine "
        "activity across multiple areas of the operations plan"
    ),
    expected_findings=["paragraph_too_long"],
    notes=(
        "Twenty short sentences with no individual sentence over the ceiling, "
        "but one long paragraph."
    ),
)

case(
    id="reading-level-too-high",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council reviewed a report.

## Reports

The municipality's appropriation ordinance amendments necessitate comprehensive \
reconciliation of budgetary classifications across departments (Item 3.1).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["3.1"],
    people=[],
    facts_block=(
        "## Reports\n\nItem 3.1: Report on appropriation ordinance amendments "
        "requiring reconciliation of budgetary classifications across departments"
    ),
    expected_findings=["reading_level"],
    notes="Deliberately dense, multisyllabic bureaucratic prose - no other rule violated.",
)

case(
    id="missing-first-reference-title",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

The Council approved a $250,000 increase to its CSG Advisors contract, \
seconded by Kamei (Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[{"raw_name": "Rosemary Kamei", "role": "councilmember"}],
    facts_block=_CSG_FACTS,
    expected_findings=["missing_first_reference_title"],
    notes="Bare surname with no prior titled reference anywhere in the digest.",
)

# --------------------------------------------------------------------------
# LLM-judge tier: rules pattern matching structurally cannot evaluate.
# Each digest below is deterministically clean by construction - checked
# against every tier-1 rule while writing it - so scoring these cases
# isolates the judge's own precision/recall. Every claim is fully grounded
# in facts_block *except* the one deliberate gap each case exists to test.
# --------------------------------------------------------------------------

case(
    id="editorializing-win-loss",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

The Council's 9-2 vote delivered a clear win for the majority, leaving \
the two dissenting councilmembers on the losing side of the debate \
(Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=(
        "## Consent Calendar\n\nItem 2.8: Contract amendment\n"
        "  - Motion: outcome: passed, tally 9-2"
    ),
    expected_findings=["editorializing"],
    notes=(
        "The 9-2 vote and its passage are real, cited facts - only the "
        "win/loss framing is added, isolating editorializing from "
        "unsupported_claim."
    ),
)

case(
    id="unsupported-claim",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

Residents packed the chamber to voice fierce opposition before the \
Council approved a $250,000 increase to its CSG Advisors contract \
(Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["unsupported_claim"],
    notes="The facts say nothing about public comment or opposition - this claim is invented.",
)

case(
    id="voice-register",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 1 item.

## Consent Calendar

Big news from the dais: the Council just locked in a fresh $250,000 \
bump for its go-to consulting partner (Item 2.8).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8"],
    people=[],
    facts_block=_CSG_FACTS,
    expected_findings=["voice_register"],
    notes=(
        "Marketing-newsletter register ('Big news', 'locked in', 'go-to') "
        "describing the same fully-grounded CSG Advisors fact as clean-consent."
    ),
)

case(
    id="wrong-item-citation",
    digest_markdown="""# San Jose City Council -- June 9, 2026

## Overview

The Council heard 2 items.

## Consent Calendar

The Council approved a $250,000 increase to a facilities agreement (Item 2.9).

Full agenda and minutes are available from the City Clerk.
""",
    known_item_numbers=["2.8", "2.9"],
    people=[],
    facts_block=(
        "## Consent Calendar\n\n"
        "Item 2.8: Contract amendment with CSG Advisors\n  - Amount: $250,000 (contract)\n\n"
        "Item 2.9: Facilities use approval for a community event\n  - (no amount recorded)"
    ),
    expected_findings=["unsupported_claim"],
    notes=(
        "The hard case this whole second tier exists for: '2.9' is a real, known "
        "item number, so the deterministic unknown_citation check has nothing to "
        "flag - but item 2.9's actual facts have no dollar amount at all. Only a "
        "judge with the per-item facts in view can catch a citation pointing at "
        "the wrong item."
    ),
)


def main() -> None:
    STYLE_CASES_DIR.mkdir(parents=True, exist_ok=True)
    for existing in STYLE_CASES_DIR.glob("*.json"):
        existing.unlink()
    for case_data in CASES:
        path = STYLE_CASES_DIR / f"{case_data['id']}.json"
        path.write_text(
            json.dumps(case_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"Wrote {len(CASES)} style cases to {STYLE_CASES_DIR}")


if __name__ == "__main__":
    main()
