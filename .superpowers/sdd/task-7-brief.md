### Task 7: CLI commands — status, history, explain

**Files:**
- Modify: `src/factor_atlas/__main__.py` (add subcommands)
- Create: `src/factor_atlas/cli_commands.py` (command implementations)
- Create: `tests/test_cli_commands.py`

**Interfaces:**
- Consumes: `compute_metrics` from `metrics.py`, `BrokerState`/`OpenPosition`/`ClosedTrade` from `broker.py`, `_load_positions_state` from `runner.py`
- Produces:
  - `cmd_status(artifacts_dir: Path) -> str` — returns formatted status string
  - `cmd_history(artifacts_dir: Path) -> str` — returns formatted history string
  - `cmd_explain(run_id: str, artifacts_dir: Path) -> str` — returns formatted explanation string

- [ ] **Step 1: Write tests for CLI commands**

```python
# tests/test_cli_commands.py
"""Tests for status, history, and explain CLI commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
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


class TestCmdHistory:
    def test_lists_sessions(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_history(artifacts)
        assert "test-run-123" in output


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'factor_atlas.cli_commands'`

- [ ] **Step 3: Implement cli_commands.py**

```python
# src/factor_atlas/cli_commands.py
"""CLI command implementations for status, history, and explain."""

from __future__ import annotations

import json
from pathlib import Path

from factor_atlas.broker import BrokerState, ClosedTrade, OpenPosition
from factor_atlas.metrics import compute_metrics


def _load_state(artifacts_dir: Path) -> BrokerState:
    state = BrokerState()
    state_path = artifacts_dir / "positions_state.json"
    if not state_path.exists():
        return state
    try:
        raw = json.loads(state_path.read_text())
        for d in raw.get("open_positions", []):
            pos = OpenPosition.from_dict(d)
            state.open_positions[pos.instrument] = pos
        for d in raw.get("closed_trades", []):
            state.closed_trades.append(ClosedTrade.from_dict(d))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return state


def _find_runs(artifacts_dir: Path) -> list[dict]:
    runs = []
    for d in sorted(artifacts_dir.iterdir()):
        manifest_path = d / "manifest.json"
        if d.is_dir() and manifest_path.exists():
            try:
                runs.append(json.loads(manifest_path.read_text()))
            except (json.JSONDecodeError, KeyError):
                continue
    return runs


def cmd_status(artifacts_dir: Path) -> str:
    """Build status output from local state."""
    state = _load_state(artifacts_dir)
    metrics = compute_metrics(state.closed_trades)
    runs = _find_runs(artifacts_dir)

    lines = ["FactorAtlas Status", ""]

    if state.open_positions:
        lines.append(f"  Open positions ({len(state.open_positions)}):")
        for inst, pos in state.open_positions.items():
            lines.append(
                f"    {inst}: {pos.side}, entry=${pos.entry_price}, "
                f"qty={pos.quantity}, factor={pos.factor_name}"
            )
    else:
        lines.append("  Open positions: none")

    lines.append("")
    n = metrics["total_trades"]
    lines.append(f"  Closed trades: {n}")
    if n > 0:
        lines.append(f"    Win rate: {metrics['win_rate']}")
        lines.append(f"    Sharpe: {metrics['sharpe_ratio']}")
        lines.append(f"    Sortino: {metrics['sortino_ratio']}")
        lines.append(f"    Max drawdown: {metrics['max_drawdown']}")
        lines.append(f"    Total PnL: {metrics['total_pnl']}")
        lines.append(f"    Avg hold: {metrics['avg_hold_hours']}h")

    lines.append("")
    lines.append(f"  Sessions: {len(runs)}")
    if runs:
        last = runs[-1]
        lines.append(
            f"  Last run: {last.get('start_timestamp', 'unknown')} ({last.get('run_id', '')[:12]})"
        )
    lines.append(f"  Logs: {artifacts_dir}")

    return "\n".join(lines)


def cmd_history(artifacts_dir: Path) -> str:
    """Build history output listing all sessions."""
    runs = _find_runs(artifacts_dir)
    if not runs:
        return "No sessions found."

    lines = [f"FactorAtlas History — {len(runs)} session(s)", ""]
    for run in runs:
        rid = run.get("run_id", "unknown")
        ts = run.get("start_timestamp", "unknown")
        mode = run.get("mode", "unknown")
        accepted = run.get("accepted_count", 0)
        rejected = run.get("rejected_count", 0)
        perf = run.get("performance_metrics", {})
        pnl = perf.get("total_pnl", "0")
        lines.append(
            f"  {rid[:12]}  {ts}  mode={mode}  "
            f"accepted={accepted} rejected={rejected}  pnl={pnl}"
        )

    return "\n".join(lines)


def cmd_explain(run_id: str, artifacts_dir: Path) -> str:
    """Build explanation output for a single run."""
    run_dir = artifacts_dir / run_id
    if not run_dir.exists():
        return f"Run '{run_id}' not found in {artifacts_dir}"

    manifest_path = run_dir / "manifest.json"
    paper_log_path = run_dir / "paper_log.jsonl"

    if not manifest_path.exists():
        return f"Run '{run_id}' has no manifest."

    manifest = json.loads(manifest_path.read_text())
    lines = [
        f"Session {manifest.get('run_id', run_id)[:12]} "
        f"({manifest.get('start_timestamp', 'unknown')})",
        f"  LLM: {manifest.get('llm_model', 'unknown')} ({manifest.get('llm_provider', 'unknown')})",
        f"  Mode: {manifest.get('mode', 'unknown')}",
        "",
    ]

    if paper_log_path.exists():
        for line in paper_log_path.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            inst = record.get("instrument", "unknown")
            status = record.get("status", "unknown")
            factor = record.get("factor_name", "")
            rationale = record.get("rationale", "")
            side = record.get("side", "")

            lines.append(f"  {inst}:")
            lines.append(f"    Status: {status}, Side: {side}, Factor: {factor}")
            if rationale:
                lines.append(f"    Rationale: {rationale[:120]}")

            gates = record.get("risk_gate_results", [])
            if gates:
                passed = sum(1 for g in gates if g.get("passed"))
                lines.append(f"    Gates: {passed}/{len(gates)} passed")
            lines.append("")

    summary = manifest.get("performance_metrics", {})
    lines.append(
        f"  Summary: {manifest.get('accepted_count', 0)} accepted, "
        f"{manifest.get('rejected_count', 0)} rejected, "
        f"PnL={summary.get('total_pnl', '0')}"
    )

    return "\n".join(lines)


__all__ = ["cmd_explain", "cmd_history", "cmd_status"]
```

- [ ] **Step 4: Wire commands into __main__.py**

Add subparsers for `status`, `history`, `explain` in `_build_parser()` and handle them in `main()`:

```python
# In _build_parser(), after the run_parser block:
    sub.add_parser("status", help="Show system state and metrics.")

    sub.add_parser("history", help="List all paper-trading sessions.")

    explain_parser = sub.add_parser("explain", help="Explain a session's decisions.")
    explain_parser.add_argument("run_id", help="Run ID to explain.")

# In main(), after the run command block:
    if args.command == "status":
        from factor_atlas.cli_commands import cmd_status
        print(cmd_status(Path("artifacts/paper-trading")))
        return 0

    if args.command == "history":
        from factor_atlas.cli_commands import cmd_history
        print(cmd_history(Path("artifacts/paper-trading")))
        return 0

    if args.command == "explain":
        from factor_atlas.cli_commands import cmd_explain
        print(cmd_explain(args.run_id, Path("artifacts/paper-trading")))
        return 0
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/cli_commands.py src/factor_atlas/__main__.py tests/test_cli_commands.py
git commit -m "feat(cli): add status, history, and explain commands"
```

---
