"""Tests for RunMetrics persistence. tmp_path only - no real data/metrics/
directory ever touched by tests."""

from civic_scraper.metrics.collect import RunMetrics
from civic_scraper.metrics.store import load_run_history, save_run_metrics


def _metrics(run_id: str, jurisdiction: str = "San Jose", generated_at: str = "") -> RunMetrics:
    return RunMetrics(
        jurisdiction=jurisdiction,
        run_id=run_id,
        generated_at=generated_at,
        rows_parsed=10,
        schema_failures=0,
        schema_failure_rate=0.0,
        field_population_rates={"motions": 1.0, "people": 1.0, "locations": 0.5, "amounts": 0.5},
        mean_confidence=0.9,
        hallucination_rate=0.0,
        review_queue_volume=2,
    )


class TestSaveAndLoad:
    def test_save_then_load_round_trips(self, tmp_path):
        save_run_metrics(_metrics("run-1"), tmp_path)

        history = load_run_history("San Jose", tmp_path)

        assert len(history) == 1
        assert history[0].run_id == "run-1"
        assert history[0].field_population_rates["motions"] == 1.0

    def test_jurisdiction_name_is_slugified_into_a_directory(self, tmp_path):
        save_run_metrics(_metrics("run-1", jurisdiction="San Jose"), tmp_path)
        assert (tmp_path / "san-jose" / "run-1.json").exists()

    def test_load_history_for_unknown_jurisdiction_is_empty(self, tmp_path):
        assert load_run_history("Nowhere", tmp_path) == []

    def test_history_is_sorted_oldest_first(self, tmp_path):
        save_run_metrics(_metrics("run-b", generated_at="2026-02-01T00:00:00"), tmp_path)
        save_run_metrics(_metrics("run-a", generated_at="2026-01-01T00:00:00"), tmp_path)

        history = load_run_history("San Jose", tmp_path)

        assert [r.run_id for r in history] == ["run-a", "run-b"]

    def test_different_jurisdictions_do_not_collide(self, tmp_path):
        save_run_metrics(_metrics("run-1", jurisdiction="San Jose"), tmp_path)
        save_run_metrics(_metrics("run-1", jurisdiction="Oakland"), tmp_path)

        assert len(load_run_history("San Jose", tmp_path)) == 1
        assert len(load_run_history("Oakland", tmp_path)) == 1
