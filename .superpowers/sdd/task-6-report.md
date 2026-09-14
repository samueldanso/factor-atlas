# Task 6 Report: Separate research prices from execution prices

## Status: DONE

## Commit
`6ab6ad9` — `fix(runner): use perp prices for exit evaluation, not SPOT research prices`

## Files Modified
- `src/factor_atlas/runner.py`:
  - Added `_fetch_perp_prices(instruments: list[str]) -> dict[str, Decimal]` after `_fetch_candles_bgc`. Fetches latest USDT-FUTURES 1D candle close price per execution symbol via bgc subprocess. Silently skips symbols whose bgc call fails or returns empty data.
  - Updated `_process_demo_exits` signature: replaced `ohlcv_data: dict[str, pd.DataFrame]` parameter with `perp_prices: dict[str, Decimal]`. Now looks up `RESEARCH_TO_EXECUTION` mapping at the top of the loop (once, for both price lookup and order placement) instead of duplicating it. Exits skip an instrument if its perp price is unavailable.
  - Updated `run_paper_session` call site: before calling `_process_demo_exits`, derives the set of execution symbols from open position keys, fetches their perp prices via `_fetch_perp_prices`, and passes `perp_prices` instead of `ohlcv_data`.
- `tests/test_runner.py`:
  - Added `TestPerpPriceFetching` with two tests: happy-path decimal return and skip-on-bgc-failure. Both mock `subprocess.run`.

## Test Summary
- 291 tests pass (2 new in `TestPerpPriceFetching`)
- ruff check clean
- ruff format clean

## Acceptance Criteria Verified
1. `_fetch_perp_prices` added and importable — verified by `TestPerpPriceFetching::test_fetch_perp_prices_returns_decimals`
2. Returns `Decimal` values keyed by execution symbol — verified by assertion `prices["AAPLUSDT"] == Decimal("332.50")`
3. Skips failed symbols without crashing — verified by `test_fetch_perp_prices_skips_failed_symbol`
4. `_process_demo_exits` takes `perp_prices` not `ohlcv_data` — verified by full test suite passing (no callers use old signature)
5. Call site in `run_paper_session` fetches perp prices and passes them — verified by 291/291 tests passing including demo-path tests
6. Fixture mode unchanged (`_process_fixture_exits` untouched) — verified by all fixture-mode tests passing

## Concerns
- None
