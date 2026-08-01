"""Tests for the pure eval-scoring functions. No network, no fixtures
beyond plain dicts - everything here is synthetic and hand-computed."""

from evals import metrics


class TestMatchers:
    def test_match_motion_requires_same_outcome(self):
        gold = {"outcome": "passed", "text": "approve the contract", "tally": "7-0"}
        pred = {"outcome": "failed", "text": "approve the contract", "tally": "7-0"}
        assert metrics.match_motion(gold, pred) is False

    def test_match_motion_matches_on_exact_tally(self):
        gold = {"outcome": "passed", "text": "approve the contract", "tally": "7-0"}
        pred = {"outcome": "passed", "text": "completely different wording", "tally": "7-0"}
        assert metrics.match_motion(gold, pred) is True

    def test_match_motion_falls_back_to_text_similarity(self):
        gold = {"outcome": "passed", "text": "approve the annual contract renewal", "tally": None}
        pred = {"outcome": "passed", "text": "approve the annual contract renewal", "tally": None}
        assert metrics.match_motion(gold, pred) is True

    def test_match_motion_fails_when_neither_tally_nor_text_agree(self):
        gold = {"outcome": "passed", "text": "approve the contract", "tally": "7-0"}
        pred = {"outcome": "passed", "text": "something unrelated entirely", "tally": "5-2"}
        assert metrics.match_motion(gold, pred) is False

    def test_match_person_requires_similar_name(self):
        assert (
            metrics.match_person({"raw_name": "Rosemary Kamei"}, {"raw_name": "Rosemary Kamei"})
            is True
        )
        assert (
            metrics.match_person({"raw_name": "Rosemary Kamei"}, {"raw_name": "Bien Doan"}) is False
        )

    def test_match_person_ignores_a_title_fused_into_one_side(self):
        # Real case found via the first live eval run: the model extracted
        # "Mayor Mahan" from a comma-separated list ("co-authored by Mayor
        # Mahan, Councilmember Tordillos...") while gold used the bare
        # surname - both are defensible readings of "as written."
        assert metrics.match_person({"raw_name": "Mahan"}, {"raw_name": "Mayor Mahan"}) is True
        assert (
            metrics.match_person({"raw_name": "Tordillos"}, {"raw_name": "Councilmember Tordillos"})
            is True
        )

    def test_match_person_title_stripping_does_not_make_different_people_match(self):
        assert (
            metrics.match_person({"raw_name": "Mayor Mahan"}, {"raw_name": "Mayor Doan"}) is False
        )

    def test_match_location_uses_text_similarity(self):
        gold = {"raw_text": "419 Lano Street"}
        pred = {"raw_text": "419 Lano Street"}
        assert metrics.match_location(gold, pred) is True

    def test_match_amount_matches_on_numeric_value_even_if_text_differs(self):
        gold = {"raw_text": "$1,000,000", "amount_usd": "1000000"}
        pred = {"raw_text": "one million dollars", "amount_usd": "1000000"}
        assert metrics.match_amount(gold, pred) is True

    def test_match_amount_falls_back_to_text_when_no_numeric_value(self):
        gold = {"raw_text": "$1,000,000", "amount_usd": None}
        pred = {"raw_text": "$1,000,000", "amount_usd": None}
        assert metrics.match_amount(gold, pred) is True

    def test_match_amount_false_for_different_numbers(self):
        gold = {"raw_text": "$1,000,000", "amount_usd": "1000000"}
        pred = {"raw_text": "$2,000,000", "amount_usd": "2000000"}
        assert metrics.match_amount(gold, pred) is False


