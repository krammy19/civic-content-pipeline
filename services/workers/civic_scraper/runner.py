"""
End-to-end pipeline runner: one real meeting, from its city's calendar
to a style-checked digest and a recorded health metric - the wiring
every prior milestone built as a standalone stage but never connected.

    uv run civic run --city "San Jose" --meeting 12/09/2025
    uv run civic run --city "San Jose" --meeting 12/09/2025 --dry-run

Walks, in order: calendar (Phase 1) -> agenda items (Phase 2, Legistar
only - see resolve_city()) -> the meeting's own source document ->
per-item extraction (provenance-verified) -> confidence routing ->
digest generation -> style check -> run metrics. Every LLM call goes
through llm.py's existing cache, so a second run against the same
meeting costs nothing.

Failure behavior is deliberately uneven across stages, and that's the
point. A stage this run cannot recover from at all - the city's
calendar won't load, the requested meeting isn't in it, the meeting has
no document to fetch - raises StageError and halts the whole run with a
diagnostic naming the stage and the cause. A single agenda item failing
extraction does not halt the run; it's counted as a schema failure
(RunMetrics.schema_failures already exists to track exactly this) and
the run continues with the remaining items, the same way
evals/run_eval.py treats one gold case's schema failure as a scored
outcome rather than a crash. Distinguishing these two failure classes is
the actual design decision in this module - everything else is calling
already-built functions in order.

This module assumes `checks/` is already importable (civic_scraper.cli's
`civic run` subcommand puts the repo root on sys.path before importing
this module, the same way it already does for `civic check`/`civic eval`).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from civic_scraper.digest.generate_digest import generate_digest, render_facts
from civic_scraper.document_text import fetch_and_extract
from civic_scraper.extraction.agenda_item import (
    DEFAULT_MODEL,
    drop_unverified,
    extract_agenda_item_raw,
)
from civic_scraper.metrics.collect import RunMetrics, compute_run_metrics
from civic_scraper.metrics.store import save_run_metrics
from civic_scraper.models import AgendaItem, FetchedDocument, LegistarAgendaEntry, Meeting
from civic_scraper.review import queue
from civic_scraper.review.models import ReviewQueueItem
from civic_scraper.review.routing import ItemContext, route_agenda_item
from civic_scraper.run_all import load_cities, make_connector


class StageError(Exception):
    """Raised for a failure the run cannot recover from at all - as
    opposed to a single agenda item failing extraction, which is
    recorded as a schema failure and does not raise."""

    def __init__(self, stage: str, cause: str):
        self.stage = stage
        self.cause = cause
        super().__init__(f"[{stage}] {cause}")


def _slug(text: str) -> str:
    return text.strip().lower().replace(" ", "-").replace("/", "-")


def resolve_city(city: str) -> dict:
    matches = load_cities(connector_filter=None, city_filter=city)
    if not matches:
        raise StageError("calendar", f"no connectorized city in cities.yaml matches {city!r}")
    if len(matches) > 1:
        names = ", ".join(m["name"] for m in matches)
        raise StageError("calendar", f"{city!r} matches more than one city: {names}")
    entry = matches[0]
    if entry["connector"] != "legistar":
        raise StageError(
            "agenda",
            f"{entry['name']} uses the {entry['connector']} connector - "
            "Phase 2 (agenda items) is Legistar-only today, so `civic run` "
            "can't walk this city's meetings yet",
        )
    return entry


def resolve_meeting(entry: dict, meeting_selector: str) -> Meeting:
    conn = make_connector(entry)
    try:
        meetings = conn.list_meetings(
            period="This Month", body=entry.get("body") or "City Council", limit=20
        )
        if not any(m.meeting_details_url for m in meetings):
            meetings = conn.list_meetings(
                period="Last Month", body=entry.get("body") or "City Council", limit=20
            )
    except Exception as exc:  # noqa: BLE001 - any connector failure halts this stage
        raise StageError("calendar", f"couldn't load {entry['name']}'s calendar: {exc}") from exc

    matches = [m for m in meetings if meeting_selector in m.date and m.meeting_details_url]
    if not matches:
        raise StageError(
            "calendar",
            f"no meeting matching {meeting_selector!r} with a details URL found for "
            f"{entry['name']} in its current calendar window",
        )
    return matches[0]


def fetch_agenda_items(entry: dict, meeting: Meeting) -> list[LegistarAgendaEntry]:
    conn = make_connector(entry)
    try:
        items = conn.get_meeting_details(meeting.meeting_details_url)
    except Exception as exc:  # noqa: BLE001 - a failed detail-page fetch halts this stage
        msg = f"couldn't fetch agenda items for {meeting.date}: {exc}"
        raise StageError("agenda", msg) from exc
    if not items:
        raise StageError("agenda", f"{meeting.date}'s detail page returned zero agenda items")
    return items


def fetch_meeting_document(meeting: Meeting) -> FetchedDocument:
    url = meeting.minutes_url or meeting.agenda_url
    if not url:
        raise StageError(
            "document", f"{meeting.jurisdiction} {meeting.date} has no minutes_url or agenda_url"
        )
    try:
        document = fetch_and_extract(url, meeting.jurisdiction)
    except Exception as exc:  # noqa: BLE001 - a failed fetch/extract halts this stage
        raise StageError("document", f"couldn't fetch/extract {url}: {exc}") from exc
    if document.ocr_required:
        raise StageError(
            "document",
            f"{url} appears to be a scan with no text layer (ocr_required=True) - "
            "this pipeline has no OCR step yet",
        )
    return document


@dataclass
class ExtractionOutcome:
    published: list[AgendaItem] = field(default_factory=list)
    queued: list[ReviewQueueItem] = field(default_factory=list)
    raw_extractions: list[tuple[AgendaItem, str]] = field(default_factory=list)
    schema_failures: int = 0


def extract_and_route(
    entries: list[LegistarAgendaEntry],
    *,
    meeting: Meeting,
    document: FetchedDocument,
    model: str,
) -> ExtractionOutcome:
    outcome = ExtractionOutcome()

    for index, entry in enumerate(entries):
        if not entry.title:
            continue
        try:
            raw_item = extract_agenda_item_raw(
                item_title=entry.title,
                item_number=entry.file_number,
                document_text=document.text,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001 - one bad item is a scored failure, not a crash
            print(f"  [extract] FAIL {entry.file_number or index}: {exc}")
            outcome.schema_failures += 1
            continue

        outcome.raw_extractions.append((raw_item, document.text))
        filtered_item = drop_unverified(raw_item, document.text, document.source_url)

        case_id = (
            f"{_slug(meeting.jurisdiction)}-{_slug(meeting.date)}-{entry.file_number or index}"
        )
        context = ItemContext(
            case_id=case_id,
            jurisdiction=meeting.jurisdiction,
            body=meeting.body,
            meeting_date=meeting.date,
            source_document=document.source_url,
            document_text=document.text,
        )
        result = route_agenda_item(filtered_item, context=context)
        outcome.published.append(result.published)
        outcome.queued.extend(result.queued)

    return outcome


@dataclass
class RunOutcome:
    meeting: Meeting
    digest: str | None
    style_findings: list
    metrics: RunMetrics
    metrics_path: str


def run(
    *,
    city: str,
    meeting_selector: str,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> RunOutcome | dict:
    """Runs the full pipeline for one meeting. Returns a `dict` describing
    the plan (and spends nothing) when `dry_run` is True, otherwise a
    `RunOutcome` after every stage below has completed.
    """
    print("[calendar] resolving city and meeting...")
    entry = resolve_city(city)
    meeting = resolve_meeting(entry, meeting_selector)
    print(f"[calendar] {meeting.jurisdiction} {meeting.body}, {meeting.date}")

    print("[agenda] fetching agenda items...")
    entries = fetch_agenda_items(entry, meeting)
    titled = [e for e in entries if e.title]
    print(f"[agenda] {len(entries)} item(s) ({len(titled)} with a title to extract)")

    print("[document] fetching the meeting's source document...")
    document = fetch_meeting_document(meeting)
    print(
        f"[document] {document.source_url} "
        f"({len(document.text)} chars, {document.page_count} pages)"
    )

    if dry_run:
        return {
            "city": entry["name"],
            "meeting_date": meeting.date,
            "meeting_details_url": meeting.meeting_details_url,
            "document_url": document.source_url,
            "document_chars": len(document.text),
            "items_to_extract": len(titled),
            "estimated_api_calls": len(titled),
        }

    print(f"[extract] extracting {len(titled)} item(s) with model={model}...")
    extraction = extract_and_route(entries, meeting=meeting, document=document, model=model)
    print(
        f"[extract] {len(extraction.published)} published, "
        f"{len(extraction.queued)} queued for review, "
        f"{extraction.schema_failures} schema failure(s)"
    )
    if extraction.queued:
        queue.save_items(extraction.queued)

    run_meeting = meeting.model_copy(update={"agenda_items": extraction.published})

    print("[digest] generating digest...")
    digest = generate_digest(meeting=run_meeting)
    print(f"[digest] {len(digest)} chars")

    print("[style-check] checking digest against the style guide...")
    from checks.style_check import check_deterministic, context_from_agenda_items, judge_style

    style_context = context_from_agenda_items(run_meeting.agenda_items)
    facts_block = render_facts(run_meeting.agenda_items)
    findings = check_deterministic(digest, style_context)
    findings += judge_style(digest_markdown=digest, facts_block=facts_block, model=model)
    high = [f for f in findings if f.severity == "high"]
    print(f"[style-check] {len(findings)} finding(s), {len(high)} high-severity")

    print("[metrics] recording run health metrics...")
    run_id = f"run-{_slug(meeting.date)}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    run_metrics = compute_run_metrics(
        jurisdiction=meeting.jurisdiction,
        run_id=run_id,
        agenda_items=extraction.published,
        raw_extractions=extraction.raw_extractions,
        schema_failures=extraction.schema_failures,
        review_queue_volume=len(extraction.queued),
    )
    metrics_path = save_run_metrics(run_metrics)
    print(f"[metrics] wrote {metrics_path}")

    return RunOutcome(
        meeting=run_meeting,
        digest=digest,
        style_findings=findings,
        metrics=run_metrics,
        metrics_path=str(metrics_path),
    )
