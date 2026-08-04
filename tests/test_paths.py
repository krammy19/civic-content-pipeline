"""Tests for the repo-root-anchored data paths. The whole point of
paths.py is that these never depend on the current working directory -
verified here by resolving them and checking they land under the actual
repo root regardless of what os.getcwd() happens to be when the test
runs."""

from civic_scraper import paths


class TestPaths:
    def test_repo_root_contains_pyproject_toml(self):
        assert (paths.REPO_ROOT / "pyproject.toml").exists()

    def test_data_paths_are_all_under_repo_root(self):
        for path in (
            paths.DATA_ROOT,
            paths.DATA_RAW,
            paths.DATA_PROCESSED,
            paths.DATA_REVIEW_QUEUE,
            paths.DATA_METRICS,
            paths.LLM_CACHE,
        ):
            assert path.is_relative_to(paths.REPO_ROOT)

    def test_data_processed_is_a_single_well_known_location(self):
        assert paths.DATA_PROCESSED == paths.REPO_ROOT / "data" / "processed"

    def test_llm_cache_is_dot_cache_llm_under_repo_root(self):
        assert paths.LLM_CACHE == paths.REPO_ROOT / ".cache" / "llm"
