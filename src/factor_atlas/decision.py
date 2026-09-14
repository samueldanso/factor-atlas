"""DecisionProvider protocol and fixture implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.contracts import (
    FactorHypothesis,
    MarketSnapshot,
    TradeDecision,
    ValidationResult,
)

_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DecisionProvider(Protocol):
    """Select one validated candidate and return a TradeDecision, or None."""

    def decide(
        self,
        snapshot: MarketSnapshot,
        candidates: list[tuple[FactorHypothesis, ValidationResult]],
        cycle_id: str,
    ) -> TradeDecision | None:
        """Select one validated candidate and return a TradeDecision, or None if no trade."""
        ...


# ---------------------------------------------------------------------------
# FixtureDecisionProvider
# ---------------------------------------------------------------------------


class FixtureDecisionProvider:
    """Deterministic decision provider that picks the highest-Sharpe candidate.

    Credential-free: uses only the validation metrics already computed.
    """

    def decide(
        self,
        snapshot: MarketSnapshot,
        candidates: list[tuple[FactorHypothesis, ValidationResult]],
        cycle_id: str,
    ) -> TradeDecision | None:
        """Pick the candidate with the highest Sharpe ratio.

        Returns None if candidates is empty.
        """
        if not candidates:
            return None

        # Sort by Sharpe descending, pick best
        best_hyp, best_val = max(
            candidates,
            key=lambda pair: pair[1].metrics.sharpe_ratio.value,
        )

        decision_id = _det_uuid(f"decision-{cycle_id}-{best_hyp.hypothesis_id}")

        # Map hypothesis direction to order side
        side = "buy" if best_hyp.direction == "long" else "sell"

        return TradeDecision(
            decision_id=decision_id,
            cycle_id=cycle_id,
            hypothesis_id=best_hyp.hypothesis_id,
            instrument=snapshot.instrument,
            side=side,
            quantity=Decimal(1),
            price=snapshot.close,
            rationale=(
                f"Best Sharpe={best_val.metrics.sharpe_ratio.value:.4f} "
                f"from {best_hyp.factor_name} on {snapshot.instrument}"
            ),
            timestamp=datetime.now(tz=UTC),
        )


__all__ = [
    "DecisionProvider",
    "FixtureDecisionProvider",
]
