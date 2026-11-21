import pytest

from collusion_sim.analysis import classify_mo, combine_evidence, evidence_rule, functional_dependency


def c(actor, function):
    return {"actor": actor, "function": function}


# Test: when each of two actors has a function the other lacks, both ROLES are necessary.
# Expected: both necessary. (Dependency only, it does not say they colluded.)
def test_both_roles_functionally_necessary(cfg):
    d = functional_dependency([c("provider", "assessment_result"), c("employer", "fee_funding")], cfg)
    assert d.necessary_roles == ["employer", "provider"] and d.single_actor_feasible_by == []
    assert "does not show cooperation or intent" in d.note


# Test: an actor whose function another participant could also do is substitutable.
# Expected: trainee substitutable (the employer can also attest attendance).
def test_substitutable_role_is_flagged(cfg):
    d = functional_dependency([c("employer", "employment_record"), c("provider", "course_delivery_record"),
                               c("trainee", "attendance_attestation")], cfg)
    assert d.substitutable_roles == ["trainee"]
    removal = {r.removed_actor: r for r in d.removal_results}
    assert removal["employer"].uncovered_functions == ["employment_record"]


# Test: one actor who can do every required function alone is recorded as single-actor feasible.
# Expected: provider can do it alone.
def test_single_actor_feasible(cfg):
    d = functional_dependency([c("provider", "course_delivery_record"), c("provider", "grant_claim_submission")], cfg)
    assert d.single_actor_feasible_by == ["provider"]


# Test: no contributions means no participants.
# Expected: nothing necessary, no participants.
def test_no_contributions(cfg):
    d = functional_dependency([], cfg)
    assert d.participants == [] and d.necessary_roles == []


@pytest.mark.parametrize("tags,label,full", [
    (["sham_employment", "employment_ends_after_course"], "KNOWN", ["MO-06"]),
    (["falsified_attendance", "sham_employment", "employment_ends_after_course"], "KNOWN", ["MO-05", "MO-06"]),
    (["cash_incentive_for_enrolment", "recruiter_outreach", "attendance_optional", "course_bundling"],
     "VARIATION", ["MO-04"]),
    (["cash_incentive_for_enrolment", "recruiter_outreach"], "NEW", []),  # 2/3 = 0.667 < 0.67
    (["assured_pass", "volume_steering"], "NEW", []),
])
def test_mo_classification(cfg, tags, label, full):
    r = classify_mo(tags, cfg)
    assert r["label"] == label and r["fully_covered"] == full


def test_variation_lists_novel_elements(cfg):
    r = classify_mo(["falsified_attendance", "assured_pass"], cfg)
    assert r["label"] == "VARIATION" and r["novel_elements"] == ["assured_pass"]


# Test: evidence for a simulated pattern is never above LOW, whatever supports it.
# Expected: LOW with any MO link or excerpt, SPECULATIVE with nothing.
def test_evidence_rules(sources):
    assert evidence_rule(["MO-04"], ["S1", "S3", "S4"], sources)[0] == "LOW"  # observed MO + 3 excerpts
    assert evidence_rule(["MO-07"], ["S2"], sources)[0] == "LOW"
    assert evidence_rule([], ["S4"], sources)[0] == "LOW"
    assert evidence_rule([], [], sources)[0] == "SPECULATIVE"
    basis = evidence_rule(["MO-04"], ["S3"], sources)[1]
    assert any("does not show that this simulated scenario occurred" in b for b in basis)
    assert any("adds no evidential weight" in b for b in basis)


# Test: the Review Agent cannot raise evidence, and nothing above LOW is ever automatic.
# Expected: reviewer's higher grade is flagged and ignored; final stays LOW.
def test_reviewer_cannot_raise_evidence():
    ev, flags = combine_evidence("LOW", "STRONG", [])
    assert ev.final_strength == "LOW" and flags == ["reviewer_overstated_evidence:STRONG>LOW"]
    ev, _ = combine_evidence("MODERATE", "MODERATE", [])
    assert ev.final_strength == "LOW"  # ceiling applies even if both said MODERATE
