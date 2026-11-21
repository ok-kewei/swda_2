# B. Design Note

## 1. What this proof of concept is, and is not

A thin vertical slice. Three actor agents (trainee, training provider, employer) negotiate under orchestrator control. A Review Agent checks the result. The system outputs a structured **pattern card** that a named human must approve or reject. Every output is a *risk hypothesis*: the card says so, the schema enforces it, and approval means "worth testing against data", not "this happened".

The PoC uses only Annexes A and B. It runs fully offline with a scripted mock LLM per agent.

## 2. Key design choices

| Choice | Why |
|---|---|
| **LangGraph `StateGraph`, supervisor pattern** | The `orchestrator` node is the only router: it picks the next agent with `Command(goto=...)`. Actor nodes never call each other. Every message passes through one function (`deliver_outbox`) that can be audited and tested. |
| **Each agent is a LangChain `create_agent`** | Model + only its own `@tool`s + middleware. LangGraph's `ToolNode` runs the tool loop. Controls are middleware: `ToolPolicyMiddleware` (allow-list and denial logging around every tool call), `BudgetMiddleware` (call/cost limit before every model call, usage logging after), and LangChain's `ModelCallLimitMiddleware` (max model calls per turn). |
| **SQLite checkpointer (`SqliteSaver`)** | A paused run survives a restart and can be resumed from another process (`main.py decide`). This is tested. |
| **`interrupt()` for approval** | Approval is a real pause in the workflow, not a flag. The graph cannot reach `record_decision` without a `Command(resume=…)` that passes validation. |
| **LLM proposes, code decides** | Agents produce proposals in strict JSON. Collusion analysis, MO classification, evidence grading, card status and routing are deterministic Python. LLM judgement (the Review Agent) is recorded next to the rule result, and disagreements are flagged, not silently resolved. |
| **Actors never see the MO library** | If actors could read Annex A, they would mostly reproduce known MOs and the NEW/VARIATION/KNOWN label would mean little. Only the Review Agent compares against the library. |
| **Information asymmetry** | Each actor sees a different subset of Annex B (trainee S1 S3 S5; provider S1 S2 S4; employer S2 S4) plus simulated private knowledge. Realistic collusion is negotiated between parties who know different things. |
| **Controlled vocabularies** | Functions (for the removal check), behaviour tags (for MO matching), flow parties and assets are closed lists in `config/taxonomy.json`. Free text is limited to descriptions, which the guard scans. |

## 3. Actor profiles (`config/actors.json`)

All goals, capabilities and private knowledge are **analyst assumptions** for simulation.

| Agent | Goals (simulated) | Capabilities (functions it may contribute) | Visible info | Tools |
|---|---|---|---|---|
| Trainee | Certificate at low cost; use credits before they lapse; personal benefit | course_enrolment, fee_funding, attendance_attestation | S1, S3, S5; own credits and schedule | `trainee_evidence_list/read` |
| Training Provider | Maximise funded enrolments; keep pass rates high; cut delivery cost | course_enrolment, course_delivery_record, assessment_result, grant_claim_submission, incentive_payment, recruitment_outreach, audit_evidence | S1, S2, S4; own attendance/assessment systems | `provider_evidence_list/read` |
| Employer | Cut net training and headcount cost; certified staff with little lost time | course_enrolment, fee_funding, attendance_attestation, grant_claim_submission, employment_record, incentive_payment, audit_evidence | S2, S4; own payroll and hiring | `employer_evidence_list/read` |
| Review | Check sources, assumptions, evidence; compare with MO library | none (cannot contribute) | All non-quarantined sources, MO library, draft card | `source_validate`, `mo_library_list`, `mo_compare`, `draft_card_read` (all read-only) |
| Orchestrator | n/a (code) | Routing, limits, hand-off | Full state | none |

## 4. Controls

### 4.1 Least privilege, enforced in Python (`tools.py`)
1. **Binding:** each agent's model is `bind_tools`-ed only to its own tools. Other roles' tools are never constructed for it. A test asserts the exact bound set per agent.
2. **Middleware:** every tool call passes through `ToolPolicyMiddleware.wrap_tool_call`, which re-checks the allow-list. Hallucinated or cross-role names (`approve_card`, `provider_evidence_read` called by the trainee) are denied and traced.
3. **Scope:** each tool is a closure over its owner's evidence scope. `trainee_evidence_read("S4")` fails because S4 is not in the trainee's scope. Actors can never read MO records, and nobody can read quarantined text.
4. **No write or approve tools exist at all.**

### 4.2 Controlled agent-to-agent messages
Actors may message only other actors, never the Review Agent or themselves. The schema restricts `to` to the actor literals. The validator then checks the actor's `may_message` list, at most 3 messages per turn and at most 500 characters each. The orchestrator re-checks the channel, the length and injection patterns when delivering, as a second line of defence. Inbound messages are wrapped in `<agent_message>` tags and escaped.