class TestGreedyMatch:
    def test_perfect_one_to_one_match(self):
        gold = [{"raw_name": "A"}, {"raw_name": "B"}]
        pred = [{"raw_name": "A"}, {"raw_name": "B"}]
        result = metrics.greedy_match(gold, pred, metrics.match_person)
        assert len(result.tp_pairs) == 2
        assert result.unmatched_gold == []
        assert result.unmatched_pred == []

    def test_extra_prediction_is_a_false_positive(self):
        gold = [{"raw_name": "A"}]
        pred = [{"raw_name": "A"}, {"raw_name": "Z"}]
        result = metrics.greedy_match(gold, pred, metrics.match_person)
        assert len(result.tp_pairs) == 1
        assert result.unmatched_pred == [1]

    def test_missing_prediction_is_a_false_negative(self):
        gold = [{"raw_name": "A"}, {"raw_name": "B"}]
        pred = [{"raw_name": "A"}]
        result = metrics.greedy_match(gold, pred, metrics.match_person)
        assert len(result.tp_pairs) == 1
        assert result.unmatched_gold == [1]

    def test_a_prediction_is_never_claimed_by_two_gold_entries(self):
        gold = [{"raw_name": "A"}, {"raw_name": "A"}]
        pred = [{"raw_name": "A"}]
        result = metrics.greedy_match(gold, pred, metrics.match_person)
        assert len(result.tp_pairs) == 1
        assert result.unmatched_gold == [1]


class TestScoreField:
    def test_perfect_score(self):
        gold = [{"raw_name": "A"}, {"raw_name": "B"}]
        pred = [{"raw_name": "A"}, {"raw_name": "B"}]
        score = metrics.score_field("people", gold, pred)
        assert score.precision == 1.0
        assert score.recall == 1.0
        assert score.f1 == 1.0

    def test_empty_gold_and_empty_pred_is_perfect(self):
        score = metrics.score_field("people", [], [])
        assert (score.precision, score.recall, score.f1) == (1.0, 1.0, 1.0)

    def test_false_positive_only_hurts_precision(self):
        score = metrics.score_field("people", [], [{"raw_name": "Ghost"}])
        assert score.precision == 0.0
        assert score.recall == 1.0
        assert score.f1 == 0.0

    def test_false_negative_zeroes_out_f1(self):
        score = metrics.score_field("people", [{"raw_name": "A"}], [])
        assert score.precision == 1.0
        assert score.recall == 0.0
        assert score.f1 == 0.0


class TestIsVerified:
    def test_true_when_source_text_present(self):
        fact = {"provenance": {"source_text": "moved by Kamei"}}
        assert metrics.is_verified(fact, "the record shows moved by Kamei today") is True

    def test_false_when_fabricated(self):
        fact = {"provenance": {"source_text": "this never happened"}}
        assert metrics.is_verified(fact, "the record shows moved by Kamei today") is False


def _extracted(value: dict, confidence: float, source_text: str) -> dict:
    return {
        "value": value,
        "confidence": confidence,
        "provenance": {"source_document": "x", "source_text": source_text},
    }


class TestEvaluateCase:
    def test_verified_and_matched_prediction_scores_as_correct(self):
        document_text = "Councilmember Kamei moved to approve the contract. Passed 7-0."
        gold = {"people": [{"raw_name": "Kamei", "source_text": "Councilmember Kamei"}]}
        raw = {"people": [_extracted({"raw_name": "Kamei"}, 0.9, "Councilmember Kamei")]}
        filtered = raw  # nothing to drop - it's verified

        ev = metrics.evaluate_case("case-1", gold, raw, filtered, document_text)

        assert ev.hallucinated == 0
        assert ev.total_raw_extractions == 1
        assert ev.calibration_points == [(0.9, True)]
        assert ev.field_scores["people"].true_positives == 1

    def test_fabricated_extraction_counts_as_hallucinated_and_dropped_from_filtered(self):
        document_text = "Councilmember Kamei moved to approve the contract. Passed 7-0."
        gold = {"people": [{"raw_name": "Kamei", "source_text": "Councilmember Kamei"}]}
        raw = {
            "people": [_extracted({"raw_name": "Ghost"}, 0.8, "this text is not in the document")]
        }
        filtered = {"people": []}  # already dropped by the real filtering step

        ev = metrics.evaluate_case("case-2", gold, raw, filtered, document_text)

        assert ev.hallucinated == 1
        assert ev.total_raw_extractions == 1
        assert ev.calibration_points == [(0.8, False)]
        # Precision/recall computed against FILTERED output: gold has one
        # person, filtered has none -> a false negative, not a false positive.
        assert ev.field_scores["people"].false_negatives == 1
        assert ev.field_scores["people"].false_positives == 0

    def test_verified_but_wrong_fact_is_not_correct_for_calibration(self):
        document_text = "Councilmember Doan moved to approve the contract. Passed 7-0."
        gold = {"people": [{"raw_name": "Kamei", "source_text": "Councilmember Kamei"}]}
        # "Doan" really is in the document (verified) but doesn't match the gold fact.
        raw = {"people": [_extracted({"raw_name": "Doan"}, 0.95, "Councilmember Doan")]}
        filtered = raw

        ev = metrics.evaluate_case("case-3", gold, raw, filtered, document_text)

        assert ev.calibration_points == [(0.95, False)]


