"""Tests for the HTML evidence report generator."""

from __future__ import annotations

import json
from pathlib import Path

from factor_atlas.report import generate_report, generate_report_file

_MANIFEST = {
    "run_id": "test-run-001",
    "start_timestamp": "2026-09-14T09:00:00+00:00",
    "end_timestamp": "2026-09-14T09:10:00+00:00",
    "timezone": "UTC",
    "mode": "demo",
    "instruments": ["RAAPLUSDT"],
    "execution_instruments": ["AAPLUSDT"],
    "cycles_completed": 2,
    "accepted_count": 1,
    "rejected_count": 1,
    "code_commit": "abc1234",
    "config_hash": "sha256:test",
    "software_version": "0.1.0",
    "performance_metrics": {
        "total_trades": 1,
        "win_rate": 1.0,
        "total_pnl": "5.00",
        "avg_pnl": "5.00",
        "sharpe_ratio": 2.5,
        "sortino_ratio": 3.0,
        "max_drawdown": 2.0,
        "profit_factor": 2.0,
        "turnover": 500.0,
        "avg_hold_hours": 12.0,
        "equity_curve": [
            ["2026-09-14T09:05:00+00:00", 5.0],
        ],
    },
    "llm_provider": "aws-bedrock",
    "llm_model": "claude-sonnet-4-6",
    "llm_mode": "live",
}

_PAPER_LOG = [
    {
        "record_type": "close",
        "order_id": None,
        "timestamp": "2026-09-14T09:05:00+00:00",
        "instrument": "AAPLUSDT",
        "category": "USDT-FUTURES",
        "side": "sell",
        "price": "335.00",
        "quantity": "1",
        "notional": "335.00",
        "status": "closed",
        "fill_price": "335.00",
        "entry_price": "330.00",
        "exit_price": "335.00",
        "pnl": "5.00",
        "pnl_pct": 0.0152,
        "won": True,
        "hold_duration_hours": 12.0,
        "factor_name": "momentum",
        "rationale": "exit: pnl=5.00 (1.52%), hold=12.0h",
        "risk_gate_results": [],
        "software_version": "0.1.0",
        "config_hash": "sha256:test",
        "bgc_order_id": "123456",
    },
    {
        "record_type": "open",
        "order_id": "order-001",
        "decision_id": "dec-001",
        "event_id": "dec-001",
        "timestamp": "2026-09-14T09:06:00+00:00",
        "instrument": "AAPLUSDT",
        "category": "USDT-FUTURES",
        "side": "buy",
        "price": "331.00",
        "quantity": "1",
        "notional": "331.00",
        "pre_balance": "100000",
        "post_balance": "99999.50",
        "fees": "0.33",
        "slippage": "0.17",
        "status": "filled",
        "fill_price": "331.00",
        "cycle_id": "cycle-001",
        "hypothesis_id": "hyp-001",
        "factor_name": "mean_reversion",
        "risk_gate_results": [
            {"gate_name": "max_position", "passed": True, "reason": "positions 0 < 3"},
            {"gate_name": "balance_check", "passed": True, "reason": "ok"},
        ],
        "validation_sharpe": 2.5,
        "rationale": "Mean reversion signal detected at support level.",
        "software_version": "0.1.0",
        "config_hash": "sha256:test",
        "bgc_order_id": "789012",
        "verification_status": "verified_filled",
    },
    {
        "record_type": "open",
        "order_id": "order-002",
        "decision_id": "dec-002",
        "event_id": "dec-002",
        "timestamp": "2026-09-14T09:07:00+00:00",
        "instrument": "METAUSDT",
        "category": "USDT-FUTURES",
        "side": "sell",
        "price": "640.00",
        "quantity": "1",
        "notional": "640.00",
        "pre_balance": "99999.50",
        "post_balance": "99999.50",
        "fees": "0",
        "slippage": "0",
        "status": "rejected",
        "fill_price": None,
        "cycle_id": "cycle-002",
        "hypothesis_id": "hyp-002",
        "factor_name": "momentum",
        "risk_gate_results": [
            {
                "gate_name": "max_position",
                "passed": False,
                "reason": "positions 3 >= 3",
            },
        ],
        "validation_sharpe": 1.8,
        "rationale": "Momentum signal strong but position limit reached.",
        "software_version": "0.1.0",
        "config_hash": "sha256:test",
    },
]

