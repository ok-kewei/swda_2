"""Append-only, hash-chained run trace (JSONL) plus a LangChain callback.

Each event stores the SHA-256 of the previous event, so any edit, deletion or
reordering of the trace file is detectable with ``TraceStore.verify``. Events
are appended to disk as they happen, so the trace survives a process restart
and continues seamlessly when a paused run is resumed for human approval.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from langchain_core.callbacks import BaseCallbackHandler

from .config import canonical_json

GENESIS = "0" * 64


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _hash(rec: dict) -> str:
    return hashlib.sha256(canonical_json(rec).encode()).hexdigest()


class TraceStore:
    def __init__(self, path: Path, run_id: str, clock: Callable[[], str] = utc_now):
        self.path = Path(path)
        self.run_id = run_id
        self.clock = clock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq, self._prev = 0, GENESIS
        # LangGraph's ToolNode runs tool calls in parallel threads, so writes must take turns.
        self._lock = threading.Lock()
        if self.path.exists():
            events = self.read(self.path)
            if events:
                self._seq, self._prev = events[-1]["seq"] + 1, events[-1]["hash"]

    def emit(self, event: str, agent: str | None = None, round: int | None = None, **data: Any) -> dict:
        with self._lock:
            rec = {"seq": self._seq, "run_id": self.run_id, "ts": self.clock(), "event": event,
                   "agent": agent, "round": round, "data": data, "prev_hash": self._prev}
            rec["hash"] = _hash(rec)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            self._seq += 1
            self._prev = rec["hash"]
            return rec

    # --- reading / verification -------------------------------------------
    @staticmethod
    def read(path: Path) -> list[dict]:
        return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def verify(path: Path) -> tuple[bool, int | None]:
        prev = GENESIS
        for i, rec in enumerate(TraceStore.read(path)):
            body = {k: v for k, v in rec.items() if k != "hash"}
            if rec.get("seq") != i or rec.get("prev_hash") != prev or _hash(body) != rec.get("hash"):
                return False, i
            prev = rec["hash"]
        return True, None

    @staticmethod
    def summarise(events: list[dict]) -> dict:
        kinds = Counter(e["event"] for e in events)
        calls_by_agent = Counter(e["agent"] for e in events if e["event"] == "llm_end")
        tokens = sum(e["data"].get("tokens", 0) for e in events if e["event"] == "llm_usage")
        cost = sum(e["data"].get("cost_usd", 0.0) for e in events if e["event"] == "llm_usage")
        return {
            "events": len(events),
            "llm_calls": kinds.get("llm_end", 0),
            "llm_calls_by_agent": dict(calls_by_agent),
            "estimated_tokens": tokens,
            "estimated_cost_usd": round(cost, 6),
            "retries": kinds.get("retry", 0),
            "validation_failures": kinds.get("validation_failed", 0),
            "tool_calls_allowed": kinds.get("tool_allowed", 0),
            "tool_calls_denied": kinds.get("tool_denied", 0),
            "messages_routed": kinds.get("message_routed", 0),
            "messages_blocked": kinds.get("message_blocked", 0),
            "sources_quarantined": kinds.get("source_quarantined", 0),
            "limit_hits": kinds.get("limit_hit", 0),
            "event_counts": dict(sorted(kinds.items())),
        }


class TraceCallback(BaseCallbackHandler):
    """Records every chat-model call (hashes, sizes) without storing raw prompts twice."""

    def __init__(self, trace: TraceStore, agent: str, round: int | None):
        self.trace, self.agent, self.round = trace, agent, round

    def on_chat_model_start(self, serialized, messages, **kwargs):  # noqa: D401
        flat = "\n".join(str(m.content) for batch in messages for m in batch)
        self.trace.emit("llm_start", self.agent, self.round,
                        prompt_sha256=hashlib.sha256(flat.encode()).hexdigest(),
                        n_messages=sum(len(b) for b in messages), prompt_chars=len(flat))

    def on_llm_end(self, response, **kwargs):
        gen = response.generations[0][0]
        msg = getattr(gen, "message", None)
        text = gen.text or ""
        self.trace.emit("llm_end", self.agent, self.round,
                        output_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        output_chars=len(text),
                        tool_calls=[tc["name"] for tc in getattr(msg, "tool_calls", []) or []])

    def on_llm_error(self, error, **kwargs):
        self.trace.emit("llm_error", self.agent, self.round, error=type(error).__name__)
