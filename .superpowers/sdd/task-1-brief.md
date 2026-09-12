# Task T1 Brief: Typed Contracts and Fixture Event Stream

## Spec Section
Technical spec → Core contracts (Factor hypothesis, Validation result, Paper order, Audit event)

## Scope
Define all typed contracts for FactorAtlas and create fixture event streams for deterministic testing.

## Contracts Required

### 1. MarketSnapshot
- timestamp (datetime, UTC)
- snapshot_id (UUID string)
- instrument (string, must be in allowed set: AAPLUSDT, NVDAUSDT, TSLAUSDT, METAUSDT)
- category: literal "USDT-FUTURES" 
- ohlcv data: open, high, low, close, volume (all Decimal for precision)
- source: literal "fixture" | "bitget-demo" | "bitget-signal"
- Reject unknown instruments, missing timestamps

### 2. FactorHypothesis
- hypothesis_id (UUID string)
- factor_name (string, must be in registered factor vocabulary — validated)
- parameters (dict with parameter validation per factor)
- lookback (int, positive, bounded)
- instruments (list of valid instruments)
- direction: literal "long" | "short"
- entry_rule (string)
- exit_rule (string)
- rationale (string, non-empty)
- created_at (datetime, UTC)
- Reject unknown factor names, out-of-range parameters, empty instruments

### 3. ValidationResult
- validation_id (UUID string)
- hypothesis_id (reference to FactorHypothesis)
- snapshot_id (reference to MarketSnapshot)
- train_window (tuple of start/end dates)
- test_window (tuple of start/end dates)
- observations (int, positive)
- metrics: a nested model with:
  - total_return (float, labeled "observed")
  - sharpe_ratio (float, labeled "observed")
  - sortino_ratio (float, labeled "observed")
  - max_drawdown (float, labeled "observed")
  - turnover (float, labeled "observed")
  - fees (float, labeled "estimated")
  - slippage (float, labeled "estimated")
  - win_rate (float, labeled "observed")
- Each metric carries a label: "observed" | "estimated" | "targeted"
- passed (bool)
- rejection_reasons (list of strings, empty when passed)
- Reject if observations < minimum sample size threshold (configurable, default 20)

### 4. TradeDecision
- decision_id (UUID string)
- cycle_id (UUID string)
- hypothesis_id (reference)
- instrument (valid instrument)
- side: literal "buy" | "sell"
- quantity (Decimal, positive, bounded)
- price (Decimal, positive)
- rationale (string, non-empty)
- timestamp (datetime, UTC)

### 5. PaperOrder
- order_id (UUID string)
- decision_id (reference to TradeDecision)
- event_id (reference)
- timestamp (datetime, UTC)
- instrument (valid instrument)
- category: literal "USDT-FUTURES"
- side: literal "buy" | "sell"
- price (Decimal, positive)
- quantity (Decimal, positive)
- notional (Decimal = price * quantity)
- pre_balance (Decimal, non-negative)
- post_balance (Decimal, non-negative)
- fees (Decimal, non-negative, labeled "estimated")
- slippage (Decimal, non-negative, labeled "estimated")
- status: literal "filled" | "rejected" | "error"
- rejection_reason (optional string)
- fill_price (optional Decimal)

### 6. AuditEvent
- event_id (UUID string)
- cycle_id (UUID string)
- stage: literal "observe" | "propose" | "evaluate" | "decide" | "gate" | "execute" | "learn"
- timestamp (datetime, UTC)
- parent_event_id (optional UUID string — links to prior stage)
- payload (dict — stage-specific data)
- Append-only: events form a chain via parent_event_id

### 7. RiskGateResult
- gate_name (string)
- passed (bool)
- reason (string — always present, explains pass or fail)
- value (optional float — the measured value)
- threshold (optional float — the limit)

## Fixtures Required

Create deterministic fixture data under `src/factor_atlas/fixtures/`:
- `events.py`: at least 2 fixture market snapshots (one that leads to an accepted cycle, one that leads to rejection)
- `hypotheses.py`: at least 2 fixture hypotheses (one valid, one invalid/rejected)
- Pre-built OHLCV data series (30+ bars) for AAPLUSDT fixture

All fixtures must be:
- Credential-free
- Deterministic (same output every time)
- Importable as Python objects

## Allowed instrument universe (constant)
```python
INSTRUMENTS = frozenset({"AAPLUSDT", "NVDAUSDT", "TSLAUSDT", "METAUSDT"})
CATEGORY = "USDT-FUTURES"
```

## Files to create
- `src/factor_atlas/__init__.py`
- `src/factor_atlas/contracts.py` — all Pydantic models
- `src/factor_atlas/config.py` — constants (instruments, category, thresholds)
- `src/factor_atlas/fixtures/__init__.py`
- `src/factor_atlas/fixtures/events.py` — fixture market snapshots and OHLCV
- `src/factor_atlas/fixtures/hypotheses.py` — fixture hypotheses
- `tests/__init__.py`
- `tests/test_contracts.py` — validation tests

## Acceptance Criteria
1. Invalid IDs, instruments, timestamps, quantities, and factor names fail validation with clear error messages
2. All fixtures are credential-free and importable
3. Fixture serialization is deterministic (same JSON output every run)
4. `uv run pytest tests/test_contracts.py` passes
5. `uv run ruff check .` clean
6. `uv run ruff format --check .` clean
7. `uv run mypy src/ tests/` clean (or only expected library stubs)

## Credential mode
Unused — pure fixtures, no network, no API.

## Verification commands
```bash
uv run pytest tests/test_contracts.py -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
```
