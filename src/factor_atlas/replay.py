"""Deterministic replay verification for FactorAtlas audit trails."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from factor_atlas.audit import AuditLogger
from factor_atlas.contracts import AuditEvent
from factor_atlas.decision import DecisionProvider
from factor_atlas.orchestrator import run_cycles
from factor_atlas.proposer import Proposer
from factor_atlas.risk import RiskConfig

# ---------------------------------------------------------------------------
# ReplayResult
# ---------------------------------------------------------------------------


@dataclass
class ReplayResult:
    """Outcome of a deterministic replay comparison."""

    matches: bool
    original_count: int
    replay_count: int
    first_mismatch_index: int | None
    mismatch_detail: str | None


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _event_signature(event: AuditEvent) -> dict[str, object]:
    """Return the deterministic subset of an event used for comparison.

    Ignores ``event_id`` (UUID) and ``timestamp`` (wall-clock).
    ``parent_event_id`` is also excluded because it derives from ``event_id``.
    """
    return {
        "cycle_id": event.cycle_id,
        "stage": event.stage,
        "payload": event.payload,
    }


# ---------------------------------------------------------------------------
# verify_replay
# ---------------------------------------------------------------------------


def verify_replay(
    snapshots: list[object],
    ohlcv_data: dict[str, pd.DataFrame],
    proposer: Proposer,
    decision_provider: DecisionProvider,
    config: RiskConfig,
    original_events: list[AuditEvent],
) -> ReplayResult:
    """Re-run the same inputs and compare audit output for determinism.

    Same snapshots + same OHLCV + same config → same audit events
    (ignoring ``event_id`` UUIDs and ``timestamp`` values).
    """
    from factor_atlas.broker import BrokerState
    from factor_atlas.contracts import MarketSnapshot

    typed_snapshots: list[MarketSnapshot] = [
        s for s in snapshots if isinstance(s, MarketSnapshot)
    ]

    # Re-run cycles
    broker = BrokerState()
    results = run_cycles(
        typed_snapshots,
        ohlcv_data,
        proposer,
        decision_provider,
        broker_state=broker,
        risk_config=config,
    )

    # Re-log
    logger = AuditLogger()
    replay_events: list[AuditEvent] = []
    for cr in results:
        replay_events.extend(logger.log_cycle(cr))

    original_count = len(original_events)
    replay_count = len(replay_events)

    if original_count != replay_count:
        return ReplayResult(
            matches=False,
            original_count=original_count,
            replay_count=replay_count,
            first_mismatch_index=min(original_count, replay_count),
            mismatch_detail=(
                f"event count differs: original={original_count}, replay={replay_count}"
            ),
        )

    for i, (orig, replay) in enumerate(zip(original_events, replay_events)):
        orig_sig = _event_signature(orig)
        replay_sig = _event_signature(replay)
        if orig_sig != replay_sig:
            return ReplayResult(
                matches=False,
                original_count=original_count,
                replay_count=replay_count,
                first_mismatch_index=i,
                mismatch_detail=(
                    f"mismatch at index {i}: "
                    f"stage={orig.stage} vs {replay.stage}, "
                    f"cycle_id={orig.cycle_id} vs {replay.cycle_id}"
                ),
            )

    return ReplayResult(
        matches=True,
        original_count=original_count,
        replay_count=replay_count,
        first_mismatch_index=None,
        mismatch_detail=None,
    )


__all__ = [
    "ReplayResult",
    "verify_replay",
]