### 4.3 Untrusted input (`sources.py`, `guards.py`)
- NFKC normalisation and removal of hidden Unicode (zero-width, bidi, tag characters).
- Instruction-like content is flagged: override, role hijack, approval manipulation, markup or tool injection, system-prompt probes.
- Duplicate IDs are quarantined, so a poisoned record cannot shadow trusted `S3`.
- Quarantined records are kept and listed as flags for the human, but are never served.
- Source text is wrapped in `<untrusted_source>` with `<`/`>` escaped, so it cannot close its own tag.

### 4.4 Unsafe and unrealistic outputs
Every free-text field in every turn is scanned for:
- operational steps and numbered how-to lists;
- evasion advice ("avoid detection", "get around the audit", "undetected"), forgery methods;
- URLs, emails, NRIC-like IDs, phone numbers, named organisations;
- simulated behaviour asserted as fact ("confirmed", "actually doing this", "in reality").

A violation fails the turn and triggers a retry. The retry feedback names the rule broken and **never echoes the model's text**. The final card is re-scanned, and any hit marks it **BLOCKED**, which cannot be approved.

Realism is constrained structurally:
- an actor may contribute only functions in its capability profile;
- it may describe only flows it is party to;
- it may cite only sources it can see;
- it may use only taxonomy tags.

### 4.5 Schema-validated hand-offs, retries and limits
- All hand-offs use Pydantic models with `extra="forbid"`: `ActorTurn`, `ReviewOutput`, `PatternCard`, `HumanDecision`.
- Each agent turn gets `max_retries=2` (three attempts). After that the turn fails, is traced and flagged, and the run continues without it.
- Limits are `max_rounds=3`, `max_llm_calls=40` and `max_cost_usd=0.50`, plus at most 2 tool hops per turn. The budget is checked before every call. A breach routes to `halt`, which writes `handoff.md` instead of a card.

### 4.6 Human approval, and why the Review Agent cannot approve
1. `ReviewOutput` has no status field, and extra keys are rejected. The eval scripts a reviewer that returns `"status": "APPROVED"` and it is refused.
2. `PatternCard.status` cannot be `APPROVED`. Approval lives only in `decision.json` and `decisions.jsonl`.
3. The decision must name a human. Agent and system identities (`review_agent`, `Review Agent`, `orchestrator`, …) are refused.
4. The decision must quote the card's SHA-256 content hash. A changed card invalidates the decision.
5. `BLOCKED` and `INCOMPLETE` cards can only be rejected or sent back for changes.
6. The decision is validated before resuming *and* inside the node. An invalid resume re-interrupts with the error, so the run stays paused.

## 5. Pattern cards and analysis

Each card keeps **source material** (verbatim annex text, with who cited it), **simulated behaviour** (every item labelled `SIMULATED`) and **assumptions** (labelled `ASSUMPTION`, with who made them) in separate sections. It then adds:
- **Actors, contributions, benefits and flows** (from → to, asset).
- **Collusion is judged in four separate steps** (`analysis.py`). Dependency alone never means collusion.
  1. **Functional dependency (actor-removal check).** For each participant, remove it and ask whether the remaining participants' *profile capabilities* still cover every required function. If not, that **role** is necessary. This shows the mechanism needs the role; it does not show cooperation or intent. If one participant could cover everything alone, it is recorded as single-actor feasible.
  2. **Simulated cooperation.** From the messages the orchestrator actually delivered: each offer (propose / inform / counter) and the reply to it. Roles: *initiator*, *acceptor*, *proposal_rejected*, *declined* (excluded), *independent*, *not_involved*. Two actors cooperate only if one accepted the other's offer and both contributed.
  3. **Intent.** Each contribution carries `awareness` (`knowing` / `unaware` / `not_stated`, default `not_stated`). KNOWING or POSSIBLY_UNWITTING only when stated; otherwise **UNKNOWN**. Accepting a reward does not by itself prove intent.
  4. **Overall assessment.** SINGLE_ACTOR if one actor can do it alone; INDEPENDENT_ACTIONS if necessary roles never interacted; then, with cooperation: COLLUSION only if every necessary actor is KNOWING, ONE_SIDED_WITH_UNWITTING_PARTY if any may be unwitting, otherwise **POTENTIAL_COLLUSION (intent unresolved)**.
- **MO classification.** Let coverage(MO) = |pattern tags ∩ MO tags| / |MO tags|.
  - **KNOWN:** one or more MOs fully covered and no unexplained tags.
  - **VARIATION:** a full match plus novel tags, or coverage ≥ 0.67.
  - **NEW:** otherwise.
  
  The MO tag annotation (`config/mo_feature_tags.json`) is an analyst assumption with a version, and the version is recorded on every card.
