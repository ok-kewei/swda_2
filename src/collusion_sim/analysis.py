"""Deterministic analysis of a simulated pattern, in separate steps:

1. functional_dependency  - which roles the mechanism NEEDS (actor-removal check)
2. cooperation_analysis   - did the actors actually interact (offer -> accept)?
3. intent_assessment      - did each actor KNOW the conduct was improper?
4. overall_assessment     - combines 1-3; dependency alone never means collusion
plus MO classification and evidence strength.

These run in plain Python so they are reproducible and auditable. The Review
Agent gives an independent LLM judgement; disagreements are flagged for the
human rather than silently resolved.
"""
from __future__ import annotations

from typing import Iterable

from .config import Config
from .schemas import (AUTO_EVIDENCE_CEILING, EVIDENCE_ORDER, ActorRemovalResult, ActorRole, Cooperation,
                      EvidenceAssessment, FunctionalDependency, IntentAssessment, Interaction,
                      OverallAssessment)
from .sources import SourceStore

OFFER_INTENTS = ("propose", "inform", "counter")
REPLY_INTENTS = {"accept": "accepted", "decline": "declined", "counter": "countered"}


# --------------------------------------------------------------------------
# 1. Functional dependency (actor-removal check)
# --------------------------------------------------------------------------
def functional_dependency(contributions: list[dict], cfg: Config) -> FunctionalDependency:
    """For each participant: remove it, and check if the others can still cover every
    required function with their profile capabilities. If not, its ROLE is necessary.

    This shows role dependency only. It does not show that anyone cooperated or knew.
    """
    participants = sorted({c["actor"] for c in contributions})
    required = sorted({c["function"] for c in contributions})
    capabilities = {a: cfg.profiles[a].capabilities for a in participants}

    def uncovered(actors: Iterable[str]) -> list[str]:
        covered: set[str] = set()
        for actor in actors:
            covered |= capabilities[actor]
        return sorted(set(required) - covered)

    results = []
    for actor in participants:
        remaining = [p for p in participants if p != actor]
        missing = uncovered(remaining)
        results.append(ActorRemovalResult(removed_actor=actor, remaining_actors=remaining,
                                          still_feasible=not missing, uncovered_functions=missing,
                                          functionally_necessary=bool(missing)))

    return FunctionalDependency(
        participants=participants,
        required_functions=required,
        removal_results=results,
        necessary_roles=[r.removed_actor for r in results if r.functionally_necessary],
        substitutable_roles=[r.removed_actor for r in results if not r.functionally_necessary],
        single_actor_feasible_by=[a for a in participants if not uncovered([a])],
        note="Shows which roles the simulated mechanism needs. It does not show cooperation or intent.",
    )


# --------------------------------------------------------------------------
# 2. Cooperation (from the messages the orchestrator actually delivered)
# --------------------------------------------------------------------------
def cooperation_analysis(contributions: list[dict], messages: list[dict],
                         actor_ids: list[str]) -> Cooperation:
    """Find each offer (propose / inform / counter) from A to B and B's first reply to A.

    A pair cooperates only if B ACCEPTED A's offer and BOTH contributed to the mechanism.
    """
    contributed = {c["actor"] for c in contributions}

    interactions: list[Interaction] = []
    for i, offer in enumerate(messages):
        if offer["intent"] not in OFFER_INTENTS:
            continue
        reply = None
        for later in messages[i + 1:]:
            if later["from"] == offer["to"] and later["to"] == offer["from"] and later["intent"] in REPLY_INTENTS:
                reply = later
                break
        interactions.append(Interaction(
            from_actor=offer["from"], to_actor=offer["to"], round=offer["round"],
            offer_intent=offer["intent"], offer_text=offer["text"],
            response=REPLY_INTENTS[reply["intent"]] if reply else "no_response",
            response_text=reply["text"] if reply else ""))

    accepted = [x for x in interactions if x.response == "accepted"]
    pairs = sorted({tuple(sorted((x.from_actor, x.to_actor))) for x in accepted
                    if x.from_actor in contributed and x.to_actor in contributed})

    roles = []
    for actor in actor_ids:
        offered_and_accepted = any(x.from_actor == actor for x in accepted)
        accepted_an_offer = any(x.to_actor == actor for x in accepted)
        proposed = any(x.from_actor == actor and x.offer_intent == "propose" for x in interactions)
        declined = any(m["from"] == actor and m["intent"] == "decline" for m in messages)
        if offered_and_accepted:
            role = "initiator"
        elif accepted_an_offer:
            role = "acceptor"
        elif proposed:
            role = "proposal_rejected"
        elif declined and actor not in contributed:
            role = "declined"
        elif actor in contributed:
            role = "independent"
        else:
            role = "not_involved"
        roles.append(ActorRole(actor=actor, role=role, contributed=actor in contributed,
                               excluded=actor not in contributed))

    if pairs:
        summary = "SIMULATED_COOPERATION"
        why = "; ".join(f"{x.to_actor} accepted an offer from {x.from_actor} (round {x.round})"
                        for x in accepted if tuple(sorted((x.from_actor, x.to_actor))) in pairs)
    elif any(x.response in ("declined", "no_response") and x.offer_intent == "propose" for x in interactions):
        summary = "PROPOSAL_REJECTED"
        why = "A proposal was made but not accepted by a contributing actor."
    else:
        summary = "NO_INTERACTION"
        why = "No accepted offer between contributing actors."
    return Cooperation(interactions=interactions, roles=roles, cooperating_pairs=[list(p) for p in pairs],
                       summary=summary, explanation=why + " (Simulated interaction, not a real-world fact.)")


