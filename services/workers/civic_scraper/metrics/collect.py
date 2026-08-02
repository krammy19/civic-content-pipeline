"""
Per-run, per-city production health metrics.

This is deliberately not the eval harness (evals/): there's no gold set
and no hand-labeled ground truth here. It watches a real extraction
run's own output for signs the run itself went badly - rows that failed
schema validation, fields that came back suspiciously empty, confidence
that dropped, provenance that stopped verifying, a review queue that
suddenly grew. None of that requires knowing what the "correct" answer
was; it's watching for drift against the same city's own recent history
(see drift.py), which is what actually catches a platform template
changing out from under a connector.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from civic_scraper.extraction.agenda_item import verify_provenance
from civic_scraper.models import AgendaItem

FIELD_TYPES = ("motions", "people", "locations", "amounts")


@dataclass
class RunMetrics:
    jurisdiction: str
    run_id: str
    generated_at: str
    rows_parsed: int
    schema_failures: int
    schema_failure_rate: float
    field_population_rates: dict[str, float] = field(default_factory=dict)
    mean_confidence: float = 0.0
    hallucination_rate: float = 0.0
    review_queue_volume: int = 0


def _population_rates(agenda_items: list[AgendaItem]) -> dict[str, float]:
    if not agenda_items:
        return dict.fromkeys(FIELD_TYPES, 0.0)
    return {
        field_type: sum(1 for item in agenda_items if getattr(item, field_type)) / len(agenda_items)
        for field_type in FIELD_TYPES
    }


def compute_run_metrics(
    *,
    jurisdiction: str,
    run_id: str,
    agenda_items: list[AgendaItem],
    raw_extractions: list[tuple[AgendaItem, str]] = (),
    schema_failures: int = 0,
    review_queue_volume: int = 0,
) -> RunMetrics:
    """Summarize one run.

    `agenda_items` are the items that actually validated this run - used
    for rows-parsed and field population rates. `raw_extractions` pairs
    each *unfiltered* (pre-provenance-check) AgendaItem from this run
    with the document_text it was extracted from - the raw, not the
    filtered, output is what mean confidence and hallucination rate need
    to mean anything, for the same reason evals/run_eval.py scores raw
    output for those two numbers: filtering already removes exactly the
    fabrications a hallucination rate exists to measure, and scoring
    post-filter output would read 0% by construction.
    """
    rows_parsed = len(agenda_items) + schema_failures
    schema_failure_rate = schema_failures / rows_parsed if rows_parsed else 0.0

    all_extracted = [
        (extracted, document_text)
        for raw_item, document_text in raw_extractions
        for field_type in FIELD_TYPES
        for extracted in getattr(raw_item, field_type)
    ]
    confidences = [extracted.confidence for extracted, _ in all_extracted]
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    hallucinated = sum(
        1 for extracted, doc in all_extracted if not verify_provenance(extracted, doc)
    )
    hallucination_rate = hallucinated / len(all_extracted) if all_extracted else 0.0

    return RunMetrics(
        jurisdiction=jurisdiction,
        run_id=run_id,
        generated_at=datetime.now(UTC).isoformat(),
        rows_parsed=rows_parsed,
        schema_failures=schema_failures,
        schema_failure_rate=schema_failure_rate,
        field_population_rates=_population_rates(agenda_items),
        mean_confidence=mean_confidence,
        hallucination_rate=hallucination_rate,
        review_queue_volume=review_queue_volume,
    )
