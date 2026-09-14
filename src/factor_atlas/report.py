"""Generate a self-contained HTML evidence report from a paper-trading run."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _fmt_pct(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val:.2%}"


def _fmt_dec(val: str | float | None, places: int = 2) -> str:
    if val is None:
        return "—"
    return f"{float(val):,.{places}f}"


def _status_class(status: str) -> str:
    s = status.lower()
    if s in ("filled", "closed", "accepted", "verified_filled"):
        return "success"
    if s in ("rejected", "failed", "verified_rejected", "verified_cancelled"):
        return "danger"
    if s in ("no_candidate", "no_hypothesis", "skipped"):
        return "muted"
    return "warn"


def _gate_badge(gate: dict[str, Any]) -> str:
    cls = "gate-pass" if gate["passed"] else "gate-fail"
    name = escape(gate["gate_name"])
    reason = escape(gate["reason"])
    return f'<span class="{cls}" title="{reason}">{name}</span>'


def _build_cycle_html(
    record: dict[str, Any],
    audit_by_cycle: dict[str, list[dict[str, Any]]],
) -> str:
    inst = escape(record.get("instrument", "—"))
    status = record.get("status", "unknown")
    cls = _status_class(status)
    side = record.get("side") or "—"
    price = _fmt_dec(record.get("price"))
    qty = _fmt_dec(record.get("quantity"), 0)
    factor = escape(record.get("factor_name") or "—")
    rationale = escape(record.get("rationale") or "—")
    sharpe = _fmt_dec(record.get("validation_sharpe"), 4)
    bgc_id = record.get("bgc_order_id") or "—"
    verification = record.get("verification_status") or "—"
    cycle_id = record.get("cycle_id", "")

    gates_html = ""
    gates = record.get("risk_gate_results", [])
    if gates:
        badges = " ".join(_gate_badge(g) for g in gates)
        passed = sum(1 for g in gates if g["passed"])
        total = len(gates)
        gates_html = f"""
        <div class="gates">
            <div class="gates-summary">{passed}/{total} gates passed</div>
            <div class="gates-list">{badges}</div>
        </div>"""

    # Build audit pipeline from audit log
    pipeline_html = ""
    events = audit_by_cycle.get(cycle_id, [])
    if events:
        stages = []
        for ev in sorted(events, key=lambda e: e.get("timestamp", "")):
            stage = ev.get("stage", "?")
            payload = ev.get("payload", {})
            detail = ""

            if stage == "observe":
                detail = f"Source: {escape(str(payload.get('source', '')))} | {escape(str(payload.get('instrument', '')))}"
            elif stage == "propose":
                names = payload.get("factor_names", [])
                detail = f"{payload.get('count', 0)} hypotheses: {', '.join(escape(n) for n in names)}"
            elif stage == "evaluate":
                evals = payload.get("evaluations", [])
                passed_count = sum(1 for e in evals if e.get("passed"))
                detail = f"{passed_count}/{len(evals)} passed validation"
                eval_details = []
                for ev_item in evals:
                    s = _fmt_dec(ev_item.get("sharpe"), 2)
                    dd = _fmt_dec(ev_item.get("drawdown"), 4)
                    p = "pass" if ev_item.get("passed") else "fail"
                    reasons = ev_item.get("rejection_reasons", [])
                    reason_text = f" — {escape(reasons[0])}" if reasons else ""
                    eval_details.append(
                        f'<span class="eval-{p}">[{p}] Sharpe={s} DD={dd}{reason_text}</span>'
                    )
                detail += "<br>" + "<br>".join(eval_details)
            elif stage == "decide":
                d_status = payload.get("status", "")
                detail = f"Status: {escape(d_status)}"
                if payload.get("rationale"):
                    detail += f"<br><em>{escape(str(payload['rationale']))}</em>"
            elif stage == "gate":
                all_passed = payload.get("all_passed", False)
                g_results = payload.get("gate_results", [])
                detail = f"{'All passed' if all_passed else 'BLOCKED'} ({len(g_results)} gates)"
            elif stage == "execute":
                detail = f"Status: {escape(str(payload.get('status', '')))} | Order: {escape(str(payload.get('order_id', '') or '—'))}"
            elif stage == "learn":
                summary = payload.get("cycle_summary", {})
                pnl = summary.get("pnl_estimate", 0)
                detail = f"Cycle: {escape(str(summary.get('status', '')))} | PnL estimate: {_fmt_dec(pnl, 4)}"

            stage_cls = (
                "stage-pass"
                if stage not in ("execute",) or payload.get("status") != "skipped"
                else "stage-skip"
            )
            if stage == "gate" and not payload.get("all_passed", True):
                stage_cls = "stage-fail"
            if stage == "decide" and payload.get("status") == "no_candidate":
                stage_cls = "stage-skip"

            stages.append(f"""
                <div class="pipeline-stage {stage_cls}">
                    <div class="stage-name">{escape(stage.upper())}</div>
                    <div class="stage-detail">{detail}</div>
                </div>""")

        pipeline_html = f'<div class="pipeline">{"".join(stages)}</div>'

    side_cls = "side-buy" if side == "buy" else "side-sell" if side == "sell" else ""

    return f"""
    <div class="cycle-card">
        <div class="cycle-header">
            <span class="instrument">{inst}</span>
            <span class="badge {cls}">{escape(status.upper())}</span>
            <span class="{side_cls}">{escape(side.upper()) if side != "—" else "—"}</span>
            <span class="factor-tag">{factor}</span>
        </div>
        <div class="cycle-body">
            <div class="cycle-meta">
                <div><strong>Price:</strong> ${price}</div>
                <div><strong>Qty:</strong> {qty}</div>
                <div><strong>Sharpe:</strong> {sharpe}</div>
                <div><strong>Bitget Order:</strong> <code>{escape(str(bgc_id))}</code></div>
                <div><strong>Verification:</strong> <span class="badge {_status_class(verification)}">{escape(str(verification))}</span></div>
            </div>
            {f'<div class="rationale"><strong>LLM Rationale:</strong> {rationale}</div>' if rationale != "—" else ""}
            {gates_html}
            {pipeline_html}
        </div>
    </div>"""


def _build_close_html(record: dict[str, Any]) -> str:
    inst = escape(record.get("instrument", "—"))
    entry = _fmt_dec(record.get("entry_price"))
    exit_p = _fmt_dec(record.get("exit_price"))
    pnl = record.get("pnl", "0")
    pnl_pct = record.get("pnl_pct", 0)
    won = record.get("won", False)
    hold = _fmt_dec(record.get("hold_duration_hours"), 1)
    factor = escape(record.get("factor_name") or "—")
    reason = escape(record.get("rationale") or "—")
    bgc_id = record.get("bgc_order_id") or "—"
    cls = "success" if won else "danger"
    side = record.get("side") or "—"

    return f"""
    <div class="trade-card {cls}">
        <div class="trade-header">
            <span class="instrument">{inst}</span>
            <span class="badge {cls}">{"WIN" if won else "LOSS"}</span>
            <span>{escape(side.upper())}</span>
            <span class="factor-tag">{factor}</span>
        </div>
        <div class="trade-body">
            <div class="trade-meta">
                <div><strong>Entry:</strong> ${entry}</div>
                <div><strong>Exit:</strong> ${exit_p}</div>
                <div><strong>PnL:</strong> <span class="{cls}">${_fmt_dec(pnl)}</span> ({_fmt_pct(pnl_pct)})</div>
                <div><strong>Hold:</strong> {hold}h</div>
                <div><strong>Close Order:</strong> <code>{escape(str(bgc_id))}</code></div>
            </div>
            <div class="rationale">{reason}</div>
        </div>
    </div>"""


def _build_equity_svg(equity_curve: list[list[Any]]) -> str:
    if not equity_curve or len(equity_curve) < 2:
        return ""

    values = [float(pt[1]) for pt in equity_curve]
    n = len(values)
    min_v = min(values)
    max_v = max(values)
    spread = max_v - min_v if max_v != min_v else 1.0

    width = 400
    height = 120
    padding = 20

    points = []
    for i, v in enumerate(values):
        x = padding + (i / max(n - 1, 1)) * (width - 2 * padding)
        y = padding + (1 - (v - min_v) / spread) * (height - 2 * padding)
        points.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(points)
    zero_y = padding + (1 - (0 - min_v) / spread) * (height - 2 * padding)

    return f"""
    <div class="equity-chart">
        <h3>Equity Curve (Cumulative PnL)</h3>
        <svg viewBox="0 0 {width} {height}" class="equity-svg">
            <line x1="{padding}" y1="{zero_y:.1f}" x2="{width - padding}" y2="{zero_y:.1f}"
                  stroke="#666" stroke-dasharray="4" stroke-width="0.5"/>
            <polyline points="{polyline}" fill="none" stroke="#4f8cff" stroke-width="2"/>
            {" ".join(f'<circle cx="{points[i].split(",")[0]}" cy="{points[i].split(",")[1]}" r="3" fill="{("#22c55e" if values[i] >= 0 else "#ef4444")}"/>' for i in range(n))}
            <text x="{padding}" y="{height - 2}" font-size="10" fill="#888">Start</text>
            <text x="{width - padding - 20}" y="{height - 2}" font-size="10" fill="#888">End</text>
            <text x="2" y="{padding - 4}" font-size="9" fill="#888">${_fmt_dec(max_v)}</text>
            <text x="2" y="{height - padding + 12}" font-size="9" fill="#888">${_fmt_dec(min_v)}</text>
        </svg>
    </div>"""


CSS = """
:root {
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #4f8cff;
    --green: #22c55e; --red: #ef4444; --yellow: #f59e0b;
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: var(--font); background: var(--bg); color: var(--text); padding: 24px; max-width: 1000px; margin: 0 auto; line-height: 1.5; }
h1 { font-size: 1.5rem; margin-bottom: 4px; }
h2 { font-size: 1.2rem; margin: 32px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
h3 { font-size: 1rem; margin-bottom: 8px; color: var(--muted); }
.subtitle { color: var(--muted); font-size: 0.9rem; margin-bottom: 16px; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }
.stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px; text-align: center; }
.stat-value { font-size: 1.4rem; font-weight: 700; color: var(--accent); }
.stat-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
.badge.success { background: rgba(34,197,94,0.15); color: var(--green); }
.badge.danger { background: rgba(239,68,68,0.15); color: var(--red); }
.badge.warn { background: rgba(245,158,11,0.15); color: var(--yellow); }
.badge.muted { background: rgba(139,148,158,0.15); color: var(--muted); }
.cycle-card, .trade-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
.cycle-header, .trade-header { display: flex; align-items: center; gap: 10px; padding: 12px 16px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.cycle-body, .trade-body { padding: 16px; }
.instrument { font-weight: 700; font-size: 1rem; }
.factor-tag { background: rgba(79,140,255,0.15); color: var(--accent); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
.side-buy { color: var(--green); font-weight: 600; }
.side-sell { color: var(--red); font-weight: 600; }
.cycle-meta, .trade-meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 6px; font-size: 0.85rem; margin-bottom: 12px; }
.rationale { background: rgba(79,140,255,0.05); border-left: 3px solid var(--accent); padding: 10px 14px; margin-top: 10px; font-size: 0.85rem; border-radius: 0 6px 6px 0; }
.gates { margin-top: 12px; }
.gates-summary { font-size: 0.8rem; color: var(--muted); margin-bottom: 6px; }
.gates-list { display: flex; flex-wrap: wrap; gap: 4px; }
.gate-pass, .gate-fail { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.7rem; font-weight: 500; cursor: help; }
.gate-pass { background: rgba(34,197,94,0.1); color: var(--green); }
.gate-fail { background: rgba(239,68,68,0.15); color: var(--red); font-weight: 700; }
.pipeline { display: flex; flex-direction: column; gap: 2px; margin-top: 12px; }
.pipeline-stage { display: flex; gap: 12px; padding: 8px 12px; border-radius: 4px; font-size: 0.8rem; border-left: 3px solid var(--border); }
.pipeline-stage.stage-pass { border-left-color: var(--green); }
.pipeline-stage.stage-fail { border-left-color: var(--red); }
.pipeline-stage.stage-skip { border-left-color: var(--muted); opacity: 0.7; }
.stage-name { min-width: 70px; font-weight: 700; color: var(--accent); font-size: 0.75rem; }
.stage-detail { color: var(--muted); }
.stage-detail em { color: var(--text); font-style: normal; }
.eval-pass { color: var(--green); }
.eval-fail { color: var(--red); }
.trade-card.success { border-left: 3px solid var(--green); }
.trade-card.danger { border-left: 3px solid var(--red); }
code { background: rgba(139,148,158,0.15); padding: 1px 5px; border-radius: 3px; font-size: 0.8rem; word-break: break-all; }
.equity-chart { margin: 16px 0; }
.equity-svg { width: 100%; max-width: 500px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; }
.footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.75rem; text-align: center; }
.agent-flow { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 24px; }
.flow-steps { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; justify-content: center; }
.flow-step { background: rgba(79,140,255,0.1); border: 1px solid rgba(79,140,255,0.3); padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; }
.flow-arrow { color: var(--muted); font-size: 1.2rem; }
@media (max-width: 600px) {
    body { padding: 12px; }
    .summary-grid { grid-template-columns: repeat(2, 1fr); }
    .cycle-meta, .trade-meta { grid-template-columns: 1fr; }
}
"""


def generate_report(run_dir: Path) -> str:
    """Generate an HTML evidence report from a paper-trading run directory."""
    manifest_path = run_dir / "manifest.json"
    paper_path = run_dir / "paper_log.jsonl"
    audit_path = run_dir / "audit_log.jsonl"

    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())

    paper_records = _load_jsonl(paper_path)
    audit_records = _load_jsonl(audit_path)

    # Group audit events by cycle_id
    audit_by_cycle: dict[str, list[dict[str, Any]]] = {}
    for ev in audit_records:
        cid = ev.get("cycle_id", "")
        if cid:
            audit_by_cycle.setdefault(cid, []).append(ev)

    # Separate open/close records
    opens = [r for r in paper_records if r.get("record_type") == "open"]
    closes = [r for r in paper_records if r.get("record_type") == "close"]

    # Manifest data
    run_id = manifest.get("run_id", "unknown")
    start = manifest.get("start_timestamp", "—")
    end = manifest.get("end_timestamp", "—")
    mode = manifest.get("mode", "—")
    llm_provider = manifest.get("llm_provider", "—")
    llm_model = manifest.get("llm_model", "—")
    cycles = manifest.get("cycles_completed", len(opens))
    accepted = manifest.get("accepted_count", 0)
    rejected = manifest.get("rejected_count", 0)
    commit = manifest.get("code_commit", "—")
    config_hash = manifest.get("config_hash", "—")

    perf = manifest.get("performance_metrics", {})
    total_trades = perf.get("total_trades", 0)
    win_rate = perf.get("win_rate", 0)
    sharpe = perf.get("sharpe_ratio", 0)
    sortino = perf.get("sortino_ratio", 0)
    max_dd = perf.get("max_drawdown", 0)
    total_pnl = perf.get("total_pnl", "0")
    profit_factor = perf.get("profit_factor", 0)
    avg_hold = perf.get("avg_hold_hours", 0)
    equity_curve = perf.get("equity_curve", [])

    exec_instruments = manifest.get("execution_instruments", [])

    # Build sections
    cycles_html = "".join(_build_cycle_html(r, audit_by_cycle) for r in opens)
    closes_html = "".join(_build_close_html(r) for r in closes)
    equity_html = _build_equity_svg(equity_curve)

    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FactorAtlas — Evidence Report</title>
<style>{CSS}</style>
</head>
<body>
<h1>FactorAtlas — Evidence Report</h1>
<div class="subtitle">
    Autonomous Factor Discovery Agent for Bitget AI Genesis S2<br>
    Run: <code>{escape(run_id)}</code> | Generated: {now}
</div>

<div class="agent-flow">
    <h3>Agent Flow (each cycle)</h3>
    <div class="flow-steps">
        <span class="flow-step">Market Data</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">LLM Hypotheses</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">Factor Validation</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">LLM Decision</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">14 Risk Gates</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">Demo Order</span>
        <span class="flow-arrow">→</span>
        <span class="flow-step">Verify Fill</span>
    </div>
</div>

<h2>Run Summary</h2>
<div class="summary-grid">
    <div class="stat-card"><div class="stat-value">{cycles}</div><div class="stat-label">Cycles</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--green)">{accepted}</div><div class="stat-label">Accepted</div></div>
    <div class="stat-card"><div class="stat-value" style="color:var(--red)">{rejected}</div><div class="stat-label">Rejected</div></div>
    <div class="stat-card"><div class="stat-value">{total_trades}</div><div class="stat-label">Closed Trades</div></div>
    <div class="stat-card"><div class="stat-value">{_fmt_pct(win_rate)}</div><div class="stat-label">Win Rate</div></div>
    <div class="stat-card"><div class="stat-value">{_fmt_dec(sharpe, 2)}</div><div class="stat-label">Sharpe</div></div>
    <div class="stat-card"><div class="stat-value">{_fmt_dec(sortino, 2)}</div><div class="stat-label">Sortino</div></div>
    <div class="stat-card"><div class="stat-value">${_fmt_dec(max_dd, 2)}</div><div class="stat-label">Max Drawdown</div></div>
    <div class="stat-card"><div class="stat-value">${_fmt_dec(total_pnl, 2)}</div><div class="stat-label">Total PnL</div></div>
    <div class="stat-card"><div class="stat-value">{_fmt_dec(profit_factor, 2)}</div><div class="stat-label">Profit Factor</div></div>
    <div class="stat-card"><div class="stat-value">{_fmt_dec(avg_hold, 1)}h</div><div class="stat-label">Avg Hold</div></div>
</div>

<div class="cycle-meta" style="font-size:0.85rem; margin-bottom:24px;">
    <div><strong>Mode:</strong> {escape(mode)} | <strong>LLM:</strong> {escape(llm_model)} ({escape(llm_provider)})</div>
    <div><strong>Time:</strong> {escape(start)} → {escape(end)}</div>
    <div><strong>Instruments:</strong> {", ".join(escape(i) for i in exec_instruments)}</div>
    <div><strong>Commit:</strong> <code>{escape(commit)}</code> | <strong>Config:</strong> <code>{escape(config_hash)}</code></div>
</div>

{equity_html}

{"<h2>Closed Trades</h2>" + closes_html if closes else ""}

<h2>Cycle Details</h2>
{cycles_html if cycles_html else '<p style="color:var(--muted)">No cycles recorded.</p>'}

<div class="footer">
    FactorAtlas v{escape(manifest.get("software_version", "0.1.0"))} — Bitget AI Genesis Season 2, Track 2 Agentic Trading<br>
    This report was generated from machine-produced audit logs. All orders executed on Bitget Demo (paper trading).
</div>
</body>
</html>"""


def generate_report_file(run_dir: Path, output: Path | None = None) -> Path:
    """Generate and write the HTML report. Returns the output path."""
    html = generate_report(run_dir)
    out = output or (run_dir / "evidence_report.html")
    out.write_text(html)
    return out


__all__ = ["generate_report", "generate_report_file"]
