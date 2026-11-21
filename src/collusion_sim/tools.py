"""Least-privilege tools and the orchestrator-owned ToolGateway.

Permissions are enforced in Python at three layers, none of which rely on the
system prompt:

1. Binding: each agent's model is bound ONLY to the tools in its profile's
   ``allowed_tools``; other roles' tools are never constructed for it.
2. Middleware: every tool call the model emits passes through
   ``ToolPolicyMiddleware.wrap_tool_call`` (middleware.py), which re-checks the
   caller's allow-list with ``ToolGateway.is_allowed`` and denies (and traces)
   anything else, including made-up tool names. ``ToolGateway.dispatch`` does
   the same checks for a direct call (used by the tests).
3. Scope: each tool is a closure over its owner's evidence scope; e.g.
   ``trainee_evidence_read`` refuses sources not visible to the trainee and
   all quarantined sources, whoever calls it.

No tool writes anything. There is no approval tool.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, tool

from .analysis import classify_mo
from .config import Config
from .sources import SourceStore
from .trace import TraceStore


class ToolScopeError(PermissionError):
    """Raised inside a tool when a request is outside the owner's scope."""


def wrap_untrusted(sid: str, basis: str, text: str) -> str:
    # Delimit untrusted content as data. The guard has already stripped hidden
    # Unicode; angle brackets are escaped so a source cannot close the tag.
    safe = text.replace("<", "&lt;").replace(">", "&gt;")
    return f'<untrusted_source id="{sid}" basis="{basis}">{safe}</untrusted_source>'


def _actor_evidence_tools(actor: str, cfg: Config, sources: SourceStore) -> list[BaseTool]:
    """Make the two evidence tools for one actor. They only see that actor's posts."""
    profile = cfg.profiles[actor]

    def in_scope(source_id: str) -> bool:
        # Allowed only if: it is a social media post, this actor can see it, and it is not blocked.
        record = sources.records.get(source_id)
        if record is None or record.quarantined:
            return False
        return record.annex in ("B", "extra") and profile.can_see(source_id)

    @tool(f"{actor}_evidence_list")
    def evidence_list() -> str:
        """List the social media post IDs this actor is allowed to read."""
        ids = [r.id for r in sources.social() if in_scope(r.id)]
        return json.dumps({"owner": actor, "source_ids": ids})

    @tool(f"{actor}_evidence_read")
    def evidence_read(source_id: str) -> str:
        """Read one social media post this actor is allowed to see (untrusted text)."""
        if not in_scope(source_id):
            raise ToolScopeError(f"{source_id} is not in {actor}'s evidence scope")
        record = sources.records[source_id]
        return wrap_untrusted(record.id, record.basis, record.text)

    return [evidence_list, evidence_read]


def _review_tools(cfg: Config, sources: SourceStore, gateway: "ToolGateway") -> list[BaseTool]:
    """Make the Review Agent's tools. All are read-only."""

    @tool
    def source_validate(source_ids: list[str]) -> str:
        """Read-only: check source IDs exist, are not blocked, and return their text."""
        results = []
        for source_id in source_ids:
            record = sources.records.get(source_id)
            if record is None:
                results.append({"source_id": source_id, "exists": False})
            elif record.quarantined:
                results.append({"source_id": source_id, "exists": True, "quarantined": True,
                                "flags": list(record.flags)})
            else:
                results.append({"source_id": source_id, "exists": True, "quarantined": False,
                                "annex": record.annex, "basis": record.basis,
                                "text": wrap_untrusted(record.id, record.basis, record.text)})
        return json.dumps(results, ensure_ascii=False)

    @tool
    def mo_library_list() -> str:
        """Read-only: list the MO library (Annex A) with analyst tags."""
        library = []
        for record in sources.mos():
            library.append({"id": record.id, "name": record.name, "basis": record.basis,
                            "text": wrap_untrusted(record.id, record.basis, record.text),
                            "analyst_tags": sorted(cfg.mo_tags.get(record.id, []))})
        return json.dumps(library, ensure_ascii=False)

    @tool
    def mo_compare(behaviour_tags: list[str]) -> str:
        """Read-only: compare behaviour tags with the MO library (known / variation / new)."""
        valid_tags = [t for t in behaviour_tags if t in cfg.behaviour_tags]
        return json.dumps(classify_mo(valid_tags, cfg))

    @tool
    def draft_card_read() -> str:
        """Read-only: return the draft pattern card under review."""
        return json.dumps(gateway.draft_card or {}, ensure_ascii=False)

    return [source_validate, mo_library_list, mo_compare, draft_card_read]


class ToolGateway:
    def __init__(self, cfg: Config, sources: SourceStore, trace: TraceStore):
        self.cfg, self.sources, self.trace = cfg, sources, trace
        self.draft_card: dict | None = None
        candidates: dict[str, list[BaseTool]] = {a: _actor_evidence_tools(a, cfg, sources) for a in cfg.actor_ids}
        candidates["review"] = _review_tools(cfg, sources, self)
        # Keep only what each profile allows; anything else is never reachable.
        self._registry: dict[str, dict[str, BaseTool]] = {
            agent: {t.name: t for t in tools if t.name in cfg.profiles[agent].allowed_tools}
            for agent, tools in candidates.items()
        }

    def tools_for(self, agent: str) -> list[BaseTool]:
        return list(self._registry.get(agent, {}).values())

    def allowed_names(self, agent: str) -> set[str]:
        return set(self._registry.get(agent, {}))

    def is_allowed(self, agent: str, tool_name: str) -> bool:
        """True only if the tool was built for this agent AND is in its profile's allow-list."""
        in_registry = tool_name in self._registry.get(agent, {})
        in_profile = tool_name in self.cfg.profiles[agent].allowed_tools
        return in_registry and in_profile

    def dispatch(self, agent: str, call: dict[str, Any], round: int | None) -> ToolMessage:
        name, args, cid = call.get("name", ""), call.get("args", {}) or {}, call.get("id") or "call"
        tool = self._registry.get(agent, {}).get(name)
        if not self.is_allowed(agent, name):
            self.trace.emit("tool_denied", agent, round, tool=name, reason="not_in_allow_list")
            return ToolMessage(content=json.dumps({"error": "permission_denied", "tool": name}),
                               tool_call_id=cid, status="error")
        try:
            result = tool.invoke(args)
        except ToolScopeError as e:
            self.trace.emit("tool_denied", agent, round, tool=name, reason="out_of_scope", detail=str(e))
            return ToolMessage(content=json.dumps({"error": "out_of_scope"}), tool_call_id=cid, status="error")
        except Exception as e:  # bad args etc.
            self.trace.emit("tool_error", agent, round, tool=name, error=type(e).__name__)
            return ToolMessage(content=json.dumps({"error": "tool_error"}), tool_call_id=cid, status="error")
        self.trace.emit("tool_allowed", agent, round, tool=name, args=args)
        return ToolMessage(content=str(result), tool_call_id=cid)