# --------------------------------------------------------------------------
# 3. Intent (only from what the simulation explicitly states)
# --------------------------------------------------------------------------
def intent_assessment(contributions: list[dict], actor_ids: list[str]) -> list[IntentAssessment]:
    """KNOWING / POSSIBLY_UNWITTING only if the actor's contributions say so.
    Otherwise UNKNOWN: accepting a reward or taking part does not by itself prove intent."""
    results = []
    for actor in actor_ids:
        mine = [c for c in contributions if c["actor"] == actor]
        if not mine:
            results.append(IntentAssessment(actor=actor, intent="NOT_APPLICABLE",
                                            basis="Did not contribute to the mechanism."))
            continue
        stated = {c.get("awareness", "not_stated") for c in mine} - {"not_stated"}
        if stated == {"knowing"}:
            intent, basis = "KNOWING", "The simulated contributions state that this actor knowingly takes part."
        elif stated == {"unaware"}:
            intent, basis = "POSSIBLY_UNWITTING", "The simulated contributions state that this actor does not realise the conduct is improper."
        elif stated:
            intent, basis = "UNKNOWN", "The simulated contributions give conflicting signals about awareness."
        else:
            intent, basis = "UNKNOWN", ("The scenario does not establish whether this actor knew the conduct was "
                                        "improper. Taking part or accepting a reward does not by itself show intent.")
        results.append(IntentAssessment(actor=actor, intent=intent, basis=basis))
    return results


# --------------------------------------------------------------------------
# 4. Overall assessment
# --------------------------------------------------------------------------
def overall_assessment(dependency: FunctionalDependency, cooperation: Cooperation,
                       intents: list[IntentAssessment]) -> OverallAssessment:
    """Collusion needs ALL of: >=2 necessary roles, simulated cooperation between them,
    and knowing intent. Missing intent -> POTENTIAL_COLLUSION, never COLLUSION."""
    participants = dependency.participants
    intent_of = {i.actor: i.intent for i in intents}

    if not participants:
        return OverallAssessment(classification="INSUFFICIENT", core_actors=[], intent_resolved=False,
                                 explanation="No actor contributed to a mechanism.")

    if len(participants) == 1 or dependency.single_actor_feasible_by:
        solo = dependency.single_actor_feasible_by or participants
        return OverallAssessment(
            classification="SINGLE_ACTOR", core_actors=list(solo), intent_resolved=False,
            explanation=f"{', '.join(solo)} can carry out the mechanism alone; other parties are not needed. "
                        "Treat as single-actor misconduct, not collusion.")

    core = dependency.necessary_roles if len(dependency.necessary_roles) >= 2 else participants

    # Every core actor must be linked to another core actor by an accepted offer.
    linked: set[str] = set()
    for a, b in cooperation.cooperating_pairs:
        if a in core and b in core:
            linked |= {a, b}
    if linked != set(core):
        return OverallAssessment(
            classification="INDEPENDENT_ACTIONS", core_actors=core, intent_resolved=False,
            explanation="The necessary roles were not linked by any accepted offer in the simulation. "
                        "Their actions look independent; this is not evidence of collusion.")

    core_intents = [intent_of[a] for a in core]
    if all(i == "KNOWING" for i in core_intents):
        return OverallAssessment(
            classification="COLLUSION", core_actors=core, intent_resolved=True,
            explanation="Necessary roles cooperated in the simulation and each is stated to act knowingly. "
                        "This is a simulated hypothesis, not a finding.")
    if "POSSIBLY_UNWITTING" in core_intents:
        unwitting = [a for a in core if intent_of[a] == "POSSIBLY_UNWITTING"]
        return OverallAssessment(
            classification="ONE_SIDED_WITH_UNWITTING_PARTY", core_actors=core, intent_resolved=True,
            explanation=f"Roles depend on each other, but {', '.join(unwitting)} may be unwitting. "
                        "Treat as one-sided misconduct using an unwitting party, not collusion.")
    unknown = [a for a in core if intent_of[a] == "UNKNOWN"]
    return OverallAssessment(
        classification="POTENTIAL_COLLUSION", core_actors=core, intent_resolved=False,
        explanation=f"Necessary roles ({', '.join(core)}) interacted in the simulation, but intent is "
                    f"unresolved for {', '.join(unknown)}. Needs human review and real data.")


