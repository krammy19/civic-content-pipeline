"""Tests for content-addressed document fetch/caching. No real network calls -
requests.get is always mocked."""

from unittest.mock import MagicMock, patch

import pytest
import requests as real_requests
from civic_scraper import document_fetch


@pytest.fixture(autouse=True)
def _isolated_raw_root(tmp_path, monkeypatch):
    monkeypatch.setattr(document_fetch, "RAW_ROOT", tmp_path / "data" / "raw")


def _mock_response(content: bytes, content_type: str) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.headers = {"Content-Type": content_type}
    resp.raise_for_status = MagicMock()
    return resp


class TestContentAddress:
    def test_deterministic_for_the_same_url(self):
        a = document_fetch.content_address("https://city.gov/agenda.pdf")
        b = document_fetch.content_address("https://city.gov/agenda.pdf")
        assert a == b

    def test_differs_for_different_urls(self):
        a = document_fetch.content_address("https://city.gov/agenda.pdf")
        b = document_fetch.content_address("https://city.gov/minutes.pdf")
        assert a != b


class TestInferExtension:
    def test_pdf_content_type(self):
        assert document_fetch._infer_extension("application/pdf", "https://x/doc") == ".pdf"

    def test_html_content_type_ignores_charset_suffix(self):
        ext = document_fetch._infer_extension("text/html; charset=utf-8", "https://x/doc")
        assert ext == ".html"

    def test_falls_back_to_url_suffix_when_content_type_unknown(self):
        assert document_fetch._infer_extension("", "https://x/doc.pdf") == ".pdf"

    def test_falls_back_to_bin_when_nothing_is_known(self):
        assert document_fetch._infer_extension("", "https://x/doc") == ".bin"


class TestFetchDocument:
    def test_downloads_and_writes_the_file(self, tmp_path):
        with patch("civic_scraper.document_fetch.requests.get") as mock_get:
            mock_get.return_value = _mock_response(b"%PDF-1.4 fake", "application/pdf")
            path = document_fetch.fetch_document("https://city.gov/agenda.pdf", "Testville")

        assert path.exists()
        assert path.suffix == ".pdf"
        assert path.read_bytes() == b"%PDF-1.4 fake"
        assert path.parent.name == "testville"
        mock_get.assert_called_once()

    def test_second_fetch_of_the_same_url_skips_the_network_call(self):
        url = "https://city.gov/agenda.pdf"
        with patch("civic_scraper.document_fetch.requests.get") as mock_get:
            mock_get.return_value = _mock_response(b"first", "application/pdf")
            first = document_fetch.fetch_document(url, "Testville")
            second = document_fetch.fetch_document(url, "Testville")

        assert first == second
        mock_get.assert_called_once()

    def test_different_urls_get_independent_cache_entries(self):
        with patch("civic_scraper.document_fetch.requests.get") as mock_get:
            mock_get.side_effect = [
                _mock_response(b"agenda bytes", "application/pdf"),
                _mock_response(b"minutes bytes", "application/pdf"),
            ]
            agenda = document_fetch.fetch_document("https://city.gov/a.pdf", "Testville")
            minutes = document_fetch.fetch_document("https://city.gov/m.pdf", "Testville")

        assert agenda != minutes
        assert agenda.read_bytes() == b"agenda bytes"
        assert minutes.read_bytes() == b"minutes bytes"

    def test_http_error_propagates_instead_of_writing_a_partial_file(self):
        with patch("civic_scraper.document_fetch.requests.get") as mock_get:
            resp = MagicMock()
            resp.raise_for_status.side_effect = real_requests.exceptions.HTTPError("404")
            mock_get.return_value = resp

            with pytest.raises(real_requests.exceptions.HTTPError):
                document_fetch.fetch_document("https://city.gov/missing.pdf", "Testville")

        assert document_fetch.cached_path("https://city.gov/missing.pdf", "Testville") is None
