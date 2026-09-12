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

# Risk-gate thresholds
MAX_DATA_AGE_HOURS: int = 24
MAX_NOTIONAL: str = "10000"  # Decimal string
MAX_CONCURRENT_POSITIONS: int = 3
MAX_EXPOSURE: str = "50000"  # Decimal string
COOLDOWN_SECONDS: int = 300
DAILY_LOSS_LIMIT: str = "2000"  # Decimal string
MAX_CONCENTRATION_PER_INSTRUMENT: int = 2

# Paper-broker defaults
DEFAULT_FEE_RATE: str = "0.001"
DEFAULT_SLIPPAGE_BPS: str = "0.0005"
INITIAL_BALANCE: str = "100000"  # 100k USDT
