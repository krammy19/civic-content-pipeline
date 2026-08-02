"""Tests for the data-model doc generator. render_type() is tested
directly against real annotations from civic_scraper.models - the exact
type shapes the generated doc actually needs to render correctly. The
final test is the drift check itself: the committed docs/data-model.md
must match what generate() produces right now, so a model change that
isn't followed by regenerating the doc fails locally, not just in CI.
"""

from pathlib import Path
from typing import Literal

from civic_scraper.models import AgendaItem, Extracted, Meeting, Motion, Person

from checks.docs_drift import OUTPUT_PATH, generate, render_type


class TestRenderType:
    def test_plain_class(self):
        assert render_type(str) == "str"
        assert render_type(int) == "int"

    def test_optional(self):
        assert render_type(str | None) == "str | None"

    def test_list_of_class(self):
        assert render_type(list[AgendaItem]) == "list[AgendaItem]"

    def test_nested_generic(self):
        assert render_type(list[Extracted[Motion]]) == "list[Extracted[Motion]]"

    def test_literal_with_string_values_uses_double_quotes(self):
        result = render_type(Literal["a", "b"])
        assert result == 'Literal["a", "b"]'

    def test_none_type(self):
        assert render_type(type(None)) == "None"

    def test_matches_real_model_fields(self):
        # A spot check against the actual schema, not just synthetic types -
        # this is what would break if models.py's shapes ever changed.
        assert render_type(Meeting.model_fields["agenda_items"].annotation) == "list[AgendaItem]"
        assert render_type(Meeting.model_fields["time"].annotation) == "str | None"
        assert (
            render_type(Person.model_fields["role"].annotation)
            == 'Literal["mayor", "councilmember", "staff", "applicant", "public", "unknown"]'
        )


class TestGenerate:
    def test_produces_a_section_per_family(self):
        text = generate()
        assert "## Scrape output" in text
        assert "## Extraction output" in text
        assert "## Document fetch output" in text

    def test_every_model_gets_its_own_heading(self):
        text = generate()
        for model_name in ("Meeting", "Person", "Motion", "AgendaItem", "FetchedDocument"):
            assert f"### {model_name}" in text

    def test_is_idempotent(self):
        assert generate() == generate()

    def test_computed_field_is_documented(self):
        text = generate()
        assert "`is_consent` (computed)" in text


class TestCommittedFileMatchesGenerator:
    def test_docs_data_model_has_no_drift(self):
        """The actual CI check, run locally: if this fails, someone changed
        a model without running `checks/docs_drift.py --write`."""
        committed = Path(OUTPUT_PATH).read_text(encoding="utf-8")
        assert committed == generate(), (
            "docs/data-model.md is out of date - "
            "run `uv run python checks/docs_drift.py --write` and commit the result."
        )
