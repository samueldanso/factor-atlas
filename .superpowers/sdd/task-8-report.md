# Task 8 Report: Wire exchange verification into runner

## Status: DONE

## Commit
`8c319d4` — `feat(runner): wire exchange verification, reconciliation, and pre-flight`

## Files Modified
- `src/factor_atlas/orchestrator.py` — added `exchange_state: object | None = None` param to both `run_cycle` and `run_cycles`; pass it through to `run_gates` keyword arg
- `src/factor_atlas/runner.py` — (1) pre-flight exchange query + reconciliation after `_load_positions_state` (demo only, wrapped in broad Exception catch); (2) pass `exchange_state` to `run_cycles`; (3) order verification loop after bgc entry placement; (4) `verification_status` field in all open-cycle paper log records ("not_applicable" in fixture, classify result or "query_failed" in demo)
- `tests/test_runner.py` — added `TestOrderVerification` class with two tests: checks `verification_status` is absent/None or "not_applicable" for all records, and that open-type records specifically have "not_applicable" in fixture mode

## Test Summary
- 304 tests pass total (up from 302; 2 new tests added)
- ruff check clean
- ruff format clean

## Acceptance Criteria Verified
1. Pre-flight exchange query runs in demo mode — implemented after `_load_positions_state`, wrapped in `except Exception` so failures are non-fatal
2. Reconciliation divergences printed to stderr — implemented via `reconcile_positions`, iterates and prints each `Divergence`
3. `exchange_state` passed to orchestrator and through to `run_gates` — added param to `run_cycle` and `run_cycles`, threaded through
4. Order verification after placement — loops over `bgc_order_ids`, calls `query_order_status` + `classify_order_status`, stores per cycle_id
5. `verification_status` in paper log — "not_applicable" in fixture mode; classify result or "query_failed" in demo mode
6. Fixture mode makes no exchange calls — pre-flight and verification blocks both gated on `mode == "demo"`
7. Exchange failures non-fatal — pre-flight uses broad `except Exception`; verification uses `except (RuntimeError, OSError, ValueError)`

## Concerns
- The pre-flight broad `except Exception` (with `noqa: BLE001`) is intentional: bgc can return structurally unexpected responses (e.g., `data` as a string vs list), producing `TypeError`/`KeyError` that shouldn't crash the session. Narrowing would require patching `exchange.py` parsing to be defensive, which is out of scope for this task.