_AUDIT_LOG = [
    {
        "event_id": "ev-001",
        "cycle_id": "cycle-001",
        "stage": "observe",
        "timestamp": "2026-09-14T09:06:00Z",
        "parent_event_id": None,
        "payload": {
            "snapshot_id": "demo-RAAPLUSDT-123",
            "instrument": "RAAPLUSDT",
            "source": "bitget-demo",
        },
    },
    {
        "event_id": "ev-002",
        "cycle_id": "cycle-001",
        "stage": "propose",
        "timestamp": "2026-09-14T09:06:01Z",
        "parent_event_id": "ev-001",
        "payload": {
            "hypothesis_ids": ["hyp-001"],
            "count": 1,
            "factor_names": ["mean_reversion"],
        },
    },
    {
        "event_id": "ev-003",
        "cycle_id": "cycle-001",
        "stage": "evaluate",
        "timestamp": "2026-09-14T09:06:02Z",
        "parent_event_id": "ev-002",
        "payload": {
            "evaluations": [
                {
                    "hypothesis_id": "hyp-001",
                    "passed": True,
                    "rejection_reasons": [],
                    "sharpe": 2.5,
                    "drawdown": -0.005,
                },
            ],
        },
    },
    {
        "event_id": "ev-004",
        "cycle_id": "cycle-001",
        "stage": "decide",
        "timestamp": "2026-09-14T09:06:03Z",
        "parent_event_id": "ev-003",
        "payload": {
            "decision_id": "dec-001",
            "selected_hypothesis_id": "hyp-001",
            "rationale": "Best Sharpe ratio.",
            "status": "accepted",
        },
    },
    {
        "event_id": "ev-005",
        "cycle_id": "cycle-001",
        "stage": "gate",
        "timestamp": "2026-09-14T09:06:04Z",
        "parent_event_id": "ev-004",
        "payload": {
            "gate_results": [
                {"gate_name": "max_position", "passed": True, "reason": "ok"},
            ],
            "all_passed": True,
        },
    },
    {
        "event_id": "ev-006",
        "cycle_id": "cycle-001",
        "stage": "execute",
        "timestamp": "2026-09-14T09:06:05Z",
        "parent_event_id": "ev-005",
        "payload": {
            "order_id": "order-001",
            "status": "filled",
            "fill_price": "331.00",
            "fees": "0.33",
            "slippage": "0.17",
            "pre_balance": "100000",
            "post_balance": "99999.50",
        },
    },
    {
        "event_id": "ev-007",
        "cycle_id": "cycle-001",
        "stage": "learn",
        "timestamp": "2026-09-14T09:06:06Z",
        "parent_event_id": "ev-006",
        "payload": {
            "cycle_summary": {
                "cycle_id": "cycle-001",
                "status": "accepted",
                "instrument": "RAAPLUSDT",
                "side": "buy",
                "pnl_estimate": -0.5,
            },
        },
    },
]


class TestGenerateReport:
    def test_generates_valid_html(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-001"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(_MANIFEST))
        (run_dir / "paper_log.jsonl").write_text(
            "\n".join(json.dumps(r) for r in _PAPER_LOG)
        )
        (run_dir / "audit_log.jsonl").write_text(
            "\n".join(json.dumps(r) for r in _AUDIT_LOG)
        )

        html = generate_report(run_dir)
        assert "<!DOCTYPE html>" in html
        assert "FactorAtlas" in html
        assert "test-run-001" in html
        assert "AAPLUSDT" in html
        assert "mean_reversion" in html
        assert "momentum" in html
        assert "max_position" in html
        assert "positions 3 &gt;= 3" in html
        assert "FILLED" in html
        assert "REJECTED" in html
        assert "WIN" in html
        assert "789012" in html
        assert "verified_filled" in html

    def test_writes_file(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-002"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(_MANIFEST))
        (run_dir / "paper_log.jsonl").write_text(
            "\n".join(json.dumps(r) for r in _PAPER_LOG)
        )
        (run_dir / "audit_log.jsonl").write_text("")

        path = generate_report_file(run_dir)
        assert path.exists()
        assert path.name == "evidence_report.html"
        content = path.read_text()
        assert "<!DOCTYPE html>" in content

    def test_custom_output_path(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-003"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(_MANIFEST))
        (run_dir / "paper_log.jsonl").write_text("")
        (run_dir / "audit_log.jsonl").write_text("")

        out = tmp_path / "custom_report.html"
        path = generate_report_file(run_dir, out)
        assert path == out
        assert out.exists()

    def test_empty_run_dir(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-empty"
        run_dir.mkdir()
        html = generate_report(run_dir)
        assert "<!DOCTYPE html>" in html
        assert "No cycles recorded" in html

    def test_audit_pipeline_in_output(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run-audit"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(json.dumps(_MANIFEST))
        (run_dir / "paper_log.jsonl").write_text(
            "\n".join(json.dumps(r) for r in _PAPER_LOG)
        )
        (run_dir / "audit_log.jsonl").write_text(
            "\n".join(json.dumps(r) for r in _AUDIT_LOG)
        )

        html = generate_report(run_dir)
        assert "OBSERVE" in html
        assert "PROPOSE" in html
        assert "EVALUATE" in html
        assert "DECIDE" in html
        assert "GATE" in html
        assert "EXECUTE" in html
        assert "LEARN" in html
        assert "bitget-demo" in html
