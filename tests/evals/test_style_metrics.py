"""Tests for the style-checker eval scoring functions. Synthetic rule-name
sets only - no digests, no checks.style_check import."""

from evals import style_metrics


class TestScoreCase:
    def test_exact_match_is_all_true_positives(self):
        tp, fp, fn = style_metrics.score_case({"missing_citation"}, {"missing_citation"})
        assert tp == {"missing_citation"}
        assert fp == set()
        assert fn == set()

    def test_extra_actual_rule_is_a_false_positive(self):
        tp, fp, fn = style_metrics.score_case(
            {"missing_citation"}, {"missing_citation", "reading_level"}
        )
        assert fp == {"reading_level"}

    def test_missing_expected_rule_is_a_false_negative(self):
        tp, fp, fn = style_metrics.score_case({"missing_citation"}, set())
        assert fn == {"missing_citation"}

    def test_both_empty_is_a_perfect_match(self):
        tp, fp, fn = style_metrics.score_case(set(), set())
        assert (tp, fp, fn) == (set(), set(), set())


class TestAggregateByRule:
    def test_pools_counts_across_cases_not_averages(self):
        r1 = style_metrics.evaluate_case("a", {"banned_construction"}, {"banned_construction"})
        r2 = style_metrics.evaluate_case("b", {"banned_construction"}, set())

        scores = style_metrics.aggregate_by_rule([r1, r2])

        assert scores["banned_construction"].true_positives == 1
        assert scores["banned_construction"].false_negatives == 1
        assert scores["banned_construction"].recall == 0.5

    def test_rule_only_ever_a_false_positive_gets_zero_precision(self):
        r1 = style_metrics.evaluate_case("a", set(), {"unexpected_section"})
        scores = style_metrics.aggregate_by_rule([r1])
        assert scores["unexpected_section"].precision == 0.0

    def test_rule_never_seen_at_all_is_absent(self):
        r1 = style_metrics.evaluate_case("a", set(), set())
        assert style_metrics.aggregate_by_rule([r1]) == {}


class TestAggregateOverall:
    def test_perfect_run_has_precision_and_recall_of_one(self):
        results = [
            style_metrics.evaluate_case("a", {"missing_citation"}, {"missing_citation"}),
            style_metrics.evaluate_case("b", set(), set()),
        ]
        overall = style_metrics.aggregate_overall(results)
        assert overall.precision == 1.0
        assert overall.recall == 1.0
        assert overall.f1 == 1.0

    def test_mixed_run_pools_across_every_rule(self):
        results = [
            style_metrics.evaluate_case("a", {"missing_citation"}, {"missing_citation"}),
            style_metrics.evaluate_case("b", {"reading_level"}, set()),
            style_metrics.evaluate_case("c", set(), {"banned_construction"}),
        ]
        overall = style_metrics.aggregate_overall(results)
        assert overall.true_positives == 1
        assert overall.false_negatives == 1
        assert overall.false_positives == 1

    def test_empty_results_is_vacuously_perfect(self):
        overall = style_metrics.aggregate_overall([])
        assert (overall.precision, overall.recall) == (1.0, 1.0)
