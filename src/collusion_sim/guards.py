"""Deterministic safeguards.

* Input guard: hidden Unicode and instruction-like text in untrusted sources
  and in agent-to-agent messages.
* Output guard: keeps content at risk-pattern level (no operational
  how-to, evasion advice, personal identifiers or named organisations) and
  stops simulated behaviour from being asserted as fact.
* Turn validator: role boundaries, citation scope, controlled vocabularies,
  channel policy and message limits.

These are regex/rule based on purpose: they are cheap, explainable and
testable. They are a floor, not a ceiling; a production system would add a
model-based classifier behind them (see docs/DESIGN_NOTE.md).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from .config import ActorProfile, Config
    from .schemas import ActorTurn, ReviewOutput
    from .sources import SourceStore

HIDDEN_UNICODE_RE = re.compile(
    "[​-‏ -‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]"
)

INJECTION_RULES: dict[str, re.Pattern] = {
    "override_instructions": re.compile(
        r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|rules?|prompts?|guidelines?)\b", re.I),
    # Narrow on purpose: plain "act as" appears in legitimate MO text
    # ("Dormant entities act as employers"), which an earlier version quarantined.
    "role_hijack": re.compile(
        r"\b(you are now|from now on,? you|pretend to be|your new role|"
        r"act as (an?|the) (ai|assistant|system|admin(istrator)?|reviewer|approver|developer))\b", re.I),
    "system_prompt_probe": re.compile(r"\b(system prompt|developer message|hidden instructions?)\b", re.I),
    "approval_manipulation": re.compile(
        r"\b(mark|set|flag)\b.{0,30}\b(approved|approve|cleared|safe)\b|\bauto-?approve\b", re.I),
    "markup_injection": re.compile(r"(<\|[a-z_]+\|>|</?(system|assistant|tool)>|^\s*#{2,}\s*(system|instruction))",
                                   re.I | re.M),
    "tool_invocation": re.compile(r"\b(call|invoke|run)\b.{0,20}\b(tool|function)\b", re.I),
}

UNSAFE_RULES: dict[str, re.Pattern] = {
    "operational_steps": re.compile(r"\bstep\s*\d+\b|^\s*\d+[.)]\s+\S", re.I | re.M),
    "evasion_advice": re.compile(
        r"\b(avoid|evad|escap|bypass|defeat|get(ting)? around|beat)\w*\b.{0,20}"
        r"\b(detection|screening|checks?|audits?|auditors?|controls?|the system|flags?)\b", re.I),
    "undetected": re.compile(r"\bundetect(ed|able)\b|without (being |getting )?(caught|detected|flagged|noticed)", re.I),
    "forgery_method": re.compile(r"\bhow to\b.{0,30}\b(forge|fake|falsify|spoof|backdate)\b", re.I),
    "url": re.compile(r"https?://|www\.", re.I),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "national_id": re.compile(r"\b[STFGM]\d{7}[A-Z]\b"),
    "phone_number": re.compile(r"(?<!\$)\b[689]\d{3}[ -]?\d{4}\b"),
    "named_organisation": re.compile(
        r"\b[A-Z][\w&'-]*(?:\s+[A-Z][\w&'-]*)*\s+(?:Pte\.?\s*Ltd|Ltd|LLP|Inc|Academy|Institute|College|Centre)\b"),
}

FACT_ASSERTION_RULES: dict[str, re.Pattern] = {
    "asserted_as_fact": re.compile(
        r"(?<!not )(?<!un)\b(confirmed|proven)\b|\b(is|are) (currently|actually) (happening|doing this)\b"
        r"|\bwe know (that )?\b|\bin reality\b|\bthis (definitely|certainly) happens\b", re.I),
}


def scan_injection(text: str) -> list[str]:
    hits = [f"injection:{name}" for name, rx in INJECTION_RULES.items() if rx.search(text)]
    if HIDDEN_UNICODE_RE.search(text):
        hits.append("injection:hidden_unicode")
    return hits


def scan_output(text: str) -> list[str]:
    hits = [f"unsafe:{n}" for n, rx in UNSAFE_RULES.items() if rx.search(text)]
    hits += [f"fact:{n}" for n, rx in FACT_ASSERTION_RULES.items() if rx.search(text)]
    hits += scan_injection(text)
    return hits


@dataclass(frozen=True)
class Violation:
    code: str
    where: str
    detail: str = ""

    def __str__(self) -> str:  # used in retry feedback; never echoes raw model text
        return f"{self.code} at {self.where}" + (f" ({self.detail})" if self.detail else "")


def _scan_fields(fields: Iterable[tuple[str, str]]) -> list[Violation]:
    out: list[Violation] = []
    for where, text in fields:
        for hit in scan_output(text):
            out.append(Violation(hit, where))
    return out


def validate_actor_turn(turn: "ActorTurn", profile: "ActorProfile", cfg: "Config",
                        sources: "SourceStore") -> list[Violation]:
    v: list[Violation] = []
    lim = cfg.limits
    if len(turn.messages) > lim.max_messages_per_agent_per_round:
        v.append(Violation("limit:too_many_messages", "messages", str(len(turn.messages))))
    texts: list[tuple[str, str]] = []
    for i, m in enumerate(turn.messages):
        if m.to not in profile.may_message:
            v.append(Violation("channel:recipient_not_allowed", f"messages[{i}]", m.to))
        if len(m.text) > lim.max_message_chars:
            v.append(Violation("limit:message_too_long", f"messages[{i}]", str(len(m.text))))
        texts.append((f"messages[{i}].text", m.text))
    for i, c in enumerate(turn.contributions):
        if c.function not in cfg.functions:
            v.append(Violation("vocab:unknown_function", f"contributions[{i}]", c.function))
        elif c.function not in profile.capabilities:
            v.append(Violation("role:capability_outside_profile", f"contributions[{i}]", c.function))
        for t in c.behaviour_tags:
            if t not in cfg.behaviour_tags:
                v.append(Violation("vocab:unknown_tag", f"contributions[{i}]", t))
        for j, g in enumerate(c.grounding):
            if not sources.exists(g.source_id):
                v.append(Violation("citation:unknown_source", f"contributions[{i}].grounding[{j}]", g.source_id))
            elif not sources.usable(g.source_id):
                v.append(Violation("citation:quarantined_source", f"contributions[{i}].grounding[{j}]", g.source_id))
            elif not profile.can_see(g.source_id):
                v.append(Violation("citation:outside_visibility", f"contributions[{i}].grounding[{j}]", g.source_id))
            texts.append((f"contributions[{i}].grounding[{j}].relation", g.relation))
        texts += [(f"contributions[{i}].description", c.description),
                  (f"contributions[{i}].benefit_to_self", c.benefit_to_self)]
    for i, f in enumerate(turn.flows):
        for party in (f.from_party, f.to_party):
            if party not in cfg.flow_parties:
                v.append(Violation("vocab:unknown_party", f"flows[{i}]", party))
        if f.asset not in cfg.flow_assets:
            v.append(Violation("vocab:unknown_asset", f"flows[{i}]", f.asset))
        if profile.id not in (f.from_party, f.to_party):
            # An actor may only describe flows it is a party to.
            v.append(Violation("role:flow_not_involving_actor", f"flows[{i}]"))
        texts.append((f"flows[{i}].description", f.description))
    texts += [(f"assumptions[{i}]", a.text) for i, a in enumerate(turn.assumptions)]
    return v + _scan_fields(texts)


def validate_review(out: "ReviewOutput", cfg: "Config", sources: "SourceStore",
                    cited: set[str], n_assumptions: int) -> list[Violation]:
    v: list[Violation] = []
    for i, f in enumerate(out.source_findings):
        if not sources.exists(f.source_id):
            v.append(Violation("citation:unknown_source", f"source_findings[{i}]", f.source_id))
    missing = cited - {f.source_id for f in out.source_findings}
    if missing:
        v.append(Violation("review:cited_sources_not_checked", "source_findings", ",".join(sorted(missing))))
    for i, a in enumerate(out.assumption_findings):
        if a.assumption_index >= n_assumptions:
            v.append(Violation("review:bad_assumption_index", f"assumption_findings[{i}]"))
    for mo in out.mo_ids:
        if mo not in cfg.mo_tags:
            v.append(Violation("citation:unknown_mo", "mo_ids", mo))
    texts = [("mo_rationale", out.mo_rationale)]
    texts += [(f"source_findings[{i}].note", f.note) for i, f in enumerate(out.source_findings)]
    texts += [(f"concerns[{i}]", c) for i, c in enumerate(out.concerns)]
    texts += [(f"test_data_needed[{i}]", f"{t.data_item} {t.purpose}") for i, t in enumerate(out.test_data_needed)]
    return v + _scan_fields(texts)