# --------------------------------------------------------------------------
# MO classification
# --------------------------------------------------------------------------
def classify_mo(tags: Iterable[str], cfg: Config) -> dict:
    """Rule-based NEW / VARIATION / KNOWN.

    coverage(MO) = |pattern_tags ∩ MO_tags| / |MO_tags|
    KNOWN     : >=1 MO fully covered and no pattern tags left unexplained
    VARIATION : >=1 MO fully covered with extra (novel) tags, or any MO with
                coverage >= variation_min_coverage
    NEW       : otherwise
    """
    p = set(tags)
    coverage = {mo: round(len(p & t) / len(t), 3) for mo, t in cfg.mo_tags.items() if p & t}
    full = sorted(mo for mo, c in coverage.items() if c >= 1.0)
    explained = set().union(*(cfg.mo_tags[m] for m in full)) if full else set()
    novel = sorted(p - explained)
    partial = {mo: c for mo, c in sorted(coverage.items()) if c < 1.0}
    if full and not novel:
        label = "KNOWN"
    elif full or any(c >= cfg.variation_min_coverage for c in partial.values()):
        label = "VARIATION"
    else:
        label = "NEW"
    linked = full or [m for m, c in partial.items() if c >= cfg.variation_min_coverage]
    return {"label": label, "fully_covered": full, "partial": partial,
            "novel_elements": novel, "linked_mos": sorted(linked)}


# --------------------------------------------------------------------------
# Evidence strength
# --------------------------------------------------------------------------
def evidence_rule(linked_mos: list[str], supporting_social: list[str],
                  sources: SourceStore) -> tuple[str, list[str]]:
    """Evidence for a SIMULATED pattern.

    SPECULATIVE : no linked MO and no supporting excerpt
    LOW         : otherwise. Excerpts are unverified, and an MO being observed at
                  typology level does not show THIS scenario happened.
    MODERATE / STRONG are never assigned automatically: they need verified data
    and a human. Simulated agent behaviour never adds evidential weight.
    """
    basis: list[str] = []
    for mo in linked_mos:
        basis.append(f"{mo} basis '{sources.records[mo].basis}' is a typology-level label; "
                     "it does not show that this simulated scenario occurred.")
    for sid in supporting_social:
        basis.append(f"{sid}: unverified social media excerpt; at most a weak signal for one element, "
                     "not proof of the full arrangement.")
    basis.append("Simulated agent behaviour is a hypothesis and adds no evidential weight.")
    basis.append("MODERATE or STRONG require verified data and a human reviewer.")
    strength = "LOW" if (linked_mos or supporting_social) else "SPECULATIVE"
    return strength, basis


def combine_evidence(rule: str, reviewer: str | None, basis: list[str]) -> tuple[EvidenceAssessment, list[str]]:
    flags: list[str] = []
    final = rule
    if reviewer is not None:
        if EVIDENCE_ORDER[reviewer] > EVIDENCE_ORDER[rule]:
            flags.append(f"reviewer_overstated_evidence:{reviewer}>{rule}")
        final = min(rule, reviewer, key=EVIDENCE_ORDER.__getitem__)
    if EVIDENCE_ORDER[final] > EVIDENCE_ORDER[AUTO_EVIDENCE_CEILING]:  # defence in depth
        final = AUTO_EVIDENCE_CEILING
    return EvidenceAssessment(rule_strength=rule, reviewer_strength=reviewer,
                              final_strength=final, basis=basis), flags
