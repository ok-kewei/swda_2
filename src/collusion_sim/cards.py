"""Assembly, checking and rendering of pattern cards."""
from __future__ import annotations

import hashlib
from typing import Any

from .analysis import (classify_mo, combine_evidence, cooperation_analysis, evidence_rule,
                       functional_dependency, intent_assessment, overall_assessment)
from .config import Config, canonical_json
from .guards import scan_output
from .schemas import (ActorSummary, AssumptionItem, CheckResult, MOClassification,
                      PatternCard, ReviewOutput, ReviewSection, SimulatedContribution,
                      SimulatedFlow, SourceItem)
from .sources import SourceStore

DISCLAIMER = (
    "SIMULATED RISK HYPOTHESIS. Produced by scripted/LLM agents role-playing incentives; it is NOT "
    "evidence that any person or organisation has behaved this way. Social media excerpts are "
    "unverified. Human approval means 'worth testing against data', not a finding of fact."
)


def card_hash(card: dict) -> str:
    body = {k: v for k, v in card.items() if k != "content_hash"}
    return hashlib.sha256(canonical_json(body).encode()).hexdigest()


def assemble_draft(state: dict, cfg: Config, sources: SourceStore) -> dict:
    contribs = state.get("contributions", [])
    messages = state.get("message_log", [])

    # Four separate assessments. Dependency alone never decides collusion.
    dependency = functional_dependency(contribs, cfg)
    cooperation = cooperation_analysis(contribs, messages, cfg.actor_ids)
    intents = intent_assessment(contribs, cfg.actor_ids)
    overall = overall_assessment(dependency, cooperation, intents)
    tags = sorted({t for c in contribs for t in c["behaviour_tags"]})
    mo = classify_mo(tags, cfg)

    cited: dict[str, set[str]] = {}
    for c in contribs:
        for g in c["grounding"]:
            cited.setdefault(g["source_id"], set()).add(c["actor"])
    for m in mo["linked_mos"]:
        cited.setdefault(m, set()).add("rule:mo_classification")
    source_material = []
    for sid in sorted(cited):
        r = sources.records[sid]
        if r.quarantined:
            continue  # never copied into a card; surfaced as a flag instead
        source_material.append(SourceItem(source_id=sid, annex=r.annex, text=r.text, basis=r.basis,
                                          cited_by=sorted(cited[sid])).model_dump())

    # One row per actor, including those who declined (shown as excluded).
    role_of = {r.actor: r.role for r in cooperation.roles}
    intent_of = {i.actor: i.intent for i in intents}
    actors = []
    for a in cfg.actor_ids:
        mine = [c for c in contribs if c["actor"] == a]
        necessary = a in dependency.necessary_roles if mine else None
        actors.append(ActorSummary(actor=a, role=role_of[a], functions=sorted({c["function"] for c in mine}),
                                   contributions=[c["description"] for c in mine],
                                   benefits=sorted({c["benefit_to_self"] for c in mine}),
                                   functionally_necessary=necessary, intent=intent_of[a]).model_dump())
    return {
        "run_id": state["run_id"], "scenario_id": state["scenario_id"],
        "title": f"{state['title']} (simulated)", "theme": state["theme"],
        "actors": actors,
        "flows": [SimulatedFlow(**f).model_dump() for f in state.get("flows", [])],
        "source_material": source_material,
        "simulated_behaviour": [SimulatedContribution(**c).model_dump() for c in contribs],
        "assumptions": [AssumptionItem(**a).model_dump() for a in state.get("assumptions", [])],
        "behaviour_tags": tags,
        "functional_dependency": dependency.model_dump(),
        "cooperation": cooperation.model_dump(),
        "intent_assessment": [i.model_dump() for i in intents],
        "overall_assessment": overall.model_dump(),
        "mo_rule": mo,
        "cited_social_ids": sorted(s for s in cited if sources.records[s].annex in ("B", "extra")),
    }


