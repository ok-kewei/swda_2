"""Scripted mock LLM (one per agent) built on LangChain's GenericFakeChatModel.

Each agent gets its own model instance with an ordered script of responses.
A script entry may be:

* a dict   -> serialised to JSON as the assistant content
* a string -> used verbatim (lets us script malformed JSON)
* {"__tool_calls__": [{"name": ..., "args": {...}}]} -> an AIMessage that
  requests tool calls (lets us script legitimate and forbidden tool use)

``bind_tools`` records the tool names the orchestrator bound, so tests can
prove which tools each agent was offered. A real model would be any LangChain
chat model that supports ``bind_tools``, passed in through ``llm_factory``.

The mock is deterministic and ignores its prompt. See docs/DESIGN_NOTE.md
("What the mock cannot prove").
"""
from __future__ import annotations

import json
from typing import Any, Callable, Iterator

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import Field

EXHAUSTED = json.dumps({"done": True})


def to_message(entry: Any, idx: int) -> AIMessage:
    if isinstance(entry, dict) and "__tool_calls__" in entry:
        calls = [{"name": c["name"], "args": c.get("args", {}), "id": f"call_{idx}_{i}", "type": "tool_call"}
                 for i, c in enumerate(entry["__tool_calls__"])]
        return AIMessage(content="", tool_calls=calls)
    if isinstance(entry, str):
        return AIMessage(content=entry)
    return AIMessage(content=json.dumps(entry, ensure_ascii=False))


def _script_iter(script: list[Any]) -> Iterator[AIMessage]:
    for i, e in enumerate(script):
        yield to_message(e, i)
    while True:  # after the script ends the agent simply passes
        yield AIMessage(content=EXHAUSTED)


class ScriptedChatModel(GenericFakeChatModel):
    agent_id: str = "unknown"
    bound_tool_names: list[str] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        self.bound_tool_names = [t.name for t in tools]
        return self


def scripted_llm(agent_id: str, script: list[Any]) -> ScriptedChatModel:
    return ScriptedChatModel(agent_id=agent_id, messages=_script_iter(script))


LLMFactory = Callable[[str], Any]


def make_llm_factory(scripts: dict[str, list[Any]]) -> LLMFactory:
    """Return agent_id -> chat model. Models are created once per agent and cached."""
    cache: dict[str, Any] = {}

    def factory(agent_id: str):
        if agent_id not in cache:
            cache[agent_id] = scripted_llm(agent_id, scripts.get(agent_id, []))
        return cache[agent_id]

    factory.cache = cache  # type: ignore[attr-defined]
    return factory
