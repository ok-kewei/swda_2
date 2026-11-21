# Short-term hiring timed to funded courses (simulated)

> **SIMULATED RISK HYPOTHESIS. Produced by scripted/LLM agents role-playing incentives; it is NOT evidence that any person or organisation has behaved this way. Social media excerpts are unverified. Human approval means 'worth testing against data', not a finding of fact.**

- Card: `PC-hire_train_release`  
- Status: **PENDING_HUMAN_REVIEW**  
- Content hash: `4999c221396884f196f868ee5aa98fb201879989fa6ef688656b8910daaa3cab`

**Theme:** How might an employer and a provider align hiring and course cohorts so that grant support, rather than the job, drives the hire?

## Summary

| Item | Result |
|---|---|
| Overall assessment | **POTENTIAL_COLLUSION** (intent unresolved) |
| Functional dependency | necessary roles: employer, provider; substitutable: trainee |
| Simulated cooperation | SIMULATED_COOPERATION |
| Intent | trainee: UNKNOWN; provider: UNKNOWN; employer: UNKNOWN |
| Evidence strength | **LOW** |
| MO classification | provisional KNOWN of MO-06 |
| Human-review flags | 5 (see section 13) |

## 1. Actors (SIMULATED)

| Actor | Role | Functionally necessary | Intent |
|---|---|---|---|
| trainee | acceptor | no | UNKNOWN |
| provider | acceptor | yes | UNKNOWN |
| employer | initiator | yes | UNKNOWN |

**trainee**. Functions: attendance_attestation
  - Attends and confirms attendance in a role expected to end after the course.
  - *Benefit:* Short-term wage and a certificate.

**provider**. Functions: course_delivery_record
  - Runs cohorts timed to the employer's hiring cycle and records delivery.
  - *Benefit:* Reliably filled cohorts.

**employer**. Functions: course_enrolment, employment_record, fee_funding, grant_claim_submission
  - Hires people on short contracts timed to a funded course and releases them after completion.
  - Nominates the new hires for the funded course.
  - Sponsors the course fee, which is largely offset by subsidy.
  - Claims fee subsidy and any wage support for the hires.
  - *Benefit:* Eligibility for course and wage support; Grant-supported headcount at low net cost; Low net training cost; Receives grant funds.

## 2. Functional dependency (actor-removal check)

*Shows which roles the simulated mechanism needs. It does not show cooperation or intent.*

| Removed actor | Mechanism still possible? | Uncovered functions | Role necessary |
|---|---|---|---|
| employer | no | employment_record | **yes** |
| provider | no | course_delivery_record | **yes** |
| trainee | yes | - | no |

## 3. Simulated cooperation

**SIMULATED_COOPERATION**. provider accepted an offer from employer (round 1); trainee accepted an offer from employer (round 1) (Simulated interaction, not a real-world fact.)

| From | To | Round | Offer | Response |
|---|---|---|---|---|
| employer | provider | 1 | Simulated: would you run cohorts timed to our short-term hires so their course falls inside the contract period? | accepted: Simulated: would schedule cohorts around your hiring dates. |
| employer | trainee | 1 | Simulated: role offered for the course period; extension not expected. | accepted: Simulated: would take the short role for the wage and certificate. |

## 4. Intent assessment

- **trainee: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.
- **provider: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.
- **employer: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.

## 5. Overall assessment

**POTENTIAL_COLLUSION** (intent resolved: False). Necessary roles (employer, provider) interacted in the simulation, but intent is unresolved for employer, provider. Needs human review and real data.


## 6. Flows (SIMULATED)

| From | To | Asset | Description |
|---|---|---|---|
| employer | provider | course_fee | Sponsored fee for each hire. |
| grant_scheme | employer | grant_funds | Fee subsidy and wage support claimed for the hires. |
| employer | trainee | employment | Short contract covering the course period. |

## 7. Source material (verbatim, untrusted)

- **MO-06** (Annex A, Observed; cited by rule:mo_classification): "Employment created for grants: People are hired only to attend a course and are let go afterwards"

## 8. Assumptions

- [employer, r1] Wage support is available to the employer while a hire attends training; not stated in sources.
- [provider, r1] The provider knows the hires are temporary; it could equally be unaware.
- [trainee, r1] The trainee may not know the role is temporary.

## 9. MO classification

- Rule: **provisional KNOWN**; fully covered: MO-06; partial: -; novel elements: -
- Review Agent: **KNOWN** ['MO-06']: Matches MO-06: people hired only to attend a course and let go afterwards. No Annex B excerpt relates to this pattern.
- Agreement: True (tag annotation v2026-11-19.1)

## 10. Evidence strength

- Rule: LOW; reviewer: LOW; **final: LOW**
  - MO-06 basis 'Observed' is a typology-level label; it does not show that this simulated scenario occurred.
  - Simulated agent behaviour is a hypothesis and adds no evidential weight.
  - MODERATE or STRONG require verified data and a human reviewer.

## 11. Data needed to test this pattern

- Employment start and end dates relative to course dates (pseudonymised_record): Detect contracts that start and end with a funded course
- Employer retention rate after course completion (aggregate): Compare against sector baseline
- Share of an employer's training claims from staff with tenure under three months (aggregate): Spot hiring driven by grants

## 12. Review checks

| Check | Passed | Blocking | Detail |
|---|---|---|---|
| grounding_ids_exist_and_usable | yes | True | all grounding IDs resolve to usable sources |
| grounding_within_actor_visibility | yes | True | each actor cited only sources it could see |
| no_quarantined_text_in_card | yes | True | none |
| output_safety_rescan | yes | True | no unsafe or fact-asserting content |
| review_checked_all_cited_sources | yes | False | all cited excerpts reviewed |
| mo_label_agreement | yes | False | rule and reviewer agree |
| evidence_not_overstated | yes | False | reviewer grading within rule ceiling |
| dependency_cooperation_intent_assessed_separately | yes | False | POTENTIAL_COLLUSION: Necessary roles (employer, provider) interacted in the simulation, but intent is unresolved for employer, provider. Needs human review and real data. |

**Review Agent concerns:**
- Provider is functionally essential but may be unwitting; avoid treating it as a co-conspirator without data.

## 13. Flags for the human reviewer

- intent_unresolved:employer
- intent_unresolved:provider
- intent_unresolved:trainee
- mo_label_provisional:KNOWN
- substitutable_actor:trainee
