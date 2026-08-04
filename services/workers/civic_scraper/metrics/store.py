"""Persistence for RunMetrics: one JSON file per run, under
data/metrics/{jurisdiction-slug}/{run_id}.json - per SPEC's target
layout. Slugified so a jurisdiction name with spaces or mixed case
(cities.yaml's `name` field, e.g. "San Jose") produces one stable
directory regardless of how it's capitalized when passed in.
"""

import json
from dataclasses import asdict
from pathlib import Path

from ..paths import DATA_METRICS as METRICS_ROOT
from .collect import RunMetrics


def _slugify(jurisdiction: str) -> str:
    return jurisdiction.strip().lower().replace(" ", "-")


def save_run_metrics(metrics: RunMetrics, root: Path = METRICS_ROOT) -> Path:
    city_dir = root / _slugify(metrics.jurisdiction)
    city_dir.mkdir(parents=True, exist_ok=True)
    path = city_dir / f"{metrics.run_id}.json"
    path.write_text(json.dumps(asdict(metrics), indent=2), encoding="utf-8")
    return path


def load_run_history(jurisdiction: str, root: Path = METRICS_ROOT) -> list[RunMetrics]:
    """Every run recorded for `jurisdiction`, oldest first. Empty list -
    not an error - for a jurisdiction with no prior runs; a first run has
    nothing to have history yet."""
    city_dir = root / _slugify(jurisdiction)
    if not city_dir.exists():
        return []
    runs = [
        RunMetrics(**json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(city_dir.glob("*.json"))
    ]
    return sorted(runs, key=lambda r: r.generated_at)
