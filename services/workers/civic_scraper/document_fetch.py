"""
Content-addressed document fetch: download agenda/minutes documents
(PDF or HTML) to data/raw/{jurisdiction}/, skipping re-downloads of
anything already cached under the same URL.

The cache key is a hash of the URL itself, not the response body — this
is deliberate. It lets fetch_document() check "have we already fetched
this URL" with zero network calls (a directory glob), which matters once
this runs across hundreds of documents per city.
"""

import hashlib
from pathlib import Path

import requests

from .paths import DATA_RAW as RAW_ROOT

_HEADERS = {"User-Agent": "Mozilla/5.0 (civic-engagement-app)"}

_CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
}


def content_address(url: str) -> str:
    """Stable cache key for a URL, independent of query-param ordering quirks."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _infer_extension(content_type: str, url: str) -> str:
    mime = content_type.split(";")[0].strip().lower()
    if mime in _CONTENT_TYPE_EXTENSIONS:
        return _CONTENT_TYPE_EXTENSIONS[mime]
    suffix = Path(url.split("?", 1)[0]).suffix
    return suffix if suffix else ".bin"


def cached_path(url: str, jurisdiction: str) -> Path | None:
    """Return the local path for `url` if it's already been fetched, else None."""
    slug = jurisdiction.lower().replace(" ", "-")
    out_dir = RAW_ROOT / slug
    digest = content_address(url)
    matches = sorted(out_dir.glob(f"{digest}.*"))
    return matches[0] if matches else None


def fetch_document(url: str, jurisdiction: str, timeout: int = 30) -> Path:
    """Download `url` to data/raw/<jurisdiction-slug>/<content-hash><ext>.

    Returns the existing local path without making a request if this URL
    was already fetched for this jurisdiction. Raises for HTTP errors via
    requests' raise_for_status() - callers decide how to handle failures,
    this function never silently returns a partial/missing file.
    """
    existing = cached_path(url, jurisdiction)
    if existing is not None:
        return existing

    slug = jurisdiction.lower().replace(" ", "-")
    out_dir = RAW_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()

    ext = _infer_extension(resp.headers.get("Content-Type", ""), url)
    out_path = out_dir / f"{content_address(url)}{ext}"
    out_path.write_bytes(resp.content)
    return out_path
