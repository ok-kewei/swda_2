"""Regression tests: functional dependency, cooperation, intent and the overall
assessment are judged SEPARATELY. Dependency alone must never mean collusion.

Each test builds a small simulated situation (contributions + delivered messages)
and runs the same four analysis steps the app uses.
"""
from pathlib import Path

from collusion_sim.analysis import (cooperation_analysis, functional_dependency, intent_assessment,
                                    overall_assessment)
from collusion_sim.runtime import start_run


def contribution(actor, function, awareness="not_stated"):
    return {"actor": actor, "function": function, "awareness": awareness}


def message(sender, to, intent, text="Simulated message.", rnd=1):
    return {"from": sender, "to": to, "intent": intent, "text": text, "round": rnd}


def assess(cfg, contributions, messages):
    """Run the four steps exactly as the app does (cards.assemble_draft)."""
    dependency = functional_dependency(contributions, cfg)
    cooperation = cooperation_analysis(contributions, messages, cfg.actor_ids)
    intents = intent_assessment(contributions, cfg.actor_ids)
    overall = overall_assessment(dependency, cooperation, intents)
    roles = {r.actor: r.role for r in cooperation.roles}
    intent_of = {i.actor: i.intent for i in intents}
    return dependency, cooperation, roles, intent_of, overall


def provider_cash_offer(trainee_awareness, provider_awareness="not_stated"):
    """Provider offers cash for using credits; trainee pays with credits and attests attendance."""
    return [
        contribution("provider", "recruitment_outreach", provider_awareness),
        contribution("provider", "incentive_payment", provider_awareness),
        contribution("provider", "grant_claim_submission", provider_awareness),
        contribution("trainee", "fee_funding", trainee_awareness),
        contribution("trainee", "attendance_attestation", trainee_awareness),
    ]


OFFER_ACCEPTED = [message("provider", "trainee", "propose", "Simulated offer: cash reward for using credits."),
                  message("trainee", "provider", "accept", "Simulated: would accept.")]


# Test 1: provider misconduct with an UNWITTING trainee.
# Expected: both roles necessary and they interacted, but the trainee may be unwitting,
# so it is one-sided misconduct, NOT collusion.
def test_provider_misconduct_with_unwitting_trainee(cfg):
    dep, coop, roles, intent, overall = assess(cfg, provider_cash_offer("unaware"), OFFER_ACCEPTED)
    assert dep.necessary_roles == ["provider", "trainee"]
    assert coop.summary == "SIMULATED_COOPERATION"
    assert intent["trainee"] == "POSSIBLY_UNWITTING"
    assert overall.classification == "ONE_SIDED_WITH_UNWITTING_PARTY"


# Test 2: provider and trainee KNOWINGLY cooperate.
# Expected: necessary roles + cooperation + knowing intent on both sides = COLLUSION.
def test_provider_and_trainee_knowingly_cooperate(cfg):
    dep, coop, roles, intent, overall = assess(cfg, provider_cash_offer("knowing", "knowing"), OFFER_ACCEPTED)
    assert roles["provider"] == "initiator" and roles["trainee"] == "acceptor"
    assert intent["provider"] == "KNOWING" and intent["trainee"] == "KNOWING"
    assert overall.classification == "COLLUSION" and overall.intent_resolved


# Test 3: provider proposes but the trainee REJECTS.
# Expected: trainee declined and is excluded; no cooperation; only the provider acted.
def test_provider_proposes_trainee_rejects(cfg):
    contributions = [contribution("provider", "recruitment_outreach"),
                     contribution("provider", "incentive_payment")]
    messages = [message("provider", "trainee", "propose", "Simulated offer."),
                message("trainee", "provider", "decline", "Simulated: no thanks.")]
    dep, coop, roles, intent, overall = assess(cfg, contributions, messages)
    assert roles["trainee"] == "declined" and roles["provider"] == "proposal_rejected"
    assert coop.summary == "PROPOSAL_REJECTED" and coop.cooperating_pairs == []
    assert intent["trainee"] == "NOT_APPLICABLE"
    assert overall.classification == "SINGLE_ACTOR"


