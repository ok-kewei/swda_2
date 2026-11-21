"""Public API: start a run (pauses for human approval), check its state, and
resume a run with a human decision. Uses a SQLite checkpointer so a paused run
survives process restarts and can be resumed from a different process.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .agents import AgentRunner
from .approval import validate_decision
from .config import REPO_ROOT, canonical_json, load_config, sha256_bytes
from .graph import Runtime, build_graph
from .llm import LLMFactory, make_llm_factory
from .sources import SourceStore
from .tools import ToolGateway
from .trace import TraceStore, utc_now

DEFAULT_RUNS_DIR = REPO_ROOT / "runs"
SCENARIO_DIR = REPO_ROOT / "scenarios"
RECURSION_LIMIT = 200


class RunError(RuntimeError):
    pass


def load_scenario(ref: str | Path) -> dict:
    p = Path(ref)
    if not p.exists():
        p = SCENARIO_DIR / f"{ref}.json"
    sc = json.loads(p.read_text(encoding="utf-8"))
    if "scripts_from" in sc:  # reuse another scenario's mock scripts
        sc["scripts"] = load_scenario(sc["scripts_from"])["scripts"]
    sc["_path"] = str(p.resolve())
    return sc


@contextmanager
def checkpointer(runs_dir: Path) -> Iterator[SqliteSaver]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(runs_dir / "checkpoints.sqlite", check_same_thread=False)
    try:
        yield SqliteSaver(conn)
    finally:
        conn.close()


def _runtime(scenario: dict, run_id: str, runs_dir: Path, clock: Callable[[], str],
             llm_factory: LLMFactory | None) -> Runtime:
    cfg = load_config(limits_override=scenario.get("limits_override"))
    sources = SourceStore.load(cfg.data_dir, scenario.get("extra_sources"))
    run_dir = runs_dir / run_id
    trace = TraceStore(run_dir / "trace.jsonl", run_id, clock)
    gateway = ToolGateway(cfg, sources, trace)
    runner = AgentRunner(cfg, sources, gateway, trace, llm_factory or make_llm_factory(scenario.get("scripts", {})))
    return Runtime(cfg, sources, trace, gateway, runner, run_dir, runs_dir)


def _thread(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}, "recursion_limit": RECURSION_LIMIT}


def _result(app, run_id: str, run_dir: Path) -> dict[str, Any]:
    st = app.get_state(_thread(run_id))
    v = st.values
    pending = [i.value for t in st.tasks for i in t.interrupts]
    return {"run_id": run_id, "run_dir": str(run_dir), "status": v.get("status"),
            "awaiting": list(st.next), "interrupt": pending[0] if pending else None,
            "card": v.get("card"), "decision": v.get("decision"), "halt_reason": v.get("halt_reason")}


def start_run(scenario: dict | str, runs_dir: Path = DEFAULT_RUNS_DIR, run_id: str | None = None,
              clock: Callable[[], str] = utc_now, llm_factory: LLMFactory | None = None) -> dict:
    sc = load_scenario(scenario) if isinstance(scenario, (str, Path)) else scenario
    run_id = run_id or f"{sc['id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    run_dir = runs_dir / run_id
    if (run_dir / "trace.jsonl").exists():
        raise RunError(f"run {run_id} already exists")
    rt = _runtime(sc, run_id, runs_dir, clock, llm_factory)
    run_dir.mkdir(parents=True, exist_ok=True)
    scen_ref = None
    if "_path" in sc:
        sp = Path(sc["_path"])
        scen_ref = str(sp.relative_to(REPO_ROOT)) if sp.is_relative_to(REPO_ROOT) else str(sp)
    (run_dir / "manifest.json").write_text(json.dumps({"run_id": run_id, "scenario": scen_ref,
                                                       "scenario_id": sc["id"]}, indent=2))
    scen_hash = sha256_bytes(canonical_json({k: v for k, v in sc.items() if k != "_path"}).encode())
    rt.trace.emit("run_start", None, None, scenario_id=sc["id"], scenario_sha256=scen_hash,
                  config_hashes=rt.cfg.file_hashes, annex_hashes=rt.sources.file_hashes,
                  limits=rt.cfg.limits.__dict__,
                  tools_bound={a: sorted(rt.gateway.allowed_names(a)) for a in rt.cfg.profiles})
    for r in rt.sources.quarantined():
        rt.trace.emit("source_quarantined", None, None, source_id=r.id, annex=r.annex, flags=list(r.flags))
    rt.trace.emit("round_start", None, 1)

    order = sc.get("turn_order", rt.cfg.actor_ids)
    init = {
        "run_id": run_id, "scenario_id": sc["id"], "title": sc["title"], "theme": sc["theme"],
        "turn_order": order, "max_rounds": min(sc.get("max_rounds", rt.cfg.limits.max_rounds),
                                               rt.cfg.limits.max_rounds),
        "round": 1, "turn_idx": 0, "activity": False,
        "inboxes": {a: [] for a in rt.cfg.actor_ids}, "outbox": [], "message_log": [], "contributions": [], "flows": [],
        "assumptions": [], "done": {}, "budget": {"llm_calls": 0, "tokens": 0, "cost_usd": 0.0},
        "status": "RUNNING", "flags": [], "review": None,
    }
    with checkpointer(runs_dir) as cp:
        app = build_graph(rt, cp)
        app.invoke(init, _thread(run_id))
        res = _result(app, run_id, run_dir)
    if res["interrupt"]:
        rt.trace.emit("run_paused", None, None, awaiting="human_approval", card_id=res["interrupt"]["card_id"])
    summary = TraceStore.summarise(TraceStore.read(run_dir / "trace.jsonl"))
    (run_dir / "metrics.json").write_text(json.dumps(summary, indent=2))
    return res


def _resume_runtime(run_id: str, runs_dir: Path, clock: Callable[[], str]) -> Runtime:
    manifest_p = runs_dir / run_id / "manifest.json"
    if not manifest_p.exists():
        raise RunError(f"unknown run {run_id}")
    m = json.loads(manifest_p.read_text())
    ref = m.get("scenario")
    if ref and not Path(ref).is_absolute():
        ref = REPO_ROOT / ref
    sc = load_scenario(ref) if ref else {"id": m["scenario_id"]}
    # No LLM is needed after the simulation; scripts are irrelevant on resume.
    return _runtime(sc, run_id, runs_dir, clock, make_llm_factory({}))


def run_status(run_id: str, runs_dir: Path = DEFAULT_RUNS_DIR, clock: Callable[[], str] = utc_now) -> dict:
    rt = _resume_runtime(run_id, runs_dir, clock)
    with checkpointer(runs_dir) as cp:
        return _result(build_graph(rt, cp), run_id, rt.run_dir)


def submit_decision(run_id: str, decision: dict, runs_dir: Path = DEFAULT_RUNS_DIR,
                    clock: Callable[[], str] = utc_now) -> dict:
    """Validate a human decision, then resume the paused graph with it."""
    rt = _resume_runtime(run_id, runs_dir, clock)
    with checkpointer(runs_dir) as cp:
        app = build_graph(rt, cp)
        st = _result(app, run_id, rt.run_dir)
        if not st["interrupt"]:
            raise RunError(f"run {run_id} is not awaiting a human decision (next={st['awaiting']})")
        validate_decision(decision, st["card"])  # pre-check; the node validates again
        rt.trace.emit("run_resumed", None, None, by=decision.get("reviewer"))
        app.invoke(Command(resume=decision), _thread(run_id))
        return _result(app, run_id, rt.run_dir)
