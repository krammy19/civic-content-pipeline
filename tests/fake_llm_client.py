"""Minimal fake Anthropic client for tests. Never makes a network call -
just records what it was asked and returns a pre-baked response."""


class FakeToolUseBlock:
    def __init__(self, name: str, input: dict):
        self.type = "tool_use"
        self.name = name
        self.input = input


class FakeMessage:
    def __init__(self, content: list):
        self.content = content


class FakeMessages:
    def __init__(self, response: FakeMessage):
        self._response = response
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class FakeClient:
    """tool_name/tool_input builds a single tool_use response (the common case).
    Pass content=[...] directly to simulate something unusual, e.g. no tool_use
    block at all."""

    def __init__(self, tool_name: str | None = None, tool_input: dict | None = None, content=None):
        if content is None:
            content = [FakeToolUseBlock(tool_name, tool_input)] if tool_name else []
        self.messages = FakeMessages(FakeMessage(content))

    @property
    def call_count(self) -> int:
        return len(self.messages.calls)
