"""Tests for LLM-based agenda item extraction and provenance verification -
the M2 hallucination detector. No real API calls; every test injects a
FakeClient."""

from civic_scraper.extraction.agenda_item import extract_agenda_item, verify_provenance
from civic_scraper.models import Extracted, Person, Provenance

from tests.fake_llm_client import FakeClient

DOCUMENT_TEXT = (
    "AGENDA ITEM 5: Approve construction contract.\n"
    "Councilmember Perez moved to approve the contract; seconded by Councilmember Diaz.\n"
    "Motion passed 7-0.\n"
)


def _person_extraction(raw_name: str, source_text: str, role: str = "councilmember") -> dict:
    return {
        "value": {"raw_name": raw_name, "canonical_name": None, "role": role},
        "confidence": 0.9,
        # source_document deliberately wrong/placeholder here - extract_agenda_item
        # must overwrite it with the real, known value regardless of this.
        "provenance": {"source_document": "whatever the model said", "source_text": source_text},
    }


def _tool_input(**overrides) -> dict:
    base = {
        "item_number": "5",
        "title": "Approve construction contract",
        "item_type": "action",
        "motions": [],
        "people": [],
        "locations": [],
        "amounts": [],
    }
    base.update(overrides)
    return base


class TestVerifyProvenance:
    def test_true_when_source_text_is_verbatim_in_the_document(self):
        extracted = Extracted[Person](
            value=Person(raw_name="M. Perez", role="councilmember"),
            confidence=0.9,
            provenance=Provenance(source_document="doc", source_text="Councilmember Perez moved"),
        )
        assert verify_provenance(extracted, DOCUMENT_TEXT) is True

    def test_false_when_source_text_is_fabricated(self):
        extracted = Extracted[Person](
            value=Person(raw_name="Ghost", role="public"),
            confidence=0.9,
            provenance=Provenance(
                source_document="doc", source_text="this sentence appears nowhere"
            ),
        )
        assert verify_provenance(extracted, DOCUMENT_TEXT) is False


class TestExtractAgendaItem:
    def test_valid_extraction_round_trips_and_overwrites_source_document(self):
        tool_input = _tool_input(
            people=[_person_extraction("Perez", "Councilmember Perez moved")],
        )
        client = FakeClient(tool_name="extract_agenda_item", tool_input=tool_input)

        item = extract_agenda_item(
            item_title="Approve construction contract",
            item_number="5",
            source_document="https://city.gov/agenda.pdf",
            document_text=DOCUMENT_TEXT,
            client=client,
        )

        assert item.title == "Approve construction contract"
        assert item.item_type == "action"
        assert len(item.people) == 1
        assert item.people[0].value.raw_name == "Perez"
        # Real, known document identifier wins over whatever the model produced.
        assert item.people[0].provenance.source_document == "https://city.gov/agenda.pdf"

    def test_fabricated_extraction_is_dropped_entirely(self):
        tool_input = _tool_input(
            people=[
                _person_extraction("Ghost", "a sentence that is not in the document", role="public")
            ]
        )
        client = FakeClient(tool_name="extract_agenda_item", tool_input=tool_input)

        item = extract_agenda_item(
            item_title="t",
            item_number=None,
            source_document="doc",
            document_text=DOCUMENT_TEXT,
            client=client,
        )

        assert item.people == []

    def test_mixed_batch_keeps_only_the_verified_entries(self):
        tool_input = _tool_input(
            people=[
                _person_extraction("Perez", "Councilmember Perez moved"),
                _person_extraction("Ghost", "fabricated span not in the source", role="public"),
            ]
        )
        client = FakeClient(tool_name="extract_agenda_item", tool_input=tool_input)

        item = extract_agenda_item(
            item_title="t",
            item_number=None,
            source_document="doc",
            document_text=DOCUMENT_TEXT,
            client=client,
        )

        assert len(item.people) == 1
        assert item.people[0].value.raw_name == "Perez"

    def test_empty_extraction_lists_are_valid(self):
        client = FakeClient(tool_name="extract_agenda_item", tool_input=_tool_input())
        item = extract_agenda_item(
            item_title="t",
            item_number=None,
            source_document="doc",
            document_text=DOCUMENT_TEXT,
            client=client,
        )
        assert item.motions == []
        assert item.people == []
        assert item.locations == []
        assert item.amounts == []

    def test_caches_under_its_own_prompt_version(self):
        from civic_scraper import llm

        client = FakeClient(tool_name="extract_agenda_item", tool_input=_tool_input())
        extract_agenda_item(
            item_title="t",
            item_number=None,
            source_document="doc",
            document_text=DOCUMENT_TEXT,
            client=client,
        )
        cached = list(llm.CACHE_ROOT.glob("extract_agenda_item.v1__*"))
        assert len(cached) == 1
