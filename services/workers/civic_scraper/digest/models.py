from pydantic import BaseModel


class MeetingDigest(BaseModel):
    """The one-field tool schema digest generation returns. A single
    markdown string is genuinely all there is to validate here - forcing
    it through a tool call anyway (rather than a plain completion) keeps
    every LLM call in this codebase on the same "structured output,
    never free-text parsing" discipline, and avoids markdown-fence or
    preamble stripping a plain completion would otherwise need.
    """

    digest_markdown: str
