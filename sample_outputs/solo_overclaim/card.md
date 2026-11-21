# Provider overclaims delivered hours (simulated)

> **SIMULATED RISK HYPOTHESIS. Produced by scripted/LLM agents role-playing incentives; it is NOT evidence that any person or organisation has behaved this way. Social media excerpts are unverified. Human approval means 'worth testing against data', not a finding of fact.**

- Card: `PC-solo_overclaim`  
- Status: **PENDING_HUMAN_REVIEW**  
- Content hash: `d054b9c37f3633f401b0c57f03a2cdaf326f7914f9dec48e35f6632cee8d6551`

**Theme:** Could a provider claim for more training than it delivered, and does that need anyone else's cooperation?

## Summary

| Item | Result |
|---|---|
| Overall assessment | **SINGLE_ACTOR** (intent unresolved) |
| Functional dependency | necessary roles: provider; substitutable: - |
| Simulated cooperation | NO_INTERACTION |
| Intent | trainee: NOT_APPLICABLE; provider: UNKNOWN; employer: NOT_APPLICABLE |
| Evidence strength | **LOW** |
| MO classification | provisional KNOWN of MO-07 |
| Human-review flags | 3 (see section 13) |

## 1. Actors (SIMULATED)

| Actor | Role | Functionally necessary | Intent |
|---|---|---|---|
| trainee | not_involved | - | NOT_APPLICABLE |
| provider | independent | yes | UNKNOWN |
| employer | not_involved | - | NOT_APPLICABLE |

**provider**. Functions: course_delivery_record, grant_claim_submission
  - Records more training hours than were delivered.
  - Claims funding for the recorded hours.
  - *Benefit:* Full funding for partial delivery; Lower delivery cost per trainee.

## 2. Functional dependency (actor-removal check)

*Shows which roles the simulated mechanism needs. It does not show cooperation or intent.*

| Removed actor | Mechanism still possible? | Uncovered functions | Role necessary |
|---|---|---|---|
| provider | no | course_delivery_record, grant_claim_submission | **yes** |

## 3. Simulated cooperation

**NO_INTERACTION**. No accepted offer between contributing actors. (Simulated interaction, not a real-world fact.)

| From | To | Round | Offer | Response |
|---|---|---|---|---|
| provider | trainee | 1 | Simulated: class time is shortened; the course record is unchanged. | no_response |
| trainee | provider | 1 | Simulated: unaware of what is recorded; no action taken. | no_response |

## 4. Intent assessment

- **trainee: NOT_APPLICABLE**. Did not contribute to the mechanism.
- **provider: UNKNOWN**. The scenario does not establish whether this actor knew the conduct was improper. Taking part or accepting a reward does not by itself show intent.
- **employer: NOT_APPLICABLE**. Did not contribute to the mechanism.

## 5. Overall assessment

**SINGLE_ACTOR** (intent resolved: False). provider can carry out the mechanism alone; other parties are not needed. Treat as single-actor misconduct, not collusion.


## 6. Flows (SIMULATED)

| From | To | Asset | Description |
|---|---|---|---|
| grant_scheme | provider | grant_funds | Funding for hours recorded but not delivered. |

## 7. Source material (verbatim, untrusted)

- **MO-07** (Annex A, Observed overseas; cited by rule:mo_classification): "Overclaimed training: Claims exceed the training or attendance actually delivered"
- **S2** (Annex B, Unverified; cited by provider): "Almost $600 for basic cleaning training? How is that worth it?"

## 8. Assumptions

- [provider, r1] Trainees do not see or sign the hour-level delivery record.

## 9. MO classification

- Rule: **provisional KNOWN**; fully covered: MO-07; partial: -; novel elements: -
- Review Agent: **KNOWN** ['MO-07']: Matches MO-07, claims exceeding training delivered. MO-07 basis is observed overseas, so local applicability is an assumption.
- Agreement: True (tag annotation v2026-11-19.1)

## 10. Evidence strength

- Rule: LOW; reviewer: LOW; **final: LOW**
  - MO-07 basis 'Observed overseas' is a typology-level label; it does not show that this simulated scenario occurred.
  - S2: unverified social media excerpt; at most a weak signal for one element, not proof of the full arrangement.
  - Simulated agent behaviour is a hypothesis and adds no evidential weight.
  - MODERATE or STRONG require verified data and a human reviewer.

## 11. Data needed to test this pattern

- Claimed hours versus scheduled session hours per course run (aggregate): Detect claims above schedule
- Session-level attendance timestamps (pseudonymised_record): Compare actual session length with recorded length

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
| dependency_cooperation_intent_assessed_separately | yes | False | SINGLE_ACTOR: provider can carry out the mechanism alone; other parties are not needed. Treat as single-actor misconduct, not collusion. |

**Review Agent concerns:**
- Single-actor misconduct: route to standard provider audit rather than collusion review.

## 13. Flags for the human reviewer

- intent_unresolved:provider
- mo_label_provisional:KNOWN
- single_actor_feasible:provider
