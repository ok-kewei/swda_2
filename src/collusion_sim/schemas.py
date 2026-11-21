"""Pydantic schemas for every hand-off in the system.

All models forbid unknown fields, so an agent cannot smuggle extra keys
(for example ``"status": "APPROVED"``) through a hand-off. Every LLM output is
parsed into one of these models before the orchestrator acts on it, and the
final pattern card is validated again before it is handed to a human.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActorId = Literal["trainee", "provider", "employer"]
AgentId = Literal["trainee", "provider", "employer", "review"]
SourceId = str  # validated against the SourceStore at runtime (S\d+ or MO-\d\d)

# Evidence for a SIMULATED pattern. The system never assigns more than LOW on its own:
# MODERATE / STRONG need verified data and a human (see analysis.evidence_rule).
EvidenceStrength = Literal["SPECULATIVE", "LOW", "MODERATE", "STRONG"]
EVIDENCE_ORDER: dict[str, int] = {"SPECULATIVE": 0, "LOW": 1, "MODERATE": 2, "STRONG": 3}
AUTO_EVIDENCE_CEILING = "LOW"

# Whether a simulated actor knows the conduct is improper.
# "not_stated" is the default: accepting a reward does not by itself show intent.
Awareness = Literal["knowing", "unaware", "not_stated"]
MOLabel = Literal["NEW", "VARIATION", "KNOWN"]

SCHEMA_VERSION = "1.0"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------------
# Actor agent output (one turn)
# --------------------------------------------------------------------------
class OutMessage(StrictModel):
    to: ActorId
    intent: Literal["propose", "accept", "decline", "counter", "inform"]
    text: str = Field(min_length=1, max_length=2000)


class Grounding(StrictModel):
    """Link from a simulated step to a source that motivated it.

    A grounding does NOT mean the source shows the behaviour happened; it records
    which (unverified) source inspired the hypothesis.
    """

    source_id: SourceId = Field(pattern=r"^(S\d+|MO-\d{2})$")
    relation: str = Field(min_length=1, max_length=300)


class Contribution(StrictModel):
    function: str
    description: str = Field(min_length=1, max_length=400)
    benefit_to_self: str = Field(min_length=1, max_length=300)
    behaviour_tags: list[str] = Field(default_factory=list, max_length=6)
    grounding: list[Grounding] = Field(default_factory=list, max_length=5)
    awareness: Awareness = "not_stated"


class Flow(StrictModel):
    from_party: str
    to_party: str
    asset: str
    description: str = Field(min_length=1, max_length=300)


class Assumption(StrictModel):
    text: str = Field(min_length=1, max_length=300)


class ActorTurn(StrictModel):
    messages: list[OutMessage] = Field(default_factory=list)
    contributions: list[Contribution] = Field(default_factory=list, max_length=6)
    flows: list[Flow] = Field(default_factory=list, max_length=8)
    assumptions: list[Assumption] = Field(default_factory=list, max_length=6)
    done: bool = False


# --------------------------------------------------------------------------
# Review agent output. Note: no status / approval field exists.
# --------------------------------------------------------------------------
class SourceFinding(StrictModel):
    source_id: SourceId
    finding: Literal["supports", "weak", "irrelevant", "not_found"]
    note: str = Field(max_length=300)


class AssumptionFinding(StrictModel):
    assumption_index: int = Field(ge=0)
    finding: Literal["reasonable", "questionable", "unsupported"]
    note: str = Field(max_length=300)


class TestDataNeed(StrictModel):
    data_item: str = Field(max_length=200)
    purpose: str = Field(max_length=300)
    granularity: Literal["aggregate", "pseudonymised_record"]


class ReviewOutput(StrictModel):
    source_findings: list[SourceFinding]
    assumption_findings: list[AssumptionFinding] = Field(default_factory=list)
    evidence_strength: EvidenceStrength
    mo_label: MOLabel
    mo_ids: list[str] = Field(default_factory=list)
    mo_rationale: str = Field(max_length=600)
    test_data_needed: list[TestDataNeed] = Field(min_length=1, max_length=8)
    concerns: list[str] = Field(default_factory=list, max_length=8)


# --------------------------------------------------------------------------
# Pattern card (hand-off to the human reviewer)
# --------------------------------------------------------------------------
class SourceItem(StrictModel):
    source_id: str
    annex: Literal["A", "B", "extra"]
    text: str
    basis: str
    cited_by: list[str]


class SimulatedContribution(StrictModel):
    label: Literal["SIMULATED"] = "SIMULATED"
    actor: ActorId
    round: int
    function: str
    description: str
    benefit_to_self: str
    behaviour_tags: list[str]
    grounding: list[Grounding]
    awareness: Awareness = "not_stated"


class SimulatedFlow(StrictModel):
    label: Literal["SIMULATED"] = "SIMULATED"
    proposed_by: ActorId
    round: int
    from_party: str
    to_party: str
    asset: str
    description: str


class AssumptionItem(StrictModel):
    label: Literal["ASSUMPTION"] = "ASSUMPTION"
    made_by: str
    round: int
    text: str


class ActorRemovalResult(StrictModel):
    removed_actor: ActorId
    remaining_actors: list[ActorId]
    still_feasible: bool
    uncovered_functions: list[str]
    functionally_necessary: bool


class FunctionalDependency(StrictModel):
    """Which roles the simulated mechanism NEEDS. Says nothing about cooperation or intent."""
    participants: list[ActorId]
    required_functions: list[str]
    removal_results: list[ActorRemovalResult]
    necessary_roles: list[ActorId]
    substitutable_roles: list[ActorId]
    single_actor_feasible_by: list[ActorId]
    note: str


class Interaction(StrictModel):
    """One simulated offer between two actors and the reply to it (from routed messages)."""
    from_actor: ActorId
    to_actor: ActorId
    round: int
    offer_intent: Literal["propose", "inform", "counter"]
    offer_text: str
    response: Literal["accepted", "declined", "countered", "no_response"]
    response_text: str


class ActorRole(StrictModel):
    actor: ActorId
    role: Literal["initiator", "acceptor", "proposal_rejected", "declined", "independent", "not_involved"]
    contributed: bool
    excluded: bool


class Cooperation(StrictModel):
    """How the actors interacted in the simulation (who offered, who accepted)."""
    interactions: list[Interaction]
    roles: list[ActorRole]
    cooperating_pairs: list[list[ActorId]]
    summary: Literal["SIMULATED_COOPERATION", "PROPOSAL_REJECTED", "NO_INTERACTION"]
    explanation: str


class IntentAssessment(StrictModel):
    actor: ActorId
    intent: Literal["KNOWING", "POSSIBLY_UNWITTING", "UNKNOWN", "NOT_APPLICABLE"]
    basis: str


class OverallAssessment(StrictModel):
    classification: Literal["COLLUSION", "POTENTIAL_COLLUSION", "ONE_SIDED_WITH_UNWITTING_PARTY",
                            "INDEPENDENT_ACTIONS", "SINGLE_ACTOR", "INSUFFICIENT"]
    core_actors: list[ActorId]
    intent_resolved: bool
    explanation: str


class MOClassification(StrictModel):
    provisional: bool = True  # a simulated pattern's MO label is never final until a human confirms it
    rule_label: MOLabel
    fully_covered_mos: list[str]
    partial_matches: dict[str, float]
    novel_elements: list[str]
    reviewer_label: MOLabel | None
    reviewer_mo_ids: list[str]
    reviewer_rationale: str
    agreement: bool
    tag_annotation_version: str


class EvidenceAssessment(StrictModel):
    rule_strength: EvidenceStrength
    reviewer_strength: EvidenceStrength | None
    final_strength: EvidenceStrength
    basis: list[str]


class CheckResult(StrictModel):
    name: str
    passed: bool
    blocking: bool
    detail: str


class ActorSummary(StrictModel):
    actor: ActorId
    role: str
    functions: list[str]
    contributions: list[str]
    benefits: list[str]
    functionally_necessary: bool | None
    intent: str


class ReviewSection(StrictModel):
    performed_by: Literal["review_agent"] = "review_agent"
    completed: bool
    source_findings: list[SourceFinding]
    assumption_findings: list[AssumptionFinding]
    concerns: list[str]
    deterministic_checks: list[CheckResult]


class PatternCard(StrictModel):
    schema_version: str = SCHEMA_VERSION
    card_id: str
    run_id: str
    scenario_id: str
    title: str
    theme: str
    disclaimer: str
    # A card can never carry an approved status. Approval is a separate,
    # human-only record in the decisions log (see approval.py).
    status: Literal["PENDING_HUMAN_REVIEW", "BLOCKED", "INCOMPLETE"]
    actors: list[ActorSummary]
    flows: list[SimulatedFlow]
    source_material: list[SourceItem]
    simulated_behaviour: list[SimulatedContribution]
    assumptions: list[AssumptionItem]
    functional_dependency: FunctionalDependency
    cooperation: Cooperation
    intent_assessment: list[IntentAssessment]
    overall_assessment: OverallAssessment
    mo_classification: MOClassification
    evidence: EvidenceAssessment
    test_data_needed: list[TestDataNeed]
    review: ReviewSection
    flags: list[str]
    content_hash: str = ""
