"""Append-only JSONL audit logger for FactorAtlas cycles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.contracts import (
    AuditEvent,
    AuditStageType,
    PaperOrder,
)
from factor_atlas.orchestrator import CycleResult

_NS = NAMESPACE_DNS

_STAGE_ORDER: list[AuditStageType] = [
    "observe",
    "propose",
    "evaluate",
    "decide",
    "gate",
    "execute",
    "learn",
]


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def _observe_payload(cr: CycleResult) -> dict[str, Any]:
    return {
        "snapshot_id": cr.snapshot.snapshot_id,
        "instrument": cr.snapshot.instrument,
        "timestamp": cr.snapshot.timestamp.isoformat(),
        "source": cr.snapshot.source,
    }


def _propose_payload(cr: CycleResult) -> dict[str, Any]:
    return {
        "hypothesis_ids": [h.hypothesis_id for h in cr.hypotheses],
        "count": len(cr.hypotheses),
        "factor_names": [h.factor_name for h in cr.hypotheses],
    }


def _evaluate_payload(cr: CycleResult) -> dict[str, Any]:
    evals = []
    for hyp, val in cr.evaluations:
        evals.append(
            {
                "hypothesis_id": hyp.hypothesis_id,
                "passed": val.passed,
                "rejection_reasons": val.rejection_reasons,
                "sharpe": val.metrics.sharpe_ratio.value,
                "drawdown": val.metrics.max_drawdown.value,
            }
        )
    return {"evaluations": evals}


def _decide_payload(cr: CycleResult) -> dict[str, Any]:
    if cr.decision is not None:
        return {
            "decision_id": cr.decision.decision_id,
            "selected_hypothesis_id": cr.decision.hypothesis_id,
            "rationale": cr.decision.rationale,
            "status": cr.status,
        }
    return {
        "decision_id": None,
        "selected_hypothesis_id": None,
        "rationale": "no validated candidate",
        "status": cr.status,
    }


def _gate_payload(cr: CycleResult) -> dict[str, Any]:
    if cr.gate_results is not None:
        return {
            "gate_results": [
                {
                    "gate_name": g.gate_name,
                    "passed": g.passed,
                    "reason": g.reason,
                }
                for g in cr.gate_results
            ],
            "all_passed": all(g.passed for g in cr.gate_results),
        }
    return {"gate_results": [], "all_passed": False}


def _execute_payload(cr: CycleResult) -> dict[str, Any]:
    if cr.order is not None:
        o: PaperOrder = cr.order
        if o.status == "filled":
            return {
                "order_id": o.order_id,
                "status": o.status,
                "fill_price": str(o.fill_price),
                "fees": str(o.fees),
                "slippage": str(o.slippage),
                "pre_balance": str(o.pre_balance),
                "post_balance": str(o.post_balance),
            }
        return {
            "order_id": o.order_id,
            "status": o.status,
            "rejection_reason": o.rejection_reason or "unknown",
        }
    return {"order_id": None, "status": "skipped", "rejection_reason": "no order"}


def _learn_payload(cr: CycleResult) -> dict[str, Any]:
    side: str | None = None
    pnl_estimate: float = 0.0
    if cr.decision is not None:
        side = cr.decision.side
    if cr.order is not None and cr.order.status == "filled":
        pnl_estimate = float(cr.order.post_balance - cr.order.pre_balance)

    return {
        "cycle_summary": {
            "cycle_id": cr.cycle_id,
            "status": cr.status,
            "instrument": cr.snapshot.instrument,
            "side": side,
            "pnl_estimate": pnl_estimate,
        }
    }


_PAYLOAD_BUILDERS: dict[str, Any] = {
    "observe": _observe_payload,
    "propose": _propose_payload,
    "evaluate": _evaluate_payload,
    "decide": _decide_payload,
    "gate": _gate_payload,
    "execute": _execute_payload,
    "learn": _learn_payload,
}


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Append-only JSONL audit logger.

    If *output_path* is ``None``, events are buffered in memory only.
    """

    def __init__(self, output_path: Path | None = None) -> None:
        self._output_path = output_path
        self._events: list[AuditEvent] = []

    # -- public API ---------------------------------------------------------

    def log_cycle(self, cycle_result: CycleResult) -> list[AuditEvent]:
        """Convert a *CycleResult* into a chain of 7 ``AuditEvent``s."""
        chain: list[AuditEvent] = []
        parent_id: str | None = None

        for stage in _STAGE_ORDER:
            event_id = _det_uuid(f"evt-{cycle_result.cycle_id}-{stage}")
            payload = _PAYLOAD_BUILDERS[stage](cycle_result)

            event = AuditEvent(
                event_id=event_id,
                cycle_id=cycle_result.cycle_id,
                stage=stage,
                timestamp=_now(),
                parent_event_id=parent_id,
                payload=payload,
            )
            chain.append(event)
            parent_id = event_id

        self._events.extend(chain)

        if self._output_path is not None:
            self._append_to_file(chain)

        return chain

    def get_events(self) -> list[AuditEvent]:
        """Return all logged events."""
        return list(self._events)

    def flush(self) -> None:
        """Write buffered events to disk (JSONL). No-op if no output path."""
        if self._output_path is None:
            return
        with self._output_path.open("w") as f:
            for event in self._events:
                f.write(json.dumps(event.model_dump(mode="json")) + "\n")

    # -- internals ----------------------------------------------------------

    def _append_to_file(self, events: list[AuditEvent]) -> None:
        assert self._output_path is not None
        with self._output_path.open("a") as f:
            for event in events:
                f.write(json.dumps(event.model_dump(mode="json")) + "\n")


__all__ = [
    "AuditLogger",
]
