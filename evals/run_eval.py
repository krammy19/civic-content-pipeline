"""
Eval harness entry point.

    uv run python evals/run_eval.py                  # score against evals/baseline.json
    uv run python evals/run_eval.py --update-baseline # write current scores as the new baseline
    uv run python evals/run_eval.py --model claude-sonnet-5

Loads every case in evals/gold/, runs the real extraction pipeline
(extraction.agenda_item.extract_agenda_item_raw() + drop_unverified(),
routed through the same cached llm.py every other extraction call uses -
a re-run against inputs already seen costs nothing), scores the result
with evals/metrics.py, and prints a scorecard.

Exits non-zero if any field's F1 has regressed more than 3 points (0.03)
below evals/baseline.json - the CI regression gate. See docs/evals.md for
the full methodology.
"""

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "services" / "workers"))
sys.path.insert(0, str(_REPO_ROOT))

from civic_scraper.extraction.agenda_item import (  # noqa: E402
    DEFAULT_MODEL,
    drop_unverified,
    extract_agenda_item_raw,
)

from evals import metrics  # noqa: E402

GOLD_DIR = Path(__file__).resolve().parent / "gold"
BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

REGRESSION_THRESHOLD = 0.03


def load_gold_cases(gold_dir: Path = GOLD_DIR) -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(gold_dir.glob("*.json"))]
    if not cases:
        raise RuntimeError(f"No gold cases found in {gold_dir}")
    return cases


def run_case(case: dict, model: str) -> tuple[metrics.CaseEvaluation, bool]:
    """Returns (evaluation, schema_valid). schema_valid is False if Claude's
    tool-use output didn't validate against AgendaItem at all - a
    real API/schema failure, not something metrics.py's matching logic
    can score."""
    annotated_fields = case.get("annotated_fields")
    annotated_fields = tuple(annotated_fields) if annotated_fields is not None else None

    try:
        raw_item = extract_agenda_item_raw(
            item_title=case["item_title"],
            item_number=case["item_number"],
            document_text=case["document_text"],
            model=model,
        )
    except Exception as exc:  # noqa: BLE001 - a failed call is a scored failure, not a crash
        print(f"  [SCHEMA FAIL] {case['id']}: {exc}")
        empty = {"motions": [], "people": [], "locations": [], "amounts": []}
        ev = metrics.evaluate_case(
            case["id"], case["expected"], empty, empty, case["document_text"], annotated_fields
        )
        return ev, False

    filtered_item = drop_unverified(raw_item, case["document_text"], case["source_document"])

    raw_dump = raw_item.model_dump(mode="json")
    filtered_dump = filtered_item.model_dump(mode="json")

    ev = metrics.evaluate_case(
        case["id"],
        case["expected"],
        raw_dump,
        filtered_dump,
        case["document_text"],
        annotated_fields,
    )
    return ev, True


def _buckets_json(buckets: list[metrics.CalibrationBucket]) -> list[dict]:
    return [
        {
            "range": b.range_label,
            "count": b.count,
            "mean_confidence": round(b.mean_confidence, 4),
            "accuracy": round(b.accuracy, 4),
        }
        for b in buckets
    ]


def build_scorecard(evaluations: list[metrics.CaseEvaluation], schema_valid_count: int) -> dict:
    field_scores = metrics.aggregate_field_scores(evaluations)
    all_calibration_points = [p for ev in evaluations for p in ev.calibration_points]
    agg_points = [(c, ok) for _, c, ok in all_calibration_points]
    buckets, ece = metrics.compute_calibration(agg_points)

    by_field_points = metrics.calibration_points_by_field(all_calibration_points)
    calibration_by_field = {}
    for field, points in by_field_points.items():
        field_buckets, field_ece = metrics.compute_calibration(points)
        calibration_by_field[field] = {
            "expected_calibration_error": round(field_ece, 4),
            "n": len(points),
            "buckets": _buckets_json(field_buckets),
        }

    return {
        "model": None,  # filled in by caller
        "gold_set_size": len(evaluations),
        "fields": {
            field: {
                "precision": round(score.precision, 4),
                "recall": round(score.recall, 4),
                "f1": round(score.f1, 4),
                "true_positives": score.true_positives,
                "false_positives": score.false_positives,
                "false_negatives": score.false_negatives,
            }
            for field, score in field_scores.items()
        },
        "hallucination_rate": round(metrics.aggregate_hallucination_rate(evaluations), 4),
        "schema_validity_rate": round(
            metrics.schema_validity_rate(schema_valid_count, len(evaluations)), 4
        ),
        "mean_confidence": round(metrics.mean_confidence(agg_points), 4),
        "calibration": {
            "expected_calibration_error": round(ece, 4),
            "buckets": _buckets_json(buckets),
        },
        "calibration_by_field": calibration_by_field,
    }


