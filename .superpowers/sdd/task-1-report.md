# Task T1 Report: Typed Contracts and Fixture Event Stream

## Status: COMPLETE

## Commit

`2066c49` — `feat(contracts): add typed schemas and fixture events`

## Files Created (10)

| File | Purpose |
|------|---------|
| `src/factor_atlas/__init__.py` | Package root with `__all__` exports |
| `src/factor_atlas/config.py` | Constants: instruments, category, factor vocabulary, thresholds |
| `src/factor_atlas/contracts.py` | 9 Pydantic v2 models (all frozen, Decimal-based financials) |
| `src/factor_atlas/fixtures/__init__.py` | Fixture package re-exports |
| `src/factor_atlas/fixtures/events.py` | 30-bar AAPLUSDT OHLCV series + 2 cycle snapshots |
| `src/factor_atlas/fixtures/hypotheses.py` | 2 fixture hypotheses (valid + rejected) |
| `tests/__init__.py` | Test package marker |
| `tests/test_contracts.py` | 39 validation tests |
| `pyproject.toml` | Added build system, mypy, pytest, ruff config |
| `uv.lock` | Updated lockfile with mypy dependency |

## Contracts Implemented

1. **MarketSnapshot** — OHLCV bar with instrument/UTC/Decimal validation
2. **FactorHypothesis** — Factor proposal with vocabulary + lookback bounds
3. **LabeledMetric** — Value + label ("observed" / "estimated" / "targeted")
4. **ValidationMetrics** — Nested metrics container
5. **ValidationResult** — Walk-forward result with min-observations gate
6. **TradeDecision** — Agent decision with positive price/quantity enforcement
7. **PaperOrder** — Simulated execution with notional = price × quantity check
8. **RiskGateResult** — Gate pass/fail with reason
9. **AuditEvent** — Append-only audit log entry with stage validation

## Verification Results

```
uv run pytest tests/test_contracts.py -v   → 39 passed in 0.08s
uv run ruff check .                        → All checks passed!
uv run ruff format --check .               → 21 files already formatted
uv run mypy src/ tests/                    → Success: no issues found in 8 source files
```

## Test Coverage Summary

- Valid construction of all 9 contracts
- Invalid instrument rejection (Literal + validator)
- Invalid factor name rejection
- Missing/naive UTC timestamp rejection
- Negative price/quantity rejection
- Empty required fields (rationale, instruments, IDs)
- Out-of-range lookback (0 and 999)
- Observations below minimum threshold
- Notional mismatch detection
- Metric label validation
- Model immutability (frozen)
- Fixture deterministic serialization (JSON round-trip stability)
- Fixture UUID determinism (uuid5 reproducibility)
- Audit event chaining via parent_event_id

## Design Decisions

1. **Literal types for enums** — Used `Literal` unions instead of Python `enum.Enum` to get Pydantic's native validation without custom serialization.
2. **`frozen=True` on all models** — Immutability is enforced at the Pydantic level per the brief.
3. **`uuid5` for fixture IDs** — Deterministic UUIDs seeded from `NAMESPACE_DNS` + a fixed name string, ensuring identical IDs across runs.
4. **Validators on Literal fields** — Pydantic's `Literal` catches type mismatches before custom validators run, so both layers are present but Literal is the first gate.
5. **`category` defaults** — `CATEGORY` constant is the default; the `# type: ignore[assignment]` on category fields is the one suppression — Pydantic accepts the string but mypy sees a `str` assigned to `Literal`.

## Concerns

None. All acceptance criteria met. Ready for T2.
