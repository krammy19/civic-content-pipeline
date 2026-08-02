"""Tests for the Markdown health report renderer."""

from civic_scraper.metrics.collect import RunMetrics
from civic_scraper.metrics.drift import DriftFlag
from civic_scraper.metrics.report import render_city_report, render_fleet_report


def _metrics(**overrides) -> RunMetrics:
    base = dict(
        jurisdiction="San Jose",
        run_id="run-1",
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


class TestRenderCityReport:
    def test_includes_jurisdiction_and_run_id(self):
        text = render_city_report(_metrics(), None, [])
        assert "San Jose" in text
        assert "run-1" in text

    def test_no_baseline_says_so(self):
        text = render_city_report(_metrics(), None, [])
        assert "No baseline yet" in text

    def test_no_flags_with_a_baseline_says_so(self):
        text = render_city_report(_metrics(), _metrics(), [])
        assert "No drift flags" in text

    def test_flags_are_listed_with_their_message(self):
        flag = DriftFlag("mean_confidence", 0.9, 0.5, -0.4, "Mean confidence dropped a lot.")
        text = render_city_report(_metrics(), _metrics(), [flag])
        assert "1 drift flag" in text
        assert "Mean confidence dropped a lot." in text

    def test_metrics_table_shows_current_and_baseline(self):
        current = _metrics(mean_confidence=0.5)
        baseline = _metrics(mean_confidence=0.9)
        text = render_city_report(current, baseline, [])
        assert "0.500" in text
        assert "0.900" in text


class TestRenderFleetReport:
    def test_summarizes_zero_flags(self):
        text = render_fleet_report([(_metrics(), None, [])])
        assert "No drift flags" in text

    def test_summarizes_flagged_cities(self):
        flag = DriftFlag("mean_confidence", 0.9, 0.5, -0.4, "dropped")
        oakland = _metrics(jurisdiction="Oakland")
        entries = [(_metrics(), None, [flag]), (oakland, None, [])]
        text = render_fleet_report(entries)
        assert "1 drift flag" in text
        assert "San Jose" in text

    def test_includes_a_section_per_city(self):
        entries = [(_metrics(), None, []), (_metrics(jurisdiction="Oakland"), None, [])]
        text = render_fleet_report(entries)
        assert "## San Jose" in text
        assert "## Oakland" in text