def print_scorecard(scorecard: dict) -> None:
    print(f"\nModel: {scorecard['model']}")
    print(f"Gold cases: {scorecard['gold_set_size']}")
    print(f"Schema validity rate: {scorecard['schema_validity_rate']:.1%}")
    print(f"Hallucination rate (raw output): {scorecard['hallucination_rate']:.1%}")
    print(f"Mean confidence (raw output): {scorecard['mean_confidence']:.3f}")

    print(
        f"\n{'Field':<12} {'Precision':<11} {'Recall':<9} {'F1':<8} {'TP':<5} {'FP':<5} {'FN':<5}"
    )
    print("-" * 60)
    for field, s in scorecard["fields"].items():
        print(
            f"{field:<12} {s['precision']:<11.3f} {s['recall']:<9.3f} {s['f1']:<8.3f} "
            f"{s['true_positives']:<5} {s['false_positives']:<5} {s['false_negatives']:<5}"
        )

    print(f"\nCalibration (ECE = {scorecard['calibration']['expected_calibration_error']:.4f}):")
    print(f"{'Confidence range':<20} {'n':<6} {'Mean confidence':<17} {'Actual accuracy':<17}")
    print("-" * 62)
    for b in scorecard["calibration"]["buckets"]:
        if b["count"] == 0:
            continue
        print(
            f"{b['range']:<20} {b['count']:<6} {b['mean_confidence']:<17.3f} {b['accuracy']:<17.3f}"
        )

    print("\nCalibration by field:")
    print(f"{'Field':<12} {'n':<5} {'ECE':<8} {'Confidence range':<20} {'accuracy'}")
    print("-" * 62)
    for field, cal in scorecard["calibration_by_field"].items():
        for b in cal["buckets"]:
            if b["count"] == 0:
                continue
            print(
                f"{field:<12} {b['count']:<5} {cal['expected_calibration_error']:<8.4f} "
                f"{b['range']:<20} {b['accuracy']:.3f}"
            )
    print()


def check_regression(current: dict, baseline: dict) -> list[str]:
    failures = []
    for field, current_score in current["fields"].items():
        baseline_score = baseline.get("fields", {}).get(field)
        if baseline_score is None:
            continue
        drop = baseline_score["f1"] - current_score["f1"]
        if drop > REGRESSION_THRESHOLD:
            failures.append(
                f"{field}: F1 {current_score['f1']:.4f} is {drop:.4f} below baseline "
                f"{baseline_score['f1']:.4f} (threshold {REGRESSION_THRESHOLD})"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    """`argv` defaults to `sys.argv[1:]` via argparse when None - lets
    `civic_scraper.cli`'s `civic eval` subcommand pass through its own
    remaining arguments directly."""
    parser = argparse.ArgumentParser(description="Run the agenda-item extraction eval suite")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model id to evaluate")
    parser.add_argument(
        "--update-baseline", action="store_true", help="Write current scores as the new baseline"
    )
    parser.add_argument("--gold-dir", type=Path, default=GOLD_DIR)
    args = parser.parse_args(argv)

    cases = load_gold_cases(args.gold_dir)
    print(f"Loaded {len(cases)} gold cases from {args.gold_dir}")
    print(f"Running extraction with model={args.model} (cached - repeat runs cost nothing)\n")

    evaluations = []
    schema_valid_count = 0
    for case in cases:
        ev, valid = run_case(case, args.model)
        evaluations.append(ev)
        schema_valid_count += int(valid)
        print(f"  [{'ok' if valid else 'FAIL':<4}] {case['id']}")

    scorecard = build_scorecard(evaluations, schema_valid_count)
    scorecard["model"] = args.model
    print_scorecard(scorecard)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / "latest.json"
    results_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(f"Wrote machine-readable results to {results_path}")

    if args.update_baseline:
        BASELINE_PATH.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        print(f"Updated baseline at {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.exists():
        print(
            "No baseline.json yet - nothing to compare against. Run with --update-baseline first."
        )
        return 0

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    failures = check_regression(scorecard, baseline)
    if failures:
        print("REGRESSION DETECTED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("No regression vs. baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