def _checks(draft: dict, cfg: Config, sources: SourceStore, review: ReviewOutput | None,
            mo_agree: bool, ev_flags: list[str]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    bad_ids, bad_scope = [], []
    for c in draft["simulated_behaviour"]:
        for g in c["grounding"]:
            if not sources.usable(g["source_id"]):
                bad_ids.append(g["source_id"])
            elif not cfg.profiles[c["actor"]].can_see(g["source_id"]):
                bad_scope.append(f"{c['actor']}:{g['source_id']}")
    checks.append(CheckResult(name="grounding_ids_exist_and_usable", passed=not bad_ids, blocking=True,
                              detail=", ".join(bad_ids) or "all grounding IDs resolve to usable sources"))
    checks.append(CheckResult(name="grounding_within_actor_visibility", passed=not bad_scope, blocking=True,
                              detail=", ".join(bad_scope) or "each actor cited only sources it could see"))
    q_in_card = [s["source_id"] for s in draft["source_material"] if not sources.usable(s["source_id"])]
    checks.append(CheckResult(name="no_quarantined_text_in_card", passed=not q_in_card, blocking=True,
                              detail=", ".join(q_in_card) or "none"))
    texts = [c["description"] + " " + c["benefit_to_self"] for c in draft["simulated_behaviour"]]
    texts += [f["description"] for f in draft["flows"]] + [a["text"] for a in draft["assumptions"]]
    if review:
        texts += [review.mo_rationale, *review.concerns, *[f.note for f in review.source_findings]]
    hits = sorted({h for t in texts for h in scan_output(t)})
    checks.append(CheckResult(name="output_safety_rescan", passed=not hits, blocking=True,
                              detail=", ".join(hits) or "no unsafe or fact-asserting content"))
    if review:
        missing = set(draft["cited_social_ids"]) - {f.source_id for f in review.source_findings}
        checks.append(CheckResult(name="review_checked_all_cited_sources", passed=not missing, blocking=False,
                                  detail=", ".join(sorted(missing)) or "all cited excerpts reviewed"))
    checks.append(CheckResult(name="mo_label_agreement", passed=mo_agree, blocking=False,
                              detail="no reviewer label (review failed)" if review is None
                              else "rule and reviewer agree" if mo_agree else "rule and reviewer disagree"))
    checks.append(CheckResult(name="evidence_not_overstated", passed=not ev_flags, blocking=False,
                              detail="; ".join(ev_flags) or "reviewer grading within rule ceiling"))
    overall = draft["overall_assessment"]
    checks.append(CheckResult(name="dependency_cooperation_intent_assessed_separately", passed=True,
                              blocking=False, detail=f"{overall['classification']}: {overall['explanation']}"))
    return checks


def finalize_card(draft: dict, review: ReviewOutput | None, cfg: Config, sources: SourceStore,
                  extra_flags: list[str]) -> dict:
    mo = draft["mo_rule"]
    agree = review is not None and review.mo_label == mo["label"]
    mo_cls = MOClassification(
        rule_label=mo["label"], fully_covered_mos=mo["fully_covered"], partial_matches=mo["partial"],
        novel_elements=mo["novel_elements"], reviewer_label=review.mo_label if review else None,
        reviewer_mo_ids=review.mo_ids if review else [], reviewer_rationale=review.mo_rationale if review else "",
        agreement=agree, tag_annotation_version=cfg.mo_tag_version)

    supported = list(draft["cited_social_ids"])
    if review:
        weak = {f.source_id for f in review.source_findings if f.finding in ("irrelevant", "not_found")}
        supported = [s for s in supported if s not in weak]
    rule_strength, basis = evidence_rule(mo["linked_mos"], supported, sources)
    evidence, ev_flags = combine_evidence(rule_strength, review.evidence_strength if review else None, basis)

    checks = _checks(draft, cfg, sources, review, agree, ev_flags)
    flags = list(extra_flags) + ev_flags
    if review is None:
        flags.append("review_failed")
    elif not agree:
        flags.append(f"mo_label_disagreement:rule={mo['label']},reviewer={review.mo_label}")
    dependency, overall = draft["functional_dependency"], draft["overall_assessment"]
    flags += [f"substitutable_actor:{a}" for a in dependency["substitutable_roles"]]
    flags += [f"single_actor_feasible:{a}" for a in dependency["single_actor_feasible_by"]]
    flags += [f"sources_quarantined:{r.id}" for r in sources.quarantined()]
    flags += [f"excluded_declined:{r['actor']}" for r in draft["cooperation"]["roles"] if r["role"] == "declined"]
    flags += [f"intent_unresolved:{i['actor']}" for i in draft["intent_assessment"] if i["intent"] == "UNKNOWN"]
    flags += [f"possibly_unwitting:{i['actor']}" for i in draft["intent_assessment"]
              if i["intent"] == "POSSIBLY_UNWITTING"]
    flags.append(f"mo_label_provisional:{mo['label']}")

    if overall["classification"] == "INSUFFICIENT" or review is None:
        status = "INCOMPLETE"
    elif any(c.blocking and not c.passed for c in checks):
        status = "BLOCKED"
    else:
        status = "PENDING_HUMAN_REVIEW"

    card = PatternCard(
        card_id=f"PC-{draft['run_id']}", run_id=draft["run_id"], scenario_id=draft["scenario_id"],
        title=draft["title"], theme=draft["theme"], disclaimer=DISCLAIMER, status=status,
        actors=draft["actors"], flows=draft["flows"], source_material=draft["source_material"],
        simulated_behaviour=draft["simulated_behaviour"], assumptions=draft["assumptions"],
        functional_dependency=draft["functional_dependency"], cooperation=draft["cooperation"],
        intent_assessment=draft["intent_assessment"], overall_assessment=draft["overall_assessment"],
        mo_classification=mo_cls, evidence=evidence,
        test_data_needed=review.test_data_needed if review else [],
        review=ReviewSection(completed=review is not None,
                             source_findings=review.source_findings if review else [],
                             assumption_findings=review.assumption_findings if review else [],
                             concerns=review.concerns if review else [], deterministic_checks=checks),
        flags=sorted(set(flags)),
    ).model_dump(mode="json")
    card["content_hash"] = card_hash(card)
    PatternCard.model_validate(card)  # schema-validated hand-off
    return card


# --------------------------------------------------------------------------
def render_markdown(card: dict) -> str:
    dep, coop, overall = card["functional_dependency"], card["cooperation"], card["overall_assessment"]
    mo, ev = card["mo_classification"], card["evidence"]
    L: list[str] = [f"# {card['title']}", "", f"> **{card['disclaimer']}**", "",
                    f"- Card: `{card['card_id']}`  ", f"- Status: **{card['status']}**  ",
                    f"- Content hash: `{card['content_hash']}`", "", f"**Theme:** {card['theme']}", ""]

    L += ["## Summary", "",
          "| Item | Result |", "|---|---|",
          f"| Overall assessment | **{overall['classification']}**"
          f"{'' if overall['intent_resolved'] else ' (intent unresolved)'} |",
          f"| Functional dependency | necessary roles: {', '.join(dep['necessary_roles']) or '-'}; "
          f"substitutable: {', '.join(dep['substitutable_roles']) or '-'} |",
          f"| Simulated cooperation | {coop['summary']} |",
          "| Intent | " + "; ".join(f"{i['actor']}: {i['intent']}" for i in card["intent_assessment"]) + " |",
          f"| Evidence strength | **{ev['final_strength']}** |",
          f"| MO classification | {'provisional ' if mo['provisional'] else ''}{mo['rule_label']}"
          f"{' of ' + ', '.join(mo['fully_covered_mos']) if mo['fully_covered_mos'] else ''} |",
          f"| Human-review flags | {len(card['flags'])} (see section 13) |", ""]

    L += ["## 1. Actors (SIMULATED)", "", "| Actor | Role | Functionally necessary | Intent |", "|---|---|---|---|"]
    for a in card["actors"]:
        necessary = "-" if a["functionally_necessary"] is None else ("yes" if a["functionally_necessary"] else "no")
        L.append(f"| {a['actor']} | {a['role']} | {necessary} | {a['intent']} |")
    for a in card["actors"]:
        if a["contributions"]:
            L.append("")
            L.append(f"**{a['actor']}**. Functions: {', '.join(a['functions'])}")
            L += [f"  - {c}" for c in a["contributions"]]
            L.append(f"  - *Benefit:* {'; '.join(b.rstrip('.') for b in a['benefits'])}.")

    L += ["", "## 2. Functional dependency (actor-removal check)", "", f"*{dep['note']}*", "",
          "| Removed actor | Mechanism still possible? | Uncovered functions | Role necessary |",
          "|---|---|---|---|"]
    L += [f"| {r['removed_actor']} | {'yes' if r['still_feasible'] else 'no'} | "
          f"{', '.join(r['uncovered_functions']) or '-'} | {'**yes**' if r['functionally_necessary'] else 'no'} |"
          for r in dep["removal_results"]]

    L += ["", "## 3. Simulated cooperation", "", f"**{coop['summary']}**. {coop['explanation']}", "",
          "| From | To | Round | Offer | Response |", "|---|---|---|---|---|"]
    L += [f"| {x['from_actor']} | {x['to_actor']} | {x['round']} | {x['offer_text']} | "
          f"{x['response']}{': ' + x['response_text'] if x['response_text'] else ''} |"
          for x in coop["interactions"]] or ["| - | - | - | no messages | - |"]

    L += ["", "## 4. Intent assessment", ""]
    L += [f"- **{i['actor']}: {i['intent']}**. {i['basis']}" for i in card["intent_assessment"]]

    L += ["", "## 5. Overall assessment", "",
          f"**{overall['classification']}** (intent resolved: {overall['intent_resolved']}). {overall['explanation']}", ""]
    L += ["", "## 6. Flows (SIMULATED)", "", "| From | To | Asset | Description |", "|---|---|---|---|"]
    L += [f"| {f['from_party']} | {f['to_party']} | {f['asset']} | {f['description']} |" for f in card["flows"]]
    L += ["", "## 7. Source material (verbatim, untrusted)", ""]
    L += [f"- **{s['source_id']}** (Annex {s['annex']}, {s['basis']}; cited by {', '.join(s['cited_by'])}): "
          f"\"{s['text']}\"" for s in card["source_material"]] or ["- none"]
    L += ["", "## 8. Assumptions", ""]
    L += [f"- [{a['made_by']}, r{a['round']}] {a['text']}" for a in card["assumptions"]] or ["- none"]
    L += ["", "## 9. MO classification", "",
          f"- Rule: **{'provisional ' if mo['provisional'] else ''}{mo['rule_label']}**; fully covered: {', '.join(mo['fully_covered_mos']) or '-'}; "
          f"partial: {mo['partial_matches'] or '-'}; novel elements: {', '.join(mo['novel_elements']) or '-'}",
          f"- Review Agent: **{mo['reviewer_label']}** {mo['reviewer_mo_ids']}: {mo['reviewer_rationale']}",
          f"- Agreement: {mo['agreement']} (tag annotation v{mo['tag_annotation_version']})", "",
          "## 10. Evidence strength", "",
          f"- Rule: {ev['rule_strength']}; reviewer: {ev['reviewer_strength']}; **final: {ev['final_strength']}**"]
    L += [f"  - {b}" for b in ev["basis"]]
    L += ["", "## 11. Data needed to test this pattern", ""]
    L += [f"- {t['data_item']} ({t['granularity']}): {t['purpose']}" for t in card["test_data_needed"]] or ["- none"]
    L += ["", "## 12. Review checks", "", "| Check | Passed | Blocking | Detail |", "|---|---|---|---|"]
    L += [f"| {c['name']} | {'yes' if c['passed'] else '**NO**'} | {c['blocking']} | {c['detail']} |"
          for c in card["review"]["deterministic_checks"]]
    if card["review"]["concerns"]:
        L += ["", "**Review Agent concerns:**"] + [f"- {c}" for c in card["review"]["concerns"]]
    L += ["", "## 13. Flags for the human reviewer", ""] + ([f"- {f}" for f in card["flags"]] or ["- none"])
    return "\n".join(L) + "\n"


def normalise_for_regression(card: dict) -> dict[str, Any]:
    """Strip run-specific fields so cards from different runs can be compared."""
    c = {k: v for k, v in card.items() if k not in ("run_id", "card_id", "content_hash")}
    return c