# Test 4: the trainee acts on its own, with no provider involvement.
# Expected: single actor; trainee independent; provider not involved; no interaction.
def test_trainee_acts_independently(cfg):
    contributions = [contribution("trainee", "fee_funding"), contribution("trainee", "attendance_attestation")]
    dep, coop, roles, intent, overall = assess(cfg, contributions, [])
    assert roles["trainee"] == "independent" and roles["provider"] == "not_involved"
    assert coop.summary == "NO_INTERACTION"
    assert overall.classification == "SINGLE_ACTOR" and overall.core_actors == ["trainee"]


# Test 4b: both roles are necessary but the actors never interacted.
# Expected: INDEPENDENT_ACTIONS, not collusion (dependency without cooperation).
def test_necessary_roles_without_interaction_are_not_collusion(cfg):
    dep, coop, roles, intent, overall = assess(cfg, provider_cash_offer("knowing", "knowing"), [])
    assert dep.necessary_roles == ["provider", "trainee"]
    assert coop.summary == "NO_INTERACTION"
    assert overall.classification == "INDEPENDENT_ACTIONS"


# Test 5: the employer declines and is excluded from the arrangement.
# Expected: employer role "declined", not a participant, intent not applicable.
def test_employer_declines_and_is_excluded(cfg):
    messages = OFFER_ACCEPTED + [message("provider", "employer", "inform", "Simulated: would your staff join?"),
                                 message("employer", "provider", "decline", "Simulated: declines.")]
    dep, coop, roles, intent, overall = assess(cfg, provider_cash_offer("not_stated"), messages)
    assert roles["employer"] == "declined"
    assert "employer" not in dep.participants
    assert intent["employer"] == "NOT_APPLICABLE"
    employer_offer = [x for x in coop.interactions if x.to_actor == "employer"][0]
    assert employer_offer.response == "declined"


# Test 6: both roles necessary, they interacted, but the trainee's intent is NOT stated.
# Expected: POTENTIAL_COLLUSION with intent unresolved (accepting a reward is not proof of intent).
def test_both_necessary_but_trainee_intent_unknown(cfg):
    dep, coop, roles, intent, overall = assess(cfg, provider_cash_offer("not_stated", "knowing"), OFFER_ACCEPTED)
    assert dep.necessary_roles == ["provider", "trainee"]
    assert intent["trainee"] == "UNKNOWN" and intent["provider"] == "KNOWING"
    assert overall.classification == "POTENTIAL_COLLUSION" and not overall.intent_resolved


# Test 7 (end to end): the bundled-enrolment scenario through the real LangGraph run.
# Expected: the interpretation agreed for this scenario, and the run still waits for a human.
def test_bundled_scenario_end_to_end(runs: Path):
    result = start_run("bundled_enrolment_cash_reward", runs_dir=runs, run_id="bundled")
    card = result["card"]
    roles = {r["actor"]: r["role"] for r in card["cooperation"]["roles"]}
    intent = {i["actor"]: i["intent"] for i in card["intent_assessment"]}

    assert roles == {"provider": "initiator", "trainee": "acceptor", "employer": "declined"}
    assert card["functional_dependency"]["necessary_roles"] == ["provider", "trainee"]
    assert card["cooperation"]["summary"] == "SIMULATED_COOPERATION"
    assert intent["trainee"] == "UNKNOWN"
    assert card["overall_assessment"]["classification"] == "POTENTIAL_COLLUSION"
    assert card["overall_assessment"]["intent_resolved"] is False
    assert card["evidence"]["final_strength"] == "LOW"
    assert card["mo_classification"]["rule_label"] == "VARIATION"
    assert card["mo_classification"]["provisional"] is True
    assert "excluded_declined:employer" in card["flags"]
    assert result["awaiting"] == ["human_approval"]  # human approval is still mandatory
