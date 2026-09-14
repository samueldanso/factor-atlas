"""ATR-based position sizing for FactorAtlas.

Sizing formula:
  sl_distance = SL_ATR_MULT × ATR
  quantity = MAX_RISK_PER_TRADE / sl_distance
  quantity = min(quantity, max_notional / price)
  quantity = max(quantity, 1)
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

import pandas as pd

from factor_atlas.config import MAX_RISK_PER_TRADE, SL_ATR_MULT
from factor_atlas.risk import RiskConfig


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Compute Average True Range from OHLCV data.

    Uses the standard Wilder method: TR = max(H-L, |H-Cprev|, |L-Cprev|),
    ATR = EWM of TR over ``period`` bars.

    Returns the last ATR value. If the DataFrame has fewer rows than
    ``period``, uses all available data.
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    return float(atr.iloc[-1])


def compute_position_size(
    price: Decimal,
    atr: float,
    risk_config: RiskConfig,
) -> Decimal:
    """Compute position size based on ATR and risk budget.

    Returns integer quantity (Bitget stock perps require whole numbers).
    Minimum 1, capped by max_notional / price.
    """
    sl_distance = Decimal(str(SL_ATR_MULT * atr))
    if sl_distance <= 0:
        return Decimal(1)

    max_risk = Decimal(MAX_RISK_PER_TRADE)
    raw_qty = max_risk / sl_distance

    # Cap by max_notional
    max_qty_by_notional = risk_config.max_notional / price
    qty = min(raw_qty, max_qty_by_notional)

    # Floor to integer, minimum 1
    qty = qty.to_integral_value(rounding=ROUND_DOWN)
    return max(qty, Decimal(1))


__all__ = ["compute_atr", "compute_position_size"]
