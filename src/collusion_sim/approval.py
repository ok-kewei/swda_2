"""Human approval rules.

Approval is a genuine workflow interruption: the graph pauses in the
``human_approval`` node via LangGraph ``interrupt()`` and only continues when a
caller resumes it with ``Command(resume=<decision>)``. The decision is
validated twice: before resuming (``submit_decision`` in runtime.py) and again
inside the node, so a bad decision can never be recorded. An invalid
resume re-interrupts with the error, leaving the run paused for a valid one.

Why the Review Agent cannot approve its own output:
* its output schema (ReviewOutput) has no status/approval field and forbids
  extra keys, so an "approved" claim fails validation;
* the card schema has no APPROVED status at all;
* no tool exposes approval and the review node never calls ``Command``;
* decisions are rejected when the reviewer identity is an agent or system
  name, and must quote the content hash of the card the human actually read.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, ValidationError

from .schemas import StrictModel

RESERVED_IDENTITIES = {"trainee", "provider", "employer", "review", "review_agent", "reviewer_agent",
                       "orchestrator", "system", "agent", "llm", "assistant", "ai", "bot", "auto"}

APPROVAL_MEANING = "Approved as a risk hypothesis worth testing against data. Not a finding of fact."


class ApprovalError(ValueError):
    pass


class HumanDecision(StrictModel):
    decision: Literal["approve", "reject", "request_changes"]
    reviewer: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=10, max_length=1000)
    card_hash: str = Field(min_length=64, max_length=64)


def allowed_decisions(card_status: str) -> list[str]:
    return ["approve", "reject", "request_changes"] if card_status == "PENDING_HUMAN_REVIEW" else ["reject",
                                                                                                    "request_changes"]


def validate_decision(raw: object, card: dict) -> HumanDecision:
    if not isinstance(raw, dict):
        raise ApprovalError("decision must be an object with decision, reviewer, reason, card_hash")
    try:
        d = HumanDecision.model_validate(raw)
    except ValidationError as e:
        raise ApprovalError(f"invalid decision: {e.errors()[0]['loc']} {e.errors()[0]['msg']}") from None
    who = d.reviewer.strip().lower()
    tokens = set(who.replace("-", " ").replace("_", " ").replace(":", " ").split())
    if who in RESERVED_IDENTITIES or tokens & RESERVED_IDENTITIES:
        raise ApprovalError(f"reviewer identity '{d.reviewer}' is reserved for agents/system; a named human is required")
    if d.card_hash != card["content_hash"]:
        raise ApprovalError("card_hash does not match the card awaiting review (card changed or wrong card)")
    if d.decision not in allowed_decisions(card["status"]):
        raise ApprovalError(f"'{d.decision}' not allowed for a card with status {card['status']}")
    return d
