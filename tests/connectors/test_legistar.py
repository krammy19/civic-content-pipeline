"""Tests for LegistarConnector's header-driven parsing.

Legistar table layouts are not stable across cities: optional columns
(Accessible Agenda, Agenda Packet, Accessible Minutes, Video) appear or
disappear, icon columns carry no header text, and pager rows share the
table with real data. Early positional parsing broke on exactly these
cases — see docs/engineering-log.md, 2026-05-19. These tests pin the
header-driven replacement against that same set of failure modes so a
future regression back to positional assumptions fails loudly.
"""

from bs4 import BeautifulSoup

from tests.html_builders import agenda_table, calendar_table


def _table(html: str):
    return BeautifulSoup(html, "html.parser").find("table")


class TestExtractHeaders:
    def test_expands_colspan_so_indices_align_with_cells(self, connector):
        html = (
            "<table><thead><tr>"
            '<th class="rgHeader" colspan="2">Name</th>'
            '<th class="rgHeader">Meeting Date</th>'
            "</tr></thead></table>"
        )
        headers = connector._extract_headers(_table(html))
        assert headers == ["Name", "Name", "Meeting Date"]

    def test_falls_back_to_plain_th_row_when_no_rgheader_class(self, connector):
        html = "<table><tr><th>Name</th><th>Meeting Date</th></tr></table>"
        headers = connector._extract_headers(_table(html))
        assert headers == ["Name", "Meeting Date"]

    def test_ignores_pager_row_th_cells(self, connector):
        # Pager rows use <th> too but must not be mistaken for the header row.
        html = (
            "<table>"
            '<tr class="rgPager"><th colspan="3">1 2 3</th></tr>'
            '<tr><th class="rgHeader">Name</th><th class="rgHeader">Meeting Date</th></tr>'
            "</table>"
        )
        headers = connector._extract_headers(_table(html))
        assert headers == ["Name", "Meeting Date"]

    def test_no_header_row_returns_empty_list(self, connector):
        html = "<table><tbody><tr><td>x</td></tr></tbody></table>"
        assert connector._extract_headers(_table(html)) == []


class TestResolveCol:
    def test_exact_match(self, connector):
        col_index = {"meeting date": 1, "name": 0}
        assert connector._resolve_col(col_index, "Meeting Date") == 1

    def test_falls_back_to_alias(self, connector):
        # Some Legistar sites label the body column "Body" instead of "Name".
        col_index = {"body": 0}
        assert connector._resolve_col(col_index, "Name") == 0

    def test_unknown_column_returns_none(self, connector):
        assert connector._resolve_col({"name": 0}, "Video") is None


class TestGetCell:
    def test_get_cell_text_out_of_range_returns_none(self, connector):
        # Header says the column exists, but this particular row is short a cell.
        cols = _table("<table><tr><td>only one</td></tr></table>").find("tr").find_all("td")
        col_index = {"video": 5}
        assert connector._get_cell_text(cols, col_index, "Video") is None

    def test_get_cell_link_missing_anchor_returns_none(self, connector):
        cols = _table("<table><tr><td>no link here</td></tr></table>").find("tr").find_all("td")
        col_index = {"agenda": 0}
        assert connector._get_cell_link(cols, col_index, "Agenda") is None

    def test_get_cell_link_resolves_relative_href(self, connector):
        cols = (
            _table('<table><tr><td><a href="View.ashx?ID=1">Agenda</a></td></tr></table>')
            .find("tr")
            .find_all("td")
        )
        col_index = {"agenda": 0}
        link = connector._get_cell_link(cols, col_index, "Agenda")
        assert link == "https://testville.legistar.com/View.ashx?ID=1"


