"""
Style-checker eval harness entry point.

    uv run python evals/run_style_eval.py                    # score against the baseline
    uv run python evals/run_style_eval.py --update-baseline  # write scores as the new baseline
    uv run python evals/run_style_eval.py --model claude-sonnet-5

Loads every case in evals/style_cases/, runs the real two-tier checker
(checks.style_check.check_deterministic() + judge_style()) against each
digest, scores the result against that case's labeled expected_findings,
and prints a scorecard. judge_style() calls route through the same
cached llm.py every other LLM call in this project uses - a re-run
against inputs already seen costs nothing.

Exits non-zero if overall F1 has regressed more than 3 points (0.03)
below evals/style_baseline.json - the CI regression gate. See
docs/style-checking.md for the full methodology.
"""

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "services" / "workers"))
sys.path.insert(0, str(_REPO_ROOT))

from checks.style_check import (  # noqa: E402
    DEFAULT_MODEL,
    StyleContext,
    check_deterministic,
    judge_style,
)
from evals import style_metrics  # noqa: E402

STYLE_CASES_DIR = Path(__file__).resolve().parent / "style_cases"
BASELINE_PATH = Path(__file__).resolve().parent / "style_baseline.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

REGRESSION_THRESHOLD = 0.03


def load_style_cases(cases_dir: Path = STYLE_CASES_DIR) -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(cases_dir.glob("*.json"))]
    if not cases:
        raise RuntimeError(f"No style cases found in {cases_dir}")
    return cases


def run_case(case: dict, model: str) -> style_metrics.CaseResult:
    context = StyleContext(
        known_item_numbers=set(case["known_item_numbers"]), people=case["people"]
    )
    deterministic_findings = check_deterministic(case["digest_markdown"], context)

    try:
        judge_findings = judge_style(
            digest_markdown=case["digest_markdown"], facts_block=case["facts_block"], model=model
        )
    except Exception as exc:  # noqa: BLE001 - a failed judge call is a scored miss, not a crash
        print(f"  [JUDGE FAIL] {case['id']}: {exc}")
        judge_findings = []

    actual_rules = {f.rule for f in deterministic_findings} | {f.rule for f in judge_findings}
    expected_rules = set(case["expected_findings"])
    return style_metrics.evaluate_case(case["id"], expected_rules, actual_rules)


def build_scorecard(results: list[style_metrics.CaseResult]) -> dict:
    by_rule = style_metrics.aggregate_by_rule(results)
    overall = style_metrics.aggregate_overall(results)
    return {
        "model": None,  # filled in by caller
        "case_count": len(results),
        "overall": {
            "precision": round(overall.precision, 4),
            "recall": round(overall.recall, 4),
            "f1": round(overall.f1, 4),
            "true_positives": overall.true_positives,
            "false_positives": overall.false_positives,
            "false_negatives": overall.false_negatives,
        },
        "rules": {
            rule: {
                "precision": round(score.precision, 4),
                "recall": round(score.recall, 4),
                "f1": round(score.f1, 4),
                "true_positives": score.true_positives,
                "false_positives": score.false_positives,
                "false_negatives": score.false_negatives,
            }
            for rule, score in sorted(by_rule.items())
        },
    }


def print_scorecard(scorecard: dict) -> None:
    print(f"\nModel: {scorecard['model']}")
    print(f"Style cases: {scorecard['case_count']}")
    o = scorecard["overall"]
    print(f"Overall: precision {o['precision']:.3f}  recall {o['recall']:.3f}  F1 {o['f1']:.3f}")

    print(f"\n{'Rule':<32} {'Precision':<11} {'Recall':<9} {'F1':<8} {'TP':<4} {'FP':<4} {'FN':<4}")
    print("-" * 80)
    for rule, s in scorecard["rules"].items():
        print(
            f"{rule:<32} {s['precision']:<11.3f} {s['recall']:<9.3f} {s['f1']:<8.3f} "
            f"{s['true_positives']:<4} {s['false_positives']:<4} {s['false_negatives']:<4}"
        )
    print()


def check_regression(current: dict, baseline: dict) -> list[str]:
    failures = []
    drop = baseline["overall"]["f1"] - current["overall"]["f1"]
    if drop > REGRESSION_THRESHOLD:
        failures.append(
            f"overall: F1 {current['overall']['f1']:.4f} is {drop:.4f} below baseline "
            f"{baseline['overall']['f1']:.4f} (threshold {REGRESSION_THRESHOLD})"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the style-checker eval suite")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Claude model id for judge_style")
    parser.add_argument(
        "--update-baseline", action="store_true", help="Write current scores as the new baseline"
    )
    parser.add_argument("--cases-dir", type=Path, default=STYLE_CASES_DIR)
    args = parser.parse_args()

    cases = load_style_cases(args.cases_dir)
    print(f"Loaded {len(cases)} style cases from {args.cases_dir}")
    print(
        f"Running checker with model={args.model} (judge calls cached - repeat runs cost nothing)\n"
    )

    results = []
    for case in cases:
        result = run_case(case, args.model)
        results.append(result)
        status = "ok" if not (result.false_positives or result.false_negatives) else "DIFF"
        print(f"  [{status:<4}] {case['id']}")

    scorecard = build_scorecard(results)
    scorecard["model"] = args.model
    print_scorecard(scorecard)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_path = RESULTS_DIR / "style_latest.json"
    results_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(f"Wrote machine-readable results to {results_path}")

    if args.update_baseline:
        BASELINE_PATH.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        print(f"Updated baseline at {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.exists():
        print(
            "No style_baseline.json yet - nothing to compare against. "
            "Run with --update-baseline first."
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
