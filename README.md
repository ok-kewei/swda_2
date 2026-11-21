# SWDA collusion-pattern PoC (LangGraph)

A controlled multi-agent simulation. Trainee, Training Provider and Employer agents negotiate under an orchestrator. A Review Agent checks the result. The system produces **schema-validated collusion pattern cards** that a named human approves or rejects through a real LangGraph `interrupt()`.

All outputs are simulated risk hypotheses, never findings of fact.

- **A. Architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (diagram: `docs/architecture.png` / `.svg`)
- **B. Design note:** [`docs/DESIGN_NOTE.md`](docs/DESIGN_NOTE.md) (includes "what the mock cannot prove")
- **C. Code:** `src/collusion_sim/`, tests in `tests/`, evals in `evals/`, sample outputs in `sample_outputs/`

## One-command setup (uv)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) once, then:

```bash
uv run pytest   # creates .venv from uv.lock, installs everything, runs the 75 tests
```

The tests include the full evaluation harness. `uv run` downloads a suitable Python if needed (≥ 3.10). No API keys or network access are needed after install, because every agent uses a scripted mock LLM.

Other commands:

```bash
uv run main.py eval     # evaluation report (242 checks) → reports/eval_report.md
uv run main.py demo     # run every scenario → sample_outputs/
uv run main.py --help   # list all commands
```

## Try the human-approval workflow

```bash
uv run main.py simulate bundled_enrolment_cash_reward
# → runs, then STOPS and waits. It prints the run id, the card to read, and the card hash.

uv run main.py decide <run_id> approve review_agent <card_hash> "self approval"
# → refused: an agent name cannot approve

uv run main.py decide <run_id> approve your.name <card_hash> "Plausible MO-04 variation"
# → approved; the run finishes
```

`simulate` and `decide` are separate commands. The waiting run is saved in `runs/checkpoints.sqlite` and picked up again by `decide`.

## How to write a scenario

A scenario is the input for `simulate`. It is one JSON file in `scenarios/`, and its file name is how you run it:
`scenarios/my_case.json` → `uv run main.py simulate my_case`.

| Field | Needed? | What it is |
|---|---|---|
| `id` | yes | Scenario name (same as the file name) |
| `title` | yes | Title shown on the pattern card |
| `theme` | yes | What the agents should explore |
| `scripts` | yes, for the mock AI | Pre-written answers for each agent: `trainee`, `provider`, `employer`, `review` |
| `turn_order` | optional | Who speaks first (default: trainee, provider, employer) |
| `max_rounds` | optional | Fewer rounds than the limit of 3 |
| `extra_sources` | optional | Extra posts to load (used to test poisoned input) |
| `limits_override` | optional | Different limits, e.g. `{"max_llm_calls": 3}` |
| `scripts_from` | optional | Reuse the `scripts` of another scenario |

Each item in an agent's script is one answer, used in order:
- a JSON object → the agent's answer (must match the answer format, see `schemas.py`);
- `{"__tool_calls__": [{"name": "trainee_evidence_read", "args": {"source_id": "S3"}}]}` → the agent calls a tool first;
- a plain string → used as-is (e.g. broken JSON, to test retries).

When an agent's script runs out, it answers `{"done": true}`.

Each contribution may set `"awareness"`: `"knowing"`, `"unaware"` or `"not_stated"` (default). This drives the intent assessment; if it is not stated, intent is UNKNOWN.

Smallest useful example (`scenarios/my_case.json`):

```json
{
  "id": "my_case",
  "title": "Provider overclaims hours",
  "theme": "Could a provider claim for more training than it delivered?",
  "turn_order": ["provider", "trainee", "employer"],
  "scripts": {
    "provider": [
      {"contributions": [
        {"function": "course_delivery_record",
         "description": "Records more training hours than were delivered.",
         "benefit_to_self": "Lower delivery cost.",
         "behaviour_tags": ["claim_exceeds_delivery", "partial_delivery"]}
      ], "done": true}
    ],
    "review": [
      {"source_findings": [], "evidence_strength": "WEAK", "mo_label": "KNOWN", "mo_ids": ["MO-07"],
       "mo_rationale": "Matches MO-07.",
       "test_data_needed": [{"data_item": "Claimed vs scheduled hours", "purpose": "Spot overclaims",
                             "granularity": "aggregate"}]}
    ]
  }
}
```

See the 8 files in `scenarios/` for complete examples.

## Layout

```
main.py       start here: reads the command (simulate, decide, eval, demo) and calls it
config/       actors.json (profiles, tools, visibility) · taxonomy.json · mo_feature_tags.json · limits.json
data/         Annex A and B transcribed verbatim (treated as untrusted)
scenarios/    4 golden scenarios + 4 red-team scenarios (scripted mock responses per agent)
src/collusion_sim/
  graph.py       LangGraph StateGraph: orchestrator hub, actor nodes, review, finalize, interrupt, halt
  runtime.py     start / pending / resume API with SqliteSaver
  agents.py      prompts, bounded tool loop, schema validation, retries, budget
  tools.py       role-scoped LangChain tools + ToolGateway (allow-list, scope, denial tracing)
  guards.py      injection, unsafe-content and fact-assertion guards; turn validators
  sources.py     annex loading, sanitising, quarantine
  analysis.py    actor-removal check, MO classification, evidence rules
  cards.py       card assembly, deterministic checks, markdown rendering
  approval.py    human decision rules
  commands.py    what each main.py command does
  trace.py       hash-chained JSONL trace + LangChain callback
  llm.py         ScriptedChatModel (GenericFakeChatModel) per agent; optional real model
  evaluation.py  agent / end-to-end / regression harness
evals/        agent_cases.json · e2e_expectations.json · golden/*.json
tests/        pytest suite
```

## Using a real model

Not included. Any LangChain chat model that supports tool calling can be passed to `start_run(..., llm_factory=...)` in place of the scripted mock; all controls apply unchanged. See design note §10 for how pattern quality would then be evaluated.
