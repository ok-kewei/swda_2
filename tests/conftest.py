from pathlib import Path

import pytest

from collusion_sim.config import load_config
from collusion_sim.sources import SourceStore
from collusion_sim.trace import TraceStore


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def sources(cfg):
    return SourceStore.load(cfg.data_dir)


@pytest.fixture
def trace(tmp_path: Path):
    return TraceStore(tmp_path / "trace.jsonl", "test")


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    d = tmp_path / "runs"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Readable test report: written to reports/test_report.md after every run.
# ---------------------------------------------------------------------------

REPORT_FILE = Path(__file__).resolve().parents[1] / "reports" / "test_report.md"

# What each test file checks, in plain English.
FILE_TOPICS = {
    "test_guards_and_sources.py": "Safety checks (bad input blocked, unsafe text caught)",
    "test_tools.py": "Each agent can only use its own tools",
    "test_analysis.py": "Fraud rules (collusion or one person, known/new MO, evidence)",
    "test_workflow.py": "LangGraph workflow (waits for a human, approval rules, limits)",
    "test_evals.py": "Full evaluation and regression checks",
    "test_collusion_assessment.py": "Dependency, cooperation, intent and overall assessment",
}

test_results = []


def readable_name(test_name):
    """Turn 'test_own_tool_is_scope_limited[x]' into 'Own tool is scope limited (case: x)'."""
    name = test_name.removeprefix("test_")
    case = ""
    if "[" in name:
        name, case = name.split("[", 1)
        case = " (case: " + case.rstrip("]") + ")"
    sentence = name.replace("_", " ")
    text = sentence[0].upper() + sentence[1:] + case
    return text.replace("|", "\\|")  # "|" would break the markdown table


def pytest_runtest_logreport(report):
    # Record the result of each test once (the "call" step, or a failed setup).
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        file_name = report.nodeid.split("::")[0].split("/")[-1]
        test_name = report.nodeid.split("::")[-1]
        test_results.append((file_name, test_name, report.outcome))


def pytest_sessionfinish(session, exitstatus):
    if not test_results:
        return

    passed = sum(1 for _, _, outcome in test_results if outcome == "passed")
    failed = len(test_results) - passed

    lines = ["# Test report", ""]
    lines.append(f"**Total: {len(test_results)} tests. Passed: {passed}. Failed: {failed}.**")
    lines.append("")

    for file_name, topic in FILE_TOPICS.items():
        rows = [r for r in test_results if r[0] == file_name]
        if not rows:
            continue
        file_passed = sum(1 for r in rows if r[2] == "passed")
        lines.append(f"## {topic}")
        lines.append(f"File: `tests/{file_name}`. {file_passed} of {len(rows)} passed.")
        lines.append("")
        lines.append("| # | What is tested | Result |")
        lines.append("|---|---|---|")
        for number, (_, test_name, outcome) in enumerate(rows, start=1):
            result = "✅ PASS" if outcome == "passed" else "❌ FAIL"
            lines.append(f"| {number} | {readable_name(test_name)} | {result} |")
        lines.append("")

    REPORT_FILE.parent.mkdir(exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def pytest_terminal_summary(terminalreporter):
    if test_results:
        terminalreporter.write_line(f"Readable test report: {REPORT_FILE}")