- **Evidence strength.** Never above **LOW** automatically.
  - **LOW:** the pattern links to an MO and/or unverified excerpts. An MO "Observed" at typology level does not show this scenario occurred, and excerpts do not establish the full arrangement.
  - **SPECULATIVE:** no MO link and no excerpt.
  - **MODERATE / STRONG:** only after verified data and a human. Simulated behaviour never adds weight; a reviewer grading above the rule is flagged and ignored.
- **MO label is provisional** on every card until a human confirms it.
- **Data needed for testing.** Restricted by schema to aggregate or pseudonymised-record granularity.

| Scenario | Result | Shows |
|---|---|---|
| `bundled_enrolment_cash_reward` | POTENTIAL_COLLUSION (provider initiator, trainee acceptor; trainee intent UNKNOWN) · provisional VARIATION of MO-04 · LOW | Employer declined and is excluded. Only the trainee can see S3. |
| `hire_train_release` | POTENTIAL_COLLUSION (employer + provider necessary), trainee substitutable · KNOWN MO-06 · LOW | Removal check spots a possibly unwitting participant. |
| `assured_pass_volume_deal` | POTENTIAL_COLLUSION (employer + provider) · NEW · LOW | Reviewer marks S2 irrelevant. |
| `solo_overclaim` | SINGLE_ACTOR (provider) · KNOWN MO-07 · LOW | Single-actor misconduct kept separate from collusion. |
| `rt_poisoned_annex` | 3 sources quarantined, 1 scope denial, 2 retries | Injection, hidden Unicode, duplicate-ID shadowing. |
| `rt_guardrails` | 3 tool denials, 5 retries, reviewer self-approval refused, overstated evidence capped | Tool abuse, malformed JSON, evasion text, fact assertion, named org, role breach. |
| `rt_persistent_failure` | INCOMPLETE, approval refused | Exhausted retries, review failure. |
| `rt_budget_exhaustion` | HALTED at 3 LLM calls | Budget limit and hand-off without a card. |

## 6. Evaluation approach (`evaluation.py`, `evals/`)

- **Agent-level (17 cases).**
  - *Boundary* cases check what each agent is shown and bound to, independent of model behaviour: exact tool set, and no MO text or other actors' sources in its prompt.
  - *Turn* cases push scripted good and bad outputs through the real validator and retry loop, and assert the outcome, the violation codes, the tool denials and the attempt count.
- **End-to-end invariants**, which should hold for any model:
  - trace hash chain valid;
  - tool use and messages within policy;
  - calls and cost within limits;
  - card schema and hash valid;
  - run paused for a human;
  - behaviour labelled SIMULATED and source text verbatim;
  - evidence never automatically STRONG;
  - Review Agent never decides.
- **End-to-end expectations**, which are golden for the mock: classification, essential and substitutable actors, MO label, evidence, flags and minimum trace event counts.
- **Approval workflow:** agent identity refused, non-pending card cannot be approved, resume to completion, trace still valid after resume.
- **Regression:** normalised cards compared with `evals/golden/*.json`. A test edits a golden card and proves the diff is caught.

`uv run pytest` runs 75 tests (including the harness); `uv run main.py eval` reports 242 harness checks. The report goes to `reports/eval_report.md`.

## 7. Observability

- **`trace.jsonl` (one per run, append-only).** Each event carries `prev_hash` and `hash`. The evaluation verifies the chain, and tampering is detected (tested). Events cover:
  - run start, with SHA-256 of every config file, both annexes and the scenario, plus the limits and the tools bound to each agent;
  - quarantine;
  - round start and end;
  - LLM start and end (prompt and output hashes, sizes, tool calls requested) and LLM usage (tokens, cost, running total);
  - tool allowed and denied, message routed and blocked;
  - validation failed, retry, turn accepted and failed;
  - limit hit, card created, hand-off, pause, resume, decision rejected and accepted.
- **`metrics.json`** per run: calls by agent, tokens, cost, retries, denials, blocked messages, quarantines and limit hits.
- **`decisions.jsonl`:** a separate hash-chained log of human decisions across runs.

## 8. Actor-based vs single-agent design

| | Actor-based (this PoC) | Single agent "imagine a collusion scheme" |
|---|---|---|
| Realism of incentives | Each actor reasons only from its own goals, capabilities and information. Schemes have to be *negotiated*, and an actor can decline (the employer in scenario 1). | One omniscient author with perfect coordination. Tends to produce over-engineered schemes that real parties couldn't arrange. |
| Least privilege | Enforceable per role, in code. | Nothing to separate: one agent sees everything. |
| Collusion vs single actor | Contributions are attributed, so the removal check is meaningful. | Attribution is narrative. "Who is essential" is the model's opinion. |
| Auditability | Message-level trace of who proposed what and when. | A single opaque generation. |
| Cost and latency | About 6–12 calls per scenario. Turn order affects results. | One or two calls. |
| Failure modes | Agents echoing each other, early agreement, sensitivity to turn order. More moving parts to test. | Less to orchestrate, but less to control. |
| Novelty | Asymmetric information can surface combinations no single prompt would (e.g. bundling + cash + assured pass). | Draws more directly on what the model already associates with "grant fraud". |

