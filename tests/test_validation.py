"""Tests for walk-forward validation engine and metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factor_atlas.contracts import MarketSnapshot
from factor_atlas.fixtures import AAPLUSDT_OHLCV
from factor_atlas.validation import (
    ANNUALIZATION_FACTOR,
    compute_max_drawdown,
    compute_sharpe,
    compute_sortino,
    compute_turnover,
    compute_win_rate,
    validate_factor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ohlcv_to_df(snapshots: list[MarketSnapshot]) -> pd.DataFrame:
    """Convert OHLCV fixtures to a DataFrame."""
    rows = []
    for s in snapshots:
        rows.append(
            {
                "timestamp": s.timestamp,
                "open": float(s.open),
                "high": float(s.high),
                "low": float(s.low),
                "close": float(s.close),
                "volume": float(s.volume),
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture()
def ohlcv_df() -> pd.DataFrame:
    return _ohlcv_to_df(AAPLUSDT_OHLCV)


def _float_series(values: list[float]) -> pd.Series[float]:
    """Create a float Series explicitly typed."""
    return pd.Series(values, dtype=float)


def _int_series(values: list[int]) -> pd.Series[int]:
    """Create an int Series explicitly typed."""
    return pd.Series(values, dtype=int)


# ---------------------------------------------------------------------------
# Hand-calculated Sharpe verification
# ---------------------------------------------------------------------------


class TestHandCalculatedSharpe:
    """Verify Sharpe ratio against a hand-calculated known series."""

    def test_sharpe_hand_calculated(self) -> None:
        """Hand-calculated Sharpe for a known return series.

        Returns: [0.01, 0.02, -0.01, 0.03, 0.01]
        Mean = (0.01 + 0.02 + (-0.01) + 0.03 + 0.01) / 5 = 0.06 / 5 = 0.012
        Std  = sqrt(sum((r - mean)^2) / (n-1))
             = sqrt(((0.01-0.012)^2 + (0.02-0.012)^2 + (-0.01-0.012)^2
                      + (0.03-0.012)^2 + (0.01-0.012)^2) / 4)
             = sqrt((0.000004 + 0.000064 + 0.000484 + 0.000324 + 0.000004) / 4)
             = sqrt(0.00088 / 4)
             = sqrt(0.00022)
             = 0.014832...
        Daily Sharpe = 0.012 / 0.014832 = 0.80904...
        Annualized = 0.80904 * sqrt(252) = 0.80904 * 15.8745... = 12.843...
        """
        returns = _float_series([0.01, 0.02, -0.01, 0.03, 0.01])
        mean = returns.mean()
        std = returns.std()  # ddof=1 by default

        assert abs(float(mean) - 0.012) < 1e-10
        expected_daily = float(mean) / float(std)
        expected_annual = expected_daily * ANNUALIZATION_FACTOR

        result = compute_sharpe(returns, annualize=True)
        assert abs(result - expected_annual) < 1e-6

    def test_sharpe_zero_std(self) -> None:
        """Constant returns -> std=0 -> Sharpe=0."""
        returns = _float_series([0.01, 0.01, 0.01])
        assert compute_sharpe(returns) == 0.0

    def test_sharpe_empty(self) -> None:
        returns = _float_series([])
        assert compute_sharpe(returns) == 0.0

    def test_sharpe_non_annualized(self) -> None:
        returns = _float_series([0.01, 0.02, -0.01, 0.03, 0.01])
        daily = compute_sharpe(returns, annualize=False)
        annual = compute_sharpe(returns, annualize=True)
        assert abs(annual - daily * ANNUALIZATION_FACTOR) < 1e-10


# ---------------------------------------------------------------------------
# Sortino
# ---------------------------------------------------------------------------


class TestSortino:
    def test_sortino_no_downside(self) -> None:
        """All positive returns -> Sortino=0 (no downside deviation)."""
        returns = _float_series([0.01, 0.02, 0.03])
        assert compute_sortino(returns) == 0.0

    def test_sortino_with_downside(self) -> None:
        returns = _float_series([0.01, -0.02, 0.03, -0.01])
        downside = returns[returns < 0]
        expected_daily = float(returns.mean()) / float(downside.std())
        expected_annual = expected_daily * ANNUALIZATION_FACTOR
        result = compute_sortino(returns)
        assert abs(result - expected_annual) < 1e-6


# ---------------------------------------------------------------------------
# Max drawdown
# ---------------------------------------------------------------------------


class TestMaxDrawdown:
    def test_drawdown_known_series(self) -> None:
        """Known: returns [0.10, -0.20, 0.05]
        Cumulative: [1.10, 0.88, 0.924]
        Peak:       [1.10, 1.10, 1.10]
        DD:         [0, -0.2, -0.16]
        Max DD = -0.2
        """
        returns = _float_series([0.10, -0.20, 0.05])
        dd = compute_max_drawdown(returns)
        assert abs(dd - (-0.20)) < 1e-10

    def test_drawdown_all_positive(self) -> None:
        returns = _float_series([0.01, 0.02, 0.03])
        dd = compute_max_drawdown(returns)
        assert dd == 0.0

    def test_drawdown_empty(self) -> None:
        returns = _float_series([])
        assert compute_max_drawdown(returns) == 0.0


# ---------------------------------------------------------------------------
# Turnover
# ---------------------------------------------------------------------------


class TestTurnover:
    def test_turnover_known(self) -> None:
        """Signals: [1, 1, -1, 0, 1]
        Diffs:      [NaN, 0, 2, 1, 1]
        Mean of [0, 2, 1, 1] = 1.0
        """
        signals = _int_series([1, 1, -1, 0, 1])
        assert abs(compute_turnover(signals) - 1.0) < 1e-10

    def test_turnover_no_change(self) -> None:
        signals = _int_series([1, 1, 1, 1])
        assert compute_turnover(signals) == 0.0

    def test_turnover_single(self) -> None:
        signals = _int_series([1])
        assert compute_turnover(signals) == 0.0


# ---------------------------------------------------------------------------
# Win rate
# ---------------------------------------------------------------------------


class TestWinRate:
    def test_win_rate_known(self) -> None:
        """3 active bars, 2 positive -> win_rate = 2/3."""
        returns = _float_series([0.01, -0.02, 0.03, 0.0, 0.01])
        signals = _int_series([1, -1, 1, 0, 0])
        # Active (signal!=0): returns [0.01, -0.02, 0.03]; positive: 2 of 3
        wr = compute_win_rate(returns, signals)
        assert abs(wr - 2 / 3) < 1e-10

    def test_win_rate_no_signals(self) -> None:
        returns = _float_series([0.01, 0.02])
        signals = _int_series([0, 0])
        assert compute_win_rate(returns, signals) == 0.0


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------


class TestValidateFactor:
    def test_basic_validation_runs(self, ohlcv_df: pd.DataFrame) -> None:
        """Validation produces a result (may or may not pass)."""
        result = validate_factor(
            "momentum",
            ohlcv_df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,  # fixture is only 30 bars
            min_sharpe=-999.0,  # don't reject on Sharpe
            max_drawdown=-999.0,  # don't reject on drawdown
        )
        assert result.observations >= 5
        assert result.metrics.total_return.label == "observed"
        assert result.metrics.fees.label == "estimated"
        assert result.metrics.slippage.label == "estimated"

    def test_metric_labels(self, ohlcv_df: pd.DataFrame) -> None:
        """Verify observed/estimated labels are correct."""
        result = validate_factor(
            "momentum",
            ohlcv_df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
        )
        m = result.metrics
        # Observed metrics
        assert m.total_return.label == "observed"
        assert m.sharpe_ratio.label == "observed"
        assert m.sortino_ratio.label == "observed"
        assert m.max_drawdown.label == "observed"
        assert m.turnover.label == "observed"
        assert m.win_rate.label == "observed"
        # Estimated metrics
        assert m.fees.label == "estimated"
        assert m.slippage.label == "estimated"

    def test_deterministic_replay(self, ohlcv_df: pd.DataFrame) -> None:
        """Same inputs produce same metrics."""
        r1 = validate_factor(
            "momentum",
            ohlcv_df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
            hypothesis_id="h-replay",
            snapshot_id="s-replay",
        )
        r2 = validate_factor(
            "momentum",
            ohlcv_df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
            hypothesis_id="h-replay",
            snapshot_id="s-replay",
        )

        assert r1.metrics.sharpe_ratio.value == r2.metrics.sharpe_ratio.value
        assert r1.metrics.total_return.value == r2.metrics.total_return.value
        assert r1.metrics.max_drawdown.value == r2.metrics.max_drawdown.value
        assert r1.metrics.win_rate.value == r2.metrics.win_rate.value
        assert r1.passed == r2.passed
        assert r1.rejection_reasons == r2.rejection_reasons


# ---------------------------------------------------------------------------
# Rejection criteria
# ---------------------------------------------------------------------------


class TestRejectionCriteria:
    def test_insufficient_samples(self) -> None:
        """Test window smaller than min_observations is rejected."""
        # Create a tiny dataframe (10 bars)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2026-09-01", periods=10, freq="h", tz="UTC"
                ),
                "open": np.linspace(100, 110, 10),
                "high": np.linspace(101, 111, 10),
                "low": np.linspace(99, 109, 10),
                "close": np.linspace(100.5, 110.5, 10),
                "volume": np.full(10, 50000.0),
            }
        )
        result = validate_factor(
            "momentum",
            df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=20,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
        )
        assert result.passed is False
        assert any("insufficient" in r for r in result.rejection_reasons)

    def test_leakage_detection(self) -> None:
        """Overlapping timestamps between train and test triggers rejection."""
        # Create dataframe with duplicate timestamps to force overlap
        ts = pd.date_range("2026-09-01", periods=30, freq="h", tz="UTC")
        # Inject duplicates: make last train timestamp == first test timestamp
        ts_list = list(ts)
        # With 70/30 split of 30 bars: train=21, test=9
        # Make train[-1] == test[0] by duplicating timestamp
        ts_list[21] = ts_list[20]  # force overlap
        df = pd.DataFrame(
            {
                "timestamp": ts_list,
                "open": np.linspace(100, 130, 30),
                "high": np.linspace(101, 131, 30),
                "low": np.linspace(99, 129, 30),
                "close": np.linspace(100.5, 130.5, 30),
                "volume": np.full(30, 50000.0),
            }
        )
        result = validate_factor(
            "momentum",
            df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
        )
        assert result.passed is False
        assert any("leakage" in r for r in result.rejection_reasons)

    def test_no_signal_rejection(self) -> None:
        """If all test-window signals are 0, reject."""
        # Create data with zero ROC (constant price)
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2026-09-01", periods=50, freq="h", tz="UTC"
                ),
                "open": np.full(50, 100.0),
                "high": np.full(50, 101.0),
                "low": np.full(50, 99.0),
                "close": np.full(50, 100.0),
                "volume": np.full(50, 50000.0),
            }
        )
        result = validate_factor(
            "momentum",
            df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
        )
        assert result.passed is False
        assert any("no signal" in r for r in result.rejection_reasons)

    def test_sharpe_threshold_rejection(self, ohlcv_df: pd.DataFrame) -> None:
        """Factor with Sharpe below threshold is rejected."""
        result = validate_factor(
            "momentum",
            ohlcv_df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=999.0,  # impossibly high threshold
            max_drawdown=-999.0,
        )
        assert result.passed is False
        assert any("sharpe" in r for r in result.rejection_reasons)

    def test_drawdown_threshold_rejection(self, ohlcv_df: pd.DataFrame) -> None:
        """Factor with excessive drawdown is rejected."""
        result = validate_factor(
            "momentum",
            ohlcv_df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=0.0,  # reject any drawdown at all
        )
        # If there's any drawdown, it should be rejected
        # If no drawdown, it passes -- both are valid
        if result.metrics.max_drawdown.value < 0.0:
            assert result.passed is False
            assert any("drawdown" in r for r in result.rejection_reasons)

    def test_passed_true_no_rejections(self, ohlcv_df: pd.DataFrame) -> None:
        """When passed=True, rejection_reasons must be empty."""
        result = validate_factor(
            "momentum",
            ohlcv_df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
        )
        if result.passed:
            assert result.rejection_reasons == []

    def test_passed_false_has_reasons(self) -> None:
        """When passed=False, rejection_reasons must be non-empty."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2026-09-01", periods=50, freq="h", tz="UTC"
                ),
                "open": np.full(50, 100.0),
                "high": np.full(50, 101.0),
                "low": np.full(50, 99.0),
                "close": np.full(50, 100.0),
                "volume": np.full(50, 50000.0),
            }
        )
        result = validate_factor(
            "momentum",
            df,
            {"lookback": 5, "threshold": 0.01},
            min_observations=5,
            min_sharpe=-999.0,
            max_drawdown=-999.0,
        )
        if not result.passed:
            assert len(result.rejection_reasons) > 0
