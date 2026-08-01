"""
LLM-based digest generation: turns a Meeting's validated AgendaItems into
a plain-language, cited Markdown digest, following docs/style-guide.md.

Uses forced tool use against MeetingDigest's own one-field schema,
consistent with the rest of the codebase's "structured output, never
free-text parsing" discipline - see digest/models.py's docstring for why
that applies even to a prose result.

The prompt is built from rendered facts - never raw document text - so
every claim the model can make is already traceable to a specific item
number and a provenance-verified fact. That is what makes the style
guide's "every claim cites an item number" rule enforceable at all: the
model has nothing else to draw on. Callers are responsible for passing
only *published* AgendaItems (the output of confidence routing - see
docs/review.md); this module has no opinion about confidence routing
itself.
"""

from pathlib import Path

from civic_scraper.llm import call_with_tool
from civic_scraper.models import AgendaItem, Meeting

from .models import MeetingDigest

PROMPT_VERSION = "generate_digest.v1"
_REPO_ROOT = Path(__file__).resolve().parents[4]
PROMPT_PATH = _REPO_ROOT / "prompts" / f"{PROMPT_VERSION}.md"
STYLE_GUIDE_PATH = _REPO_ROOT / "docs" / "style-guide.md"
DEFAULT_MODEL = "claude-sonnet-5"

_TOOL_NAME = "generate_digest"

# Fixed section order the style guide requires - see "Required structure"
# in docs/style-guide.md. Any item_type not listed here (currently just
# "unknown") falls into "Other Actions" rather than being silently
# dropped from the digest.
_SECTION_LABELS = {
    "ceremonial": "Ceremonial Items",
    "consent": "Consent Calendar",
    "public_hearing": "Public Hearings",
    "action": "Other Actions",
    "report": "Reports",
}
_SECTION_ORDER = [
    "Ceremonial Items",
    "Consent Calendar",
    "Public Hearings",
    "Other Actions",
    "Reports",
]


def _tool_schema() -> dict:
    return {
        "name": _TOOL_NAME,
        "description": "Return the complete meeting digest as Markdown text.",
        "input_schema": MeetingDigest.model_json_schema(),
    }


def _render_item(item: AgendaItem) -> str:
    lines = [f"Item {item.item_number or '(no number)'}: {item.title}"]
    for motion in item.motions:
        m = motion.value
        who = f", moved by {m.moved_by.raw_name}" if m.moved_by else ""
        who += f", seconded by {m.seconded_by.raw_name}" if m.seconded_by else ""
        tally = f", tally {m.tally}" if m.tally else ""
        lines.append(f"  - Motion: {m.text} -- outcome: {m.outcome}{who}{tally}")
    for person in item.people:
        p = person.value
        lines.append(f"  - Person: {p.raw_name} ({p.role})")
    for location in item.locations:
        lines.append(f"  - Location: {location.value.raw_text}")
    for amount in item.amounts:
        a = amount.value
        usd = f" = ${a.amount_usd}" if a.amount_usd is not None else ""
        lines.append(f"  - Amount: {a.raw_text} ({a.kind}){usd}")
    return "\n".join(lines)


def render_facts(agenda_items: list[AgendaItem]) -> str:
    """Render a Meeting's validated AgendaItems into the plain-text fact
    block the prompt hands the model - the only source of truth it's
    allowed to draw on. Closed-session items are never rendered (the
    style guide prohibits describing closed-session substance in a
    digest); everything else groups into the same fixed section order
    the style guide requires, so a section absent from the facts is a
    section the model is told nothing about and therefore has no
    grounds to write.
    """
    sections: dict[str, list[str]] = {label: [] for label in _SECTION_ORDER}

    for item in agenda_items:
        if item.item_type == "closed_session":
            continue
        label = _SECTION_LABELS.get(item.item_type, "Other Actions")
        sections[label].append(_render_item(item))

    blocks = [
        f"## {label}\n\n" + "\n\n".join(entries)
        for label in _SECTION_ORDER
        if (entries := sections[label])
    ]
    return "\n\n".join(blocks) if blocks else "No items with validated facts."


def _render_prompt(*, jurisdiction: str, body: str, meeting_date: str, facts_block: str) -> str:
    """Fills the prompt template by literal replacement rather than
    str.format() - facts_block is built from real extracted government
    text (motion text, names) that could rarely contain a literal `{` or
    `}`, which would make .format() raise on a string it never actually
    needed to treat as a format field."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    style_guide = STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{jurisdiction}": jurisdiction,
        "{body}": body,
        "{meeting_date}": meeting_date,
        "{style_guide}": style_guide,
        "{facts_block}": facts_block,
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def generate_digest(*, meeting: Meeting, model: str = DEFAULT_MODEL, client=None) -> str:
    """Generate a Markdown digest from `meeting`'s agenda_items.

    Callers are responsible for passing only already confidence-routed,
    provenance-verified AgendaItems - this function has no opinion about
    routing, it just turns whatever facts it's given into a styled
    digest.
    """
    facts_block = render_facts(meeting.agenda_items)
    prompt = _render_prompt(
        jurisdiction=meeting.jurisdiction,
        body=meeting.body,
        meeting_date=meeting.date,
        facts_block=facts_block,
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
    return MeetingDigest.model_validate(raw).digest_markdown
