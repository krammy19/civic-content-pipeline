"""Tests for the single cached Claude wrapper. Real ANTHROPIC_API_KEY is
never needed - every test injects a FakeClient, and cache isolation comes
from the autouse fixture in conftest.py."""

import pytest
from civic_scraper import llm

from tests.fake_llm_client import FakeClient

_BASE_KWARGS = {
    "messages": [{"role": "user", "content": "hi"}],
    "tools": [{"name": "my_tool"}],
    "tool_choice": {"type": "tool", "name": "my_tool"},
}


class TestCallWithTool:
    def test_returns_the_tool_calls_input(self):
        client = FakeClient(tool_name="my_tool", tool_input={"answer": 42})
        result = llm.call_with_tool(
            prompt_version="v1", model="claude-x", client=client, **_BASE_KWARGS
        )
        assert result == {"answer": 42}
        assert client.call_count == 1

    def test_second_identical_call_hits_cache_not_the_client(self):
        client = FakeClient(tool_name="my_tool", tool_input={"answer": 42})
        llm.call_with_tool(prompt_version="v1", model="claude-x", client=client, **_BASE_KWARGS)
        llm.call_with_tool(prompt_version="v1", model="claude-x", client=client, **_BASE_KWARGS)
        assert client.call_count == 1

    def test_cache_survives_without_a_client_on_the_second_call(self):
        # If caching didn't work, this would try to build a real anthropic.Anthropic()
        # with no API key configured and blow up - not silently return stale data.
        client = FakeClient(tool_name="my_tool", tool_input={"answer": 7})
        llm.call_with_tool(prompt_version="v1", model="claude-x", client=client, **_BASE_KWARGS)
        result = llm.call_with_tool(prompt_version="v1", model="claude-x", **_BASE_KWARGS)
        assert result == {"answer": 7}

    def test_different_messages_are_different_cache_entries(self):
        client = FakeClient(tool_name="my_tool", tool_input={"answer": 1})
        kwargs = {k: v for k, v in _BASE_KWARGS.items() if k != "messages"}
        llm.call_with_tool(
            prompt_version="v1",
            model="claude-x",
            messages=[{"role": "user", "content": "hi"}],
            client=client,
            **kwargs,
        )
        llm.call_with_tool(
            prompt_version="v1",
            model="claude-x",
            messages=[{"role": "user", "content": "bye"}],
            client=client,
            **kwargs,
        )
        assert client.call_count == 2

    def test_different_prompt_version_is_a_different_cache_entry(self):
        client = FakeClient(tool_name="my_tool", tool_input={"answer": 1})
        llm.call_with_tool(prompt_version="v1", model="claude-x", client=client, **_BASE_KWARGS)
        llm.call_with_tool(prompt_version="v2", model="claude-x", client=client, **_BASE_KWARGS)
        assert client.call_count == 2

    def test_different_model_is_a_different_cache_entry(self):
        client = FakeClient(tool_name="my_tool", tool_input={"answer": 1})
        llm.call_with_tool(prompt_version="v1", model="claude-a", client=client, **_BASE_KWARGS)
        llm.call_with_tool(prompt_version="v1", model="claude-b", client=client, **_BASE_KWARGS)
        assert client.call_count == 2

    def test_missing_tool_use_block_raises(self):
        client = FakeClient(content=[])
        with pytest.raises(ValueError):
            llm.call_with_tool(prompt_version="v1", model="claude-x", client=client, **_BASE_KWARGS)

    def test_writes_a_cache_file_under_cache_root(self):
        client = FakeClient(tool_name="my_tool", tool_input={"answer": 1})
        llm.call_with_tool(prompt_version="v1", model="claude-x", client=client, **_BASE_KWARGS)
        cached = list(llm.CACHE_ROOT.glob("v1__claude-x__*.json"))
        assert len(cached) == 1
