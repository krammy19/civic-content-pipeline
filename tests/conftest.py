import pytest
from civic_scraper.connectors.legistar import LegistarConnector


@pytest.fixture
def connector() -> LegistarConnector:
    return LegistarConnector(
        jurisdiction="Testville",
        calendar_url="https://testville.legistar.com/Calendar.aspx",
    )
