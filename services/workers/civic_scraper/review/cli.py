"""Interactive review CLI: `python -m civic_scraper.review`

Presents one pending review-queue item at a time - the proposed value,
its provenance span, and surrounding source context - so a person can
accept, edit, or reject it. This is the human half of confidence
routing: routing.py already decided a value wasn't confident enough to
publish on its own; this CLI is where a person makes the actual call,
and an accepted or edited decision feeds back into the gold set (see
gold_export.py).
"""

import json
from pathlib import Path

from . import queue
from .models import ReviewQueueItem

_PRIMARY_FIELD = {
    "motions": "text",
    "people": "raw_name",
    "locations": "raw_text",
    "amounts": "raw_text",
}


def _context_snippet(document_text: str, source_text: str, radius: int = 80) -> str:
    idx = document_text.find(source_text)
    if idx == -1:
        # Shouldn't happen - provenance was already verified before an item
        # reached the queue - but fall back to the span alone rather than crash.
        return source_text
    start = max(0, idx - radius)
    end = min(len(document_text), idx + len(source_text) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(document_text) else ""
    return f"{prefix}{document_text[start:end]}{suffix}"


def _print_item(item: ReviewQueueItem) -> None:
    print("\n" + "=" * 72)
    print(
        f"{item.item_title} (item {item.item_number or 'n/a'}) - "
        f"{item.jurisdiction} {item.body}, {item.meeting_date}"
    )
    print(f"Field: {item.field_type}  |  Confidence: {item.confidence:.2f}  |  ID: {item.queue_id}")
    print("-" * 72)
    print("Proposed value:")
    print(json.dumps(item.value, indent=2))
    print("-" * 72)
    print("Provenance span:")
    print(f'  "{item.provenance.source_text}"')
    print("\nSurrounding context:")
    print(f"  {_context_snippet(item.document_text, item.provenance.source_text)}")
    print("=" * 72)


def _prompt_decision() -> str:
    while True:
        choice = input("[a]ccept / [e]dit / [r]eject / [s]kip / [q]uit > ").strip().lower()
        if choice in ("a", "e", "r", "s", "q"):
            return choice
        print("Please enter a, e, r, s, or q.")


def review_session(
    items: list[ReviewQueueItem], queue_dir: Path = queue.DEFAULT_QUEUE_DIR
) -> dict[str, int]:
    """Runs the interactive loop over `items`, returns a tally of decisions.

    Split out from main() so a scripted session (or a test) can drive it
    against an in-memory list without a real terminal attached.
    """
    tally = {"accepted": 0, "edited": 0, "rejected": 0, "skipped": 0}

    for item in items:
        _print_item(item)
        choice = _prompt_decision()

        if choice == "q":
            break
        if choice == "s":
            tally["skipped"] += 1
            continue
        if choice == "a":
            item.status = "accepted"
            tally["accepted"] += 1
        elif choice == "e":
            primary_field = _PRIMARY_FIELD[item.field_type]
            current = item.value.get(primary_field, "")
            corrected = input(f"Corrected {primary_field} (currently: {current!r}): ").strip()
            item.resolved_value = {**item.value, primary_field: corrected}
            item.status = "edited"
            tally["edited"] += 1
        elif choice == "r":
            item.reviewer_notes = input("Reason for rejecting (optional): ").strip() or None
            item.status = "rejected"
            tally["rejected"] += 1

        queue.save_item(item, queue_dir)

    return tally


def main() -> int:
    items = queue.load_items(status="pending")
    if not items:
        print("No pending review items.")
        return 0

    print(f"{len(items)} item(s) pending review.\n")
    tally = review_session(items)

    print("\nReview session complete.")
    for key, count in tally.items():
        print(f"  {key}: {count}")

    print("\nQueue status:")
    for key, count in queue.summarize().items():
        print(f"  {key}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
