"""Tests for confidence-based publish/review routing."""

from civic_scraper.models import AgendaItem, Extracted, Location, Person, Provenance
from civic_scraper.review.routing import ItemContext, route_agenda_item

DOCUMENT_TEXT = (
    "Councilmember Perez moved to approve the item. Seconded by Councilmember Doan. "
    "The project site is at 419 Lano Street."
)


def _context(**overrides) -> ItemContext:
    base = dict(
        case_id="test-case",
        jurisdiction="San Jose",
        body="City Council",
        meeting_date="2026-01-01",
        source_document="doc",
        document_text=DOCUMENT_TEXT,
    )
    base.update(overrides)
    return ItemContext(**base)


def _person(raw_name: str, source_text: str, confidence: float) -> Extracted[Person]:
    return Extracted[Person](
        value=Person(raw_name=raw_name, role="councilmember"),
        confidence=confidence,
        provenance=Provenance(source_document="doc", source_text=source_text),
    )


def _location(raw_text: str, confidence: float) -> Extracted[Location]:
    return Extracted[Location](
        value=Location(raw_text=raw_text),
        confidence=confidence,
        provenance=Provenance(source_document="doc", source_text=raw_text),
    )


class TestRouteAgendaItem:
    def test_high_confidence_fields_are_published_not_queued(self):
        item = AgendaItem(
            title="t",
            item_type="action",
            people=[_person("Perez", "Councilmember Perez moved", 0.97)],
        )

        result = route_agenda_item(item, context=_context())

        assert len(result.published.people) == 1
        assert result.published.people[0].value.raw_name == "Perez"
        assert result.queued == []

    def test_low_confidence_field_is_held_back_and_queued(self):
        item = AgendaItem(
            title="t",
            item_type="action",
            people=[_person("Doan", "Councilmember Doan", 0.6)],
        )

        result = route_agenda_item(item, context=_context())

        assert result.published.people == []
        assert len(result.queued) == 1
        queued = result.queued[0]
        assert queued.field_type == "people"
        assert queued.value["raw_name"] == "Doan"
        assert queued.confidence == 0.6
        assert queued.status == "pending"

    def test_mixed_confidence_splits_correctly_within_one_field_type(self):
        item = AgendaItem(
            title="t",
            item_type="action",
            people=[
                _person("Perez", "Councilmember Perez moved", 0.97),
                _person("Doan", "Councilmember Doan", 0.6),
            ],
        )

        result = route_agenda_item(item, context=_context())

        assert len(result.published.people) == 1
        assert result.published.people[0].value.raw_name == "Perez"
        assert len(result.queued) == 1
        assert result.queued[0].value["raw_name"] == "Doan"

    def test_thresholds_are_independent_per_field_type(self):
        item = AgendaItem(
            title="t",
            item_type="action",
            people=[_person("Doan", "Councilmember Doan", 0.8)],
            locations=[_location("419 Lano Street", 0.8)],
        )

        result = route_agenda_item(
            item,
            context=_context(),
            thresholds={"motions": 0.9, "people": 0.7, "locations": 0.9, "amounts": 0.9},
        )

        # people threshold (0.7) is cleared, locations threshold (0.9) is not.
        assert len(result.published.people) == 1
        assert result.published.locations == []
        assert len(result.queued) == 1
        assert result.queued[0].field_type == "locations"

    def test_queued_item_carries_full_review_context(self):
        item = AgendaItem(
            item_number="4.2",
            title="Approve the contract",
            item_type="action",
            people=[_person("Doan", "Councilmember Doan", 0.6)],
        )

        result = route_agenda_item(
            item,
            context=_context(
                case_id="sj-cc-2026-01-01-4.2",
                jurisdiction="San Jose",
                body="City Council",
                meeting_date="2026-01-01",
                source_document="san-jose-city-council-2026-01-01-minutes",
            ),
        )

        queued = result.queued[0]
        assert queued.queue_id == "sj-cc-2026-01-01-4.2-people-0"
        assert queued.item_number == "4.2"
        assert queued.item_title == "Approve the contract"
        assert queued.jurisdiction == "San Jose"
        assert queued.body == "City Council"
        assert queued.meeting_date == "2026-01-01"
        assert queued.source_document == "san-jose-city-council-2026-01-01-minutes"
        assert queued.document_text == DOCUMENT_TEXT
        assert queued.provenance.source_text == "Councilmember Doan"

    def test_empty_agenda_item_publishes_nothing_and_queues_nothing(self):
        item = AgendaItem(title="t", item_type="action")
        result = route_agenda_item(item, context=_context())
        assert result.published.people == []
        assert result.queued == []
