"""Tests for the two-tier style checker. Tier 1 is tested directly
against synthetic digest text - no fixtures beyond plain strings. Tier 2
(judge_style) injects a FakeClient - no live API calls."""

from civic_scraper.models import AgendaItem, Extracted, Person, Provenance

from checks.style_check import (
    StyleContext,
    check_banned_constructions,
    check_citations,
    check_deterministic,
    check_first_reference_titles,
    check_length_ceilings,
    check_structure,
    context_from_agenda_items,
    flesch_kincaid_grade,
    judge_style,
)
from tests.fake_llm_client import FakeClient

GOOD_DIGEST = """# San Jose City Council -- June 9, 2026

## Overview

The Council heard 8 items. One raised a contract by $250,000.

## Consent Calendar

The Council raised its deal with CSG Advisors by $250,000 (Item 2.8). \
Councilmember Rosemary Kamei backed the motion (Item 2.8).

Full agenda and minutes are available from the City Clerk.
"""


def _context(**overrides) -> StyleContext:
    base = {
        "known_item_numbers": {"2.8"},
        "people": [{"raw_name": "Rosemary Kamei", "role": "councilmember"}],
    }
    base.update(overrides)
    return StyleContext(**base)


class TestCheckStructure:
    def test_clean_digest_has_no_structure_findings(self):
        assert check_structure(GOOD_DIGEST) == []

    def test_missing_level_one_header_is_flagged(self):
        text = "## Overview\n\nSomething happened.\n"
        rules = [f.rule for f in check_structure(text)]
        assert "missing_header" in rules

    def test_missing_overview_is_flagged(self):
        text = "# Title\n\n## Consent Calendar\n\nSomething happened (Item 1.1).\n"
        rules = [f.rule for f in check_structure(text)]
        assert "missing_overview" in rules

    def test_out_of_order_sections_is_flagged(self):
        text = (
            "# Title\n\n## Overview\n\nx\n\n"
            "## Reports\n\nx\n\n"
            "## Ceremonial Items\n\nx (Item 1.1).\n"
        )
        rules = [f.rule for f in check_structure(text)]
        assert "section_order" in rules

    def test_unrecognized_heading_is_flagged_low_severity(self):
        text = "# Title\n\n## Overview\n\nx\n\n## Closing Remarks\n\nx\n"
        findings = [f for f in check_structure(text) if f.rule == "unexpected_section"]
        assert len(findings) == 1
        assert findings[0].severity == "low"


class TestCheckCitations:
    def test_clean_digest_has_no_citation_findings(self):
        assert check_citations(GOOD_DIGEST, {"2.8"}) == []

    def test_dollar_claim_with_no_citation_is_flagged(self):
        text = "## Consent Calendar\n\nThe Council approved a $250,000 contract increase.\n"
        findings = check_citations(text, {"2.8"})
        assert any(f.rule == "missing_citation" for f in findings)

    def test_outcome_verb_with_no_citation_is_flagged(self):
        text = "## Consent Calendar\n\nThe Council adopted the ordinance.\n"
        findings = check_citations(text, {"2.2"})
        assert any(f.rule == "missing_citation" for f in findings)

    def test_citation_to_unknown_item_is_flagged_even_without_a_signal_word(self):
        text = "## Consent Calendar\n\nYour neighborhood will see changes (Item 99.9).\n"
        findings = check_citations(text, {"2.8"})
        assert any(f.rule == "unknown_citation" for f in findings)

    def test_overview_claims_are_exempt_from_the_citation_requirement(self):
        text = (
            "## Overview\n\nThe Council approved a $250,000 contract increase.\n\n"
            "## Consent Calendar\n\nThe Council approved the increase (Item 2.8).\n"
        )
        findings = check_citations(text, {"2.8"})
        assert findings == []

    def test_sentence_with_no_dollar_or_outcome_verb_is_not_flagged(self):
        text = "## Overview\n\nThe meeting began at 1:30 PM.\n"
        assert check_citations(text, {"2.8"}) == []

    def test_abbreviation_period_does_not_sever_the_citation_from_its_claim(self):
        # Real case found via a live-generated digest: "Ordinance No. 31328"
        # was misread as a sentence boundary, splitting the claim from the
        # "(Item 2.2)" citation that actually appears later in the sentence.
        text = (
            "## Consent Calendar\n\n"
            "The Council adopted Ordinance No. 31328 establishing the "
            "district, passing 11-0-0 (Item 2.2).\n"
        )
        assert check_citations(text, {"2.2"}) == []

    def test_other_common_abbreviations_do_not_sever_citations(self):
        text = (
            "## Other Actions\n\n"
            "The Council awarded a contract to Blocka Construction Inc. "
            "in the amount of $11,678,000 (Item 6.1).\n"
        )
        assert check_citations(text, {"6.1"}) == []


class TestCheckBannedConstructions:
    def test_clean_text_has_no_findings(self):
        assert check_banned_constructions("The Council approved the item.") == []

    def test_passive_hiding_the_actor_is_flagged(self):
        findings = check_banned_constructions("The motion was approved.")
        assert any(f.rule == "banned_construction" for f in findings)

    def test_value_judgment_adjective_is_flagged(self):
        findings = check_banned_constructions("This was a historic vote.")
        assert any("historic" in f.message for f in findings)

    def test_exclamation_point_is_flagged(self):
        findings = check_banned_constructions("The Council approved the item!")
        assert any("exclamation" in f.message for f in findings)

    def test_direct_address_is_flagged(self):
        findings = check_banned_constructions("This decision affects your neighborhood.")
        assert any("direct address" in f.message for f in findings)


