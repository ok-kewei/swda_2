"""Start here.

Examples (run from the project folder):

    uv run main.py simulate solo_overclaim
    uv run main.py decide <run_id> approve alice <card_hash> "Looks plausible"
    uv run main.py eval
    uv run main.py demo

Run the tests with:  uv run pytest
"""
import argparse

from collusion_sim.commands import decide, demo, evaluate, simulate


def main():
    # 1. Initialize the parser
    parser = argparse.ArgumentParser(description="Simulate grant-fraud collusion patterns for human review.")
    commands = parser.add_subparsers(dest="command", required=True)

    # 2. Add the commands and their arguments
    simulate_parser = commands.add_parser("simulate", help="Run one scenario; it waits for a human decision")
    simulate_parser.add_argument("scenario", help="Scenario name, e.g. solo_overclaim")

    decide_parser = commands.add_parser("decide", help="Approve or reject a waiting card")
    decide_parser.add_argument("run_id", help="Run id printed by simulate")
    decide_parser.add_argument("decision", choices=["approve", "reject", "request_changes"])
    decide_parser.add_argument("reviewer", help="Your name")
    decide_parser.add_argument("card_hash", help="Card hash printed by simulate")
    decide_parser.add_argument("reason", help="Why you decided this")

    eval_parser = commands.add_parser("eval", help="Run the evaluation checks")
    eval_parser.add_argument("--update-golden", action="store_true", help="Save new expected results")

    commands.add_parser("demo", help="Run every scenario and save results in sample_outputs/")

    # 3. Parse the command-line arguments
    args = parser.parse_args()

    # 4. Run the chosen command
    if args.command == "simulate":
        simulate(args.scenario)
    elif args.command == "decide":
        decide(args.run_id, args.decision, args.reviewer, args.card_hash, args.reason)
    elif args.command == "eval":
        evaluate(args.update_golden)
    elif args.command == "demo":
        demo()


if __name__ == "__main__":
    main()
