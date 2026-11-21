"""LangGraph orchestrator.

Graph (see docs/ARCHITECTURE.md):

    START -> orchestrator <-> {trainee, provider, employer}   (simulation rounds)
          orchestrator -> assemble -> review -> finalize -> human_approval -> record_decision -> END
          any budget/limit breach -> halt -> END

The ``orchestrator`` node is the hub: it is the only place messages are
delivered (channel policy + injection scan), it picks the next speaker, and it
enforces round limits. Actor nodes only *propose* (an ActorTurn written to the
outbox); they cannot route, call each other or touch the card.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .agents import AgentRunner, BudgetExceeded
from .approval import APPROVAL_MEANING, ApprovalError, allowed_decisions, validate_decision
from .cards import assemble_draft, finalize_card, render_markdown
from .config import Config
from .guards import scan_injection
from .schemas import ReviewOutput
from .sources import SourceStore
from .tools import ToolGateway
from .trace import TraceStore


class SimState(TypedDict, total=False):
    run_id: str
    scenario_id: str
    title: str
    theme: str
    turn_order: list[str]
    max_rounds: int
    round: int
    turn_idx: int
    activity: bool
    inboxes: dict[str, list[dict]]
    outbox: list[dict]
    message_log: list[dict]  # every message the orchestrator delivered, in order
    contributions: list[dict]
    flows: list[dict]
    assumptions: list[dict]
    done: dict[str, bool]
    budget: dict[str, Any]
    status: str  # RUNNING | HALTED | AWAITING_HUMAN | DECIDED
    halt_reason: str
    flags: list[str]
    draft_card: dict
    review: dict | None
    card: dict
    decision: dict


@dataclass
class Runtime:
    cfg: Config
    sources: SourceStore
    trace: TraceStore
    gateway: ToolGateway
    runner: AgentRunner
    run_dir: Path
    runs_dir: Path


def deliver_outbox(outbox: list[dict], inboxes: dict[str, list[dict]], cfg: Config,
                   trace: TraceStore) -> tuple[dict[str, list[dict]], list[dict]]:
    """Orchestrator-side routing. Re-checks channel policy and scans for
    injection even though actor turns were already validated (defence in depth).

    Returns the updated inboxes and the list of messages actually delivered
    (kept in the message log, used later to assess cooperation)."""
    out = {k: list(v) for k, v in inboxes.items()}
    delivered: list[dict] = []
    for m in outbox:
        sender, to = m["from"], m["to"]
        if to == sender or to not in out or to not in cfg.profiles[sender].may_message:
            trace.emit("message_blocked", sender, m["round"], to=to, reason="channel_policy")
            continue
        if len(m["text"]) > cfg.limits.max_message_chars:
            trace.emit("message_blocked", sender, m["round"], to=to, reason="too_long")
            continue
        hits = scan_injection(m["text"])
        if hits:
            trace.emit("message_blocked", sender, m["round"], to=to, reason="injection", rules=hits)
            continue
        out[to].append(m)
        delivered.append(m)
        trace.emit("message_routed", sender, m["round"], to=to, intent=m["intent"], chars=len(m["text"]))
    return out, delivered


def build_graph(rt: Runtime, checkpointer):
    cfg, trace = rt.cfg, rt.trace

    # ------------------------------------------------------------------ hub
    def orchestrator(s: SimState) -> Command:
        # The supervisor: delivers messages, then uses Command(goto=...) to pick who goes next.
        if s.get("status") == "HALTED":
            return Command(goto="halt")
        inboxes, delivered = deliver_outbox(s.get("outbox", []), s["inboxes"], cfg, trace)
        message_log = s.get("message_log", []) + delivered

        order, r, idx, activity = s["turn_order"], s["round"], s["turn_idx"], s["activity"]
        while True:
            if idx < len(order):
                a = order[idx]
                if s["done"].get(a) and not inboxes[a]:
                    trace.emit("turn_skipped", a, r, reason="done_and_no_new_messages")
                    idx += 1
                    continue
                return Command(goto=a, update={"turn_idx": idx, "inboxes": inboxes, "outbox": [],
                                               "message_log": message_log, "round": r, "activity": activity})
            trace.emit("round_end", None, r, activity=activity)
            quiet = all(s["done"].get(a) and not inboxes[a] for a in order)
            if r >= s["max_rounds"] or quiet or not activity:
                if r >= s["max_rounds"] and not quiet and activity:
                    trace.emit("limit_hit", None, r, limit=f"max_rounds={s['max_rounds']}")
                return Command(goto="assemble", update={"inboxes": inboxes, "outbox": [],
                                                        "message_log": message_log, "round": r})
            r, idx, activity = r + 1, 0, False
            trace.emit("round_start", None, r)

    # --------------------------------------------------------------- actors
    def make_actor_node(agent: str):
        def node(s: SimState) -> dict:
            budget = dict(s["budget"])
            inboxes = {k: list(v) for k, v in s["inboxes"].items()}
            inboxes[agent] = []  # consumed
            base = {"budget": budget, "turn_idx": s["turn_idx"] + 1, "inboxes": inboxes}
            try:
                turn, violations = rt.runner.actor_turn(s, agent, budget)
            except BudgetExceeded as e:
                return {**base, "status": "HALTED", "halt_reason": str(e)}
            if turn is None:
                return {**base, "flags": s["flags"] + [f"turn_failed:{agent}@r{s['round']}"]}
            r = s["round"]
            out = [{"from": agent, "to": m.to, "intent": m.intent, "text": m.text, "round": r}
                   for m in turn.messages]
            contribs = [{"actor": agent, "round": r, **c.model_dump()} for c in turn.contributions]
            flows = [{"proposed_by": agent, "round": r, **f.model_dump()} for f in turn.flows]
            assumptions = [{"made_by": agent, "round": r, "text": a.text} for a in turn.assumptions]
            trace.emit("turn_summary", agent, r, messages=len(out), contributions=[c["function"] for c in contribs],
                       flows=len(flows), assumptions=len(assumptions), done=turn.done)
            return {**base, "outbox": out,
                    "contributions": s["contributions"] + contribs,
                    "flows": s["flows"] + flows,
                    "assumptions": s["assumptions"] + assumptions,
                    "done": {**s["done"], agent: turn.done},
                    "activity": s["activity"] or bool(out or contribs)}
        return node

    # ----------------------------------------------------- post-simulation
    def assemble(s: SimState) -> dict:
        draft = assemble_draft(s, cfg, rt.sources)
        trace.emit("draft_assembled", None, None,
                   participants=draft["functional_dependency"]["participants"],
                   necessary_roles=draft["functional_dependency"]["necessary_roles"],
                   cooperation=draft["cooperation"]["summary"],
                   classification=draft["overall_assessment"]["classification"],
                   mo_rule=draft["mo_rule"]["label"])
        return {"draft_card": draft}

    def review(s: SimState) -> Command:
        budget = dict(s["budget"])
        try:
            out, _ = rt.runner.review(s["draft_card"], budget)
        except BudgetExceeded as e:
            return Command(goto="halt", update={"budget": budget, "status": "HALTED", "halt_reason": str(e)})
        review_json = out.model_dump(mode="json") if out else None
        return Command(goto="finalize", update={"budget": budget, "review": review_json})

    def finalize(s: SimState) -> dict:
        rv = ReviewOutput.model_validate(s["review"]) if s.get("review") else None
        card = finalize_card(s["draft_card"], rv, cfg, rt.sources, s["flags"])
        rt.run_dir.mkdir(parents=True, exist_ok=True)
        (rt.run_dir / "card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
        (rt.run_dir / "card.md").write_text(render_markdown(card), encoding="utf-8")
        trace.emit("card_created", None, None, card_id=card["card_id"], status=card["status"],
                   content_hash=card["content_hash"], flags=card["flags"])
        trace.emit("handoff_to_human", None, None, card_id=card["card_id"],
                   allowed_decisions=allowed_decisions(card["status"]))
        return {"card": card, "status": "AWAITING_HUMAN"}

    def human_approval(s: SimState) -> dict:
        # LangGraph re-executes this node from the top on every resume and replays
        # earlier resume values in order. Raising on a bad value would leave that
        # value pinned to the interrupt, so we validate and re-interrupt instead:
        # an invalid decision keeps the run paused and the next one is checked anew.
        card = s["card"]
        payload = {
            "card_id": card["card_id"], "card_status": card["status"], "content_hash": card["content_hash"],
            "card_path": str(rt.run_dir / "card.md"), "allowed_decisions": allowed_decisions(card["status"]),
            "required_fields": ["decision", "reviewer", "reason", "card_hash"],
        }
        logged = {e["data"].get("attempt") for e in TraceStore.read(trace.path)
                  if e["event"] == "human_decision_rejected"}
        raw, attempt = interrupt(payload), 0
        while True:
            try:
                d = validate_decision(raw, card)
                break
            except ApprovalError as e:
                if attempt not in logged:  # replayed attempts were already traced
                    trace.emit("human_decision_rejected", None, None, attempt=attempt, error=str(e))
                attempt += 1
                raw = interrupt({**payload, "previous_attempt_rejected": str(e)})
        return {"decision": {**d.model_dump(), "meaning": APPROVAL_MEANING if d.decision == "approve" else ""},
                "status": "DECIDED"}

    def record_decision(s: SimState) -> dict:
        d = s["decision"]
        (rt.run_dir / "decision.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
        trace.emit("human_decision", None, None, card_id=s["card"]["card_id"], decision=d["decision"],
                   reviewer=d["reviewer"], card_hash=d["card_hash"])
        log = TraceStore(rt.runs_dir / "decisions.jsonl", run_id="decisions", clock=trace.clock)
        log.emit("decision", None, None, run_id=s["run_id"], card_id=s["card"]["card_id"], **d)
        return {}

    def halt(s: SimState) -> dict:
        rt.run_dir.mkdir(parents=True, exist_ok=True)
        (rt.run_dir / "handoff.md").write_text(
            f"# Run {s['run_id']} HALTED\n\nReason: {s.get('halt_reason')}\n\nNo pattern card was produced. "
            f"Partial state: {len(s['contributions'])} contributions over {s['round']} round(s). "
            "A human should review the trace before re-running with adjusted limits.\n", encoding="utf-8")
        trace.emit("run_halted", None, s.get("round"), reason=s.get("halt_reason"), budget=s["budget"])
        trace.emit("handoff_to_human", None, None, card_id=None, reason="halted")
        return {}

    g = StateGraph(SimState)
    # destinations= lists where Command(goto=...) may go, so LangGraph can draw the graph.
    g.add_node("orchestrator", orchestrator, destinations=(*cfg.actor_ids, "assemble", "halt"))
    for a in cfg.actor_ids:
        g.add_node(a, make_actor_node(a))
        g.add_edge(a, "orchestrator")
    for name, fn in (("assemble", assemble), ("finalize", finalize),
                     ("human_approval", human_approval), ("record_decision", record_decision), ("halt", halt)):
        g.add_node(name, fn)
    g.add_node("review", review, destinations=("finalize", "halt"))
    g.add_edge(START, "orchestrator")
    g.add_edge("assemble", "review")
    g.add_edge("finalize", "human_approval")
    g.add_edge("human_approval", "record_decision")
    g.add_edge("record_decision", END)
    g.add_edge("halt", END)
    return g.compile(checkpointer=checkpointer)