class TestCheckLengthCeilings:
    def test_short_text_has_no_findings(self):
        assert check_length_ceilings("## Overview\n\nShort and fine.\n") == []

    def test_long_sentence_is_flagged(self):
        long_sentence = "The Council " + ("very " * 45) + "approved the item."
        findings = check_length_ceilings(f"## Overview\n\n{long_sentence}\n")
        assert any(f.rule == "sentence_too_long" for f in findings)

    def test_long_paragraph_is_flagged(self):
        long_paragraph = " ".join(f"Word{i}." for i in range(200))
        findings = check_length_ceilings(f"## Overview\n\n{long_paragraph}\n")
        assert any(f.rule == "paragraph_too_long" for f in findings)


class TestReadingLevel:
    def test_simple_text_scores_a_low_grade(self):
        simple = "The cat sat. The dog ran. It was fun."
        assert flesch_kincaid_grade(simple) < 6

    def test_dense_text_can_exceed_the_target(self):
        dense = (
            "The municipality's appropriation ordinance amendments necessitate "
            "comprehensive reconciliation across multiple interdepartmental "
            "budgetary classifications and administrative jurisdictional "
            "boundaries."
        )
        assert flesch_kincaid_grade(dense) > 12

    def test_empty_text_is_zero_not_a_crash(self):
        assert flesch_kincaid_grade("") == 0.0


class TestCheckFirstReferenceTitles:
    def test_titled_first_reference_has_no_finding(self):
        text = "## Consent Calendar\n\nCouncilmember Rosemary Kamei seconded the motion (Item 2.8)."
        people = [{"raw_name": "Rosemary Kamei", "role": "councilmember"}]
        assert check_first_reference_titles(text, people) == []

    def test_bare_surname_before_any_titled_reference_is_flagged(self):
        text = "## Consent Calendar\n\nKamei seconded the motion (Item 2.8)."
        people = [{"raw_name": "Rosemary Kamei", "role": "councilmember"}]
        findings = check_first_reference_titles(text, people)
        assert len(findings) == 1
        assert findings[0].rule == "missing_first_reference_title"

    def test_mayor_titled_correctly_has_no_finding(self):
        text = "Mayor Matt Mahan called the meeting to order."
        people = [{"raw_name": "Matt Mahan", "role": "mayor"}]
        assert check_first_reference_titles(text, people) == []

    def test_staff_role_is_not_checked(self):
        # No single canonical title word exists for "staff" - see the
        # module's docstring on _ROLE_TITLES.
        text = "Jennifer Maguire gave a report."
        people = [{"raw_name": "Jennifer Maguire", "role": "staff"}]
        assert check_first_reference_titles(text, people) == []

    def test_person_never_mentioned_is_not_flagged(self):
        people = [{"raw_name": "Someone Else", "role": "councilmember"}]
        assert check_first_reference_titles("## Overview\n\nNothing here.", people) == []


class TestCheckDeterministic:
    def test_clean_digest_produces_no_findings(self):
        assert check_deterministic(GOOD_DIGEST, _context()) == []

    def test_runs_every_sub_check(self):
        text = "## Consent Calendar\n\nKamei's motion was approved!"
        findings = check_deterministic(text, _context())
        rules = {f.rule for f in findings}
        assert "missing_header" in rules
        assert "missing_overview" in rules
        assert "banned_construction" in rules
        assert "missing_first_reference_title" in rules


class TestContextFromAgendaItems:
    def test_builds_known_item_numbers_and_deduplicated_people(self):
        person = Extracted(
            value=Person(raw_name="Rosemary Kamei", role="councilmember"),
            confidence=0.9,
            provenance=Provenance(source_document="doc", source_text="x"),
        )
        item_a = AgendaItem(item_number="2.8", title="t", item_type="consent", people=[person])
        item_b = AgendaItem(item_number="2.9", title="t2", item_type="consent", people=[person])

        context = context_from_agenda_items([item_a, item_b])

        assert context.known_item_numbers == {"2.8", "2.9"}
        assert context.people == [{"raw_name": "Rosemary Kamei", "role": "councilmember"}]


class TestJudgeStyle:
    def test_parses_findings_from_the_tool_response(self):
        tool_input = {
            "findings": [
                {
                    "rule": "editorializing",
                    "severity": "high",
                    "message": "Implies the decision was a win for residents.",
                    "excerpt": "a welcome relief for residents",
                }
            ]
        }
        client = FakeClient(tool_name="report_style_findings", tool_input=tool_input)

        findings = judge_style(digest_markdown=GOOD_DIGEST, facts_block="facts", client=client)

        assert len(findings) == 1
        assert findings[0].rule == "editorializing"
        assert findings[0].severity == "high"

    def test_empty_findings_list_is_valid(self):
        client = FakeClient(tool_name="report_style_findings", tool_input={"findings": []})
        assert judge_style(digest_markdown=GOOD_DIGEST, facts_block="facts", client=client) == []

    def test_caches_under_its_own_prompt_version(self):
        from civic_scraper import llm

        client = FakeClient(tool_name="report_style_findings", tool_input={"findings": []})
        judge_style(digest_markdown=GOOD_DIGEST, facts_block="facts", client=client)
        cached = list(llm.CACHE_ROOT.glob("judge_digest_style.v1__*"))
        assert len(cached) == 1
