# Assured passes in exchange for routed training volume (simulated)

> **SIMULATED RISK HYPOTHESIS. Produced by scripted/LLM agents role-playing incentives; it is NOT evidence that any person or organisation has behaved this way. Social media excerpts are unverified. Human approval means 'worth testing against data', not a finding of fact.**

- Card: `PC-assured_pass_volume_deal`  
- Status: **PENDING_HUMAN_REVIEW**  
- Content hash: `17b56154a63a7617c4c398acbf4042db91769a889970e4039c3638023161aeed`

**Theme:** How might a provider and an employer trade assessment outcomes for guaranteed enrolment volume?

## Summary

| Item | Result |
|---|---|
| Overall assessment | **POTENTIAL_COLLUSION** (intent unresolved) |
| Functional dependency | necessary roles: employer, provider; substitutable: - |
| Simulated cooperation | SIMULATED_COOPERATION |
| Intent | trainee: NOT_APPLICABLE; provider: UNKNOWN; employer: UNKNOWN |
| Evidence strength | **LOW** |
| MO classification | provisional NEW |
| Human-review flags | 3 (see section 13) |

## 1. Actors (SIMULATED)

| Actor | Role | Functionally necessary | Intent |
|---|---|---|---|
| trainee | not_involved | - | NOT_APPLICABLE |
| provider | initiator | yes | UNKNOWN |
| employer | acceptor | yes | UNKNOWN |

**provider**. Functions: assessment_result, grant_claim_submission
  - Assures pass outcomes for staff the employer nominates.
  - Claims funding for each nominated trainee.
  - *Benefit:* A steady block of funded enrolments; Predictable grant revenue.

**employer**. Functions: course_enrolment, fee_funding
  - Nominates all staff needing mandatory certification to this one provider.
  - Sponsors fees for the nominated staff, largely offset by subsidy.
  - *Benefit:* Certified staff with minimal lost work time; Low net cost of compliance training.

## 2. Functional dependency (actor-removal check)

*Shows which roles the simulated mechanism needs. It does not show cooperation or intent.*

| Removed actor | Mechanism still possible? | Uncovered functions | Role necessary |
|---|---|---|---|
| employer | no | fee_funding | **yes** |
| provider | no | assessment_result | **yes** |

## 3. Simulated cooperation

**SIMULATED_COOPERATION**. employer accepted an offer from provider (round 1) (Simulated interaction, not a real-world fact.)

| From | To | Round | Offer | Response |
|---|---|---|---|---|
| provider | employer | 1 | Simulated: assured pass outcomes for staff you nominate, if all your mandatory training is routed to us. | accepted: Simulated: would route all staff certifications to you on that basis. |

## 4. Intent assessment

- **trainee: NOT_APPLICABLE**. Did not contribute to the mechanism.
- **provider: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.
- **employer: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.

## 5. Overall assessment

**POTENTIAL_COLLUSION** (intent resolved: False). Necessary roles (employer, provider) interacted in the simulation, but intent is unresolved for employer, provider. Needs human review and real data.


## 6. Flows (SIMULATED)

| From | To | Asset | Description |
|---|---|---|---|
| provider | employer | certification | Certificates for nominated staff regardless of competence. |
| grant_scheme | provider | grant_funds | Funding per nominated trainee. |
| employer | provider | enrolments | All mandatory training volume routed to one provider. |
| employer | provider | course_fee | Sponsored fees. |

## 7. Source material (verbatim, untrusted)

- **S2** (Annex B, Unverified; cited by employer): "Almost $600 for basic cleaning training? How is that worth it?"
- **S4** (Annex B, Unverified; cited by provider): "Nobody in my class ever fails. Feels like providers just pass everyone to keep the funding."

## 8. Assumptions

- [provider, r1] The employer can route all mandatory training to one provider without challenge.
- [employer, r1] Staff competence is not checked independently after certification.

## 9. MO classification

- Rule: **provisional NEW**; fully covered: -; partial: -; novel elements: assured_pass, employer_nomination, volume_steering
- Review Agent: **NEW** []: No MO in the library covers assessment integrity traded for enrolment volume. MO-08 involves a sponsor but concerns value flowing back, which is absent here.
- Agreement: True (tag annotation v2026-11-19.1)

## 10. Evidence strength

- Rule: LOW; reviewer: LOW; **final: LOW**
  - S4: unverified social media excerpt; at most a weak signal for one element, not proof of the full arrangement.
  - Simulated agent behaviour is a hypothesis and adds no evidential weight.
  - MODERATE or STRONG require verified data and a human reviewer.

## 11. Data needed to test this pattern

- Pass rate by provider and by sponsoring employer (aggregate): Find provider-employer pairs with unusually high pass rates
- Concentration of an employer's sponsored enrolments across providers (aggregate): Detect exclusive routing
- Assessment re-sit and fail counts per cohort (aggregate): Check whether failure is ever recorded

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
- Exclusive provider relationships are often legitimate; the signal is pass-rate anomaly combined with exclusivity.

## 13. Flags for the human reviewer

- intent_unresolved:employer
- intent_unresolved:provider
- mo_label_provisional:NEW
