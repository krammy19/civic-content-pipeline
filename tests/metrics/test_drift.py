"""Tests for trailing-baseline drift detection."""

from civic_scraper.metrics.collect import RunMetrics
from civic_scraper.metrics.drift import detect_drift, trailing_baseline


def _metrics(**overrides) -> RunMetrics:
    base = dict(
        jurisdiction="San Jose",
        run_id="r",
        generated_at="2026-01-01T00:00:00",
        rows_parsed=20,
        schema_failures=0,
        schema_failure_rate=0.0,
        field_population_rates={"motions": 0.8, "people": 0.9, "locations": 0.4, "amounts": 0.5},
        mean_confidence=0.87,
        hallucination_rate=0.0,
        review_queue_volume=3,
    )
    base.update(overrides)
    return RunMetrics(**base)


class TestTrailingBaseline:
    def test_no_history_is_none(self):
        assert trailing_baseline([]) is None

    def test_single_run_baseline_equals_that_run(self):
        run = _metrics(mean_confidence=0.9)
        baseline = trailing_baseline([run])
        assert baseline.mean_confidence == 0.9

    def test_averages_across_multiple_runs(self):
        runs = [_metrics(mean_confidence=0.8), _metrics(mean_confidence=1.0)]
        baseline = trailing_baseline(runs)
        assert baseline.mean_confidence == 0.9

    def test_averages_field_population_rates_per_field(self):
        runs = [
            _metrics(
                field_population_rates={
                    "motions": 1.0,
                    "people": 1.0,
                    "locations": 0.0,
                    "amounts": 0.0,
                }
            ),
            _metrics(
                field_population_rates={
                    "motions": 0.0,
                    "people": 1.0,
                    "locations": 0.0,
                    "amounts": 0.0,
                }
            ),
        ]
        baseline = trailing_baseline(runs)
        assert baseline.field_population_rates["motions"] == 0.5
        assert baseline.field_population_rates["people"] == 1.0


class TestDetectDrift:
    def test_no_baseline_means_no_flags(self):
        assert detect_drift(_metrics(), None) == []

    def test_no_deviation_produces_no_flags(self):
        baseline = _metrics()
        current = _metrics()
        assert detect_drift(current, baseline) == []

    def test_schema_failure_rate_spike_is_flagged(self):
        baseline = _metrics(schema_failure_rate=0.02)
        current = _metrics(schema_failure_rate=0.50)
        flags = detect_drift(current, baseline)
        assert any(f.metric == "schema_failure_rate" for f in flags)

    def test_field_population_rate_collapse_is_flagged(self):
        baseline = _metrics(
            field_population_rates={"motions": 0.8, "people": 0.9, "locations": 0.4, "amounts": 0.5}
        )
        current = _metrics(
            field_population_rates={"motions": 0.0, "people": 0.9, "locations": 0.4, "amounts": 0.5}
        )
        flags = detect_drift(current, baseline)
        assert any(f.metric == "field_population_rate.motions" for f in flags)

    def test_small_field_population_variation_is_not_flagged(self):
        baseline = _metrics(
            field_population_rates={"motions": 0.8, "people": 0.9, "locations": 0.4, "amounts": 0.5}
        )
        current = _metrics(
            field_population_rates={
                "motions": 0.75,
                "people": 0.9,
                "locations": 0.4,
                "amounts": 0.5,
            }
        )
        assert detect_drift(current, baseline) == []

    def test_confidence_drop_is_flagged(self):
        baseline = _metrics(mean_confidence=0.9)
        current = _metrics(mean_confidence=0.6)
        flags = detect_drift(current, baseline)
        assert any(f.metric == "mean_confidence" for f in flags)

    def test_confidence_increase_is_not_flagged(self):
        baseline = _metrics(mean_confidence=0.7)
        current = _metrics(mean_confidence=0.95)
        assert detect_drift(current, baseline) == []

    def test_hallucination_rate_spike_is_flagged(self):
        baseline = _metrics(hallucination_rate=0.0)
        current = _metrics(hallucination_rate=0.20)
        flags = detect_drift(current, baseline)
        assert any(f.metric == "hallucination_rate" for f in flags)

    def test_multiple_flags_can_fire_at_once(self):
        baseline = _metrics(
            schema_failure_rate=0.0,
            mean_confidence=0.9,
            field_population_rates={
                "motions": 0.8,
                "people": 0.9,
                "locations": 0.4,
                "amounts": 0.5,
            },
        )
        current = _metrics(
            schema_failure_rate=0.5,
            mean_confidence=0.4,
            field_population_rates={
                "motions": 0.0,
                "people": 0.0,
                "locations": 0.4,
                "amounts": 0.5,
            },
        )
        flags = detect_drift(current, baseline)
        metrics_flagged = {f.metric for f in flags}
        assert "schema_failure_rate" in metrics_flagged
        assert "mean_confidence" in metrics_flagged
        assert "field_population_rate.motions" in metrics_flagged
        assert "field_population_rate.people" in metrics_flagged
