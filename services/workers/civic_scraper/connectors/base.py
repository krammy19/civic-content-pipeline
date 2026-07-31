from abc import ABC, abstractmethod

from civic_scraper.models import Meeting


class CivicConnector(ABC):
    @abstractmethod
    def list_meetings(
        self,
        period: str | None = None,
        body: str | None = None,
        limit: int | None = None,
    ) -> list[Meeting]:
        pass
