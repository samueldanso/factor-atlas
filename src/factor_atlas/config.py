"""Constants and configuration for FactorAtlas."""

from __future__ import annotations

from typing import Literal

INSTRUMENTS: frozenset[str] = frozenset(
    {"AAPLUSDT", "NVDAUSDT", "TSLAUSDT", "METAUSDT"}
)

CATEGORY: Literal["USDT-FUTURES"] = "USDT-FUTURES"

FACTOR_VOCABULARY: frozenset[str] = frozenset(
    {
        "momentum",
        "mean_reversion",
        "volatility_breakout",
        "volume_spike",
        "ema_crossover",
    }
)

METRIC_LABELS: frozenset[str] = frozenset({"observed", "estimated", "targeted"})

AUDIT_STAGES: frozenset[str] = frozenset(
    {"observe", "propose", "evaluate", "decide", "gate", "execute", "learn"}
)

# Validation thresholds
MIN_OBSERVATIONS: int = 20
MAX_LOOKBACK: int = 500
MIN_LOOKBACK: int = 1
MAX_QUANTITY: str = "1000000"  # Decimal string for comparison
