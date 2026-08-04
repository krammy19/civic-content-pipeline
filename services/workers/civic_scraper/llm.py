"""
Single wrapper for every Claude API call in this project.

Two things live here on purpose, together: the only place that touches
`anthropic.Anthropic()`, and response caching keyed on
(prompt_version, model, full request payload). Re-running extraction (or
an eval sweep, once one exists) against inputs already seen costs zero
tokens and makes zero network calls - the cache check happens before the
client is even constructed.

Cache entries live under .cache/llm/ (gitignored - this is a cache, not
a fixture). Delete the directory to force a full re-run.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from .paths import LLM_CACHE as CACHE_ROOT


def _cache_key(prompt_version: str, model: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"{prompt_version}__{model}__{digest}"


def _cache_path(cache_key: str) -> Path:
    return CACHE_ROOT / f"{cache_key}.json"


def call_with_tool(
    *,
    prompt_version: str,
    model: str,
    messages: list[dict],
    tools: list[dict],
    tool_choice: dict,
    max_tokens: int = 4096,
    thinking: dict | None = None,
    client=None,
) -> dict:
    """Call Claude with forced tool use; return the tool call's `input` dict.

    Cached on (prompt_version, model, messages, tools, tool_choice,
    max_tokens, thinking) - anything that could change the response.
    Pass `client` (an anthropic.Anthropic-compatible object) to override
    the default client, mainly for tests.

    Raises ValueError if Claude's response has no tool_use block - a
    forced tool_choice should always produce one, so this means
    something is wrong with the request, not with the model's answer.
    """
    payload: dict[str, Any] = {
        "messages": messages,
        "tools": tools,
        "tool_choice": tool_choice,
        "max_tokens": max_tokens,
        "thinking": thinking,
    }
    cache_key = _cache_key(prompt_version, model, payload)
    cache_path = _cache_path(cache_key)

    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    if client is None:
        import anthropic

        client = anthropic.Anthropic()

    request_kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
    )
    if thinking is not None:
        request_kwargs["thinking"] = thinking

    message = client.messages.create(**request_kwargs)

    tool_use = next((block for block in message.content if block.type == "tool_use"), None)
    if tool_use is None:
        raise ValueError(
            f"Claude returned no tool_use block for forced tool_choice {tool_choice!r}"
        )

    result = tool_use.input

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result
