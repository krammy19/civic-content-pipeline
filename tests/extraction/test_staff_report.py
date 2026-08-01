"""Tests for the staff-report extraction pipeline. extract_sections() runs
against a real fpdf2-generated PDF; extract_with_claude()/fetch_and_extract()
use a FakeClient - no real API calls or network."""

from unittest.mock import MagicMock, patch

from civic_scraper.extraction import staff_report
from fpdf import FPDF

from tests.fake_llm_client import FakeClient


def _report_pdf(tmp_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        0,
        8,
        "BACKGROUND\n"
        "The city proposes to build a new park on Elm Street.\n"
        "FISCAL IMPACT\n"
        "The total cost is $500,000, funded from the general fund.\n"
        "RECOMMENDATION\n"
        "Staff recommends approval.",
    )
    path = tmp_path / "report.pdf"
    pdf.output(str(path))
    return path


class TestExtractSections:
    def test_splits_on_recognized_section_headers(self, tmp_path):
        path = _report_pdf(tmp_path)
        sections = staff_report.extract_sections(path.read_bytes())

        assert "BACKGROUND" in sections
        assert "Elm Street" in sections["BACKGROUND"]
        assert "FISCAL IMPACT" in sections
        assert "$500,000" in sections["FISCAL IMPACT"]
        assert "RECOMMENDATION" in sections
        assert "Staff recommends approval" in sections["RECOMMENDATION"]

    def test_full_text_key_holds_the_whole_document(self, tmp_path):
        path = _report_pdf(tmp_path)
        sections = staff_report.extract_sections(path.read_bytes())
        assert "BACKGROUND" in sections["_full_text"]
        assert "Staff recommends approval" in sections["_full_text"]


class TestExtractWithClaude:
    def test_routes_through_the_shared_llm_wrapper_and_returns_tool_input(self):
        tool_input = {"fiscal": [], "summary": "A short summary."}
        client = FakeClient(tool_name="extract_civic_data", tool_input=tool_input)

        result = staff_report.extract_with_claude(
            {"BACKGROUND": "Some background text."}, client=client
        )

        assert result == tool_input
        assert client.call_count == 1
        sent_prompt = client.messages.calls[0]["messages"][0]["content"]
        assert "Some background text." in sent_prompt

    def test_falls_back_to_full_text_when_no_priority_sections_present(self):
        tool_input = {"summary": "ok"}
        client = FakeClient(tool_name="extract_civic_data", tool_input=tool_input)

        staff_report.extract_with_claude(
            {"_full_text": "Nothing but a full document."}, client=client
        )

        sent_prompt = client.messages.calls[0]["messages"][0]["content"]
        assert "Nothing but a full document." in sent_prompt


class TestFetchAndExtract:
    def test_downloads_extracts_and_calls_claude(self, tmp_path):
        pdf_path = _report_pdf(tmp_path)
        tool_input = {"summary": "ok"}
        llm_client = FakeClient(tool_name="extract_civic_data", tool_input=tool_input)

        resp = MagicMock()
        resp.content = pdf_path.read_bytes()
        resp.raise_for_status = MagicMock()

        with patch("civic_scraper.extraction.staff_report.requests.get", return_value=resp):
            result = staff_report.fetch_and_extract(
                "https://city.gov/report.pdf", client=llm_client
            )

        assert result == tool_input
        assert llm_client.call_count == 1
