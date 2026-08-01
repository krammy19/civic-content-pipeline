"""Tests for digest generation. No live API calls - every generation
test injects a FakeClient; render_facts() is pure and tested directly."""

from civic_scraper.digest.generate_digest import generate_digest, render_facts
from civic_scraper.models import (
    AgendaItem,
    Extracted,
    Meeting,
    MonetaryAmount,
    Motion,
    Person,
    Provenance,
)

from tests.fake_llm_client import FakeClient


def _extracted(value, confidence=0.9, source_text="x"):
    return Extracted(
        value=value,
        confidence=confidence,
        provenance=Provenance(source_document="doc", source_text=source_text),
    )


def _agenda_item(item_number, title, item_type, **fields) -> AgendaItem:
    return AgendaItem(item_number=item_number, title=title, item_type=item_type, **fields)


class TestRenderFacts:
    def test_empty_list_says_so(self):
        assert render_facts([]) == "No items with validated facts."

    def test_renders_section_header_and_item_number(self):
        item = _agenda_item("1.1", "Proclamation", "ceremonial")
        text = render_facts([item])
        assert "## Ceremonial Items" in text
        assert "Item 1.1: Proclamation" in text

    def test_closed_session_items_are_never_rendered(self):
        item = _agenda_item("5.1", "Personnel matter", "closed_session")
        assert render_facts([item]) == "No items with validated facts."

    def test_unknown_item_type_falls_into_other_actions(self):
        item = _agenda_item("9.1", "Something odd", "unknown")
        text = render_facts([item])
        assert "## Other Actions" in text

    def test_section_order_is_fixed_regardless_of_input_order(self):
        consent = _agenda_item("2.1", "Consent thing", "consent")
        ceremonial = _agenda_item("1.1", "Proclamation", "ceremonial")
        text = render_facts([consent, ceremonial])
        assert text.index("## Ceremonial Items") < text.index("## Consent Calendar")

    def test_renders_motion_person_location_and_amount_details(self):
        item = _agenda_item(
            "2.8",
            "Contract amendment",
            "consent",
            motions=[
                _extracted(
                    Motion(
                        text="approved",
                        outcome="passed",
                        tally="11-0-0",
                        seconded_by=Person(raw_name="Kamei", role="councilmember"),
                    )
                )
            ],
            people=[_extracted(Person(raw_name="Kamei", role="councilmember"))],
            locations=[],
            amounts=[
                _extracted(
                    MonetaryAmount(raw_text="$250,000", amount_usd="250000", kind="contract")
                )
            ],
        )
        text = render_facts([item])
        assert "outcome: passed" in text
        assert "seconded by Kamei" in text
        assert "tally 11-0-0" in text
        assert "Person: Kamei (councilmember)" in text
        assert "Amount: $250,000 (contract) = $250000" in text


class TestGenerateDigest:
    def test_returns_the_tools_markdown_and_caches(self):
        from civic_scraper import llm

        meeting = Meeting(
            source="legistar",
            jurisdiction="San Jose",
            body="City Council",
            date="2026-06-09",
            agenda_items=[_agenda_item("1.1", "Proclamation", "ceremonial")],
        )
        client = FakeClient(
            tool_name="generate_digest", tool_input={"digest_markdown": "# Digest\n\nHello."}
        )

        result = generate_digest(meeting=meeting, client=client)

        assert result == "# Digest\n\nHello."
        cached = list(llm.CACHE_ROOT.glob("generate_digest.v1__*"))
        assert len(cached) == 1

    def test_prompt_survives_a_literal_brace_in_rendered_facts(self):
        # A real motion's text could contain a stray `{`/`}` from a garbled
        # source document; the prompt renderer must not choke on it the way
        # str.format() would.
        meeting = Meeting(
            source="legistar",
            jurisdiction="San Jose",
            body="City Council",
            date="2026-06-09",
            agenda_items=[
                _agenda_item(
                    "2.1",
                    "Odd item",
                    "action",
                    motions=[
                        _extracted(Motion(text="approved the {budget} line item", outcome="passed"))
                    ],
                )
            ],
        )
        client = FakeClient(tool_name="generate_digest", tool_input={"digest_markdown": "ok"})

        result = generate_digest(meeting=meeting, client=client)

        assert result == "ok"
        sent_prompt = client.messages.calls[0]["messages"][0]["content"]
        assert "{budget}" in sent_prompt
