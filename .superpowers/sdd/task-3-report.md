### Task 3 Report: New risk gates (balance_check, pending_order_check)

**Status:** COMPLETE

**Commit:** `ccba429` — `feat(risk): add balance_check and pending_order_check exchange gates`

**Test summary:** 282 passed, 0 failed — 42 tests in test_risk.py (30 existing + 12 new across TestGateBalanceCheck and TestGatePendingOrderCheck)

---

**What was done:**

1. Added `gate_balance_check` and `gate_pending_order_check` to `src/factor_atlas/risk.py` after `gate_max_quantity`. Both gates follow the brief's interface exactly: skip with `passed=True` and a `"skipped: ..."` reason when `exchange_state is None` (fixture mode); otherwise assert `isinstance(exchange_state, ExchangeState)` and apply the gate logic.

2. Extended `_GATE_ORDER` and `_GATE_FNS` to include the two new gates (positions 13 and 14).

3. Updated `run_gates()` signature to accept `exchange_state: object | None = None` as a keyword argument; the value is passed through `kwargs` to all gate functions.

4. Updated `__all__` to export both new gate functions.

5. Added 8 new tests to `tests/test_risk.py` (4 per gate: pass, fail, no-exchange-state skip, plus a cross-instrument non-conflict test for `pending_order_check`). Updated the `TestRunGates` count assertions from 12 to 14.

6. Ran `uv run ruff check --fix` to resolve 10 FURB157 lint warnings (verbose string literals in `Decimal()` constructors) introduced by the test code.

**Concerns / notes:**

- The brief's `test_fails_when_conflicting_pending_order` used `_decision()` with `symbol="RAAPLUSDT"` in the pending order — these would not conflict if the decision instrument stayed at the default `"AAPLUSDT"`. The test was written using `_make_decision(instrument="RAAPLUSDT")` to match the pending order symbol, which is the correct behavior for the gate.
- An additional test (`test_passes_when_pending_order_is_different_instrument`) was added to explicitly cover the non-conflict case.
- No live exchange calls; existing fixture-mode backward compatibility is preserved.
