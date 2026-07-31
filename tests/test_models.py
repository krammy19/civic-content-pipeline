"""Tests for the Pydantic schema in models.py.

Mostly pins two things that are easy to break silently in a Pydantic
migration: required fields actually reject missing/None data (dataclasses
never enforced this), and computed fields (is_consent) show up in
model_dump() output the way callers depend on.
"""

import pytest
from civic_scraper.models import (
    AgendaItem,
    Extracted,
    LegistarAgendaEntry,
    Meeting,
    Motion,
    Person,
    Provenance,
)
from pydantic import ValidationError


class TestMeeting:
    def test_constructs_with_only_required_fields(self):
        meeting = Meeting(
            source="legistar", jurisdiction="Testville", body="City Council", date="6/2/2026"
        )
        assert meeting.time is None
        assert meeting.agenda_items == []
        assert meeting.extraction_run_id is None

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Meeting(jurisdiction="Testville", body="City Council", date="6/2/2026")


class TestLegistarAgendaEntry:
    def test_title_is_required(self):
        with pytest.raises(ValidationError):
            LegistarAgendaEntry(title=None)

    def test_is_consent_true_for_consent_type(self):
        entry = LegistarAgendaEntry(title="Minutes approval", type="Consent Calendar")
        assert entry.is_consent is True

    def test_is_consent_appears_in_model_dump(self):
        # is_consent is a @computed_field specifically so serialized JSON keeps
        # carrying it, matching the old dataclass to_dict() behavior.
        entry = LegistarAgendaEntry(title="Item", type=None)
        dumped = entry.model_dump()
        assert "is_consent" in dumped
        assert dumped["is_consent"] is False


class TestExtractedProvenance:
    def test_extraction_without_provenance_is_rejected(self):
        with pytest.raises(ValidationError):
            Extracted[Person](
                value=Person(raw_name="M. Perez", role="councilmember"),
                confidence=0.9,
                # provenance omitted entirely - must be a validation error,
                # not a silently-accepted None.
            )

    def test_valid_extraction_round_trips_through_model_dump(self):
        person = Person(raw_name="M. Perez", role="councilmember")
        prov = Provenance(source_document="agenda.pdf", source_text="moved by M. Perez")
        extracted = Extracted[Person](value=person, confidence=0.85, provenance=prov)

        dumped = extracted.model_dump()
        assert dumped["value"]["raw_name"] == "M. Perez"
        assert dumped["confidence"] == 0.85
        assert dumped["provenance"]["source_text"] == "moved by M. Perez"


class TestAgendaItem:
    def test_defaults_to_no_extracted_facts(self):
        item = AgendaItem(title="Approve contract", item_type="action")
        assert item.motions == []
        assert item.people == []
        assert item.locations == []
        assert item.amounts == []

    def test_invalid_item_type_is_rejected(self):
        with pytest.raises(ValidationError):
            AgendaItem(title="Approve contract", item_type="not_a_real_type")

    def test_holds_extracted_motions(self):
        motion = Motion(text="Motion to approve", outcome="passed", tally="7-0")
        prov = Provenance(
            source_document="minutes.pdf", source_text="Motion to approve, passed 7-0"
        )
        item = AgendaItem(
            title="Approve contract",
            item_type="action",
            motions=[Extracted[Motion](value=motion, confidence=0.95, provenance=prov)],
        )
        assert item.motions[0].value.outcome == "passed"
