# Recruiter-led bundled enrolment with cash reward (simulated)

> **SIMULATED RISK HYPOTHESIS. Produced by scripted/LLM agents role-playing incentives; it is NOT evidence that any person or organisation has behaved this way. Social media excerpts are unverified. Human approval means 'worth testing against data', not a finding of fact.**

- Card: `PC-bundled_enrolment_cash_reward`  
- Status: **PENDING_HUMAN_REVIEW**  
- Content hash: `193426681aa350625c58e7e75bb5bc860ae7699fffb642a37c3eef99ab65a0f5`

**Theme:** How might recruiter outreach, course bundling and cash rewards combine around the use of individual training credits?

## Summary

| Item | Result |
|---|---|
| Overall assessment | **POTENTIAL_COLLUSION** (intent unresolved) |
| Functional dependency | necessary roles: provider, trainee; substitutable: - |
| Simulated cooperation | SIMULATED_COOPERATION |
| Intent | trainee: UNKNOWN; provider: UNKNOWN; employer: NOT_APPLICABLE |
| Evidence strength | **LOW** |
| MO classification | provisional VARIATION of MO-04 |
| Human-review flags | 4 (see section 13) |

## 1. Actors (SIMULATED)

| Actor | Role | Functionally necessary | Intent |
|---|---|---|---|
| trainee | acceptor | yes | UNKNOWN |
| provider | initiator | yes | UNKNOWN |
| employer | declined | - | NOT_APPLICABLE |

**trainee**. Functions: attendance_attestation, course_enrolment, fee_funding
  - Applies own training credits to the bundled diploma.
  - Enrols without a clear view of what the course covers.
  - Confirms attendance while attending little of the course.
  - *Benefit:* Keeps the reward and the certificate; Low effort; reward without real study; Receives the cash reward.

**provider**. Functions: assessment_result, grant_claim_submission, incentive_payment, recruitment_outreach
  - Uses recruiters to approach people with unused credits and promote a short course that is only sold inside a longer diploma.
  - Offers the enrolee a cash reward after credits are applied.
  - Passes enrolees regardless of participation so the course stays fundable.
  - Claims funding for the full diploma.
  - *Benefit:* Completion and pass rates stay high; Higher conversion of approached people into enrolments; More funded enrolments at the higher diploma fee; Receives grant funds for the whole bundle.

## 2. Functional dependency (actor-removal check)

*Shows which roles the simulated mechanism needs. It does not show cooperation or intent.*

| Removed actor | Mechanism still possible? | Uncovered functions | Role necessary |
|---|---|---|---|
| provider | no | assessment_result, grant_claim_submission, incentive_payment, recruitment_outreach | **yes** |
| trainee | no | attendance_attestation, fee_funding | **yes** |

## 3. Simulated cooperation

**SIMULATED_COOPERATION**. trainee accepted an offer from provider (round 1) (Simulated interaction, not a real-world fact.)

| From | To | Round | Offer | Response |
|---|---|---|---|---|
| provider | trainee | 1 | Simulated offer: enrol in a bundled diploma using your credits; a cash reward follows once credits are applied, and attendance is presented as flexible. | accepted: Simulated: would accept, since the credits would otherwise go unused and the reward is attractive. |
| provider | employer | 1 | Simulated: would any of your staff join the bundled diploma on the same terms? | declined: Simulated: declines; no staff need this course and sponsorship would be traceable to the business. |

## 4. Intent assessment

- **trainee: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.
- **provider: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.
- **employer: NOT_APPLICABLE**. Did not contribute to the mechanism.

## 5. Overall assessment

**POTENTIAL_COLLUSION** (intent resolved: False). Necessary roles (provider, trainee) interacted in the simulation, but intent is unresolved for provider, trainee. Needs human review and real data.


## 6. Flows (SIMULATED)

| From | To | Asset | Description |
|---|---|---|---|
| provider | trainee | cash | Cash reward to the enrolee after credits are applied. |
| grant_scheme | provider | grant_funds | Funding claimed for the full diploma. |
| trainee | provider | training_credits | Credits applied to the bundled diploma fee. |

## 7. Source material (verbatim, untrusted)

- **MO-04** (Annex A, Observed; cited by rule:mo_classification): "Cash for enrolment: Agents or recruiters offer cash for using credits and suggest attendance is optional"
- **S1** (Annex B, Unverified; cited by provider): "I signed up for a short course, then found out it's only available as part of a longer diploma. Feels misleading."
- **S3** (Annex B, Unverified; cited by trainee): "A marketing agent kept pushing my elderly mum to use her credits and mentioned a cash reward. Not sure what the course even was."
- **S4** (Annex B, Unverified; cited by provider): "Nobody in my class ever fails. Feels like providers just pass everyone to keep the funding."

## 8. Assumptions

- [provider, r1] Recruiters are paid per enrolment; this is not stated in any source.
- [trainee, r1] The trainee knowingly accepts low attendance; some targets may instead be unwitting, as S3 hints.

## 9. MO classification

- Rule: **provisional VARIATION**; fully covered: MO-04; partial: -; novel elements: assured_pass, course_bundling
- Review Agent: **VARIATION** ['MO-04']: Covers all MO-04 features (recruiter outreach, cash for credit use, optional attendance) and adds course bundling and assured passing.
- Agreement: True (tag annotation v2026-11-19.1)

## 10. Evidence strength

- Rule: LOW; reviewer: LOW; **final: LOW**
  - MO-04 basis 'Observed' is a typology-level label; it does not show that this simulated scenario occurred.
  - S1: unverified social media excerpt; at most a weak signal for one element, not proof of the full arrangement.
  - S3: unverified social media excerpt; at most a weak signal for one element, not proof of the full arrangement.
  - S4: unverified social media excerpt; at most a weak signal for one element, not proof of the full arrangement.
  - Simulated agent behaviour is a hypothesis and adds no evidential weight.
  - MODERATE or STRONG require verified data and a human reviewer.

## 11. Data needed to test this pattern

- Enrolment counts by recruiter or referral channel (aggregate): Check whether bundled-diploma enrolments cluster by channel
- Attendance versus assessment outcome per enrolment (pseudonymised_record): Test whether passes occur with low attendance
- Share of short-course enquiries converted to diploma enrolments (aggregate): Measure bundling effect
- Age band of credit users by provider (aggregate): Check for concentration among older credit holders

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
| dependency_cooperation_intent_assessed_separately | yes | False | POTENTIAL_COLLUSION: Necessary roles (provider, trainee) interacted in the simulation, but intent is unresolved for provider, trainee. Needs human review and real data. |

**Review Agent concerns:**
- S3 involves an elderly relative; if the pattern is real, vulnerable credit holders may be targeted and could be unwitting.

## 13. Flags for the human reviewer

- excluded_declined:employer
- intent_unresolved:provider
- intent_unresolved:trainee
- mo_label_provisional:VARIATION
