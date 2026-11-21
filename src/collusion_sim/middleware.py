"""LangChain agent middleware: the controls that run inside every agent.

Each agent is built with `create_agent(...)` (see agents.py). These middleware
classes plug into it:

* ToolPolicyMiddleware  - runs around every tool call. Blocks tools the agent
                          is not allowed to use, and logs allowed/denied calls.
* BudgetMiddleware      - runs before/after every model call. Stops the run
                          when the call or cost limit is reached, and logs usage.

The hop limit (how many model calls one agent turn may make) uses LangChain's
built-in ModelCallLimitMiddleware.
"""
from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from .config import Config
from .tools import ToolGateway, ToolScopeError
from .trace import TraceStore


class BudgetExceeded(RuntimeError):
    """Raised when the run has used its allowed LLM calls or cost."""


def budget_block_reason(budget: dict, cfg: Config) -> str | None:
    """Return why the next model call is not allowed, or None if it is allowed."""
    if budget["llm_calls"] >= cfg.limits.max_llm_calls:
        return f"max_llm_calls={cfg.limits.max_llm_calls}"
    if budget["cost_usd"] >= cfg.limits.max_cost_usd:
        return f"max_cost_usd={cfg.limits.max_cost_usd}"
    return None


class BudgetMiddleware(AgentMiddleware):
    """Check the budget before each model call; record usage after it."""

    def __init__(self, agent: str, rnd: int | None, budget: dict, cfg: Config, trace: TraceStore):
        super().__init__()
        self.agent = agent
        self.rnd = rnd
        self.budget = budget  # shared dict for the whole run; updated in place
        self.cfg = cfg
        self.trace = trace

    def before_model(self, state, runtime):
        reason = budget_block_reason(self.budget, self.cfg)
        if reason:
            self.trace.emit("limit_hit", self.agent, self.rnd, limit=reason)
            raise BudgetExceeded(reason)
        return None

    def after_model(self, state, runtime):
        last_message = state["messages"][-1]

        # Real models report tokens; the scripted mock does not, so estimate (characters / 4).
        usage = getattr(last_message, "usage_metadata", None) or {}
        tokens = usage.get("total_tokens")
        if not tokens:
            characters = sum(len(str(m.content)) for m in state["messages"])
            tokens = max(1, characters // 4)

        cost = tokens / 1000 * self.cfg.limits.usd_per_1k_tokens
        self.budget["llm_calls"] += 1
        self.budget["tokens"] += tokens
        self.budget["cost_usd"] = round(self.budget["cost_usd"] + cost, 6)
        self.trace.emit("llm_usage", self.agent, self.rnd, tokens=tokens, cost_usd=round(cost, 6),
                        cumulative_cost_usd=self.budget["cost_usd"])
        return None


class ToolPolicyMiddleware(AgentMiddleware):
    """Allow only the agent's own tools; log every tool call."""

    def __init__(self, agent: str, rnd: int | None, gateway: ToolGateway, trace: TraceStore):
        super().__init__()
        self.agent = agent
        self.rnd = rnd
        self.gateway = gateway
        self.trace = trace

    def _denied(self, call: dict, reason: str, detail: str = "") -> ToolMessage:
        self.trace.emit("tool_denied", self.agent, self.rnd, tool=call["name"], reason=reason, detail=detail)
        return ToolMessage(content=f'{{"error": "{reason}"}}', tool_call_id=call["id"],
                           name=call["name"], status="error")

    def wrap_tool_call(self, request, handler):
        call = request.tool_call

        # 1. Is this tool on the agent's allow-list? (also catches made-up tool names)
        if not self.gateway.is_allowed(self.agent, call["name"]):
            return self._denied(call, "not_in_allow_list")

        # 2. Run the tool. The tool itself refuses data outside the agent's scope.
        try:
            result = handler(request)
        except ToolScopeError as error:
            return self._denied(call, "out_of_scope", str(error))

        self.trace.emit("tool_allowed", self.agent, self.rnd, tool=call["name"], args=call.get("args", {}))
        return result
