"""Runs the full evaluation harness and proves the regression check bites."""
import json
import shutil

from collusion_sim import evaluation
from collusion_sim.evaluation import Report, run_agent_evals, run_e2e_evals


def test_agent_level_evals_pass():
    rep = Report()
    run_agent_evals(rep)
    assert rep.outcomes and not rep.failed, [vars(o) for o in rep.failed]


def test_end_to_end_evals_and_regression_pass(tmp_path):
    rep = Report()
    run_e2e_evals(rep, tmp_path / "runs")
    assert not rep.failed, [vars(o) for o in rep.failed]
    assert {o.suite for o in rep.outcomes} >= {"invariant", "expect", "approval", "regression"}
    assert all(o.check == "matches_golden" for o in rep.outcomes if o.suite == "regression")


def test_regression_detects_changed_output(tmp_path, monkeypatch):
    golden = tmp_path / "golden"
    shutil.copytree(evaluation.GOLDEN_DIR, golden)
    g = json.loads((golden / "solo_overclaim.json").read_text())
    g["evidence"]["final_strength"] = "MODERATE"
    (golden / "solo_overclaim.json").write_text(json.dumps(g))
    monkeypatch.setattr(evaluation, "GOLDEN_DIR", golden)
    rep = Report()
    run_e2e_evals(rep, tmp_path / "runs")
    failed = [(o.case, o.check, o.detail) for o in rep.failed]
    assert failed == [("solo_overclaim", "matches_golden", "['evidence']")]
