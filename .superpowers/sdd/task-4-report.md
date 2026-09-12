# Task T4 Report: Deterministic Risk Gates and Automatic Paper Broker

## Status: COMPLETE

## Commit
`e0dea1f` — `feat(risk): add risk gates and paper broker`

## Files changed
- `src/factor_atlas/config.py` — added 10 risk/broker constants (MAX_DATA_AGE_HOURS, MAX_NOTIONAL, etc.)
- `src/factor_atlas/risk.py` — NEW: RiskConfig dataclass, 12 pure-function gates, run_gates runner, all_gates_passed helper
- `src/factor_atlas/broker.py` — NEW: BrokerState mutable dataclass, execute_paper_order with fee/slippage simulation
- `src/factor_atlas/orchestrator.py` — extended CycleResult with gate_results + order fields; run_cycle/run_cycles accept optional broker_state + risk_config; gate → execute integrated after decision
- `tests/test_risk.py` — 36 tests: each gate tested for pass + fail paths, run_gates integration, all_gates_passed
- `tests/test_broker.py` — 16 tests: fill, rejection, fee math (hand-calculated), balance safety, multi-order

## Test summary
- **160 total** (108 prior + 52 new) — all passing
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean
- `uv run mypy src/ tests/` — clean (0 errors)

## Acceptance criteria met
1. Passing decision submitted automatically (no approval pause) — execute_paper_order fires immediately after gates
2. Any veto prevents execution — first failing gate reason captured as rejection_reason
3. Balance never negative — insufficient_balance guard tested
4. Each gate has pass + fail test
5. Fee/slippage math tested with hand-calculated values (notional=1000 → fee=1.000, slip=0.5000)
6. Bounded quantity check via gate_max_quantity
7. All 108 prior tests still pass
8-10. Ruff, format, mypy all clean

## Design decisions
- Gates are keyword-only after `decision` to stay type-safe with **kwargs dispatch
- run_gates uses `# type: ignore[operator]` for the dynamic dispatch dict (mypy can't narrow union of callables)
- Orchestrator integration is opt-in: broker_state=None → no gates/broker (backward compatible)
- BrokerState.processed_events stores `"event_id|instrument|side"` strings for dedup

## Concerns
- None blocking. The orchestrator backward-compat is clean — all existing tests pass unchanged.
