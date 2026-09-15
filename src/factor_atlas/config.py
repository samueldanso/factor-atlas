"""Constants and configuration for FactorAtlas."""

from __future__ import annotations

from typing import Literal

# rToken SPOT instruments — used for market data and factor research.
# These are the Reality-tokenized US stocks that trade 7×24 on Bitget.
RESEARCH_INSTRUMENTS: frozenset[str] = frozenset(
    {"RAAPLUSDT", "RNVDAUSDT", "RTSLAUSDT", "RMETAUSDT"}
)

# Stock perp instruments — used for Bitget Demo order execution only.
# rToken SPOT demo trading is unavailable (HTTP 404 on place-reality-order).
EXECUTION_INSTRUMENTS: frozenset[str] = frozenset(
    {"AAPLUSDT", "NVDAUSDT", "TSLAUSDT", "METAUSDT"}
)

# All valid instruments (research + execution)
INSTRUMENTS: frozenset[str] = RESEARCH_INSTRUMENTS | EXECUTION_INSTRUMENTS

# Mapping: rToken research instrument → stock perp execution instrument
RESEARCH_TO_EXECUTION: dict[str, str] = {
    "RAAPLUSDT": "AAPLUSDT",
    "RNVDAUSDT": "NVDAUSDT",
    "RTSLAUSDT": "TSLAUSDT",
    "RMETAUSDT": "METAUSDT",
}

# Category for rToken market data (SPOT candles endpoint)
RESEARCH_CATEGORY: Literal["SPOT"] = "SPOT"

# Category for Bitget Demo order execution (USDT-FUTURES)
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

# ATR-based sizing and exit thresholds
ATR_PERIOD: int = 14
MAX_RISK_PER_TRADE: str = "500"  # Risk $500 per trade on $100K account = 0.5%
SL_ATR_MULT: float = 3.0  # Stop-loss = 3 × ATR
TP_ATR_MULT: float = 6.0  # Take-profit = 6 × ATR (2:1 R:R)
MAX_MARGIN_PCT: float = 0.25  # Hard cap: 25% of balance per trade

# Paper-broker defaults
DEFAULT_FEE_RATE: str = "0.001"
DEFAULT_SLIPPAGE_BPS: str = "0.0005"
INITIAL_BALANCE: str = "100000"  # 100k USDT
