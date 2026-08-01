"""Tests for the style-eval orchestration script - the regression gate,
scorecard building, and run_case()'s combination of both checker tiers.
No live API calls: judge_style() is patched directly."""

from unittest.mock import patch

from checks.style_check import Finding
from evals import run_style_eval


def _case(**overrides) -> dict:
    base = {
        "id": "test-case",
        "digest_markdown": "# Title\n\n## Overview\n\nx\n",
        "known_item_numbers": [],
        "people": [],
        "facts_block": "facts",
        "expected_findings": [],
    }
    base.update(overrides)
    return base


class TestCheckRegression:
    def test_no_regression_when_scores_match(self):
        current = {"overall": {"f1": 0.9}}
        baseline = {"overall": {"f1": 0.9}}
        assert run_style_eval.check_regression(current, baseline) == []

    def test_no_regression_when_score_improves(self):
        current = {"overall": {"f1": 0.95}}
        baseline = {"overall": {"f1": 0.9}}
        assert run_style_eval.check_regression(current, baseline) == []

    def test_small_drop_within_threshold_is_not_a_regression(self):
        current = {"overall": {"f1": 0.88}}
        baseline = {"overall": {"f1": 0.9}}
        assert run_style_eval.check_regression(current, baseline) == []

    def test_drop_past_threshold_is_flagged(self):
        current = {"overall": {"f1": 0.70}}
        baseline = {"overall": {"f1": 0.9}}
        failures = run_style_eval.check_regression(current, baseline)
        assert len(failures) == 1
        assert "overall" in failures[0]


class TestBuildScorecard:
    def test_aggregates_rule_scores_and_overall(self):
        from evals import style_metrics

        results = [
            style_metrics.evaluate_case("a", {"missing_citation"}, {"missing_citation"}),
            style_metrics.evaluate_case("b", set(), set()),
        ]

        scorecard = run_style_eval.build_scorecard(results)

        assert scorecard["case_count"] == 2
        assert scorecard["overall"]["f1"] == 1.0
        assert scorecard["rules"]["missing_citation"]["true_positives"] == 1


class TestRunCase:
    def test_judge_failure_is_scored_not_raised(self):
        case = _case(
            digest_markdown="## Overview\n\nx\n",  # no "# " header
            expected_findings=["missing_header"],
        )
        with patch.object(run_style_eval, "judge_style", side_effect=ValueError("boom")):
            result = run_style_eval.run_case(case, model="claude-x")

        # The deterministic finding still contributes even though the judge call failed.
        assert "missing_header" in result.true_positives

    def test_combines_deterministic_and_judge_findings(self):
        case = _case(
            digest_markdown="# Title\n\n## Overview\n\nx\n",
            expected_findings=["editorializing"],
        )
        judge_finding = Finding(rule="editorializing", severity="high", message="m")
        with patch.object(run_style_eval, "judge_style", return_value=[judge_finding]):
            result = run_style_eval.run_case(case, model="claude-x")

        assert result.true_positives == {"editorializing"}
        assert result.false_positives == set()
        assert result.false_negatives == set()
