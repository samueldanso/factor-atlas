# Task T3 Report: Autonomous Discovery-and-Decision Cycle

## Status: COMPLETE

## Commit
`95c6f46` — `feat(orchestrator): add autonomous cycle runner`

## Files Created
- `src/factor_atlas/proposer.py` — `Proposer` protocol + `FixtureProposer` (generates hypotheses from FACTOR_REGISTRY with valid PARAM_SCHEMAS params)
- `src/factor_atlas/decision.py` — `DecisionProvider` protocol + `FixtureDecisionProvider` (picks highest-Sharpe validated candidate)
- `src/factor_atlas/orchestrator.py` — `CycleResult` dataclass, `run_cycle()`, `run_cycles()`
- `tests/test_orchestrator.py` — 23 tests across 6 test classes

## Test Summary
- 108 tests passed (85 prior + 23 new), 0 failures
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean
- `uv run mypy src/ tests/` — clean (0 issues across 16 files)

## Acceptance Criteria Verification
1. Runner proceeds without human approval pause — verified by `test_no_human_approval_pause` and `test_multi_cycle_no_pause`
2. No passing candidate produces no order — verified by `test_no_candidate_when_no_ohlcv` (status="no_candidate", decision=None)
3. Decision contains instrument/side/quantity/rationale — verified by `test_decision_contains_required_fields`
4. Multi-cycle fixture run completes autonomously — verified by `test_multi_cycle_returns_list` (2 snapshots) and `test_multi_cycle_no_pause` (3 snapshots)
5. Candidate allowlist — verified by `test_decision_references_validated_hypothesis` and `test_cannot_select_non_validated`
6. Both accepted and no_candidate demonstrated — verified by `test_both_statuses_demonstrated`
7. `uv run pytest tests/test_orchestrator.py -v` — 23/23 passed
8. All prior tests still pass — 108/108 passed
9. Ruff check clean
10. Ruff format clean
11. Mypy clean

## Design Decisions
- **FixtureProposer** generates hypotheses dynamically from the sorted FACTOR_VOCABULARY with valid parameter defaults matching PARAM_SCHEMAS (not from the pre-built fixture hypotheses in `fixtures/hypotheses.py`, which have mismatched param names like `window` vs `lookback`).
- **Deterministic UUIDs** via `uuid5(NAMESPACE_DNS, ...)` for cycle_id, hypothesis_id, and decision_id in fixture mode.
- **Missing OHLCV data** for an instrument results in zero evaluations → `no_candidate` status (no crash).
- **CycleResult** is a plain dataclass (not Pydantic) since it holds intermediate pipeline state, not a validated contract.

## Concerns
None. Ready for T4.
