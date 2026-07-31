"""Tests for PDF text extraction and scan detection, against real PDFs
generated on the fly with fpdf2 (no checked-in binary fixtures)."""

from civic_scraper import document_text
from fpdf import FPDF


def _pdf_with_text(tmp_path, text: str, pages: int = 1):
    pdf = FPDF()
    for _ in range(pages):
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, text)
    path = tmp_path / "sample.pdf"
    pdf.output(str(path))
    return path


def _blank_pdf(tmp_path, pages: int = 1):
    pdf = FPDF()
    for _ in range(pages):
        pdf.add_page()
    path = tmp_path / "blank.pdf"
    pdf.output(str(path))
    return path


class TestExtractPdfText:
    def test_extracts_real_text_and_is_not_flagged_as_a_scan(self, tmp_path):
        path = _pdf_with_text(
            tmp_path, "AGENDA ITEM 12: Approve the annual budget for fiscal year 2026."
        )
        text, page_count, ocr_required = document_text.extract_pdf_text(path)

        assert page_count == 1
        assert "annual budget" in text
        assert ocr_required is False

    def test_page_with_no_text_layer_is_flagged_as_ocr_required(self, tmp_path):
        # A scanned page has no embedded text at all - simulated here by a
        # genuinely blank page rather than a rendered scan image, since what
        # matters for the heuristic is the absence of an extractable text
        # layer, not the visual content.
        path = _blank_pdf(tmp_path)
        text, page_count, ocr_required = document_text.extract_pdf_text(path)

        assert page_count == 1
        assert text.strip() == ""
        assert ocr_required is True

    def test_zero_page_document_is_not_flagged_ocr_required(self, tmp_path, monkeypatch):
        # Zero pages isn't a scan - it's a different problem the caller should
        # handle separately (e.g. a fetch that returned a corrupt/empty file).
        # fpdf2 always auto-adds a page, so this exercises the page_count == 0
        # branch directly via a stub rather than a real on-disk PDF.
        class _EmptyPdf:
            pages: list = []

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(document_text.pdfplumber, "open", lambda _path: _EmptyPdf())

        text, page_count, ocr_required = document_text.extract_pdf_text(tmp_path / "empty.pdf")
        assert page_count == 0
        assert ocr_required is False

    def test_one_real_page_keeps_a_mixed_document_below_the_ocr_threshold(self, tmp_path):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, "Real agenda text on the first page, well over the threshold.")
        pdf.add_page()  # second page has no text at all
        path = tmp_path / "mixed.pdf"
        pdf.output(str(path))

        text, page_count, ocr_required = document_text.extract_pdf_text(path)
        assert page_count == 2
        assert ocr_required is False


class TestFetchAndExtract:
    def test_pdf_end_to_end(self, tmp_path, monkeypatch):
        pdf_path = _pdf_with_text(tmp_path, "Real agenda text for an end to end test.")
        monkeypatch.setattr(document_text, "fetch_document", lambda url, jurisdiction: pdf_path)

        doc = document_text.fetch_and_extract("https://city.gov/agenda.pdf", "Testville")

        assert doc.source_url == "https://city.gov/agenda.pdf"
        assert doc.local_path == str(pdf_path)
        assert doc.ocr_required is False
        assert "agenda text" in doc.text

    def test_scanned_pdf_is_flagged_not_silently_emptied(self, tmp_path, monkeypatch):
        blank_path = _blank_pdf(tmp_path)
        monkeypatch.setattr(document_text, "fetch_document", lambda url, jurisdiction: blank_path)

        doc = document_text.fetch_and_extract("https://city.gov/scanned.pdf", "Testville")

        assert doc.ocr_required is True
        assert doc.text.strip() == ""

    def test_non_pdf_document_is_read_as_plain_text(self, tmp_path, monkeypatch):
        html_path = tmp_path / "page.html"
        html_path.write_text("<html><body>hello agenda</body></html>", encoding="utf-8")
        monkeypatch.setattr(document_text, "fetch_document", lambda url, jurisdiction: html_path)

        doc = document_text.fetch_and_extract("https://city.gov/page.html", "Testville")

        assert doc.ocr_required is False
        assert "hello agenda" in doc.text
