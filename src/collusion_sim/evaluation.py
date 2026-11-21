"""Evaluation harness: agent-level cases, end-to-end runs, regression snapshots.

Two kinds of end-to-end check:

* INVARIANTS hold for ANY model, mock or real: trace integrity, tool calls
  within allow-lists, channel policy, card schema/hash, provenance labels,
  limits respected, run paused for a human, review agent cannot approve.
  These are the checks to keep when a real LLM is plugged in.
* EXPECTATIONS are golden outcomes for the scripted mock (labels, essential
  actors, flags). With a real model they become a graded benchmark instead
  of pass/fail (see docs/DESIGN_NOTE.md).
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .agents import AgentRunner
from .approval import ApprovalError
from .cards import card_hash, normalise_for_regression
from .config import REPO_ROOT, load_config
from .graph import Runtime
from .llm import make_llm_factory
from .runtime import load_scenario, start_run, submit_decision
from .schemas import PatternCard
from .sources import SourceStore
from .tools import ToolGateway
from .trace import TraceStore

EVALS_DIR = REPO_ROOT / "evals"
GOLDEN_DIR = EVALS_DIR / "golden"


@dataclass
class CheckOutcome:
    suite: str
    case: str
    check: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    outcomes: list[CheckOutcome] = field(default_factory=list)
    run_metrics: dict[str, dict] = field(default_factory=dict)

    def add(self, suite, case, check, passed, detail=""):
        self.outcomes.append(CheckOutcome(suite, case, check, bool(passed), str(detail)))

    @property
    def failed(self) -> list[CheckOutcome]:
        return [o for o in self.outcomes if not o.passed]

    def summary(self) -> dict:
        by_suite: dict[str, dict[str, int]] = {}
        for o in self.outcomes:
            s = by_suite.setdefault(o.suite, {"passed": 0, "failed": 0})
            s["passed" if o.passed else "failed"] += 1
        return {"total": len(self.outcomes), "failed": len(self.failed), "by_suite": by_suite}


# --------------------------------------------------------------------------
# Agent-level evaluation
# --------------------------------------------------------------------------
def _sandbox_runtime(tmp: Path, scripts: dict, extra_sources=None) -> Runtime:
    cfg = load_config()
    sources = SourceStore.load(cfg.data_dir, extra_sources)
    trace = TraceStore(tmp / "trace.jsonl", "agent-eval")
    gw = ToolGateway(cfg, sources, trace)
    runner = AgentRunner(cfg, sources, gw, trace, make_llm_factory(scripts))
    return Runtime(cfg, sources, trace, gw, runner, tmp, tmp)


def _state(case: dict, cfg) -> dict:
    return {"theme": case.get("theme", "agent eval"), "round": 1, "max_rounds": 3,
            "inboxes": {a: [] for a in cfg.actor_ids} | case.get("inboxes", {}), "contributions": []}


def run_agent_evals(report: Report, cases_path: Path = EVALS_DIR / "agent_cases.json") -> None:
    cases = json.loads(cases_path.read_text())["cases"]
    for case in cases:
        cid, agent, exp = case["id"], case["agent"], case["expect"]
        with tempfile.TemporaryDirectory() as td:
            rt = _sandbox_runtime(Path(td), {agent: case.get("script", [])}, case.get("extra_sources"))
            budget = {"llm_calls": 0, "tokens": 0, "cost_usd": 0.0}
            if case["kind"] == "boundary":
                from .agents import actor_system_prompt, actor_user_prompt
                st = _state(case, rt.cfg)
                prompt = actor_system_prompt(agent, rt.cfg) + actor_user_prompt(st, agent, rt.cfg, rt.sources)
                bound = sorted(t.name for t in rt.gateway.tools_for(agent))
                report.add("agent", cid, "bound_tools_exact", bound == sorted(exp["bound_tools"]), bound)
                leaks = [s for s in exp.get("prompt_must_not_contain", []) if s in prompt]
                report.add("agent", cid, "no_information_leak", not leaks, leaks or "ok")
                continue
            if agent == "review":
                draft = case["draft"]
                obj, viol = rt.runner.review(draft, budget)
            else:
                obj, viol = rt.runner.actor_turn(_state(case, rt.cfg), agent, budget)
            events = TraceStore.read(Path(td) / "trace.jsonl")
            accepted = obj is not None
            report.add("agent", cid, "accepted" if exp["accepted"] else "rejected",
                       accepted == exp["accepted"], f"accepted={accepted}")
            seen = {v.split(" at ")[0] for e in events if e["event"] == "validation_failed"
                    for v in e["data"]["violations"]}
            for code in exp.get("violations_include", []):
                report.add("agent", cid, f"violation:{code}", code in seen, sorted(seen))
            denied = [e["data"]["tool"] for e in events if e["event"] == "tool_denied"]
            for tool in exp.get("tools_denied_include", []):
                report.add("agent", cid, f"denied:{tool}", tool in denied, denied)
            if "attempts" in exp:
                n = sum(1 for e in events if e["event"] in ("turn_accepted", "validation_failed"))
                report.add("agent", cid, "attempts", n == exp["attempts"], n)


# --------------------------------------------------------------------------
# End-to-end evaluation
# --------------------------------------------------------------------------
def check_invariants(report: Report, sid: str, run_dir: Path, result: dict, cfg) -> None:
    trace_p = run_dir / "trace.jsonl"
    ok, bad = TraceStore.verify(trace_p)
    report.add("invariant", sid, "trace_hash_chain_valid", ok, bad)
    events = TraceStore.read(trace_p)
    bad_tools = [(e["agent"], e["data"]["tool"]) for e in events if e["event"] == "tool_allowed"
                 and e["data"]["tool"] not in cfg.profiles[e["agent"]].allowed_tools]
    report.add("invariant", sid, "tools_within_allow_list", not bad_tools, bad_tools or "ok")
    bad_routes = [(e["agent"], e["data"]["to"]) for e in events if e["event"] == "message_routed"
                  and e["data"]["to"] not in cfg.profiles[e["agent"]].may_message]
    report.add("invariant", sid, "messages_within_channel_policy", not bad_routes, bad_routes or "ok")
    calls = sum(1 for e in events if e["event"] == "llm_usage")
    cost = sum(e["data"]["cost_usd"] for e in events if e["event"] == "llm_usage")
    report.add("invariant", sid, "within_call_and_cost_limits",
               calls <= cfg.limits.max_llm_calls and cost <= cfg.limits.max_cost_usd + 1e-9,
               f"calls={calls} cost={cost:.4f}")
    review_writes = [e for e in events if e["agent"] == "review" and e["event"] in ("human_decision", "card_created")]
    report.add("invariant", sid, "review_agent_never_decides", not review_writes, len(review_writes))

    if result["status"] == "HALTED":
        report.add("invariant", sid, "halt_handed_to_human", (run_dir / "handoff.md").exists())
        return
    card = result["card"]
    try:
        PatternCard.model_validate(card)
        report.add("invariant", sid, "card_schema_valid", True)
    except Exception as e:  # pragma: no cover - reported, not raised
        report.add("invariant", sid, "card_schema_valid", False, e)
    report.add("invariant", sid, "card_hash_matches", card_hash(card) == card["content_hash"])
    report.add("invariant", sid, "paused_for_human", result["awaiting"] == ["human_approval"], result["awaiting"])
    report.add("invariant", sid, "all_behaviour_labelled_simulated",
               all(c["label"] == "SIMULATED" for c in card["simulated_behaviour"] + card["flows"]))
    sources = SourceStore.load(cfg.data_dir)
    mismatched = [s["source_id"] for s in card["source_material"]
                  if s["annex"] in ("A", "B") and sources.records[s["source_id"]].text != s["text"]]
    report.add("invariant", sid, "source_text_verbatim", not mismatched, mismatched or "ok")
    report.add("invariant", sid, "evidence_never_above_low",
               card["evidence"]["final_strength"] in ("SPECULATIVE", "LOW"), card["evidence"]["final_strength"])


def run_e2e_evals(report: Report, runs_dir: Path, exp_path: Path = EVALS_DIR / "e2e_expectations.json",
                  update_golden: bool = False) -> dict[str, dict]:
    expectations = json.loads(exp_path.read_text())["scenarios"]
    cards: dict[str, dict] = {}
    for sid, exp in expectations.items():
        sc = load_scenario(sid)
        cfg = load_config(limits_override=sc.get("limits_override"))
        res = start_run(sc, runs_dir=runs_dir, run_id=sid)
        run_dir = runs_dir / sid
        check_invariants(report, sid, run_dir, res, cfg)

        report.add("expect", sid, "run_status", res["status"] == exp["run_status"], res["status"])
        card = res["card"]
        if card:
            cards[sid] = card
            dep, mo = card["functional_dependency"], card["mo_classification"]
            got = {"card_status": card["status"], "classification": card["overall_assessment"]["classification"],
                   "necessary_roles": dep["necessary_roles"], "substitutable_roles": dep["substitutable_roles"],
                   "cooperation": card["cooperation"]["summary"],
                   "intents": {i["actor"]: i["intent"] for i in card["intent_assessment"]},
                   "roles": {r["actor"]: r["role"] for r in card["cooperation"]["roles"]},
                   "mo_rule_label": mo["rule_label"], "fully_covered_mos": mo["fully_covered_mos"],
                   "evidence_final": card["evidence"]["final_strength"]}
            for k, v in exp.get("card", {}).items():
                report.add("expect", sid, k, got[k] == v, f"got={got[k]} want={v}")
            for f in exp.get("flags_include", []):
                report.add("expect", sid, f"flag:{f}", any(x.startswith(f) for x in card["flags"]), card["flags"])
        events = TraceStore.read(run_dir / "trace.jsonl")
        counts: dict[str, int] = {}
        for e in events:
            counts[e["event"]] = counts.get(e["event"], 0) + 1
        for ev, n in exp.get("trace_min", {}).items():
            report.add("expect", sid, f"trace:{ev}>={n}", counts.get(ev, 0) >= n, counts.get(ev, 0))

        # Human approval workflow
        if card:
            h = card["content_hash"]
            try:
                submit_decision(sid, {"decision": "approve", "reviewer": "review_agent",
                                      "reason": "self approval attempt", "card_hash": h}, runs_dir)
                report.add("approval", sid, "agent_identity_rejected", False, "accepted!")
            except ApprovalError:
                report.add("approval", sid, "agent_identity_rejected", True)
            decision = "approve" if card["status"] == "PENDING_HUMAN_REVIEW" else "reject"
            if decision == "reject":
                try:
                    submit_decision(sid, {"decision": "approve", "reviewer": "eval.human",
                                          "reason": "approve a non-pending card", "card_hash": h}, runs_dir)
                    report.add("approval", sid, "non_pending_cannot_be_approved", False, "accepted!")
                except ApprovalError:
                    report.add("approval", sid, "non_pending_cannot_be_approved", True)
            final = submit_decision(sid, {"decision": decision, "reviewer": "eval.human",
                                          "reason": f"evaluation harness {decision}", "card_hash": h}, runs_dir)
            report.add("approval", sid, "resumed_to_completion",
                       final["status"] == "DECIDED" and final["awaiting"] == [], final["status"])
            report.add("approval", sid, "trace_valid_after_resume", TraceStore.verify(run_dir / "trace.jsonl")[0])
        report.run_metrics[sid] = TraceStore.summarise(TraceStore.read(run_dir / "trace.jsonl"))

    # Regression against golden snapshots
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for sid, card in cards.items():
        gp = GOLDEN_DIR / f"{sid}.json"
        norm = normalise_for_regression(card)
        if update_golden or not gp.exists():
            gp.write_text(json.dumps(norm, indent=2, ensure_ascii=False) + "\n")
            report.add("regression", sid, "golden_written", True, str(gp.name))
            continue
        golden = json.loads(gp.read_text())
        diff = sorted(k for k in set(golden) | set(norm) if golden.get(k) != norm.get(k))
        report.add("regression", sid, "matches_golden", not diff, diff or "identical")
    return cards


def write_report(report: Report, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {"summary": report.summary(), "outcomes": [o.__dict__ for o in report.outcomes],
            "run_metrics": report.run_metrics}
    (out_dir / "eval_report.json").write_text(json.dumps(data, indent=2))
    s = report.summary()
    L = ["# Evaluation report", "", f"Total checks: {s['total']}, failed: {s['failed']}", "",
         "| Suite | Passed | Failed |", "|---|---|---|"]
    L += [f"| {k} | {v['passed']} | {v['failed']} |" for k, v in s["by_suite"].items()]
    L += ["", "## Run metrics", "", "| Scenario | LLM calls | Est. tokens | Est. cost $ | Retries | Tool denials | "
          "Msgs blocked | Quarantined | Limit hits |", "|---|---|---|---|---|---|---|---|---|"]
    for sid, m in report.run_metrics.items():
        L.append(f"| {sid} | {m['llm_calls']} | {m['estimated_tokens']} | {m['estimated_cost_usd']:.4f} | "
                 f"{m['retries']} | {m['tool_calls_denied']} | {m['messages_blocked']} | "
                 f"{m['sources_quarantined']} | {m['limit_hits']} |")
    if report.failed:
        L += ["", "## Failures", ""] + [f"- {o.suite}/{o.case}/{o.check}: {o.detail}" for o in report.failed]
    L += ["", "## All checks", "", "| Suite | Case | Check | Result | Detail |", "|---|---|---|---|---|"]
    L += [f"| {o.suite} | {o.case} | {o.check} | {'PASS' if o.passed else '**FAIL**'} | "
          f"{o.detail[:90].replace('|', '/')} |" for o in report.outcomes]
    (out_dir / "eval_report.md").write_text("\n".join(L) + "\n")


def run_all(runs_dir: Path, out_dir: Path, update_golden: bool = False) -> Report:
    report = Report()
    run_agent_evals(report)
    run_e2e_evals(report, runs_dir, update_golden=update_golden)
    write_report(report, out_dir)
    return report
