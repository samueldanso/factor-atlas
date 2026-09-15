"""Tests for the structured evidence logger."""

from __future__ import annotations

import json
from pathlib import Path

from factor_atlas.evidence import EvidenceLogger


def test_evidence_logger_creates_log_dir(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logger = EvidenceLogger(logs_dir=logs_dir, run_id="test-run-001")
    assert logs_dir.exists()
    assert logger.run_id == "test-run-001"


def test_evidence_logger_files_exist(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logger = EvidenceLogger(logs_dir=logs_dir, run_id="test-run-001")
    # Files created on first write, not on init — but paths should be set
    assert logger.events_path == logs_dir / "events.jsonl"
    assert logger.decisions_path == logs_dir / "decisions.jsonl"
    assert logger.risk_path == logs_dir / "risk.jsonl"
    assert logger.trades_path == logs_dir / "trades.jsonl"
    assert logger.agent_log_path == logs_dir / "agent.log"


def test_log_event_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_event(
        cycle_id="cycle-001",
        instrument="RAAPLUSDT",
        price="231.45",
        source="bitget-demo",
        hypothesis={
            "factor_name": "momentum",
            "direction": "long",
            "parameters": {"lookback": 20, "threshold": 0.02},
            "rationale": "Strong upward trend over 20 bars",
        },
        validation={
            "sharpe": 1.82,
            "max_drawdown": -0.043,
            "passed": True,
            "observations": 60,
        },
    )
    lines = logger.events_path.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["run_id"] == "run-001"
    assert record["cycle_id"] == "cycle-001"
    assert record["instrument"] == "RAAPLUSDT"
    assert record["hypothesis"]["factor_name"] == "momentum"
    assert record["validation"]["sharpe"] == 1.82


def test_log_decision_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_decision(
        cycle_id="cycle-001",
        instrument="AAPLUSDT",
        selected_hypothesis="hyp-001",
        side="buy",
        quantity="3",
        price="231.45",
        rationale="Best risk-adjusted return from momentum factor",
    )
    lines = logger.decisions_path.read_text().strip().split("\n")
    record = json.loads(lines[0])
    assert record["side"] == "buy"
    assert record["rationale"] == "Best risk-adjusted return from momentum factor"


def test_log_risk_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    gates = [
        {"gate_name": "factor_allowlist", "passed": True, "reason": "ok"},
        {"gate_name": "max_notional", "passed": False, "reason": "exceeds $10000"},
    ]
    logger.log_risk(
        cycle_id="cycle-001",
        instrument="AAPLUSDT",
        gates=gates,
        verdict="blocked",
    )
    lines = logger.risk_path.read_text().strip().split("\n")
    record = json.loads(lines[0])
    assert record["verdict"] == "blocked"
    assert len(record["gates"]) == 2


def test_log_trade_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_trade(
        cycle_id="cycle-001",
        record_type="entry",
        instrument="AAPLUSDT",
        side="buy",
        price="231.45",
        size="3",
        order_id="1483325250270023680",
        status="filled",
    )
    lines = logger.trades_path.read_text().strip().split("\n")
    record = json.loads(lines[0])
    assert record["orderId"] == "1483325250270023680"
    assert record["orderStatus"] == "filled"


def test_agent_log_human_readable(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_run_start(mode="demo", interval=14400, llm_model="claude-sonnet-4-6")
    logger.log_event(
        cycle_id="c1",
        instrument="RAAPLUSDT",
        price="231.45",
        source="bitget-demo",
        hypothesis=None,
        validation=None,
    )
    logger.log_run_end(cycles=4, accepted=1, skipped=3)

    content = logger.agent_log_path.read_text()
    assert "Run run-001" in content
    assert "RAAPLUSDT" in content
    assert "1 accepted, 3 skipped" in content


def test_append_only_across_calls(tmp_path: Path) -> None:
    """Two separate logger instances (simulating two runs) append to same files."""
    logger1 = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger1.log_decision(
        cycle_id="c1",
        instrument="AAPLUSDT",
        selected_hypothesis="h1",
        side="buy",
        quantity="1",
        price="100",
        rationale="first",
    )
    logger2 = EvidenceLogger(logs_dir=tmp_path, run_id="run-002")
    logger2.log_decision(
        cycle_id="c2",
        instrument="METAUSDT",
        selected_hypothesis="h2",
        side="sell",
        quantity="2",
        price="200",
        rationale="second",
    )
    lines = tmp_path.joinpath("decisions.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["run_id"] == "run-001"
    assert json.loads(lines[1])["run_id"] == "run-002"
