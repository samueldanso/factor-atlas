"""Tests for factor registry and calculation functions."""

from __future__ import annotations

import pandas as pd
import pytest

from factor_atlas.contracts import MarketSnapshot
from factor_atlas.factors import (
    FACTOR_REGISTRY,
    PARAM_SCHEMAS,
    compute_ema_crossover,
    compute_factor,
    compute_mean_reversion,
    compute_momentum,
    compute_volatility_breakout,
    compute_volume_spike,
    get_factor,
)
from factor_atlas.fixtures import RAAPLUSDT_OHLCV

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
    return _ohlcv_to_df(RAAPLUSDT_OHLCV)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestFactorRegistry:
    def test_registry_contains_all_vocabulary(self) -> None:
        from factor_atlas.config import FACTOR_VOCABULARY

        for name in FACTOR_VOCABULARY:
            assert name in FACTOR_REGISTRY

    def test_registry_has_no_extra_factors(self) -> None:
        from factor_atlas.config import FACTOR_VOCABULARY

        for name in FACTOR_REGISTRY:
            assert name in FACTOR_VOCABULARY

    def test_unknown_factor_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown factor"):
            get_factor("magic_indicator")

    def test_compute_factor_unknown_raises(self) -> None:
        df = pd.DataFrame({"close": [1, 2, 3]})
        with pytest.raises(ValueError, match="Unknown factor"):
            compute_factor("nonexistent", df, {})

    def test_each_factor_has_param_schema(self) -> None:
        for name in FACTOR_REGISTRY:
            assert name in PARAM_SCHEMAS
            assert len(PARAM_SCHEMAS[name]) > 0


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    def test_momentum_missing_param(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="Missing parameter"):
            compute_momentum(ohlcv_df, {"lookback": 10})  # missing threshold

    def test_momentum_out_of_range_lookback(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="must be in"):
            compute_momentum(ohlcv_df, {"lookback": 1, "threshold": 0.01})

    def test_momentum_out_of_range_threshold(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="must be in"):
            compute_momentum(ohlcv_df, {"lookback": 10, "threshold": 1.0})

    def test_mean_reversion_out_of_range(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="must be in"):
            compute_mean_reversion(ohlcv_df, {"lookback": 5, "entry_z": 2.0})

    def test_volatility_breakout_out_of_range(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="must be in"):
            compute_volatility_breakout(ohlcv_df, {"lookback": 5, "num_std": 2.0})

    def test_volume_spike_out_of_range(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="must be in"):
            compute_volume_spike(ohlcv_df, {"lookback": 2, "multiplier": 3.0})

    def test_ema_crossover_fast_ge_slow(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="fast_period.*must be < slow_period"):
            compute_ema_crossover(ohlcv_df, {"fast_period": 30, "slow_period": 30})

    def test_non_numeric_param(self, ohlcv_df: pd.DataFrame) -> None:
        with pytest.raises(TypeError, match="must be numeric"):
            compute_momentum(ohlcv_df, {"lookback": "ten", "threshold": 0.01})


# ---------------------------------------------------------------------------
# Signal property tests
# ---------------------------------------------------------------------------


class TestSignalProperties:
    """All factors must return signals in {-1, 0, +1}."""

    def test_momentum_signals_valid(self, ohlcv_df: pd.DataFrame) -> None:
        signals = compute_momentum(ohlcv_df, {"lookback": 5, "threshold": 0.01})
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert len(signals) == len(ohlcv_df)

    def test_mean_reversion_signals_valid(self, ohlcv_df: pd.DataFrame) -> None:
        signals = compute_mean_reversion(ohlcv_df, {"lookback": 10, "entry_z": 1.5})
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert len(signals) == len(ohlcv_df)

    def test_volatility_breakout_signals_valid(self, ohlcv_df: pd.DataFrame) -> None:
        signals = compute_volatility_breakout(
            ohlcv_df, {"lookback": 10, "num_std": 2.0}
        )
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert len(signals) == len(ohlcv_df)

    def test_volume_spike_signals_valid(self, ohlcv_df: pd.DataFrame) -> None:
        signals = compute_volume_spike(ohlcv_df, {"lookback": 5, "multiplier": 2.0})
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert len(signals) == len(ohlcv_df)

    def test_ema_crossover_signals_valid(self, ohlcv_df: pd.DataFrame) -> None:
        signals = compute_ema_crossover(ohlcv_df, {"fast_period": 5, "slow_period": 20})
        assert set(signals.unique()).issubset({-1, 0, 1})
        assert len(signals) == len(ohlcv_df)


# ---------------------------------------------------------------------------
# Deterministic replay
# ---------------------------------------------------------------------------


class TestDeterministicReplay:
    """Same input must produce identical output."""

    def test_momentum_deterministic(self, ohlcv_df: pd.DataFrame) -> None:
        params = {"lookback": 5, "threshold": 0.01}
        s1 = compute_momentum(ohlcv_df, params)
        s2 = compute_momentum(ohlcv_df, params)
        pd.testing.assert_series_equal(s1, s2)

    def test_mean_reversion_deterministic(self, ohlcv_df: pd.DataFrame) -> None:
        params = {"lookback": 10, "entry_z": 1.5}
        s1 = compute_mean_reversion(ohlcv_df, params)
        s2 = compute_mean_reversion(ohlcv_df, params)
        pd.testing.assert_series_equal(s1, s2)

    def test_all_factors_deterministic_via_registry(
        self, ohlcv_df: pd.DataFrame
    ) -> None:
        test_params: dict[str, dict[str, float | int]] = {
            "momentum": {"lookback": 5, "threshold": 0.01},
            "mean_reversion": {"lookback": 10, "entry_z": 1.5},
            "volatility_breakout": {"lookback": 10, "num_std": 2.0},
            "volume_spike": {"lookback": 5, "multiplier": 2.0},
            "ema_crossover": {"fast_period": 5, "slow_period": 20},
        }
        for name, params in test_params.items():
            s1 = compute_factor(name, ohlcv_df, params)
            s2 = compute_factor(name, ohlcv_df, params)
            pd.testing.assert_series_equal(s1, s2, check_names=False)


# ---------------------------------------------------------------------------
# compute_factor gateway
# ---------------------------------------------------------------------------


class TestComputeFactorGateway:
    def test_compute_factor_returns_series(self, ohlcv_df: pd.DataFrame) -> None:
        result = compute_factor(
            "momentum", ohlcv_df, {"lookback": 5, "threshold": 0.01}
        )
        assert isinstance(result, pd.Series)
        assert len(result) == len(ohlcv_df)