class TestParseMeetings:
    FULL_HEADERS = [
        "Name",
        "Meeting Date",
        "",  # iCal icon column, no header text
        "Meeting Time",
        "Meeting Location",
        "Meeting Details",
        "Agenda",
        "Accessible Agenda",
        "Agenda Packet",
        "Minutes",
        "Accessible Minutes",
        "Video",
    ]

    def test_missing_table_returns_empty_list(self, connector):
        assert connector._parse_meetings("<html></html>", body="City Council") == []

    def test_pager_row_is_not_parsed_as_a_meeting(self, connector):
        html = calendar_table(
            headers=["Name", "Meeting Date", "Meeting Location"],
            rows=[["City Council", "6/2/2026", "Council Chambers"]],
            pager=True,
        )
        meetings = connector._parse_meetings(html, body="City Council")
        assert len(meetings) == 1
        assert meetings[0].date == "6/2/2026"

    def test_respects_limit(self, connector):
        rows = [["City Council", f"6/{d}/2026", "Council Chambers"] for d in range(1, 6)]
        html = calendar_table(headers=["Name", "Meeting Date", "Meeting Location"], rows=rows)
        meetings = connector._parse_meetings(html, body="City Council", limit=2)
        assert len(meetings) == 2

    def test_row_without_a_resolvable_date_column_is_skipped(self, connector):
        # No "Meeting Date" header at all -> every row is unparseable and skipped.
        html = calendar_table(
            headers=["Name", "Meeting Location"], rows=[["City Council", "Council Chambers"]]
        )
        assert connector._parse_meetings(html, body="City Council") == []

    def test_full_column_layout_maps_every_field_to_the_right_slot(self, connector):
        html = calendar_table(
            headers=self.FULL_HEADERS,
            rows=[
                [
                    "City Council",
                    "6/2/2026",
                    "",
                    "6:00 PM",
                    "Council Chambers",
                    '<a href="MeetingDetail.aspx?ID=1">Details</a>',
                    '<a href="View.ashx?M=A&amp;ID=1">Agenda</a>',
                    "",
                    "",
                    '<a href="View.ashx?M=M&amp;ID=1">Minutes</a>',
                    "",
                    '<a href="Video.aspx?ID=1">Video</a>',
                ]
            ],
        )
        meeting = connector._parse_meetings(html, body="City Council")[0]
        assert meeting.body == "City Council"
        assert meeting.date == "6/2/2026"
        assert meeting.time == "6:00 PM"
        assert meeting.location == "Council Chambers"
        assert meeting.meeting_details_url.endswith("MeetingDetail.aspx?ID=1")
        assert meeting.agenda_url.endswith("View.ashx?M=A&ID=1")
        assert meeting.minutes_url.endswith("View.ashx?M=M&ID=1")
        assert meeting.video_url.endswith("Video.aspx?ID=1")

    def test_minimal_column_layout_does_not_shift_fields(self, connector):
        """Regression test for the original positional-parsing bug.

        A city that omits every optional column (no icon column, no Video,
        no Accessible*/Packet columns) must still map date -> date and
        location -> location. The historical bug (docs/engineering-log.md,
        2026-05-19) put the date in `body` and a cancellation note in
        `time` when column counts didn't match what the parser assumed.
        """
        html = calendar_table(
            headers=["Name", "Meeting Date", "Meeting Time", "Meeting Location"],
            rows=[["City Council", "12/31/2026", "CANCELLED", "Council Chambers"]],
        )
        meeting = connector._parse_meetings(html, body="City Council")[0]
        assert meeting.date == "12/31/2026"
        assert meeting.time == "CANCELLED"
        assert meeting.location == "Council Chambers"
        assert meeting.body == "City Council"

    def test_missing_optional_columns_yield_none_not_misaligned_values(self, connector):
        html = calendar_table(
            headers=["Name", "Meeting Date", "Meeting Location"],
            rows=[["City Council", "6/2/2026", "Council Chambers"]],
        )
        meeting = connector._parse_meetings(html, body="City Council")[0]
        assert meeting.video_url is None
        assert meeting.minutes_url is None
        assert meeting.agenda_url is None
        assert meeting.time is None

    def test_body_column_aliased_as_name_across_cities(self, connector):
        # One city's grid calls the column "Name", another calls it "Body" -
        # both must resolve to Meeting.body via _COLUMN_ALIASES.
        html = calendar_table(
            headers=["Body", "Meeting Date"],
            rows=[["Planning Commission", "6/2/2026"]],
        )
        meeting = connector._parse_meetings(html, body="City Council")[0]
        assert meeting.body == "Planning Commission"

    def test_falls_back_to_requested_body_when_name_cell_is_blank(self, connector):
        html = calendar_table(
            headers=["Name", "Meeting Date"],
            rows=[["", "6/2/2026"]],
        )
        meeting = connector._parse_meetings(html, body="City Council")[0]
        assert meeting.body == "City Council"


