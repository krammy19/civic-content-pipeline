"""
LLM-based structured extraction of one agenda item's motions, people,
locations, and dollar amounts from its source document text.

Uses forced tool use against AgendaItem's own Pydantic JSON schema
(model_json_schema()), so a successful response conforms to the model by
construction - there is no free-text parsing step to get wrong.

Every extracted value's provenance is verified deterministically before
it's trusted: verify_provenance() checks that provenance.source_text
actually appears verbatim in the source document. A value whose quoted
span isn't really there was fabricated, and gets dropped rather than
included with a false sense of confidence. This check is a plain string
containment test - not another LLM call - specifically so it can't
itself hallucinate.
"""

from pathlib import Path

from civic_scraper.llm import call_with_tool
from civic_scraper.models import AgendaItem, Extracted

PROMPT_VERSION = "extract_agenda_item.v1"
PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts" / f"{PROMPT_VERSION}.md"
DEFAULT_MODEL = "claude-sonnet-5"

_TOOL_NAME = "extract_agenda_item"


def verify_provenance(extracted: Extracted, document_text: str) -> bool:
    """True if `extracted.provenance.source_text` appears verbatim in `document_text`.

    Deterministic substring check - the hallucination detector. A model
    that names a source_text span not actually present in the document
    fabricated it, full stop.
    """
    return extracted.provenance.source_text in document_text


def _tool_schema() -> dict:
    return {
        "name": _TOOL_NAME,
        "description": (
            "Extract structured facts (motions, people, locations, dollar amounts) "
            "from one agenda item's source text."
        ),
        "input_schema": AgendaItem.model_json_schema(),
    }


def drop_unverified(item: AgendaItem, document_text: str, source_document: str) -> AgendaItem:
    """Filter every Extracted[T] list down to entries with verified provenance,
    and overwrite provenance.source_document with the real, known document
    identifier rather than trusting whatever the model put there.

    Public (not just an internal helper of extract_agenda_item()) because
    the eval harness needs both the raw and the filtered result from the
    same extraction call: raw to measure hallucination rate and
    calibration, filtered to measure the precision/recall a caller would
    actually see in production.
    """

    def _clean(extracted_list):
        kept = []
        for extracted in extracted_list:
            if not verify_provenance(extracted, document_text):
                continue
            kept.append(
                extracted.model_copy(
                    update={
                        "provenance": extracted.provenance.model_copy(
                            update={"source_document": source_document}
                        )
                    }
                )
            )
        return kept

    return item.model_copy(
        update={
            "motions": _clean(item.motions),
            "people": _clean(item.people),
            "locations": _clean(item.locations),
            "amounts": _clean(item.amounts),
        }
    )


def extract_agenda_item_raw(
    *,
    item_title: str,
    item_number: str | None,
    document_text: str,
    model: str = DEFAULT_MODEL,
    client=None,
) -> AgendaItem:
    """Call Claude and return the AgendaItem exactly as it constructed it -
    no provenance filtering, no source_document override.

    This is what `extract_agenda_item()` calls before cleaning up the
    result. The eval harness calls this directly instead, because
    measuring hallucination rate requires seeing what the model actually
    produced before the filtering step quietly removes the fabrications.
    """
    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        item_title=item_title,
        item_number=item_number or "(none)",
        document_text=document_text,
    )

    tool = _tool_schema()
    raw = call_with_tool(
        prompt_version=PROMPT_VERSION,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[tool],
        tool_choice={"type": "tool", "name": _TOOL_NAME},
        client=client,
    )

    return AgendaItem.model_validate(raw)


def extract_agenda_item(
    *,
    item_title: str,
    item_number: str | None,
    source_document: str,
    document_text: str,
    model: str = DEFAULT_MODEL,
    client=None,
) -> AgendaItem:
    """Extract one AgendaItem from `document_text`, with unverified
    extractions dropped and provenance.source_document normalized.

    `source_document` identifies where document_text came from (a path or
    URL, typically a FetchedDocument.source_url) - it's what every
    verified extraction's provenance ends up citing, regardless of what
    the model itself produced for that field.
    """
    item = extract_agenda_item_raw(
        item_title=item_title,
        item_number=item_number,
        document_text=document_text,
        model=model,
        client=client,
    )
    return drop_unverified(item, document_text, source_document)
