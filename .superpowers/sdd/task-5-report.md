# Task T5 Report: Auditable Cycles and Deterministic Replay

## Status: COMPLETE

## Commit
`32f436f` — `feat(audit): add JSONL audit logger and deterministic replay`

## Files Created/Modified
- `src/factor_atlas/audit.py` — AuditLogger with in-memory + JSONL file output, 7-stage chain builder
- `src/factor_atlas/replay.py` — ReplayResult dataclass, verify_replay comparing event signatures
- `src/factor_atlas/orchestrator.py` — (MODIFIED) added optional `audit_logger` param to `run_cycles`
- `tests/test_audit.py` — 24 tests: in-memory logging, chain integrity, accepted/rejected payloads, JSONL output, orchestrator integration
- `tests/test_replay.py` — 6 tests: deterministic replay for accepted/rejected/multi cycles, count mismatch detection, idempotency

## Test Summary
- **190 total tests pass** (160 existing + 30 new)
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean
- `uv run mypy src/ tests/` — clean, no issues in 24 source files

## Acceptance Criteria Verified
1. Accepted and rejected cycles both produce all 7 stages (observe→propose→evaluate→decide→gate→execute→learn)
2. JSONL output: each line parses as valid JSON, round-trips to AuditEvent
3. Chain integrity: parent_event_id links form a connected chain per cycle, first event has no parent
4. Deterministic replay: same inputs produce identical event signatures (ignoring UUIDs/timestamps)
5. AuditLogger works both in-memory (None path) and to file
6. All 160 prior tests still pass
7. Ruff check clean
8. Ruff format clean
9. Mypy clean

## Design Decisions
- Event IDs are uuid5-deterministic from `cycle_id + stage`, making chains reproducible
- Replay comparison uses `_event_signature()` extracting (cycle_id, stage, payload) — ignoring event_id, timestamp, parent_event_id which are non-deterministic or derived
- AuditLogger appends to file on each `log_cycle` call; `flush()` overwrites with full buffer for recovery
- Orchestrator change is backwards-compatible: `audit_logger=None` default preserves all existing call sites

## Concerns
- None. All acceptance criteria met, no type suppressions, no credential usage.
