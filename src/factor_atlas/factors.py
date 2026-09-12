"""Closed factor registry and deterministic factor calculation functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from factor_atlas.config import FACTOR_VOCABULARY

# ---------------------------------------------------------------------------
# Type alias for factor functions
# ---------------------------------------------------------------------------

FactorFn = Callable[[pd.DataFrame, dict[str, Any]], "pd.Series[int]"]


# ---------------------------------------------------------------------------
# Parameter schemas: {param_name: (min, max)}
# ---------------------------------------------------------------------------

PARAM_SCHEMAS: dict[str, dict[str, tuple[float, float]]] = {
    "momentum": {
        "lookback": (5, 200),
        "threshold": (0.0, 0.5),
    },
    "mean_reversion": {
        "lookback": (10, 200),
        "entry_z": (1.0, 3.0),
    },
    "volatility_breakout": {
        "lookback": (10, 100),
        "num_std": (1.0, 3.0),
    },
    "volume_spike": {
        "lookback": (5, 100),
        "multiplier": (1.5, 5.0),
    },
    "ema_crossover": {
        "fast_period": (5, 50),
        "slow_period": (20, 200),
    },
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_params(factor_name: str, params: dict[str, Any]) -> None:
    """Validate parameter values against the schema for a factor."""
    schema = PARAM_SCHEMAS[factor_name]
    for param_name, (lo, hi) in schema.items():
        if param_name not in params:
            msg = f"Missing parameter '{param_name}' for factor '{factor_name}'"
            raise ValueError(msg)
        val = params[param_name]
        if not isinstance(val, (int, float)):
            msg = f"Parameter '{param_name}' must be numeric, got {type(val).__name__}"
            raise TypeError(msg)
        if val < lo or val > hi:
            msg = (
                f"Parameter '{param_name}' for factor '{factor_name}' "
                f"must be in [{lo}, {hi}], got {val}"
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Factor implementations
# ---------------------------------------------------------------------------


def compute_momentum(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series[int]:
    """Price rate of change over lookback periods.

    Signal: +1 if ROC > threshold, -1 if ROC < -threshold, else 0.
    """
    _validate_params("momentum", params)
    lookback: int = int(params["lookback"])
    threshold: float = float(params["threshold"])

    close = df["close"].astype(float)
    roc = close.pct_change(periods=lookback)

    signal: pd.Series[int] = pd.Series(np.zeros(len(df)), index=df.index, dtype=int)
    signal[roc > threshold] = 1
    signal[roc < -threshold] = -1
    signal[roc.isna()] = 0
    return signal


def compute_mean_reversion(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series[int]:
    """Z-score of price relative to rolling mean.

    Signal: +1 if z < -entry_z (buy the dip), -1 if z > entry_z (sell the rip), else 0.
    """
    _validate_params("mean_reversion", params)
    lookback: int = int(params["lookback"])
    entry_z: float = float(params["entry_z"])

    close = df["close"].astype(float)
    rolling_mean = close.rolling(window=lookback).mean()
    rolling_std = close.rolling(window=lookback).std()

    z_score = (close - rolling_mean) / rolling_std

    signal: pd.Series[int] = pd.Series(np.zeros(len(df)), index=df.index, dtype=int)
    signal[z_score < -entry_z] = 1  # buy the dip
    signal[z_score > entry_z] = -1  # sell the rip
    signal[z_score.isna()] = 0
    return signal


def compute_volatility_breakout(
    df: pd.DataFrame, params: dict[str, Any]
) -> pd.Series[int]:
    """Bollinger Band breakout.

    Signal: +1 if close > upper band, -1 if close < lower band, else 0.
    """
    _validate_params("volatility_breakout", params)
    lookback: int = int(params["lookback"])
    num_std: float = float(params["num_std"])

    close = df["close"].astype(float)
    rolling_mean = close.rolling(window=lookback).mean()
    rolling_std = close.rolling(window=lookback).std()

    upper = rolling_mean + num_std * rolling_std
    lower = rolling_mean - num_std * rolling_std

    signal: pd.Series[int] = pd.Series(np.zeros(len(df)), index=df.index, dtype=int)
    signal[close > upper] = 1
    signal[close < lower] = -1
    signal[rolling_mean.isna()] = 0
    return signal


def compute_volume_spike(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series[int]:
    """Volume spike detection.

    Signal: +1 if volume > avg * multiplier AND close > open (bullish),
           -1 if volume > avg * multiplier AND close < open (bearish), else 0.
    """
    _validate_params("volume_spike", params)
    lookback: int = int(params["lookback"])
    multiplier: float = float(params["multiplier"])

    volume = df["volume"].astype(float)
    close = df["close"].astype(float)
    open_ = df["open"].astype(float)

    avg_volume = volume.rolling(window=lookback).mean()
    spike = volume > (avg_volume * multiplier)

    signal: pd.Series[int] = pd.Series(np.zeros(len(df)), index=df.index, dtype=int)
    signal[spike & (close > open_)] = 1
    signal[spike & (close < open_)] = -1
    signal[avg_volume.isna()] = 0
    return signal


def compute_ema_crossover(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series[int]:
    """Fast EMA crosses slow EMA.

    Signal: +1 if fast > slow (golden cross), -1 if fast < slow (death cross), else 0.
    """
    _validate_params("ema_crossover", params)
    fast_period: int = int(params["fast_period"])
    slow_period: int = int(params["slow_period"])

    if fast_period >= slow_period:
        msg = f"fast_period ({fast_period}) must be < slow_period ({slow_period})"
        raise ValueError(msg)

    close = df["close"].astype(float)
    fast_ema = close.ewm(span=fast_period, adjust=False).mean()
    slow_ema = close.ewm(span=slow_period, adjust=False).mean()

    signal: pd.Series[int] = pd.Series(np.zeros(len(df)), index=df.index, dtype=int)
    signal[fast_ema > slow_ema] = 1
    signal[fast_ema < slow_ema] = -1
    return signal


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

FACTOR_REGISTRY: dict[str, tuple[FactorFn, dict[str, tuple[float, float]]]] = {
    "momentum": (compute_momentum, PARAM_SCHEMAS["momentum"]),
    "mean_reversion": (compute_mean_reversion, PARAM_SCHEMAS["mean_reversion"]),
    "volatility_breakout": (
        compute_volatility_breakout,
        PARAM_SCHEMAS["volatility_breakout"],
    ),
    "volume_spike": (compute_volume_spike, PARAM_SCHEMAS["volume_spike"]),
    "ema_crossover": (compute_ema_crossover, PARAM_SCHEMAS["ema_crossover"]),
}


def get_factor(
    name: str,
) -> tuple[FactorFn, dict[str, tuple[float, float]]]:
    """Look up a factor by name. Raises ValueError for unknown names."""
    if name not in FACTOR_VOCABULARY:
        msg = f"Unknown factor '{name}'. Must be one of {sorted(FACTOR_VOCABULARY)}"
        raise ValueError(msg)
    return FACTOR_REGISTRY[name]


def compute_factor(
    name: str, df: pd.DataFrame, params: dict[str, Any]
) -> pd.Series[int]:
    """Compute a registered factor's signals on OHLCV data.

    Returns a Series of {-1, 0, +1} signals.
    Raises ValueError for unknown factor names or invalid parameters.
    """
    fn, _schema = get_factor(name)
    return fn(df, params)


__all__ = [
    "FACTOR_REGISTRY",
    "PARAM_SCHEMAS",
    "compute_ema_crossover",
    "compute_factor",
    "compute_mean_reversion",
    "compute_momentum",
    "compute_volatility_breakout",
    "compute_volume_spike",
    "get_factor",
]