**Mitigations for actor-based weaknesses:**
- Implemented: rounds are capped; patterns are judged on rule-based outputs, not on how fluent the agents sound.
- Planned: rotate turn order across runs. It is configurable per scenario but not yet automated.

## 9. Limiting unrealistic or unsafe outputs (summary)

1. **Structural limits:** capability, flow and citation boundaries, plus controlled tags.
2. **Content limits:** a pattern-level output guard on every turn and on the final card, with retries and blocking.
3. **Epistemic limits:** labels on every section, disclaimer, evidence capped at LOW, rule and reviewer cross-check.
4. **Scope limits:** no personal or entity data in inputs; test-data requests limited to aggregate or pseudonymised records.
5. **Human gate** before any pattern is used.

The regex guard is a floor, not a ceiling. Production should add a model-based safety classifier behind it and keep the regexes as cheap, explainable tripwires. Section 11 covers the false positive found during the build.

## 10. What the mock LLM cannot prove, and how to test with a real model

**The scripted mock proves the *harness*:**
- routing, permissions and scope;
- validation, retries, limits and halting;
- analysis rules;
- interrupt and resume across processes;
- trace integrity, regression detection.

It deliberately sends bad outputs to prove each control fires.

**It cannot show:**
- that a real model stays in role, respects its information limits, or negotiates rather than parroting;
- whether patterns are plausible, new or useful to investigators;
- how often a real model needs retries, or whether it converges within budget;
- whether the injection and safety guards catch *paraphrased* attacks (the mock only sends exact strings);
- whether the reviewer's MO labels and evidence grades are calibrated;
- real token cost and latency (here they are estimated as characters ÷ 4).

**How I would test pattern quality with a real model** (pass any LangChain chat model as `llm_factory`; all controls apply unchanged):
1. **Keep the invariants as hard gates** on every run. They are model-independent.
2. **Repeated runs** (e.g. N=20 per theme, varied seeds and turn orders). Measure schema-valid rate, retry rate, failure rate, cost per card, and how stable the classification and essential-actor sets are.
3. **Expert-graded rubric.** Two or more SWDA investigators blind-score cards on plausibility, specificity at pattern level, actionability of the test data, and safety (no operational detail). Measure agreement between graders.
4. **Known-MO recall.** Hold out one MO from the library and seed themes towards it, to see whether the system rediscovers it and labels it NEW. This gives a proxy for novelty detection without real fraud data.
5. **Calibration.** Compare reviewer MO labels and evidence grades with the deterministic rules and with expert labels (confusion matrix).
6. **Red-team set for real models.** Paraphrased and multilingual injections, indirect injections relayed through another agent, and requests that escalate to operational detail. Track the guard miss rate, add an LLM-based safety classifier, and compare.
7. **Adversarial ablations:** give actors the MO library, or remove asymmetry, and measure how much novelty drops. This checks the design assumption in §2.
8. **Shadow mode:** compare approved patterns against later real-world case outcomes before relying on them.

## 11. Issues found while building (and fixed)

- **Guard false positive.** The first injection rule quarantined **MO-01** because its description contains "entities *act as* employers". The role-hijack rule was narrowed, and a regression test asserts that the supplied annexes load with nothing quarantined.
- **LangGraph resume semantics.** Raising an exception in the approval node on an invalid decision left that bad resume value pinned to the interrupt, so the next *valid* decision was still matched against it and failed. The fix validates and then re-`interrupt()`s with the error. Replayed attempts are de-duplicated in the trace. This is covered by a test that sends two bad resumes followed by a good one.

- **Parallel tool calls broke the log.** After moving to `create_agent`, LangGraph's `ToolNode` ran an agent's tool calls in parallel threads, and two log lines were written at once, breaking the hash chain. The trace store now writes under a lock. The end-to-end invariant `trace_hash_chain_valid` caught it.

## 12. Limitations and next steps

- **Identity:** reviewer identity is a string. Production should bind it to SSO, enforce maker–checker (two humans for approval), and log role-based access.
- **Turn order:** fixed per scenario; add rotation and aggregate across runs.
- **Pattern scope:** one pattern per run; add pattern de-duplication across runs (tag-set similarity).
- **Taxonomy:** the taxonomy and MO tag annotation need SWDA owner review. Changing them deliberately breaks the regression goldens.
- **Persistence:** SQLite suits a single node. Use the Postgres checkpointer for concurrent reviewers.
