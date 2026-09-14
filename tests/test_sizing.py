"""Tests for ATR-based position sizing."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from factor_atlas.risk import RiskConfig
from factor_atlas.sizing import compute_atr, compute_position_size


def _make_ohlcv(n: int = 30, base_price: float = 200.0) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame."""
    import numpy as np

    rng = np.random.default_rng(42)
    closes = base_price + rng.standard_normal(n).cumsum()
    highs = closes + rng.uniform(1, 5, n)
    lows = closes - rng.uniform(1, 5, n)
    opens = closes + rng.uniform(-2, 2, n)
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": rng.uniform(1000, 5000, n),
        }
    )


def test_compute_atr_returns_positive() -> None:
    df = _make_ohlcv(30)
    atr = compute_atr(df, period=14)
    assert atr > 0


def test_compute_atr_period_longer_than_data() -> None:
    df = _make_ohlcv(5)
    atr = compute_atr(df, period=14)
    # Should still return a value (uses available data)
    assert atr > 0


def test_position_size_basic() -> None:
    """With known ATR, position size should be max_risk / (SL_mult * ATR)."""
    config = RiskConfig()
    qty = compute_position_size(
        price=Decimal(200),
        atr=5.0,  # ATR = $5
        risk_config=config,
    )
    # SL distance = 3.0 * 5 = $15. qty = 500 / 15 = 33.33 → 33
    assert qty == Decimal(33)


def test_position_size_capped_by_notional() -> None:
    """Position size must not exceed max_notional / price."""
    config = RiskConfig()
    qty = compute_position_size(
        price=Decimal(200),
        atr=0.5,  # Very low ATR → huge qty → should be capped
        risk_config=config,
    )
    # max_notional=10000, price=200 → max qty = 50
    assert qty <= Decimal(50)


def test_position_size_minimum_one() -> None:
    """Position size should be at least 1."""
    config = RiskConfig()
    qty = compute_position_size(
        price=Decimal(5000),
        atr=100.0,  # High ATR, high price → tiny qty
        risk_config=config,
    )
    assert qty >= Decimal(1)
