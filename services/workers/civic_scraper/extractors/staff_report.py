"""
Staff report PDF extraction pipeline.

1. extract_sections(pdf_bytes) -> dict[str, str]
   Uses pdfplumber to extract full text, then splits on recognized section headers.
   Returns section name -> body text. '_full_text' key holds the complete text.

2. extract_with_claude(sections, client) -> dict
   Sends priority sections to Claude API for AI-powered structured extraction.
   Returns {fiscal, timelines, history, addresses, stakeholders, lobbying, laws, summary}.

3. fetch_and_extract(pdf_url, client) -> dict
   End-to-end helper: download PDF, extract sections, run Claude — no disk storage.
"""

import io
import re

import pdfplumber
import requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (civic-engagement-app)"}

_SECTION_NAMES = [
    "BACKGROUND",
    "ANALYSIS",
    "RECOMMENDATION",
    "FISCAL IMPACT",
    "FINANCIAL IMPACT",
    "BUDGET IMPACT",
    "COUNCIL DISTRICT",
    "CEQA",
    "COORDINATION",
    "POLICY ALTERNATIVES",
    "SUMMARY",
    "PURPOSE",
    "DISCUSSION",
    "ENVIRONMENTAL REVIEW",
    "ATTACHMENTS",
    "EXHIBITS",
    "COMMUNITY ENGAGEMENT",
    "EQUITY IMPACT",
]

# Match section headers on their own line (optional leading whitespace, optional trailing colon)
_SECTION_RE = re.compile(
    r"(?m)^[ \t]*(" + "|".join(re.escape(s) for s in _SECTION_NAMES) + r")[ \t]*:?[ \t]*$",
    re.IGNORECASE,
)

# Sections most likely to contain the data we care about — sent first to Claude
_PRIORITY_SECTIONS = [
    "BACKGROUND",
    "ANALYSIS",
    "FISCAL IMPACT",
    "FINANCIAL IMPACT",
    "BUDGET IMPACT",
    "RECOMMENDATION",
]

_EXTRACT_TOOL = {
    "name": "extract_civic_data",
    "description": "Extract structured civic information from a city staff report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fiscal": {
                "type": "array",
                "description": "Fiscal impacts: costs, revenues, fees, appropriations.",
                "items": {
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": "string",
                            "description": (
                                "Dollar amount or range, e.g. '$6.0 million' or 'up to $500,000'"
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": "What the money is for",
                        },
                        "context": {
                            "type": "string",
                            "description": (
                                "Verbatim quote from the report supporting this extraction"
                            ),
                        },
                    },
                    "required": ["amount", "description", "context"],
                },
            },
            "timelines": {
                "type": "array",
                "description": "Project milestones, deadlines, and process stages.",
                "items": {
                    "type": "object",
                    "properties": {
                        "milestone": {"type": "string"},
                        "date": {
                            "type": "string",
                            "description": (
                                "Date or relative time, e.g. 'Q3 2025' or 'upon Council approval'"
                            ),
                        },
                        "context": {"type": "string", "description": "Verbatim quote"},
                    },
                    "required": ["milestone", "context"],
                },
            },
            "history": {
                "type": "array",
                "description": "Prior actions, approvals, or events relevant to this agenda item.",
                "items": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "context": {"type": "string", "description": "Verbatim quote"},
                    },
                    "required": ["event", "context"],
                },
            },
            "addresses": {
                "type": "array",
                "description": (
                    "Physical addresses, neighborhoods, districts, or geographic areas impacted."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": (
                                "Street address, neighborhood name, or district identifier"
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": "How this location is affected or relevant",
                        },
                        "context": {"type": "string", "description": "Verbatim quote"},
                    },
                    "required": ["address", "context"],
                },
            },
            "stakeholders": {
                "type": "array",
                "description": (
                    "Named individuals, organizations, or businesses with a role in this item."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {
                            "type": "string",
                            "description": "Their role or relationship to the agenda item",
                        },
                        "context": {"type": "string", "description": "Verbatim quote"},
                    },
                    "required": ["name", "role", "context"],
                },
            },
            "lobbying": {
                "type": "array",
                "description": (
                    "Lobbying activity, advocacy groups, public comments, organized "
                    "opposition or support."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "entity": {
                            "type": "string",
                            "description": "Person or organization advocating",
                        },
                        "position": {
                            "type": "string",
                            "description": (
                                "Their stated position and argument (support/oppose/neutral)"
                            ),
                        },
                        "context": {"type": "string", "description": "Verbatim quote"},
                    },
                    "required": ["entity", "position", "context"],
                },
            },
            "laws": {
                "type": "array",
                "description": "Laws, ordinances, regulations, or policies cited or implicated.",
                "items": {
                    "type": "object",
                    "properties": {
                        "citation": {
                            "type": "string",
                            "description": "Law name, code section, or ordinance number",
                        },
                        "description": {
                            "type": "string",
                            "description": "How this law applies to the item",
                        },
                        "context": {"type": "string", "description": "Verbatim quote"},
                    },
                    "required": ["citation", "description", "context"],
                },
            },
            "summary": {
                "type": "string",
                "description": (
                    "2-3 sentence plain-language summary of what is being proposed and why."
                ),
            },
        },
        "required": [
            "fiscal",
            "timelines",
            "history",
            "addresses",
            "stakeholders",
            "lobbying",
            "laws",
            "summary",
        ],
    },
}


def extract_sections(pdf_bytes: bytes) -> dict[str, str]:
    """Extract text from a staff report PDF and split by section header.

    Returns a dict mapping uppercase section name -> body text.
    '_full_text' key contains the complete document text (transient — not for storage).
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    full_text = "\n".join(pages)

    sections: dict[str, str] = {"_full_text": full_text}

    splits = [(m.start(), m.group(1).upper().strip()) for m in _SECTION_RE.finditer(full_text)]

    for i, (pos, name) in enumerate(splits):
        end = splits[i + 1][0] if i + 1 < len(splits) else len(full_text)
        newline = full_text.find("\n", pos)
        body_start = (newline + 1) if (newline != -1 and newline < end) else pos
        sections[name] = full_text[body_start:end].strip()

    return sections


def extract_with_claude(sections: dict[str, str], client) -> dict:
    """Run Claude structured extraction on the given report sections.

    Args:
        sections: Output of extract_sections().
        client: anthropic.Anthropic() instance (caller creates once and reuses).

    Returns:
        Dict with keys: fiscal, timelines, history, addresses, stakeholders,
        lobbying, laws, summary. Each list entry includes a 'context' verbatim quote.
    """
    chunks = [f"=== {key} ===\n{sections[key]}" for key in _PRIORITY_SECTIONS if key in sections]
    if not chunks:
        chunks.append(sections.get("_full_text", "")[:8000])

    report_text = "\n\n".join(chunks)

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        tools=[_EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_civic_data"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract structured civic information from the following city staff "
                    "report sections. For each item, include a verbatim context quote from "
                    "the report. Only extract information explicitly stated in the text — "
                    "do not infer or add details.\n\n" + report_text
                ),
            }
        ],
    ) as stream:
        message = stream.get_final_message()

    for block in message.content:
        if block.type == "tool_use" and block.name == "extract_civic_data":
            return block.input

    return {}


def fetch_and_extract(pdf_url: str, client, timeout: int = 30) -> dict:
    """Download a staff report PDF and return structured extraction.

    PDF bytes are not stored — only the extraction result is returned.
    Re-fetch the URL if you need the original document again.
    """
    resp = requests.get(pdf_url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    sections = extract_sections(resp.content)
    return extract_with_claude(sections, client)
