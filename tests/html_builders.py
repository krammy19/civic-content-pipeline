"""Minimal RadGrid-shaped HTML fixtures for Legistar parsing tests.

Real Legistar pages are much larger; these builders reproduce only the
structural details the parser actually keys off of (rgHeader cells,
colspan, rgPager rows, table ids) so tests stay readable.
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