class TestParseAgendaItems:
    HEADERS = ["File #", "Ver.", "Agenda Note", "Type", "Title", "Action", "Result"]

    def _cell(self, file_number: str) -> str:
        return f'<a href="LegislationDetail.aspx?ID={file_number}">{file_number}</a>'

    def test_missing_table_returns_empty_list(self, connector):
        assert connector._parse_agenda_items("<html></html>") == []

    def test_pager_row_is_not_parsed_as_an_item(self, connector):
        html = agenda_table(
            headers=self.HEADERS,
            rows=[[self._cell("24-001"), "1", "", "Ordinance", "Adopt budget", "", ""]],
            pager=True,
        )
        items = connector._parse_agenda_items(html)
        assert len(items) == 1
        assert items[0].file_number == "24-001"

    def test_row_without_file_number_link_is_skipped(self, connector):
        html = agenda_table(
            headers=self.HEADERS,
            rows=[["", "", "", "", "Discussion item, no file number", "", ""]],
        )
        assert connector._parse_agenda_items(html) == []

    def test_row_with_file_number_but_no_legislation_link_is_skipped(self, connector):
        # A File # cell with plain text (no LegislationDetail.aspx anchor) shouldn't
        # be treated as a real item.
        html = agenda_table(
            headers=self.HEADERS,
            rows=[["24-002", "", "", "", "Not linked", "", ""]],
        )
        assert connector._parse_agenda_items(html) == []

    def test_extracts_fields_and_resolves_legislation_url(self, connector):
        html = agenda_table(
            headers=self.HEADERS,
            rows=[
                [
                    self._cell("24-003"),
                    "2",
                    "Continued from last meeting",
                    "Resolution",
                    "Approve contract",
                    "Adopted",
                    "7-0-1",
                ]
            ],
        )
        item = connector._parse_agenda_items(html)[0]
        assert item.file_number == "24-003"
        assert item.version == "2"
        assert item.agenda_note == "Continued from last meeting"
        assert item.type == "Resolution"
        assert item.title == "Approve contract"
        assert item.action == "Adopted"
        assert item.result == "7-0-1"
        assert item.legislation_url.endswith("LegislationDetail.aspx?ID=24-003")

    def test_non_breaking_spaces_in_headers_and_cells_are_normalized(self, connector):
        html = agenda_table(
            headers=["File\xa0#", "Title"],
            rows=[[self._cell("24-004"), "Item\xa0with\xa0nbsp"]],
        )
        item = connector._parse_agenda_items(html)[0]
        assert item.title == "Item with nbsp"

    def test_is_consent_true_for_consent_calendar_items(self, connector):
        html = agenda_table(
            headers=self.HEADERS,
            rows=[[self._cell("24-005"), "", "", "Consent Calendar", "Minutes approval", "", ""]],
        )
        item = connector._parse_agenda_items(html)[0]
        assert item.is_consent is True

    def test_is_consent_false_when_type_is_missing(self, connector):
        html = agenda_table(
            headers=self.HEADERS,
            rows=[[self._cell("24-006"), "", "", "", "Untyped item", "", ""]],
        )
        item = connector._parse_agenda_items(html)[0]
        assert item.is_consent is False


class TestExtractLegislationLink:
    def test_requires_legislationdetail_pattern(self, connector):
        cell = _table(
            '<table><tr><td><a href="View.ashx?ID=1">Not a legislation link</a></td></tr></table>'
        ).find("td")
        assert connector._extract_legislation_link(cell) is None

    def test_matches_and_resolves_legislationdetail_link(self, connector):
        cell = _table(
            '<table><tr><td><a href="LegislationDetail.aspx?ID=9">9</a></td></tr></table>'
        ).find("td")
        link = connector._extract_legislation_link(cell)
        assert link == "https://testville.legistar.com/LegislationDetail.aspx?ID=9"
