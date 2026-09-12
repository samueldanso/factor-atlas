# Task T2 Brief: Registered Factors and Deterministic Validation

## Spec Section
Technical spec → Core contracts (Factor hypothesis, Validation result); tasks/plan.md T2

## Scope
Build the closed factor registry, factor calculation functions, walk-forward/backtest validation loop, and metrics including fees, slippage, turnover, Sharpe, Sortino, drawdown, and win-rate.

## Dependencies
T1 contracts are complete. Import from `factor_atlas.contracts` and `factor_atlas.config`.

## Factor Registry

Create a closed registry of factor calculation functions. Each registered factor:
- Has a unique name matching the vocabulary in `factor_atlas.config.FACTOR_VOCABULARY`: {"momentum", "mean_reversion", "volatility_breakout", "volume_spike", "ema_crossover"}
- Takes a pandas DataFrame of OHLCV data + parameters dict → returns a pandas Series of signals (-1, 0, +1)
- Has parameter schemas with valid ranges
- Rejects unknown factor names at lookup time

### Factor implementations (deterministic, no randomness):

1. **momentum**: Returns price rate of change over `lookback` periods. Signal: +1 if ROC > threshold, -1 if ROC < -threshold, else 0. Params: `lookback` (int, 5-200), `threshold` (float, 0.0-0.5).

2. **mean_reversion**: Z-score of price relative to rolling mean. Signal: +1 if z < -entry_z (buy the dip), -1 if z > entry_z (sell the rip), else 0. Params: `lookback` (int, 10-200), `entry_z` (float, 1.0-3.0).

3. **volatility_breakout**: Signal when price breaks above/below Bollinger Bands. +1 if close > upper band, -1 if close < lower band, else 0. Params: `lookback` (int, 10-100), `num_std` (float, 1.0-3.0).

4. **volume_spike**: Signal when volume exceeds rolling average by a multiple. +1 if volume > avg * multiplier AND close > open (bullish), -1 if volume > avg * multiplier AND close < open (bearish), else 0. Params: `lookback` (int, 5-100), `multiplier` (float, 1.5-5.0).

5. **ema_crossover**: Fast EMA crosses slow EMA. +1 if fast > slow (golden cross), -1 if fast < slow (death cross), else 0. Params: `fast_period` (int, 5-50), `slow_period` (int, 20-200). Reject if fast_period >= slow_period.

## Walk-Forward Validation

Implement a walk-forward validation engine:

1. Split data into train/test windows (configurable ratio, default 70/30)
2. Calculate factor signals on train window
3. Compute returns from signals (next-bar returns * signal)
4. Apply fees and slippage to returns
5. Calculate metrics on the test window
6. Return a `ValidationResult` with all metrics labeled

### Metrics to compute (all deterministic):
- `total_return`: cumulative return over test window (observed)
- `sharpe_ratio`: annualized Sharpe (observed). Use 252 trading days.
- `sortino_ratio`: annualized Sortino using downside deviation (observed)
- `max_drawdown`: maximum peak-to-trough drawdown (observed)
- `turnover`: average absolute signal change per bar (observed)
- `fees`: total estimated fees = turnover * fee_rate (estimated). Default fee_rate = 0.001
- `slippage`: total estimated slippage = turnover * slippage_bps (estimated). Default slippage_bps = 0.0005
- `win_rate`: fraction of bars with positive return when signal != 0 (observed)

### Rejection criteria:
- Insufficient samples: if test window has fewer than `MIN_OBSERVATIONS` (20) bars
- Leakage: train and test windows must not overlap
- No signal: if all signals are 0, reject

### Validation threshold defaults (configurable):
- min_sharpe: 0.5
- max_drawdown: -0.20 (reject if drawdown worse than -20%)
- min_observations: 20

## Files to create
- `src/factor_atlas/factors.py` — factor registry + factor calculation functions
- `src/factor_atlas/validation.py` — walk-forward validation engine + metrics
- `tests/test_factors.py` — factor registry and calculation tests
- `tests/test_validation.py` — validation engine, metrics, rejection tests

## Important implementation details
- `from __future__ import annotations` in all files
- All factor functions must be pure functions (no side effects, no randomness)
- Use pandas/numpy for calculations; they are already in pyproject.toml
- Factor functions signature: `(df: pd.DataFrame, params: dict[str, Any]) -> pd.Series`
- Registry is a dict mapping factor_name → (calc_function, param_schema)
- Parameter schema validation uses the ranges above
- Tests must use hand-calculated fixtures for at least one metric (e.g., verify Sharpe ratio by hand for a known return series)
- Tests must verify leakage rejection (overlapping windows)
- Tests must verify insufficient-sample rejection
- Tests must verify deterministic replay (same input → same output)

## Acceptance Criteria
1. Only registered factors execute; unknown factor names raise ValueError
2. Each factor returns signals in {-1, 0, +1}
3. Parameter validation rejects out-of-range values
4. Metrics carry observed/estimated/targeted labels
5. Leakage is detected and rejected
6. Insufficient samples rejected
7. Hand-calculated fixture test for at least Sharpe
8. Deterministic replay verified
9. `uv run pytest tests/test_factors.py tests/test_validation.py -v` passes
10. `uv run ruff check .` clean
11. `uv run ruff format --check .` clean
12. `uv run mypy src/ tests/` clean

## Credential mode
Unused — pure fixtures, no network, no API.

## Verification commands
```bash
uv run pytest tests/test_factors.py tests/test_validation.py -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
```
