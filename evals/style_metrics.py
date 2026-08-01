"""
Pure scoring functions for the style-checker eval harness. No network
calls and no civic_scraper/checks imports - operates on plain rule-name
sets, so it stays testable independent of style_check.py's internals.

A case's correctness is judged per rule *name*, not per exact finding
count: evals/style_cases/*.json labels which rules SHOULD fire on a
given digest, not how many times. Exact-count precision would demand a
labeling precision this hand-built set doesn't actually have - "this
digest has a banned construction" is a defensible label; "this digest
has exactly one banned construction, located here" is not, once a real
checker might reasonably flag two adjacent words in the same sentence
as two separate findings instead of one.
"""

from dataclasses import dataclass


def score_case(
    expected_rules: set[str], actual_rules: set[str]
) -> tuple[set[str], set[str], set[str]]:
    """Returns (true_positive_rules, false_positive_rules, false_negative_rules)."""
    return (
        expected_rules & actual_rules,
        actual_rules - expected_rules,
        expected_rules - actual_rules,
    )


@dataclass
class CaseResult:
    case_id: str
    expected_rules: set[str]
    actual_rules: set[str]
    true_positives: set[str]
    false_positives: set[str]
    false_negatives: set[str]


def evaluate_case(case_id: str, expected_rules: set[str], actual_rules: set[str]) -> CaseResult:
    tp, fp, fn = score_case(expected_rules, actual_rules)
    return CaseResult(case_id, expected_rules, actual_rules, tp, fp, fn)


@dataclass
class RuleScore:
    rule: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = 1.0 if (tp + fp) == 0 else tp / (tp + fp)
    recall = 1.0 if (tp + fn) == 0 else tp / (tp + fn)
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def aggregate_by_rule(results: list[CaseResult]) -> dict[str, RuleScore]:
    """Pool TP/FP/FN per individual rule name across every case, then
    compute precision/recall/F1 - mirrors evals/metrics.py's
    aggregate_field_scores: pooled counts, not a per-case average."""
    rules: set[str] = set()
    for r in results:
        rules |= r.expected_rules | r.actual_rules

    totals = {rule: {"tp": 0, "fp": 0, "fn": 0} for rule in rules}
    for r in results:
        for rule in r.true_positives:
            totals[rule]["tp"] += 1
        for rule in r.false_positives:
            totals[rule]["fp"] += 1
        for rule in r.false_negatives:
            totals[rule]["fn"] += 1

    scores = {}
    for rule, t in totals.items():
        precision, recall, f1 = _prf(t["tp"], t["fp"], t["fn"])
        scores[rule] = RuleScore(rule, t["tp"], t["fp"], t["fn"], precision, recall, f1)
    return scores


def aggregate_overall(results: list[CaseResult]) -> RuleScore:
    """Same pooling, collapsed across every rule - a single headline
    precision/recall number for the checker as a whole."""
    tp = sum(len(r.true_positives) for r in results)
    fp = sum(len(r.false_positives) for r in results)
    fn = sum(len(r.false_negatives) for r in results)
    precision, recall, f1 = _prf(tp, fp, fn)
    return RuleScore("overall", tp, fp, fn, precision, recall, f1)
