"""The four commands that main.py can run: simulate, decide, evaluate, demo."""
import json
import shutil
import sys

from .approval import ApprovalError
from .config import REPO_ROOT
from .evaluation import run_all
from .runtime import DEFAULT_RUNS_DIR, SCENARIO_DIR, RunError, start_run, submit_decision


def show_result(result):
    """Print whether the run is waiting for a human, or was stopped by a limit."""
    if result["status"] == "HALTED":
        print(f"[{result['run_id']}] STOPPED: {result['halt_reason']}")
        return

    waiting = result["interrupt"]
    print(f"[{result['run_id']}] WAITING for a human decision.")
    print(f"  card to read:   {waiting['card_path']}")
    print(f"  you may:        {', '.join(waiting['allowed_decisions'])}")
    print(f"  to decide, run: uv run main.py decide {result['run_id']} <decision> <your_name> "
          f"{waiting['content_hash']} \"<reason>\"")


def simulate(scenario):
    result = start_run(scenario, runs_dir=DEFAULT_RUNS_DIR)
    show_result(result)


def decide(run_id, decision, reviewer, card_hash, reason):
    human_decision = {
        "decision": decision,
        "reviewer": reviewer,
        "reason": reason,
        "card_hash": card_hash,
    }
    try:
        submit_decision(run_id, human_decision, DEFAULT_RUNS_DIR)
    except (ApprovalError, RunError) as error:
        print(f"Decision refused: {error}. The run is still waiting.")
        sys.exit(2)

    print(f"[{run_id}] {decision.upper()} by {reviewer}.")


def evaluate(update_golden):
    eval_runs = DEFAULT_RUNS_DIR / "_eval"
    shutil.rmtree(eval_runs, ignore_errors=True)

    report = run_all(eval_runs, REPO_ROOT / "reports", update_golden=update_golden)

    summary = report.summary()
    print(f"{summary['total']} checks, {summary['failed']} failed: {json.dumps(summary['by_suite'])}")
    for failure in report.failed:
        print(f"  FAIL {failure.suite}/{failure.case}/{failure.check}: {failure.detail}")
    print("report: reports/eval_report.md")

    if report.failed:
        sys.exit(1)


def demo():
    output_dir = REPO_ROOT / "sample_outputs"
    demo_runs = DEFAULT_RUNS_DIR / "_demo"
    shutil.rmtree(demo_runs, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir()

    for scenario_file in sorted(SCENARIO_DIR.glob("*.json")):
        scenario_id = scenario_file.stem
        result = start_run(scenario_id, runs_dir=demo_runs, run_id=scenario_id)
        show_result(result)

        card = result["card"]
        if card:
            # A pretend human, so the demo runs without typing.
            # Normal scenarios are approved. Red-team ("rt_") and incomplete ones are rejected.
            if card["status"] == "PENDING_HUMAN_REVIEW" and not scenario_id.startswith("rt_"):
                choice = "approve"
                reason = "Plausible pattern; approve for testing with the listed data."
            else:
                choice = "reject"
                reason = "Red-team or incomplete run; kept for audit only."
            human_decision = {
                "decision": choice,
                "reviewer": "demo.analyst",
                "reason": reason,
                "card_hash": card["content_hash"],
            }
            submit_decision(scenario_id, human_decision, demo_runs)
            print(f"  -> {choice} by demo.analyst")

        shutil.copytree(demo_runs / scenario_id, output_dir / scenario_id)

    shutil.copy(demo_runs / "decisions.jsonl", output_dir / "decisions.jsonl")
    print(f"sample outputs written to {output_dir}")
