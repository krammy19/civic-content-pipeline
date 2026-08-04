"""Read/write ReviewQueueItem JSON files under data/review_queue/, and
report the queue's volume - one file per item, named after its queue_id
so the same call that adds an item can later overwrite it with a
reviewer's decision.
"""

from pathlib import Path

from ..paths import DATA_REVIEW_QUEUE as DEFAULT_QUEUE_DIR
from .models import ReviewQueueItem


def save_item(item: ReviewQueueItem, queue_dir: Path = DEFAULT_QUEUE_DIR) -> Path:
    """Write `item` to its own file, creating or overwriting as needed.
    The same function serves both "add a new queue item" and "persist a
    reviewer's decision" - both are just the item's current state."""
    queue_dir.mkdir(parents=True, exist_ok=True)
    path = queue_dir / f"{item.queue_id}.json"
    path.write_text(item.model_dump_json(indent=2), encoding="utf-8")
    return path


def save_items(items: list[ReviewQueueItem], queue_dir: Path = DEFAULT_QUEUE_DIR) -> list[Path]:
    return [save_item(item, queue_dir) for item in items]


def load_items(
    queue_dir: Path = DEFAULT_QUEUE_DIR, status: str | None = None
) -> list[ReviewQueueItem]:
    if not queue_dir.exists():
        return []
    items = [
        ReviewQueueItem.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(queue_dir.glob("*.json"))
    ]
    if status is not None:
        items = [item for item in items if item.status == status]
    return items


def summarize(queue_dir: Path = DEFAULT_QUEUE_DIR) -> dict[str, int]:
    """Counts of review-queue items by status - the review-queue-volume
    signal M4 asks for. A growing 'pending' count from one extraction run
    to the next means extraction is degrading; watching that trend over
    time and per city is M6's job (data/metrics/), not this one's."""
    items = load_items(queue_dir)
    counts = {"pending": 0, "accepted": 0, "edited": 0, "rejected": 0}
    for item in items:
        counts[item.status] += 1
    counts["total"] = len(items)
    return counts