class TestAggregation:
    def test_aggregate_field_scores_pools_counts_not_averages(self):
        s1 = metrics.FieldScore(
            "people",
            true_positives=1,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1=1.0,
        )
        s2 = metrics.FieldScore(
            "people",
            true_positives=0,
            false_positives=0,
            false_negatives=1,
            precision=1.0,
            recall=0.0,
            f1=0.0,
        )
        ev1 = metrics.CaseEvaluation(
            "a", {"people": s1, "motions": s1, "locations": s1, "amounts": s1}, 0, 0, []
        )
        ev2 = metrics.CaseEvaluation(
            "b", {"people": s2, "motions": s1, "locations": s1, "amounts": s1}, 0, 0, []
        )

        agg = metrics.aggregate_field_scores([ev1, ev2])

        # Pooled: 1 tp, 0 fp, 1 fn -> recall = 1/2, not the average of 1.0 and 0.0
        # (which would also be 0.5 here - use unequal-size cases to actually
        # distinguish pooling from averaging in a future refactor).
        assert agg["people"].true_positives == 1
        assert agg["people"].false_negatives == 1
        assert agg["people"].recall == 0.5

    def test_aggregate_hallucination_rate(self):
        ev1 = metrics.CaseEvaluation(
            "a", {}, hallucinated=1, total_raw_extractions=4, calibration_points=[]
        )
        ev2 = metrics.CaseEvaluation(
            "b", {}, hallucinated=0, total_raw_extractions=2, calibration_points=[]
        )
        assert metrics.aggregate_hallucination_rate([ev1, ev2]) == 1 / 6

    def test_aggregate_hallucination_rate_with_no_extractions_is_zero(self):
        assert metrics.aggregate_hallucination_rate([]) == 0.0


class TestSchemaValidityRate:
    def test_all_successful(self):
        assert metrics.schema_validity_rate(10, 10) == 1.0

    def test_partial_failures(self):
        assert metrics.schema_validity_rate(8, 10) == 0.8

    def test_no_attempts_is_vacuously_valid(self):
        assert metrics.schema_validity_rate(0, 0) == 1.0


class TestCalibration:
    def test_perfectly_calibrated_bucket_has_zero_gap(self):
        # 10 points at confidence 0.9, 9 correct -> accuracy 0.9, matches confidence.
        points = [(0.9, True)] * 9 + [(0.9, False)]
        buckets, ece = metrics.compute_calibration(points)
        bucket = next(b for b in buckets if b.count == 10)
        assert abs(bucket.mean_confidence - 0.9) < 1e-9
        assert abs(bucket.accuracy - 0.9) < 1e-9
        assert ece < 1e-9

    def test_overconfident_bucket_has_a_positive_gap(self):
        # Stated confidence 0.95 but only correct half the time - real overconfidence.
        points = [(0.95, True)] * 5 + [(0.95, False)] * 5
        buckets, ece = metrics.compute_calibration(points)
        bucket = next(b for b in buckets if b.count == 10)
        assert bucket.mean_confidence > bucket.accuracy
        assert ece > 0.3

    def test_empty_points_is_zero_error_not_a_crash(self):
        buckets, ece = metrics.compute_calibration([])
        assert ece == 0.0
        assert all(b.count == 0 for b in buckets)


class TestMeanConfidence:
    def test_simple_average(self):
        assert metrics.mean_confidence([(0.8, True), (0.6, False)]) == 0.7

    def test_empty_is_zero(self):
        assert metrics.mean_confidence([]) == 0.0
