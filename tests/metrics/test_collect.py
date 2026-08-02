"""Tests for per-run metrics computation. No live API calls -
verify_provenance is a plain string check, and every AgendaItem here is
constructed by hand."""

from civic_scraper.metrics.collect import compute_run_metrics
from civic_scraper.models import AgendaItem, Extracted, MonetaryAmount, Person, Provenance


def _person(raw_name: str, confidence: float, source_text: str) -> Extracted[Person]:
    return Extracted(
        value=Person(raw_name=raw_name, role="councilmember"),
        confidence=confidence,
        provenance=Provenance(source_document="doc", source_text=source_text),
    )


class TestComputeRunMetrics:
    def test_rows_parsed_includes_schema_failures(self):
        m = compute_run_metrics(
            jurisdiction="San Jose", run_id="r1", agenda_items=[], schema_failures=3
        )
        assert m.rows_parsed == 3
        assert m.schema_failure_rate == 1.0

    def test_schema_failure_rate_with_no_rows_is_zero_not_a_crash(self):
        m = compute_run_metrics(jurisdiction="San Jose", run_id="r1", agenda_items=[])
        assert m.schema_failure_rate == 0.0

    def test_field_population_rate_reflects_which_items_have_facts(self):
        with_people = AgendaItem(title="t", item_type="action", people=[_person("Kamei", 0.9, "x")])
        without = AgendaItem(title="t2", item_type="action")

        m = compute_run_metrics(
            jurisdiction="San Jose", run_id="r1", agenda_items=[with_people, without]
        )

        assert m.field_population_rates["people"] == 0.5
        assert m.field_population_rates["amounts"] == 0.0

    def test_population_rates_are_zero_with_no_items(self):
        m = compute_run_metrics(jurisdiction="San Jose", run_id="r1", agenda_items=[])
        assert all(rate == 0.0 for rate in m.field_population_rates.values())

    def test_mean_confidence_and_hallucination_rate_from_raw_extractions(self):
        document_text = "Kamei moved to approve the item."
        verified = _person("Kamei", 0.9, "Kamei moved")
        fabricated = _person("Ghost", 0.7, "this text is not in the document")
        raw_item = AgendaItem(title="t", item_type="action", people=[verified, fabricated])

        m = compute_run_metrics(
            jurisdiction="San Jose",
            run_id="r1",
            agenda_items=[],
            raw_extractions=[(raw_item, document_text)],
        )

        assert m.mean_confidence == (0.9 + 0.7) / 2
        assert m.hallucination_rate == 0.5

    def test_no_raw_extractions_gives_zero_confidence_and_hallucination(self):
        m = compute_run_metrics(jurisdiction="San Jose", run_id="r1", agenda_items=[])
        assert m.mean_confidence == 0.0
        assert m.hallucination_rate == 0.0

    def test_hallucination_rate_covers_every_field_type_not_just_people(self):
        document_text = "The contract is for $500."
        fabricated_amount = Extracted(
            value=MonetaryAmount(raw_text="$9,999", kind="contract"),
            confidence=0.6,
            provenance=Provenance(source_document="doc", source_text="not present"),
        )
        raw_item = AgendaItem(title="t", item_type="action", amounts=[fabricated_amount])

        m = compute_run_metrics(
            jurisdiction="San Jose",
            run_id="r1",
            agenda_items=[],
            raw_extractions=[(raw_item, document_text)],
        )

        assert m.hallucination_rate == 1.0

    def test_review_queue_volume_passes_through(self):
        m = compute_run_metrics(
            jurisdiction="San Jose", run_id="r1", agenda_items=[], review_queue_volume=7
        )
        assert m.review_queue_volume == 7

    def test_generated_at_is_set(self):
        m = compute_run_metrics(jurisdiction="San Jose", run_id="r1", agenda_items=[])
        assert m.generated_at
