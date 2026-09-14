"""Tests for status, history, and explain CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from factor_atlas.cli_commands import cmd_explain, cmd_history, cmd_status


def _make_artifacts(tmp_path: Path) -> Path:
    """Create minimal fixture artifacts for testing."""
    artifacts = tmp_path / "artifacts" / "paper-trading"
    artifacts.mkdir(parents=True)

    # positions_state.json
    (artifacts / "positions_state.json").write_text(
        json.dumps(
            {
                "open_positions": [
                    {
                        "instrument": "AAPLUSDT",
                        "side": "buy",
                        "entry_price": "330.33",
                        "quantity": "2",
                        "entry_time": "2026-09-14T10:00:00+00:00",
                        "hypothesis_id": "hyp-1",
                        "factor_name": "momentum",
                        "cycle_id": "cycle-1",
                    }
                ],
                "closed_trades": [
                    {
                        "instrument": "METAUSDT",
                        "side": "sell",
                        "entry_price": "641.76",
                        "exit_price": "630.00",
                        "quantity": "1",
                        "pnl": "11.76",
                        "pnl_pct": 0.0183,
                        "entry_time": "2026-09-13T10:00:00+00:00",
                        "exit_time": "2026-09-13T18:00:00+00:00",
                        "hold_duration_hours": 8.0,
                        "won": True,
                        "factor_name": "mean_reversion",
                    }
                ],
                "last_updated": "2026-09-14T10:05:00+00:00",
            }
        )
    )

    # A run directory with manifest and paper_log
    run_dir = artifacts / "test-run-123"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "test-run-123",
                "start_timestamp": "2026-09-14T10:00:00+00:00",
                "end_timestamp": "2026-09-14T10:01:00+00:00",
                "mode": "fixture",
                "cycles_completed": 2,
                "accepted_count": 1,
                "rejected_count": 1,
                "llm_provider": "fixture",
                "llm_model": "fixture",
                "llm_mode": "fixture",
                "performance_metrics": {
                    "total_trades": 1,
                    "win_rate": 1.0,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "total_pnl": "11.76",
                },
            }
        )
    )
    (run_dir / "paper_log.jsonl").write_text(
        json.dumps(
            {
                "record_type": "open",
                "instrument": "AAPLUSDT",
                "category": "USDT-FUTURES",
                "side": "buy",
                "status": "filled",
                "factor_name": "momentum",
                "rationale": "Strong momentum signal",
                "risk_gate_results": [
                    {"gate_name": "factor_allowlist", "passed": True, "reason": "ok"}
                ],
            }
        )
        + "\n"
    )

    return artifacts


class TestCmdStatus:
    def test_shows_open_positions(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_status(artifacts)
        assert "AAPLUSDT" in output
        assert "momentum" in output

    def test_shows_closed_trade_metrics(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_status(artifacts)
        assert "1" in output  # total trades
        assert "100" in output or "1.0" in output  # win rate

    def test_missing_state_file(self, tmp_path: Path) -> None:
        artifacts = tmp_path / "artifacts" / "paper-trading"
        artifacts.mkdir(parents=True)
        output = cmd_status(artifacts)
        assert "Open positions: none" in output
        assert "Closed trades: 0" in output

    def test_missing_artifacts_dir(self, tmp_path: Path) -> None:
        artifacts = tmp_path / "artifacts" / "paper-trading"
        output = cmd_status(artifacts)
        assert "Open positions: none" in output


class TestCmdHistory:
    def test_lists_sessions(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_history(artifacts)
        assert "test-run-123" in output

    def test_no_sessions(self, tmp_path: Path) -> None:
        artifacts = tmp_path / "artifacts" / "paper-trading"
        artifacts.mkdir(parents=True)
        output = cmd_history(artifacts)
        assert "No sessions found" in output

    def test_missing_dir(self, tmp_path: Path) -> None:
        artifacts = tmp_path / "artifacts" / "paper-trading"
        output = cmd_history(artifacts)
        assert "No sessions found" in output


class TestCmdExplain:
    def test_explains_run(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_explain("test-run-123", artifacts)
        assert "AAPLUSDT" in output
        assert "momentum" in output

    def test_unknown_run_id(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_explain("nonexistent", artifacts)
        assert "not found" in output.lower()

    def test_shows_rationale(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_explain("test-run-123", artifacts)
        assert "Strong momentum signal" in output

    def test_shows_gate_results(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_explain("test-run-123", artifacts)
        assert "Gates" in output
