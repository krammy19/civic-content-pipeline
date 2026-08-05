import pytest
from civic_scraper import llm
from civic_scraper.connectors.civicplus import CivicPlusConnector
from civic_scraper.connectors.legistar import LegistarConnector


@pytest.fixture(autouse=True)
def _isolated_llm_cache(tmp_path, monkeypatch):
    """Every test gets its own empty LLM cache dir - nothing ever writes to
    the real .cache/llm/ during a test run, and no test's cache can leak
    into another's."""
    monkeypatch.setattr(llm, "CACHE_ROOT", tmp_path / ".cache" / "llm")


@pytest.fixture
def connector() -> LegistarConnector:
    return LegistarConnector(
        jurisdiction="Testville",
        calendar_url="https://testville.legistar.com/Calendar.aspx",
    )


@pytest.fixture
def civicplus_connector() -> CivicPlusConnector:
    return CivicPlusConnector(
        jurisdiction="Testville",
        base_url="https://testville.civicplus.com",
        body="City Council",
    )
