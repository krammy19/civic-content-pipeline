import calendar
import re
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from civic_scraper.connectors.base import CivicConnector
from civic_scraper.models import Meeting

_HEADERS = {"User-Agent": "Mozilla/5.0 (civic-engagement-app)"}

# Maps human-readable period strings to CivicPlus dateSelector values
_DATE_SELECTOR: dict[str, str] = {
    "last week": "1",
    "last month": "2",
    "last 6 months": "3",
    "last year": "4",
}


def _this_month_range() -> tuple[str, str]:
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    start = today.replace(day=1).strftime("%m/%d/%Y")
    end = today.replace(day=last_day).strftime("%m/%d/%Y")
    return start, end


class CivicPlusConnector(CivicConnector):
    def __init__(
        self,
        jurisdiction: str,
        base_url: str,
        body: str = "City Council",
        category_id: str | None = None,
    ):
        self.jurisdiction = jurisdiction
        self.base_url = base_url.rstrip("/")
        self.body = body
        self._category_id = category_id  # pre-populate from cities.yaml to skip discovery

    # ------------------------------------------------------------------
    # Category discovery
    # ------------------------------------------------------------------

    def discover_categories(self) -> dict[str, str]:
        """Return {lowercase_body_name: category_id} from /AgendaCenter."""
        r = requests.get(f"{self.base_url}/AgendaCenter", headers=_HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cats: dict[str, str] = {}
        for cb in soup.find_all("input", {"name": "chkCategoryID"}):
            label = soup.find("label", {"for": cb.get("id")})
            if label:
                cats[label.get_text(strip=True).lower()] = cb["value"]
        return cats

    def _find_category_id(self) -> str:
        if self._category_id:
            return self._category_id

        cats = self.discover_categories()
        if not cats:
            raise ValueError(
                f"No AgendaCenter categories found at {self.base_url}. "
                "The city may use a different agenda platform."
            )

        target = self.body.lower()

        # 1. Exact match
        if target in cats:
            self._category_id = cats[target]
            return self._category_id

        # 2. Target is a substring of a category name (or vice-versa)
        for name, cid in cats.items():
            if target in name or name in target:
                self._category_id = cid
                return self._category_id

        # 3. Fallback: any category containing "council"
        for name, cid in cats.items():
            if "council" in name:
                self._category_id = cid
                return self._category_id

        available = list(cats.keys())
        raise ValueError(
            f"No category matching {self.body!r} at {self.base_url}/AgendaCenter. "
            f"Available: {available}"
        )

    # ------------------------------------------------------------------
    # Search URL construction
    # ------------------------------------------------------------------

    def _search_url(self, period: str | None, cid: str) -> str:
        base = f"{self.base_url}/AgendaCenter/Search/?term=&CIDs={cid}"

        if period is None:
            return base + "&startDate=&endDate=&dateRange=&dateSelector=3"

        key = period.lower()

        if key == "this month":
            start, end = _this_month_range()
            return base + f"&startDate={start}&endDate={end}&dateRange=&dateSelector="

        selector = _DATE_SELECTOR.get(key, "3")
        return base + f"&startDate=&endDate=&dateRange=&dateSelector={selector}"

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_body_from_title(title: str, fallback: str) -> str:
        """'Agenda for the May 6, 2025 City Council Meeting.' → 'City Council'"""
        m = re.search(
            r"(?:Agenda for(?: the)?\s+\w+\s+\d+,\s+\d+\s+)(.+?)(?:\s+Meeting\.?)?$",
            title,
            re.IGNORECASE,
        )
        return m.group(1).strip() if m else fallback

    def _parse_meetings(self, html: str, limit: int | None) -> list[Meeting]:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr", class_="catAgendaRow")
        meetings: list[Meeting] = []

        for row in rows:
            strong = row.find("strong", attrs={"aria-label": True})
            if not strong:
                continue
            date_str = strong["aria-label"].replace("Agenda for ", "").strip()

            # Agenda link (href already includes ?html=true on most sites)
            agenda_a = row.find("a", href=re.compile(r"/AgendaCenter/ViewFile/Agenda/"))
            agenda_url = urljoin(self.base_url, agenda_a["href"]) if agenda_a else None

            # Body name from link text
            title_text = agenda_a.get_text(strip=True) if agenda_a else ""
            body = self._extract_body_from_title(title_text, self.body)

            # Minutes
            minutes_td = row.find("td", class_="minutes")
            minutes_a = minutes_td.find("a", href=True) if minutes_td else None
            minutes_url = urljoin(self.base_url, minutes_a["href"]) if minutes_a else None

            # Video / media
            media_td = row.find("td", class_="media")
            video_a = media_td.find("a", href=True) if media_td else None
            video_url = urljoin(self.base_url, video_a["href"]) if video_a else None

            meetings.append(
                Meeting(
                    source="civicplus",
                    jurisdiction=self.jurisdiction,
                    body=body,
                    date=date_str,
                    time=None,
                    location=None,
                    meeting_details_url=agenda_url,
                    agenda_url=agenda_url,
                    minutes_url=minutes_url,
                    video_url=video_url,
                )
            )

            if limit is not None and len(meetings) >= limit:
                break

        return meetings

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def list_meetings(
        self,
        period: str | None = None,
        body: str | None = None,
        limit: int | None = None,
    ) -> list[Meeting]:
        if body:
            self.body = body
            self._category_id = None

        cid = self._find_category_id()
        url = self._search_url(period, cid)
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        return self._parse_meetings(r.text, limit)
