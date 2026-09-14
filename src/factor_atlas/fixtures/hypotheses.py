"""Deterministic fixture hypotheses."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.contracts import FactorHypothesis

_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


# A valid hypothesis — strong momentum signal on AAPL
VALID_HYPOTHESIS = FactorHypothesis(
    hypothesis_id=_det_uuid("valid-momentum-hypothesis"),
    factor_name="momentum",
    parameters={"window": 14, "threshold": 0.02},
    lookback=30,
    instruments=["AAPLUSDT"],
    direction="long",
    entry_rule="Close crosses above 14-bar EMA with momentum > 0.02",
    exit_rule="Close crosses below 14-bar EMA or 5% trailing stop",
    rationale="Strong upward price drift observed in AAPL fixture data",
    created_at=datetime(2026, 9, 1, 11, 0, 0, tzinfo=UTC),
)

# An invalid/rejected hypothesis — poor mean-reversion on narrow range
REJECTED_HYPOTHESIS = FactorHypothesis(
    hypothesis_id=_det_uuid("rejected-mean-rev-hypothesis"),
    factor_name="mean_reversion",
    parameters={"window": 20, "z_threshold": 1.5},
    lookback=60,
    instruments=["NVDAUSDT"],
    direction="short",
    entry_rule="Price exceeds 1.5 stddev above 20-bar mean",
    exit_rule="Price returns to 20-bar mean",
    rationale="Narrow range and low volume suggest insufficient mean-reversion potential",
    created_at=datetime(2026, 9, 1, 11, 30, 0, tzinfo=UTC),
)

__all__ = [
    "REJECTED_HYPOTHESIS",
    "VALID_HYPOTHESIS",
]
