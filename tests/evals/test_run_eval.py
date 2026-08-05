"""Tests for the eval orchestration script - the regression gate and
scorecard-building logic specifically, since those are what CI actually
depends on. No real API calls: run_case() is tested against a FakeClient,
never against extract_agenda_item_raw() with a live key."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals"))

from evals import metrics, run_eval  # noqa: E402
from tests.fake_llm_client import FakeClient  # noqa: E402


def _tool_input(**overrides) -> dict:
    base = {
        "item_number": None,
        "title": "t",
        "item_type": "action",
        "motions": [],
        "people": [],
        "locations": [],
        "amounts": [],
    }
    base.update(overrides)
    return base


def _gold_case(**overrides) -> dict:
    base = {
        "id": "test-case",
        "item_title": "t",
        "item_number": None,
        "document_text": "some real text",
        "source_document": "doc",
        "expected": {"motions": [], "people": [], "locations": [], "amounts": []},
    }
    base.update(overrides)
    return base


class TestBaselinePathFor:
    def test_default_gold_dir_maps_to_the_original_baseline(self):
        gold_dir = Path("/repo/evals/gold")
        assert run_eval.baseline_path_for(gold_dir) == Path("/repo/evals/baseline.json")

    def test_a_second_citys_gold_dir_gets_its_own_baseline_file(self):
        gold_dir = Path("/repo/evals/gold_civicplus")
        assert run_eval.baseline_path_for(gold_dir) == Path("/repo/evals/baseline_civicplus.json")


class TestCheckRegression:
    def test_no_regression_when_scores_match(self):
        current = {"fields": {"motions": {"f1": 0.88}}}
        baseline = {"fields": {"motions": {"f1": 0.88}}}
        assert run_eval.check_regression(current, baseline) == []

    def test_no_regression_when_score_improves(self):
        current = {"fields": {"motions": {"f1": 0.95}}}
        baseline = {"fields": {"motions": {"f1": 0.88}}}
        assert run_eval.check_regression(current, baseline) == []

    def test_small_drop_within_threshold_is_not_a_regression(self):
        current = {"fields": {"motions": {"f1": 0.86}}}
        baseline = {"fields": {"motions": {"f1": 0.88}}}
        assert run_eval.check_regression(current, baseline) == []

    def test_drop_past_threshold_is_flagged(self):
        # A deliberately degraded prompt/model producing worse motions
        # extraction must be caught - this is the actual CI gate.
        current = {"fields": {"motions": {"f1": 0.70}}}
        baseline = {"fields": {"motions": {"f1": 0.88}}}
        failures = run_eval.check_regression(current, baseline)
        assert len(failures) == 1
        assert "motions" in failures[0]

    def test_multiple_fields_can_each_regress(self):
        current = {
            "fields": {"motions": {"f1": 0.5}, "people": {"f1": 0.9}, "amounts": {"f1": 0.4}}
        }
        baseline = {
            "fields": {"motions": {"f1": 0.88}, "people": {"f1": 0.9}, "amounts": {"f1": 0.87}}
        }
        failures = run_eval.check_regression(current, baseline)
        assert len(failures) == 2

    def test_new_field_with_no_baseline_entry_is_ignored(self):
        current = {"fields": {"new_field": {"f1": 0.1}}}
        baseline = {"fields": {}}
        assert run_eval.check_regression(current, baseline) == []


class TestBuildScorecard:
    def test_aggregates_field_scores_and_calibration(self):
        score = metrics.FieldScore("motions", 1, 0, 0, 1.0, 1.0, 1.0)
        ev = metrics.CaseEvaluation(
            "case-1",
            {"motions": score, "people": score, "locations": score, "amounts": score},
            hallucinated=0,
            total_raw_extractions=1,
            calibration_points=[("motions", 0.9, True)],
        )

        scorecard = run_eval.build_scorecard([ev], schema_valid_count=1)

        assert scorecard["gold_set_size"] == 1
        assert scorecard["schema_validity_rate"] == 1.0
        assert scorecard["hallucination_rate"] == 0.0
        assert scorecard["fields"]["motions"]["f1"] == 1.0
        # A single (0.9, correct) point has accuracy 1.0, not 0.9 - the gap
        # (0.1) is real, not a rounding artifact, since one data point can
        # never actually land exactly on its own confidence value.
        assert scorecard["calibration"]["expected_calibration_error"] == 0.1
        # The same point also shows up in its own field's calibration curve.
        assert scorecard["calibration_by_field"]["motions"]["n"] == 1
        assert scorecard["calibration_by_field"]["motions"]["expected_calibration_error"] == 0.1
        assert scorecard["calibration_by_field"]["people"]["n"] == 0


class TestRunCase:
    def test_schema_failure_is_scored_not_raised(self):
        gold = _gold_case()
        with patch.object(run_eval, "extract_agenda_item_raw", side_effect=ValueError("boom")):
            ev, valid = run_eval.run_case(gold, model="claude-x")

        assert valid is False
        assert ev.case_id == "test-case"

    def test_successful_case_returns_valid_true(self):
        gold = _gold_case(
            expected={
                "motions": [],
                "people": [
                    {"raw_name": "Kamei", "role": "councilmember", "source_text": "Kamei moved"}
                ],
                "locations": [],
                "amounts": [],
            },
            document_text="Kamei moved to approve the item.",
        )
        tool_input = _tool_input(
            people=[
                {
                    "value": {"raw_name": "Kamei", "canonical_name": None, "role": "councilmember"},
                    "confidence": 0.9,
                    "provenance": {"source_document": "x", "source_text": "Kamei moved"},
                }
            ]
        )
        client = FakeClient(tool_name="extract_agenda_item", tool_input=tool_input)

        with patch.object(run_eval, "extract_agenda_item_raw") as mock_extract:
            from civic_scraper.extraction.agenda_item import extract_agenda_item_raw as real_raw

            mock_extract.side_effect = lambda **kwargs: real_raw(**kwargs, client=client)
            ev, valid = run_eval.run_case(gold, model="claude-x")

        assert valid is True
        assert ev.field_scores["people"].true_positives == 1
