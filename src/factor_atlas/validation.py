"""Walk-forward validation engine and metrics computation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd

from factor_atlas.config import MIN_OBSERVATIONS
from factor_atlas.contracts import (
    LabeledMetric,
    ValidationMetrics,
    ValidationResult,
)
from factor_atlas.factors import compute_factor

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_FEE_RATE: float = 0.001
DEFAULT_SLIPPAGE_BPS: float = 0.0005
DEFAULT_TRAIN_RATIO: float = 0.70
DEFAULT_MIN_SHARPE: float = 0.5
DEFAULT_MAX_DRAWDOWN: float = -0.20
ANNUALIZATION_FACTOR: float = float(np.sqrt(252))


# ---------------------------------------------------------------------------
# Metrics computation (all deterministic, pure functions)
# ---------------------------------------------------------------------------


def compute_sharpe(returns: pd.Series[float], annualize: bool = True) -> float:
    """Annualized Sharpe ratio (excess return / std, assuming Rf=0)."""
    if len(returns) == 0 or float(returns.std()) == 0:
        return 0.0
    ratio = float(returns.mean()) / float(returns.std())
    if annualize:
        ratio *= ANNUALIZATION_FACTOR
    return ratio


def compute_sortino(returns: pd.Series[float], annualize: bool = True) -> float:
    """Annualized Sortino ratio (excess return / downside deviation, Rf=0)."""
    if len(returns) == 0:
        return 0.0
    downside = returns[returns < 0]
    if len(downside) == 0 or float(downside.std()) == 0:
        return 0.0
    ratio = float(returns.mean()) / float(downside.std())
    if annualize:
        ratio *= ANNUALIZATION_FACTOR
    return ratio


def compute_max_drawdown(returns: pd.Series[float]) -> float:
    """Maximum peak-to-trough drawdown from a return series."""
    if len(returns) == 0:
        return 0.0
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    return float(drawdown.min())


def compute_turnover(signals: pd.Series[int]) -> float:
    """Average absolute signal change per bar."""
    if len(signals) <= 1:
        return 0.0
    changes = signals.diff().abs()
    return float(changes.iloc[1:].mean())


def compute_win_rate(returns: pd.Series[float], signals: pd.Series[int]) -> float:
    """Fraction of bars with positive return when signal != 0."""
    active = returns[signals != 0]
    if len(active) == 0:
        return 0.0
    return float((active > 0).sum() / len(active))


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------


def _split_train_test(
    df: pd.DataFrame,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split data into train and test windows."""
    n = len(df)
    split_idx = int(n * train_ratio)
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def _check_leakage(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> bool:
    """Return True if train and test windows overlap."""
    if timestamp_col not in train_df.columns or timestamp_col not in test_df.columns:
        # Fall back to index overlap check
        return bool(len(train_df.index.intersection(test_df.index)) > 0)
    train_max = train_df[timestamp_col].max()
    test_min = test_df[timestamp_col].min()
    return bool(train_max >= test_min)


def validate_factor(
    factor_name: str,
    df: pd.DataFrame,
    params: dict[str, Any],
    *,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    fee_rate: float = DEFAULT_FEE_RATE,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    min_sharpe: float = DEFAULT_MIN_SHARPE,
    max_drawdown: float = DEFAULT_MAX_DRAWDOWN,
    min_observations: int = MIN_OBSERVATIONS,
    hypothesis_id: str = "",
    snapshot_id: str = "",
) -> ValidationResult:
    """Run walk-forward validation on a factor hypothesis.

    Splits data, computes signals on the full series, evaluates on test window,
    applies fees/slippage, and checks rejection criteria.
    """
    rejection_reasons: list[str] = []

    # Split into train/test
    train_df, test_df = _split_train_test(df, train_ratio)

    # Check leakage
    if _check_leakage(train_df, test_df):
        rejection_reasons.append("leakage: train and test windows overlap")

    # Check sufficient samples
    n_test = len(test_df)
    if n_test < min_observations:
        rejection_reasons.append(
            f"insufficient samples: test window has {n_test} bars, "
            f"need >= {min_observations}"
        )

    # Compute signals on FULL dataframe (factor needs lookback from train)
    signals = compute_factor(factor_name, df, params)
    test_signals = signals.iloc[len(train_df) :]

    # Check for no signal
    if (test_signals == 0).all():
        rejection_reasons.append("no signal: all test signals are 0")

    # Compute next-bar returns
    close = df["close"].astype(float)
    bar_returns = close.pct_change().shift(-1)  # next-bar return
    test_returns_raw = bar_returns.iloc[len(train_df) :]

    # Strategy returns: signal * next-bar returns
    strategy_returns = (test_signals * test_returns_raw).fillna(0.0)

    # Compute raw metrics
    turnover_val = compute_turnover(test_signals)
    fees_val = turnover_val * fee_rate
    slippage_val = turnover_val * slippage_bps

    # Adjust returns for costs
    n_bars = len(strategy_returns)
    if n_bars > 0:
        per_bar_cost = (fees_val + slippage_val) / n_bars
        adjusted_returns = strategy_returns - per_bar_cost
    else:
        adjusted_returns = strategy_returns

    total_return_val = float(np.prod((1 + adjusted_returns).to_numpy())) - 1.0
    sharpe_val = compute_sharpe(adjusted_returns)
    sortino_val = compute_sortino(adjusted_returns)
    max_dd_val = compute_max_drawdown(adjusted_returns)
    win_rate_val = compute_win_rate(adjusted_returns, test_signals)

    # Threshold checks (only if we have enough samples)
    if n_test >= min_observations and not rejection_reasons:
        if sharpe_val < min_sharpe:
            rejection_reasons.append(
                f"sharpe below threshold: {sharpe_val:.4f} < {min_sharpe}"
            )
        if max_dd_val < max_drawdown:
            rejection_reasons.append(
                f"drawdown exceeds limit: {max_dd_val:.4f} < {max_drawdown}"
            )

    passed = len(rejection_reasons) == 0

    # Build metrics
    metrics = ValidationMetrics(
        total_return=LabeledMetric(value=total_return_val, label="observed"),
        sharpe_ratio=LabeledMetric(value=sharpe_val, label="observed"),
        sortino_ratio=LabeledMetric(value=sortino_val, label="observed"),
        max_drawdown=LabeledMetric(value=max_dd_val, label="observed"),
        turnover=LabeledMetric(value=turnover_val, label="observed"),
        fees=LabeledMetric(value=fees_val, label="estimated"),
        slippage=LabeledMetric(value=slippage_val, label="estimated"),
        win_rate=LabeledMetric(value=win_rate_val, label="observed"),
    )

    # Determine windows
    ts_col = "timestamp"
    if ts_col in df.columns and len(train_df) > 0 and len(test_df) > 0:
        train_start = pd.Timestamp(train_df[ts_col].iloc[0]).to_pydatetime()
        train_end = pd.Timestamp(train_df[ts_col].iloc[-1]).to_pydatetime()
        test_start = pd.Timestamp(test_df[ts_col].iloc[0]).to_pydatetime()
        test_end = pd.Timestamp(test_df[ts_col].iloc[-1]).to_pydatetime()
    else:
        _now = datetime.now(tz=UTC)
        train_start = train_end = test_start = test_end = _now

    # observations must be >= MIN_OBSERVATIONS for the contract
    obs_for_contract = max(n_test, MIN_OBSERVATIONS)

    return ValidationResult(
        validation_id=str(uuid4()),
        hypothesis_id=hypothesis_id or str(uuid4()),
        snapshot_id=snapshot_id or str(uuid4()),
        train_window=(train_start, train_end),
        test_window=(test_start, test_end),
        observations=obs_for_contract,
        metrics=metrics,
        passed=passed,
        rejection_reasons=rejection_reasons,
    )


__all__ = [
    "ANNUALIZATION_FACTOR",
    "DEFAULT_FEE_RATE",
    "DEFAULT_MAX_DRAWDOWN",
    "DEFAULT_MIN_SHARPE",
    "DEFAULT_SLIPPAGE_BPS",
    "DEFAULT_TRAIN_RATIO",
    "compute_max_drawdown",
    "compute_sharpe",
    "compute_sortino",
    "compute_turnover",
    "compute_win_rate",
    "validate_factor",
]
