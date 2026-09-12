"""Proposer protocol and fixture implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.config import FACTOR_VOCABULARY
from factor_atlas.contracts import FactorHypothesis, MarketSnapshot
from factor_atlas.factors import PARAM_SCHEMAS

_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Proposer(Protocol):
    """Generate bounded factor hypotheses for a market snapshot."""

    def propose(self, snapshot: MarketSnapshot, budget: int) -> list[FactorHypothesis]:
        """Generate up to `budget` hypotheses for a given snapshot."""
        ...


# ---------------------------------------------------------------------------
# Default parameter sets for fixture hypotheses
# ---------------------------------------------------------------------------

_FIXTURE_DEFAULTS: dict[str, dict[str, float | int | str]] = {
    "momentum": {"lookback": 10, "threshold": 0.02},
    "mean_reversion": {"lookback": 10, "entry_z": 1.5},
    "volatility_breakout": {"lookback": 10, "num_std": 2.0},
    "volume_spike": {"lookback": 10, "multiplier": 2.0},
    "ema_crossover": {"fast_period": 10, "slow_period": 30},
}

_FIXTURE_ENTRY_RULES: dict[str, str] = {
    "momentum": "ROC > threshold",
    "mean_reversion": "z-score < -entry_z",
    "volatility_breakout": "close > upper Bollinger band",
    "volume_spike": "volume > avg * multiplier and bullish candle",
    "ema_crossover": "fast EMA crosses above slow EMA",
}

_FIXTURE_EXIT_RULES: dict[str, str] = {
    "momentum": "ROC reverses below -threshold or 5% trailing stop",
    "mean_reversion": "z-score returns to 0 or 3% stop loss",
    "volatility_breakout": "close returns inside bands or 3% stop loss",
    "volume_spike": "volume returns to normal or 3% stop loss",
    "ema_crossover": "fast EMA crosses below slow EMA or 5% trailing stop",
}


# ---------------------------------------------------------------------------
# FixtureProposer
# ---------------------------------------------------------------------------


class FixtureProposer:
    """Deterministic proposer that generates hypotheses from the factor registry.

    Credential-free, uses only registered factors with valid parameters.
    """

    def propose(self, snapshot: MarketSnapshot, budget: int) -> list[FactorHypothesis]:
        """Generate up to `budget` hypotheses for the snapshot's instrument."""
        factors = sorted(FACTOR_VOCABULARY)
        now = datetime.now(tz=UTC)
        hypotheses: list[FactorHypothesis] = []

        for factor_name in factors[:budget]:
            schema = PARAM_SCHEMAS[factor_name]
            # Use fixture defaults; fall back to midpoint of schema range
            params: dict[str, float | int | str] = {}
            if factor_name in _FIXTURE_DEFAULTS:
                params = dict(_FIXTURE_DEFAULTS[factor_name])
            else:
                for pname, (lo, hi) in schema.items():
                    params[pname] = (lo + hi) / 2

            # Validate params are within bounds
            for pname, (lo, hi) in schema.items():
                val = params.get(pname, (lo + hi) / 2)
                if isinstance(val, (int, float)):
                    params[pname] = max(lo, min(hi, val))

            hyp_id = _det_uuid(f"fixture-{factor_name}-{snapshot.snapshot_id}")

            hypotheses.append(
                FactorHypothesis(
                    hypothesis_id=hyp_id,
                    factor_name=factor_name,
                    parameters=params,
                    lookback=30,
                    instruments=[snapshot.instrument],
                    direction="long",
                    entry_rule=_FIXTURE_ENTRY_RULES.get(factor_name, "signal > 0"),
                    exit_rule=_FIXTURE_EXIT_RULES.get(
                        factor_name, "signal reverses or stop loss"
                    ),
                    rationale=(
                        f"Fixture hypothesis for {factor_name} on {snapshot.instrument}"
                    ),
                    created_at=now,
                )
            )

        return hypotheses


__all__ = [
    "FixtureProposer",
    "Proposer",
]
