# Handoff notes (read this first)

Summary of how this project was built and what the owner wants. Written so a new
assistant (for example Claude in Cursor) can continue without the original chat.

## What this is

A take-home assessment for an ML/AI Engineer role (SWDA, "Part 2: Case Study").
Goal: a small multi-agent system that simulates how a trainee, a training provider and
an employer might work together to misuse a training grant, and produces "pattern cards"
that a human must approve. Only Annex A (MO library) and Annex B (social media excerpts)
may be used. All outputs are simulated risk ideas, never facts.

## How to run

    uv run pytest             # setup + all tests
    uv run main.py eval       # evaluation report
    uv run main.py demo       # sample outputs

Other commands: `simulate`, `decide` (see main.py).

## Owner's preferences (please follow)

- Use **LangGraph / LangChain** (required by the owner).
- Use **uv** for packages. **No Makefile.**
- Start the app from **main.py** with `uv run main.py ...`. No generated command names
  (no `[project.scripts]`).
- argparse is fine, but write it like the owner's own example: numbered comment steps
  (`# 1. Initialize the parser`, `# 2. Add arguments`, `# 3. Parse`, `# 4. Run`),
  one argument per line, a `help=` text on each, and end with plain `main()`.
- Keep main.py short; put longer logic in other files.
- **Keep code simple and easy to read**: one statement per line, plain comments,
  no clever one-liners or semicolons. The owner found dense code very hard to read.
- **Explain things in plain, simple language**, without jargon. Short answers, one
  topic at a time. Show real examples (exact commands and their output).
- When the owner asks "where is X", give the file name and line number first.
- Remove anything the assignment does not need.

## Most important files

| File | What it does |
|---|---|
| `main.py` | Starting point. Short: reads the typed command (simple argparse) and calls one function. |
| `src/collusion_sim/commands.py` | What each command does (simulate, decide, evaluate, demo). |
| `src/collusion_sim/graph.py` | **The LangGraph workflow.** Orchestrator, 3 actor agents, Review Agent, and the `interrupt()` that waits for a human. |
| `src/collusion_sim/runtime.py` | Starts a run, and continues it after the human decides (saved in SQLite). |
| `src/collusion_sim/agents.py` | Builds each agent with LangChain `create_agent` (own tools + middleware), checks its answer, retries. |
| `src/collusion_sim/middleware.py` | LangChain middleware: tool permissions, budget limit, usage logging. |
| `src/collusion_sim/tools.py` | Controls what each agent is allowed to read. |
| `src/collusion_sim/guards.py` | Safety checks (blocks hidden instructions and unsafe text). |
| `src/collusion_sim/analysis.py` | Fraud-pattern rules (collusion or one person alone, known/new MO, evidence strength). |
| `src/collusion_sim/approval.py` | Rules for the human decision (the AI can never approve). |
| `docs/DESIGN_NOTE.md` | Design explanation (deliverable B). |
| `docs/ARCHITECTURE.md` + `architecture.png` | Diagram (deliverable A). |

The AI in this project is a **scripted fake** (pre-written answers per agent), so it runs
offline. The tests check the safety rules and workflow, not how clever a real AI would be.

## Status

- Working: 75 tests and 242 evaluation checks pass.
- Done: switched to uv, removed Makefile, added main.py, removed extras
  (pending/show/trace commands, real-model code, svg/mermaid duplicates),
  short main.py in the owner's argparse style, logic moved to commands.py,
  removed the `all` command (use `uv run pytest`).
- Done: agents use LangChain `create_agent` + `@tool` + middleware; orchestrator and review
  route with LangGraph `Command(goto=...)`; trace writing is thread-safe (ToolNode runs tools in parallel).
- Done: collusion judged in 4 separate steps in analysis.py (functional dependency, simulated
  cooperation from delivered messages, intent from `awareness`, overall assessment); evidence never
  above LOW automatically; MO label marked provisional; tests in tests/test_collusion_assessment.py.

## Ideas not done yet (ask the owner first)

1. Rewrite `graph.py` (and then other files) in the same simple, readable style as `main.py`.
2. Make the folder structure flatter: move `src/collusion_sim/` to a simple `app/` folder
   next to `main.py`, with plain imports.
3. Walk the owner through `graph.py` step by step, in plain words.
