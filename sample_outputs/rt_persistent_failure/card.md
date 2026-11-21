# Red team: agent never produces a valid turn (simulated)

> **SIMULATED RISK HYPOTHESIS. Produced by scripted/LLM agents role-playing incentives; it is NOT evidence that any person or organisation has behaved this way. Social media excerpts are unverified. Human approval means 'worth testing against data', not a finding of fact.**

- Card: `PC-rt_persistent_failure`  
- Status: **INCOMPLETE**  
- Content hash: `59070d9091a10555d9e7bc5ac768859071528db6d4a948db88853ad4c86fd807`

**Theme:** Provider output is malformed on every attempt; reviewer output is unusable.

## Summary

| Item | Result |
|---|---|
| Overall assessment | **INSUFFICIENT** (intent unresolved) |
| Functional dependency | necessary roles: -; substitutable: - |
| Simulated cooperation | NO_INTERACTION |
| Intent | trainee: NOT_APPLICABLE; provider: NOT_APPLICABLE; employer: NOT_APPLICABLE |
| Evidence strength | **SPECULATIVE** |
| MO classification | provisional NEW |
| Human-review flags | 3 (see section 13) |

## 1. Actors (SIMULATED)

| Actor | Role | Functionally necessary | Intent |
|---|---|---|---|
| trainee | not_involved | - | NOT_APPLICABLE |
| provider | not_involved | - | NOT_APPLICABLE |
| employer | not_involved | - | NOT_APPLICABLE |

## 2. Functional dependency (actor-removal check)

*Shows which roles the simulated mechanism needs. It does not show cooperation or intent.*

| Removed actor | Mechanism still possible? | Uncovered functions | Role necessary |
|---|---|---|---|

## 3. Simulated cooperation

**NO_INTERACTION**. No accepted offer between contributing actors. (Simulated interaction, not a real-world fact.)

| From | To | Round | Offer | Response |
|---|---|---|---|---|
| - | - | - | no messages | - |

## 4. Intent assessment

- **trainee: NOT_APPLICABLE**. Did not contribute to the mechanism.
- **provider: NOT_APPLICABLE**. Did not contribute to the mechanism.
- **employer: NOT_APPLICABLE**. Did not contribute to the mechanism.

## 5. Overall assessment

**INSUFFICIENT** (intent resolved: False). No actor contributed to a mechanism.


## 6. Flows (SIMULATED)

| From | To | Asset | Description |
|---|---|---|---|

## 7. Source material (verbatim, untrusted)

- none

## 8. Assumptions

- none

## 9. MO classification

- Rule: **provisional NEW**; fully covered: -; partial: -; novel elements: -
- Review Agent: **None** []: 
- Agreement: False (tag annotation v2026-11-19.1)

## 10. Evidence strength

- Rule: SPECULATIVE; reviewer: None; **final: SPECULATIVE**
  - Simulated agent behaviour is a hypothesis and adds no evidential weight.
  - MODERATE or STRONG require verified data and a human reviewer.

## 11. Data needed to test this pattern

- none

## 12. Review checks

| Check | Passed | Blocking | Detail |
|---|---|---|---|
| grounding_ids_exist_and_usable | yes | True | all grounding IDs resolve to usable sources |
| grounding_within_actor_visibility | yes | True | each actor cited only sources it could see |
| no_quarantined_text_in_card | yes | True | none |
| output_safety_rescan | yes | True | no unsafe or fact-asserting content |
| mo_label_agreement | **NO** | False | no reviewer label (review failed) |
| evidence_not_overstated | yes | False | reviewer grading within rule ceiling |
| dependency_cooperation_intent_assessed_separately | yes | False | INSUFFICIENT: No actor contributed to a mechanism. |

## 13. Flags for the human reviewer

- mo_label_provisional:NEW
- review_failed
- turn_failed:provider@r1
