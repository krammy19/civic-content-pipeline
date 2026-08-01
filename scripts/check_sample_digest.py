"""
CI smoke test for the digest + style-check pipeline end to end: extract,
route, generate a real digest, and check it - failing if any high-
severity style finding survives. This is the mechanism SPEC's M5
acceptance criterion asks for ("CI runs the style check over generated
digests and fails on any high-severity finding"), run against real data
rather than a synthetic fixture.

Reuses the same eight real June 9, 2026 San Jose City Council agenda
items scripts/run_review_demo_batch.py extracted for M4's review-queue
demo - genuinely validated facts, not hand-written text, so this checks
the pipeline the way a real caller would use it: extract, confidence-
route, generate, check.

    ANTHROPIC_API_KEY=... uv run python scripts/check_sample_digest.py

Every call here routes through llm.py's cache exactly like every other
LLM call in this project, so re-running after the first time is free.
Exits 1 if any HIGH-severity finding remains in the final digest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from civic_scraper.digest.generate_digest import generate_digest, render_facts  # noqa: E402
from civic_scraper.extraction.agenda_item import extract_agenda_item  # noqa: E402
from civic_scraper.models import Meeting  # noqa: E402
from civic_scraper.review.routing import ItemContext, route_agenda_item  # noqa: E402
from run_review_demo_batch import (  # noqa: E402
    BODY,
    ITEMS,
    JURISDICTION,
    MEETING_DATE,
    SOURCE_DOCUMENT,
)

from checks.style_check import (  # noqa: E402
    check_deterministic,
    context_from_agenda_items,
    judge_style,
)


def build_sample_meeting() -> Meeting:
    published_items = []
    for spec in ITEMS:
        item = extract_agenda_item(
            item_title=spec["item_title"],
            item_number=spec["item_number"],
            source_document=SOURCE_DOCUMENT,
            document_text=spec["document_text"],
        )
        context = ItemContext(
            case_id=f"sj-cc-2026-06-09-{spec['item_number']}",
            jurisdiction=JURISDICTION,
            body=BODY,
            meeting_date=MEETING_DATE,
            source_document=SOURCE_DOCUMENT,
            document_text=spec["document_text"],
        )
        result = route_agenda_item(item, context=context)
        published_items.append(result.published)

    return Meeting(
        source="legistar",
        jurisdiction=JURISDICTION,
        body=BODY,
        date=MEETING_DATE,
        agenda_items=published_items,
    )


def main() -> int:
    meeting = build_sample_meeting()
    digest = generate_digest(meeting=meeting)

    print("--- Generated digest ---")
    print(digest)
    print("--- End digest ---\n")

    style_context = context_from_agenda_items(meeting.agenda_items)
    facts_block = render_facts(meeting.agenda_items)

    findings = check_deterministic(digest, style_context)
    findings += judge_style(digest_markdown=digest, facts_block=facts_block)

    if not findings:
        print("No style findings.")
    for finding in findings:
        print(f"[{finding.severity:<6}] {finding.rule}: {finding.message}")

    high_severity = [f for f in findings if f.severity == "high"]
    if high_severity:
        print(f"\n{len(high_severity)} high-severity finding(s) - failing.")
        return 1

    print(f"\n{len(findings)} finding(s), none high-severity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
