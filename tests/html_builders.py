"""Minimal HTML fixtures for connector parsing tests.

Real pages are much larger; these builders reproduce only the
structural details each parser actually keys off of (rgHeader cells,
colspan, rgPager rows for Legistar's RadGrid; catAgendaRow, aria-label,
minutes/media <td> classes for CivicPlus's AgendaCenter) so tests stay
readable.
"""


def calendar_table(headers: list[str], rows: list[list[str]], pager: bool = False) -> str:
    """headers: header text per column ("" for icon/unlabeled columns).
    rows: one list of raw <td> inner HTML per row (pre-formed <a> tags allowed).
    pager: append a trailing rgPager row, as real Legistar pages do.
    """
    header_html = "".join(f'<th class="rgHeader">{h}</th>' for h in headers)
    row_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    pager_html = (
        f'<tr class="rgPager"><td colspan="{len(headers)}">1 2 3 ...</td></tr>' if pager else ""
    )
    return f"""
    <table id="ctl00_ContentPlaceHolder1_gridCalendar_ctl00">
      <thead><tr>{header_html}</tr></thead>
      <tbody>{row_html}{pager_html}</tbody>
    </table>
    """


def agenda_table(headers: list[str], rows: list[list[str]], pager: bool = False) -> str:
    """Same shape as calendar_table(), but for the meeting-detail (agenda item) grid."""
    header_html = "".join(f'<th class="rgHeader">{h}</th>' for h in headers)
    row_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    pager_html = (
        f'<tr class="rgPager"><td colspan="{len(headers)}">1 2 3 ...</td></tr>' if pager else ""
    )
    return f"""
    <table id="ctl00_ContentPlaceHolder1_gridMain_ctl00">
      <thead><tr>{header_html}</tr></thead>
      <tbody>{row_html}{pager_html}</tbody>
    </table>
    """


def civicplus_agenda_row(
    *,
    date_label: str = "Agenda for May 6, 2025 City Council Meeting.",
    agenda_href: str | None = "/AgendaCenter/ViewFile/Agenda/_05062025-100?html=true",
    agenda_text: str = "Agenda for the May 6, 2025 City Council Meeting.",
    minutes_href: str | None = None,
    video_href: str | None = None,
) -> str:
    """One <tr class="catAgendaRow"> from a real CivicPlus AgendaCenter
    search-results page. Pass agenda_href=None to reproduce a row with no
    agenda link - list_meetings() must survive that without crashing,
    same as a Legistar row missing an optional column.
    """
    agenda_cell = f'<a href="{agenda_href}">{agenda_text}</a>' if agenda_href else ""
    minutes_cell = f'<a href="{minutes_href}">Minutes</a>' if minutes_href else ""
    media_cell = f'<a href="{video_href}">Video</a>' if video_href else ""
    return f"""
    <tr class="catAgendaRow">
      <td><strong aria-label="{date_label}">{date_label}</strong></td>
      <td>{agenda_cell}</td>
      <td class="minutes">{minutes_cell}</td>
      <td class="media">{media_cell}</td>
    </tr>
    """


def civicplus_non_data_row() -> str:
    """A row CivicPlus's own template sometimes emits with no <strong
    aria-label> at all (an empty spacer row) - the equivalent of a
    Legistar pager row mixed into the same table as real data."""
    return '<tr class="catAgendaRow"><td colspan="4">&nbsp;</td></tr>'


def civicplus_search_results(rows: list[str]) -> str:
    return f"<html><body><table>{''.join(rows)}</table></body></html>"


def civicplus_category_checkboxes(categories: dict[str, str]) -> str:
    """categories: {label text: checkbox value}, matching the
    AgendaCenter page's `<input name="chkCategoryID">` + `<label for=...>`
    pairing discover_categories() parses."""
    boxes = []
    for i, (label, value) in enumerate(categories.items()):
        cid = f"cat{i}"
        boxes.append(
            f'<input type="checkbox" name="chkCategoryID" id="{cid}" value="{value}">'
            f'<label for="{cid}">{label}</label>'
        )
    return f"<html><body>{''.join(boxes)}</body></html>"
