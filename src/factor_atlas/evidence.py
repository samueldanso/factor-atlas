"""Structured evidence logger for the FactorAtlas agent pipeline.

Produces 4 append-only JSONL files + 1 human-readable agent.log:
  events.jsonl    — observe + hypothesis + validation (judge: "Event")
  decisions.jsonl — LLM selection + rationale (judge: "Decision")
  risk.jsonl      — 14 gate verdicts (judge: "Risk control")
  trades.jsonl    — entry/exit orders + PnL (judge: "Execution")
  agent.log       — human-readable timeline (judge reads first)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class EvidenceLogger:
    """Append-only structured evidence logger.

    All log files live under ``logs_dir``. Each record carries ``run_id``
    and ``cycle_id`` so a judge can trace one trade across all 4 files.
    """

    def __init__(self, logs_dir: Path, run_id: str) -> None:
        self.logs_dir = logs_dir
        self.run_id = run_id
        logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def events_path(self) -> Path:
        return self.logs_dir / "events.jsonl"

    @property
    def decisions_path(self) -> Path:
        return self.logs_dir / "decisions.jsonl"

    @property
    def risk_path(self) -> Path:
        return self.logs_dir / "risk.jsonl"

    @property
    def trades_path(self) -> Path:
        return self.logs_dir / "trades.jsonl"

    @property
    def agent_log_path(self) -> Path:
        return self.logs_dir / "agent.log"

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        """Append one JSON record to a file."""
        with path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def _append_agent(self, line: str) -> None:
        """Append one human-readable line to agent.log."""
        ts = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        with self.agent_log_path.open("a") as f:
            f.write(f"[{ts}] {line}\n")

    def log_run_start(self, mode: str, interval: int, llm_model: str) -> None:
        """Log run start to agent.log."""
        self._append_agent(
            f"=== Run {self.run_id[:8]} started | Mode: {mode} "
            f"| Interval: {interval}s | LLM: {llm_model} ==="
        )

    def log_run_end(self, cycles: int, accepted: int, skipped: int) -> None:
        """Log run end to agent.log."""
        self._append_agent(
            f"=== Run {self.run_id[:8]} complete | "
            f"{cycles} cycles | {accepted} accepted, {skipped} skipped ==="
        )

    def log_event(
        self,
        cycle_id: str,
        instrument: str,
        price: str,
        source: str,
        hypothesis: dict[str, Any] | None,
        validation: dict[str, Any] | None,
    ) -> None:
        """Log an observe+hypothesis+validation event."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "instrument": instrument,
            "price": price,
            "source": source,
            "hypothesis": hypothesis,
            "validation": validation,
        }
        self._append_jsonl(self.events_path, record)

        # Human-readable
        if hypothesis:
            factor = hypothesis.get("factor_name", "?")
            direction = hypothesis.get("direction", "?")
            rationale = hypothesis.get("rationale", "")[:80]
            self._append_agent(
                f'🧠 {instrument} Hypothesis: {factor} → {direction} | "{rationale}"'
            )
        if validation:
            sharpe = validation.get("sharpe", 0)
            drawdown = validation.get("max_drawdown", 0)
            passed = validation.get("passed", False)
            obs = validation.get("observations", 0)
            status = "PASSED" if passed else "FAILED"
            self._append_agent(
                f"📊 Validation: Sharpe={sharpe:.2f}, MaxDD={drawdown:.2%}, "
                f"{obs} obs → {status}"
            )
        if not hypothesis:
            self._append_agent(
                f"🔍 {instrument} close=${price} — no hypothesis proposed"
            )

    def log_decision(
        self,
        cycle_id: str,
        instrument: str,
        selected_hypothesis: str | None,
        side: str | None,
        quantity: str | None,
        price: str | None,
        rationale: str,
    ) -> None:
        """Log LLM decision (selection or decline)."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "instrument": instrument,
            "selected_hypothesis": selected_hypothesis,
            "side": side,
            "quantity": quantity,
            "price": price,
            "rationale": rationale,
        }
        self._append_jsonl(self.decisions_path, record)

        if selected_hypothesis:
            self._append_agent(
                f"🤖 Decision: {side!s} {instrument} @ ${price} qty={quantity}"
                f' | "{rationale[:80]}"'
            )
        else:
            self._append_agent(f"⏭️ No trade for {instrument} — {rationale[:80]}")

    def log_risk(
        self,
        cycle_id: str,
        instrument: str,
        gates: list[dict[str, Any]],
        verdict: str,
    ) -> None:
        """Log risk gate verdicts."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "instrument": instrument,
            "gates": gates,
            "verdict": verdict,
        }
        self._append_jsonl(self.risk_path, record)

        passed_count = sum(1 for g in gates if g.get("passed"))
        total = len(gates)
        if verdict == "all_passed":
            self._append_agent(f"🛡️ Gates: {passed_count}/{total} passed")
        else:
            failed = [g for g in gates if not g.get("passed")]
            first_fail = failed[0] if failed else {}
            self._append_agent(
                f"🚫 Gates: BLOCKED by {first_fail.get('gate_name', '?')}"
                f" — {first_fail.get('reason', '?')}"
            )

    def log_trade(
        self,
        cycle_id: str,
        record_type: str,
        instrument: str,
        side: str,
        price: str,
        size: str,
        order_id: str | None,
        status: str,
        pnl: str | None = None,
        pnl_pct: float | None = None,
    ) -> None:
        """Log an entry or exit trade."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "record_type": record_type,
            "instrument": instrument,
            "side": side,
            "price": price,
            "size": size,
            "orderId": order_id,
            "orderStatus": status,
        }
        if pnl is not None:
            record["pnl"] = pnl
            record["pnl_pct"] = pnl_pct
        self._append_jsonl(self.trades_path, record)

        if record_type == "entry":
            emoji = "✅" if status == "filled" else "❌"
            self._append_agent(
                f"{emoji} Entry: {side} {instrument} @ ${price} size={size}"
                f" orderId={order_id or 'none'} status={status}"
            )
        elif record_type == "exit":
            self._append_agent(
                f"📤 Exit: {side} {instrument} @ ${price} size={size}"
                f" PnL={pnl} ({pnl_pct:.2%}) orderId={order_id or 'none'}"
            )

    def log_error(self, context: str, error: str) -> None:
        """Log an error to agent.log (no separate error file unless needed)."""
        self._append_agent(f"⚠️ ERROR [{context}]: {error}")


__all__ = ["EvidenceLogger"]
