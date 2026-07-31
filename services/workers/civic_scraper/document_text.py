"""
PDF text extraction, with layout preserved and scanned documents flagged
rather than silently returning empty text.

Municipal agenda/minutes PDFs are frequently scans of a printed or signed
document with no embedded text layer at all. A naive extractor returns ""
for those and a caller has no way to tell "empty document" apart from
"this needs OCR we haven't built yet." fetch_and_extract() always returns
which case it hit via FetchedDocument.ocr_required.
"""

from pathlib import Path

import pdfplumber

from civic_scraper.document_fetch import fetch_document
from civic_scraper.models import FetchedDocument

# Below this many non-whitespace characters per page on average, a PDF is
# treated as having no real text layer - i.e. a scan. Real born-digital
# municipal agendas run in the hundreds to thousands of characters per
# page; this threshold is deliberately far below that so it only catches
# genuinely empty/near-empty extraction, not just a sparse page.
MIN_CHARS_PER_PAGE = 20


def extract_pdf_text(path: Path) -> tuple[str, int, bool]:
    """Extract text from a PDF, preserving layout. Returns (text, page_count, ocr_required)."""
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text(layout=True) or "" for page in pdf.pages]

    page_count = len(pages)
    text = "\n\n".join(pages)

    if page_count == 0:
        return text, page_count, False

    avg_chars_per_page = len(text.strip()) / page_count
    ocr_required = avg_chars_per_page < MIN_CHARS_PER_PAGE

    return text, page_count, ocr_required


def fetch_and_extract(url: str, jurisdiction: str) -> FetchedDocument:
    """Fetch (or reuse a cached copy of) `url` and return its extracted text.

    PDFs get real extraction with scan detection. Anything else (HTML
    agenda pages, mainly) is decoded as text with ocr_required always
    False - scanning doesn't apply to a document that was never an image.
    """
    path = fetch_document(url, jurisdiction)

    if path.suffix.lower() == ".pdf":
        text, page_count, ocr_required = extract_pdf_text(path)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
        page_count = 1
        ocr_required = False

    return FetchedDocument(
        source_url=url,
        local_path=str(path),
        text=text,
        page_count=page_count,
        ocr_required=ocr_required,
    )
