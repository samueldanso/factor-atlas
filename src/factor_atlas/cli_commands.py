"""CLI command implementations for status, history, and explain."""

from __future__ import annotations

import json
from pathlib import Path

from factor_atlas.broker import BrokerState, ClosedTrade, OpenPosition
from factor_atlas.metrics import compute_metrics


def _load_state(artifacts_dir: Path) -> BrokerState:
    state = BrokerState()
    if not artifacts_dir.exists():
        return state
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
    if not artifacts_dir.exists():
        return []
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
    if not artifacts_dir.exists():
        return f"Run '{run_id}' not found in {artifacts_dir}"

    run_dir = artifacts_dir / run_id
    if not run_dir.exists():
        return f"Run '{run_id}' not found in {artifacts_dir}"

    manifest_path = run_dir / "manifest.json"
    paper_log_path = run_dir / "paper_log.jsonl"

    if not manifest_path.exists():
        return f"Run '{run_id}' has no manifest."

    manifest = json.loads(manifest_path.read_text())
    session_header = (
        f"Session {manifest.get('run_id', run_id)[:12]} "
        f"({manifest.get('start_timestamp', 'unknown')})"
    )
    lines = [
        session_header,
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
