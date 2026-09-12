# T2 Report: Registered Factors and Deterministic Validation

## Status: COMPLETE

## Commit
`79e098b` — `feat(factors): add factor registry and walk-forward validation`

## Files created
- `src/factor_atlas/factors.py` — Closed factor registry with 5 deterministic factor functions, parameter schemas with range validation, and `compute_factor()` gateway
- `src/factor_atlas/validation.py` — Walk-forward validation engine with train/test split, leakage detection, metrics computation (Sharpe, Sortino, max drawdown, turnover, fees, slippage, win rate), and rejection criteria
- `tests/test_factors.py` — 22 tests covering registry completeness, unknown factor rejection, parameter validation (missing, out-of-range, non-numeric, fast>=slow), signal properties ({-1,0,+1}), and deterministic replay
- `tests/test_validation.py` — 24 tests covering hand-calculated Sharpe verification, Sortino, max drawdown, turnover, win rate, metric labels (observed/estimated), deterministic replay, and rejection criteria (insufficient samples, leakage, no signal, Sharpe threshold, drawdown threshold)

## Test summary
85 tests passed (39 T1 + 22 T2-factors + 24 T2-validation), 0 failures.

## Verification
```
uv run pytest tests/ -v              → 85 passed
uv run ruff check .                  → All checks passed
uv run ruff format --check .         → 27 files already formatted
uv run mypy src/ tests/              → Success: no issues found in 12 source files
```

## Acceptance criteria checklist
1. ✓ Only registered factors execute; unknown factor names raise ValueError
2. ✓ Each factor returns signals in {-1, 0, +1}
3. ✓ Parameter validation rejects out-of-range values
4. ✓ Metrics carry observed/estimated labels
5. ✓ Leakage is detected and rejected
6. ✓ Insufficient samples rejected
7. ✓ Hand-calculated fixture test for Sharpe (with step-by-step arithmetic in docstring)
8. ✓ Deterministic replay verified (all 5 factors + full validation)
9. ✓ `uv run pytest tests/test_factors.py tests/test_validation.py -v` passes
10. ✓ `uv run ruff check .` clean
11. ✓ `uv run ruff format --check .` clean
12. ✓ `uv run mypy src/ tests/` clean

## Dependencies added
- `pandas-stubs` (dev) — required for mypy strict mode with pandas

## Concerns
None. All criteria met. No type suppressions. No credential usage.
