"""
Two-tier style checker for generated meeting digests, scored against
docs/style-guide.md. See docs/style-checking.md for the exact numeric
thresholds below and why they were chosen, and for how this module's
own precision/recall is measured against evals/style_cases/.

Tier 1 (every function above `judge_style`) is deterministic pattern
matching: structure, citations, banned constructions, length ceilings,
reading level, and first-reference titles. No network calls and no
civic_scraper import - the checks themselves are fully unit-testable
against synthetic digest text alone, the same design discipline as
evals/metrics.py. `context_from_agenda_items` takes real AgendaItem
objects but does so by duck typing, not an import, so even that adapter
carries no hard dependency.

Tier 2 (`judge_style`) is a forced-tool-use LLM call for the rules
pattern matching can't reliably catch: voice/register conformance,
unsupported-claim detection, and political-outcome editorializing. Both
tiers return the same Finding shape so a caller can treat them
uniformly, and so an eval harness can score them against the same
labeled cases without caring which tier produced a given finding.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Severity = Literal["low", "medium", "high"]


@dataclass
class Finding:
    rule: str
    severity: Severity
    message: str
    excerpt: str | None = None


@dataclass
class StyleContext:
    known_item_numbers: set[str] = field(default_factory=set)
    people: list[dict] = field(default_factory=list)  # [{"raw_name": ..., "role": ...}, ...]


def context_from_agenda_items(agenda_items) -> StyleContext:
    """Adapter from real AgendaItem objects to the plain StyleContext the
    checks below operate on - the only place in this module that touches
    civic_scraper.models, so the checks themselves stay dependency-free
    and directly testable against synthetic fixtures.
    """
    known_item_numbers = {item.item_number for item in agenda_items if item.item_number}
    seen: set[str] = set()
    people: list[dict] = []
    for item in agenda_items:
        for extracted_person in item.people:
            name = extracted_person.value.raw_name
            if name in seen:
                continue
            seen.add(name)
            people.append({"raw_name": name, "role": extracted_person.value.role})
    return StyleContext(known_item_numbers=known_item_numbers, people=people)


# --------------------------------------------------------------------------
# Shared text helpers
# --------------------------------------------------------------------------

# Negative lookbehinds prevent splitting right after a common abbreviation
# ("Ordinance No. 31328", "Blocka Construction Inc.") - real generated
# digests use these constantly, and without this guard every one of them
# gets misread as a sentence boundary, severing a citation from the
# claim it actually supports on the far side of the abbreviation.
_ABBREVIATIONS = (
    "No",
    "Inc",
    "St",
    "Ave",
    "Mr",
    "Mrs",
    "Ms",
    "Dr",
    "Jr",
    "Sr",
    "vs",
    "Co",
    "Corp",
    "Ltd",
)
_ABBREVIATION_GUARD = "".join(rf"(?<!\b{abbr}\.)" for abbr in _ABBREVIATIONS)
_SENTENCE_SPLIT_RE = re.compile(_ABBREVIATION_GUARD + r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    """Split into sentences, skipping heading lines and blank lines so a
    Markdown "## Section" title is never mistaken for a sentence."""
    sentences = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sentences.extend(s.strip() for s in _SENTENCE_SPLIT_RE.split(line) if s.strip())
    return sentences


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip() and not p.strip().startswith("#")]


def _snippet(text: str, limit: int = 120) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------

# Fixed order per docs/style-guide.md's "Required structure" - must match
# digest.generate_digest._SECTION_ORDER plus the two sections that always
# apply (Overview) or are content-dependent (Notable Votes...).
_REQUIRED_SECTION_ORDER = [
    "Overview",
    "Ceremonial Items",
    "Consent Calendar",
    "Public Hearings",
    "Other Actions",
    "Reports",
    "Notable Votes and Financial Actions",
]

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def check_structure(text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.strip().splitlines()

    if not lines or not lines[0].startswith("# "):
        findings.append(
            Finding(
                "missing_header",
                "high",
                "Digest does not start with a level-1 Markdown header.",
            )
        )

    headings = _HEADING_RE.findall(text)

    if "Overview" not in headings:
        findings.append(Finding("missing_overview", "high", "Digest has no '## Overview' section."))

    known_present = [h for h in _REQUIRED_SECTION_ORDER if h in headings]
    actual_known = [h for h in headings if h in _REQUIRED_SECTION_ORDER]
    if actual_known != known_present:
        findings.append(
            Finding(
                "section_order",
                "medium",
                f"Sections appear out of the required order: {actual_known}",
            )
        )

    for heading in headings:
        if heading not in _REQUIRED_SECTION_ORDER:
            findings.append(
                Finding(
                    "unexpected_section",
                    "low",
                    f"Unexpected section heading: {heading!r}",
                )
            )

    return findings


# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------

_OVERVIEW_SECTION_RE = re.compile(r"^##\s+Overview\s*$.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
_CITATION_RE = re.compile(r"\(Item\s+([\w.]+)\)")
_OUTCOME_VERBS = (
    "approved",
    "adopted",
    "passed",
    "failed",
    "rejected",
    "denied",
    "continued",
    "tabled",
    "withdrawn",
    "authorized",
    "awarded",
    "voted",
)
_AMOUNT_RE = re.compile(r"\$[\d,]+")


def check_citations(text: str, known_item_numbers: set[str]) -> list[Finding]:
    """Heuristic, not exhaustive: a sentence is treated as making a
    factual claim worth citing if it names a dollar amount or uses an
    outcome verb. This will miss claims phrased without either signal
    and can over-flag a sentence that merely mentions money or a verb
    in passing - see docs/style-checking.md's known limitations.

    The Overview section is exempt: docs/style-guide.md explicitly
    allows it to preview a claim that only carries its citation where
    it's repeated in a body section below.
    """
    findings: list[Finding] = []
    body_text = _OVERVIEW_SECTION_RE.sub("", text)

    # Every citation anywhere in the body must reference a real item -
    # checked independently of the missing-citation heuristic below, so a
    # citation to a nonexistent item isn't only caught in sentences that
    # happen to also trip the dollar-amount/outcome-verb signal.
    if known_item_numbers:
        for sentence in _split_sentences(body_text):
            for item_number in _CITATION_RE.findall(sentence):
                if item_number not in known_item_numbers:
                    findings.append(
                        Finding(
                            "unknown_citation",
                            "high",
                            f"Citation references item {item_number!r}, which isn't "
                            "in the meeting's validated facts.",
                            _snippet(sentence),
                        )
                    )

    for sentence in _split_sentences(body_text):
        has_signal = _AMOUNT_RE.search(sentence) or any(
            v in sentence.lower() for v in _OUTCOME_VERBS
        )
        if has_signal and not _CITATION_RE.search(sentence):
            findings.append(
                Finding(
                    "missing_citation",
                    "high",
                    "Sentence asserts a factual claim with no item-number citation.",
                    _snippet(sentence),
                )
            )

    return findings


# --------------------------------------------------------------------------
# Banned constructions
# --------------------------------------------------------------------------

_BANNED_PHRASES = (
    "it was decided",
    "action was taken to",
    "the motion was approved",
    "historic",
    "landmark",
    "controversial",
    "disappointing",
    "welcome",
    "long-overdue",
    "much-needed",
    "concerning",
    "reportedly",
    "it seems",
    "apparently",
    "sources suggest",
    "it should be noted that",
    "it is worth mentioning",
    "interestingly",
    "notably",
    "of course",
    "in an apparent effort to",
    "likely aiming to",
    "paving the way for",
)

_DIRECT_ADDRESS_RE = re.compile(r"\byou\b|\byour\b", re.IGNORECASE)


def check_banned_constructions(text: str) -> list[Finding]:
    findings: list[Finding] = []
    lowered = text.lower()

    for phrase in _BANNED_PHRASES:
        if phrase in lowered:
            findings.append(
                Finding(
                    "banned_construction",
                    "medium",
                    f"Contains a banned construction: {phrase!r}.",
                )
            )

    if "!" in text:
        findings.append(Finding("banned_construction", "low", "Contains an exclamation point."))

    if _DIRECT_ADDRESS_RE.search(text):
        findings.append(
            Finding(
                "banned_construction",
                "medium",
                "Contains direct address ('you'/'your').",
            )
        )

    return findings


# --------------------------------------------------------------------------
# Length ceilings
# --------------------------------------------------------------------------

MAX_SENTENCE_WORDS = 40
MAX_PARAGRAPH_WORDS = 150


def check_length_ceilings(text: str) -> list[Finding]:
    findings: list[Finding] = []

    for paragraph in _paragraphs(text):
        word_count = len(paragraph.split())
        if word_count > MAX_PARAGRAPH_WORDS:
            findings.append(
                Finding(
                    "paragraph_too_long",
                    "low",
                    f"Paragraph has {word_count} words (ceiling {MAX_PARAGRAPH_WORDS}).",
                    _snippet(paragraph),
                )
            )

    for sentence in _split_sentences(text):
        word_count = len(sentence.split())
        if word_count > MAX_SENTENCE_WORDS:
            findings.append(
                Finding(
                    "sentence_too_long",
                    "low",
                    f"Sentence has {word_count} words (ceiling {MAX_SENTENCE_WORDS}).",
                    _snippet(sentence),
                )
            )

    return findings


# --------------------------------------------------------------------------
# Reading level (Flesch-Kincaid grade level, no extra dependency)
# --------------------------------------------------------------------------

READING_LEVEL_TARGET = 12.0

_WORD_RE = re.compile(r"[A-Za-z']+")


def _count_syllables(word: str) -> int:
    word = word.lower()
    if not word:
        return 0
    vowels = "aeiouy"
    count = 0
    prev_was_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def flesch_kincaid_grade(text: str) -> float:
    """A standard, if approximate, readability formula. Syllable counting
    is a vowel-cluster heuristic, not a dictionary lookup - accurate
    enough to flag genuinely dense prose, not precise to the decimal."""
    sentences = _split_sentences(text)
    words = _WORD_RE.findall(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(_count_syllables(w) for w in words)
    return 0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59


def check_reading_level(text: str) -> list[Finding]:
    grade = flesch_kincaid_grade(text)
    if grade > READING_LEVEL_TARGET:
        return [
            Finding(
                "reading_level",
                "low",
                f"Flesch-Kincaid grade level {grade:.1f} exceeds the target "
                f"{READING_LEVEL_TARGET:.0f}.",
            )
        ]
    return []


# --------------------------------------------------------------------------
# First-reference titles
# --------------------------------------------------------------------------

# Only roles with one unambiguous, schema-known title word are checked.
# "staff" covers job titles (City Manager, Chief of Police, ...) the
# schema doesn't capture beyond role="staff", so there's no single
# correct title to check for - see docs/style-checking.md.
_ROLE_TITLES = {"mayor": "Mayor", "councilmember": "Councilmember"}


def check_first_reference_titles(text: str, people: list[dict]) -> list[Finding]:
    findings: list[Finding] = []
    checked: set[str] = set()

    for person in people:
        title = _ROLE_TITLES.get(person.get("role", ""))
        raw_name = person.get("raw_name", "")
        if title is None or not raw_name or raw_name in checked:
            continue
        checked.add(raw_name)

        surname = raw_name.split()[-1]
        surname_match = re.search(rf"\b{re.escape(surname)}\b", text)
        if surname_match is None:
            continue  # not mentioned in this digest at all

        titled_positions = [
            m.start()
            for variant in (f"{title} {raw_name}", f"{title} {surname}")
            if (m := re.search(re.escape(variant), text))
        ]
        first_titled = min(titled_positions) if titled_positions else -1

        if first_titled == -1 or surname_match.start() < first_titled:
            findings.append(
                Finding(
                    "missing_first_reference_title",
                    "medium",
                    f"'{surname}' appears before any titled first reference "
                    f"('{title} {raw_name}').",
                    _snippet(text[max(0, surname_match.start() - 40) : surname_match.start() + 40]),
                )
            )

    return findings


def check_deterministic(text: str, context: StyleContext) -> list[Finding]:
    findings: list[Finding] = []
    findings += check_structure(text)
    findings += check_citations(text, context.known_item_numbers)
    findings += check_banned_constructions(text)
    findings += check_length_ceilings(text)
    findings += check_reading_level(text)
    findings += check_first_reference_titles(text, context.people)
    return findings


# --------------------------------------------------------------------------
# Tier 2: LLM judge
#
# The three rules pattern matching can't reliably catch: voice/register
# conformance, unsupported-claim detection, and political-outcome
# editorializing. Forced tool use, same discipline as extraction and
# digest generation - a judgment is only useful if it's structured
# enough to score, not prose a human has to re-read to act on.
# --------------------------------------------------------------------------

JudgeRule = Literal["voice_register", "unsupported_claim", "editorializing"]

PROMPT_VERSION = "judge_digest_style.v1"
_REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = _REPO_ROOT / "prompts" / f"{PROMPT_VERSION}.md"
STYLE_GUIDE_PATH = _REPO_ROOT / "docs" / "style-guide.md"
DEFAULT_MODEL = "claude-sonnet-5"

_TOOL_NAME = "report_style_findings"


class _JudgeFinding(BaseModel):
    rule: JudgeRule
    severity: Severity
    message: str
    excerpt: str | None = None


class _StyleJudgment(BaseModel):
    findings: list[_JudgeFinding]


def _tool_schema() -> dict:
    return {
        "name": _TOOL_NAME,
        "description": "Report style findings for the digest under review.",
        "input_schema": _StyleJudgment.model_json_schema(),
    }


def _render_prompt(*, style_guide: str, facts_block: str, digest_markdown: str) -> str:
    """Literal replacement, not str.format() - both facts_block and
    digest_markdown are built from or derived from real extracted
    government text that could rarely contain a literal `{`/`}`."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    replacements = {
        "{style_guide}": style_guide,
        "{facts_block}": facts_block,
        "{digest_markdown}": digest_markdown,
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def judge_style(
    *,
    digest_markdown: str,
    facts_block: str,
    model: str = DEFAULT_MODEL,
    client=None,
) -> list[Finding]:
    """Score `digest_markdown` against the style guide using the three
    judgment-based rules deterministic checks can't cover. `facts_block`
    should be the same rendered fact text digest generation was given
    (see digest.generate_digest.render_facts) - the judge needs it to
    tell an unsupported claim from a validated one.
    """
    from civic_scraper.llm import call_with_tool

    style_guide = STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    prompt = _render_prompt(
        style_guide=style_guide, facts_block=facts_block, digest_markdown=digest_markdown
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
    judgment = _StyleJudgment.model_validate(raw)
    return [
        Finding(rule=f.rule, severity=f.severity, message=f.message, excerpt=f.excerpt)
        for f in judgment.findings
    ]
