"""
Live demonstration + CI smoke test for metrics/drift detection: extract
the same real June 9, 2026 San Jose agenda items scripts/
run_review_demo_batch.py used for M4, compute real RunMetrics from that
run, save it as trailing history, then simulate a deliberately broken
connector run and confirm detect_drift() flags it.

The "broken connector" run is synthetic on purpose - the acceptance
criterion this exists to prove ("a deliberately broken connector
triggers a drift flag") is not something you'd want to demonstrate by
actually breaking a real connector in production. It's built by taking
the same real extraction output and deleting a field type's facts from
every item, the way a real template change (a table Legistar renders
differently) would make a connector stop finding data that's genuinely
there - not by inventing metrics numbers from nothing.

    ANTHROPIC_API_KEY=... uv run python scripts/check_metrics_drift.py

Exits 1 if the simulated broken run does NOT trigger a drift flag -
that would mean drift detection itself is broken.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from civic_scraper.extraction.agenda_item import (  # noqa: E402
    drop_unverified,
    extract_agenda_item_raw,
)
from civic_scraper.metrics.collect import compute_run_metrics  # noqa: E402
from civic_scraper.metrics.drift import detect_drift, trailing_baseline  # noqa: E402
from civic_scraper.metrics.report import render_city_report  # noqa: E402
from civic_scraper.metrics.store import load_run_history, save_run_metrics  # noqa: E402
from run_review_demo_batch import ITEMS, JURISDICTION, SOURCE_DOCUMENT  # noqa: E402

METRICS_ROOT = Path("data/metrics")
JURISDICTION_DEMO = f"{JURISDICTION} (metrics demo)"


def _real_run():
    """Extract every ITEMS entry for real (cached after the first run)
    and return (published_items, raw_extractions) exactly like a
    production run would produce."""
    published_items = []
    raw_extractions = []
    for spec in ITEMS:
        raw_item = extract_agenda_item_raw(
            item_title=spec["item_title"],
            item_number=spec["item_number"],
            document_text=spec["document_text"],
        )
        filtered_item = drop_unverified(raw_item, spec["document_text"], SOURCE_DOCUMENT)
        published_items.append(filtered_item)
        raw_extractions.append((raw_item, spec["document_text"]))
    return published_items, raw_extractions


def _break_connector(published_items):
    """Simulate a template change that broke people/amounts extraction
    for this city - every item still parses (no schema failures), but
    two field types silently come back empty, the way a connector
    reading the wrong table column after a platform redesign would."""
    broken = []
    for item in published_items:
        broken.append(item.model_copy(update={"people": [], "amounts": []}))
    return broken


def main() -> int:
    published_items, raw_extractions = _real_run()

    baseline_run = compute_run_metrics(
        jurisdiction=JURISDICTION_DEMO,
        run_id="run-2026-06-09-baseline",
        agenda_items=published_items,
        raw_extractions=raw_extractions,
        review_queue_volume=10,
    )
    save_run_metrics(baseline_run, METRICS_ROOT)
    print("Baseline run saved:")
    print(f"  field population rates: {baseline_run.field_population_rates}")
    print(f"  mean confidence: {baseline_run.mean_confidence:.3f}")

    broken_items = _break_connector(published_items)
    broken_run = compute_run_metrics(
        jurisdiction=JURISDICTION_DEMO,
        run_id="run-2026-06-16-simulated-connector-rot",
        agenda_items=broken_items,
        raw_extractions=raw_extractions,  # raw extraction quality itself didn't change
        review_queue_volume=10,
    )
    save_run_metrics(broken_run, METRICS_ROOT)
    print("\nSimulated broken-connector run saved:")
    print(f"  field population rates: {broken_run.field_population_rates}")

    history = load_run_history(JURISDICTION_DEMO, METRICS_ROOT)
    prior_runs = [r for r in history if r.run_id != broken_run.run_id]
    baseline = trailing_baseline(prior_runs)
    flags = detect_drift(broken_run, baseline)

    print("\n" + render_city_report(broken_run, baseline, flags))

    if not flags:
        print("FAIL: simulated connector rot produced no drift flags.")
        return 1

    print(f"OK: {len(flags)} drift flag(s) correctly triggered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
