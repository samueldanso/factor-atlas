# Task 1 Report
Status: DONE
Commits: 31fab34 feat(exchange): add bgc exchange state query module
Test summary: `uv run pytest` — 257 passed (6 new in test_exchange.py)
Concerns: none

## Review Fix Round — 2026-09-14
Commit: 7d8b33c fix(exchange): validate order_id, add classify tests, minor cleanup
Test summary: `uv run pytest` — 271 passed (20 in test_exchange.py, up from 6)

### Fixes applied
1. **order_id injection guard** — `query_order_status` now calls `re.fullmatch(r'\d{1,32}', order_id)` and raises `ValueError` before any subprocess call.
2. **`classify_order_status` tests** — 11 new tests covering all branches: filled, cancelled (both spellings), rejected/failed, partial_fill/partially_filled/partial, unknown, and empty string.
3. **Test rename** — `test_network_failure_returns_query_failed` → `test_network_failure_propagates_oserror`.
4. **`ExchangeState` frozen** — changed to `@dataclass(frozen=True)`.
5. **`_run_bgc` return type** — updated to `dict[str, Any]`; added `from typing import Any`.
6. **`Decimal(0)` left as-is** — ruff FURB157 rejects `Decimal("0")` for zero; kept `Decimal(0)` to satisfy lint.

All checks passed: 271 tests, ruff lint, ruff format.
