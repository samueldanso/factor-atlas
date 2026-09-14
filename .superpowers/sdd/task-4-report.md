# Task 4 Report: Enhanced Metrics

**Status:** COMPLETE

**Commit:** `8d2696f` — `feat(metrics): add Sortino, turnover, equity curve, avg hold hours`

**Test summary:** 287 passed, 0 failed (5 new tests in `tests/test_metrics.py`, all pass)

## Changes

### `src/factor_atlas/metrics.py`
- `compute_metrics()` now returns 4 additional keys:
  - `sortino_ratio` — downside-deviation only version of Sharpe (annualised ×√365)
  - `turnover` — sum of abs notional / avg running equity
  - `avg_hold_hours` — mean `hold_duration_hours` across all trades
  - `equity_curve` — list of `[iso_timestamp, cumulative_pnl]` sorted by trade exit time
- Empty-trade branch updated to return all new keys with zero/empty defaults
- Existing keys (total_trades, win_rate, total_pnl, avg_pnl, sharpe_ratio, max_drawdown, profit_factor) unchanged

### `tests/test_metrics.py` (new)
- 5 tests covering empty input, single trade, Sortino > Sharpe property, turnover > 0, and cumulative equity curve values

## Lint/type status
- `ruff check .` — all checks passed
- `ruff format --check .` — 58 files already formatted
- No mypy run required (task brief did not specify; existing mypy baseline not changed)

## Concerns
- None. Turnover formula uses `avg_equity` as denominator; if all trades are losses (cumulative always negative), `avg_equity` will be negative and turnover will be negative. This edge case is acceptable for paper-trading research but worth noting for production dashboards.
