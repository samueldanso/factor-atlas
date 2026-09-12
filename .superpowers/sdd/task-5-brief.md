# Task T5 Brief: Auditable Cycles and Deterministic Replay

## Spec Section
Technical spec → Audit event (append-only JSON Lines); tasks/plan.md T5

## Scope
Write append-only JSONL records linking event, hypothesis, validation, decision, gates, execution/rejection, and next-cycle summary. Implement deterministic replay verification.

## Dependencies
- T1: AuditEvent contract
- T3: CycleResult
- T4: RiskGateResult, PaperOrder, BrokerState

## Audit System

### AuditLogger
```python
class AuditLogger:
    def __init__(self, output_path: Path | None = None):
        """If output_path is None, log to in-memory buffer only."""
    
    def log_cycle(self, cycle_result: CycleResult) -> list[AuditEvent]:
        """Convert a CycleResult into a chain of AuditEvents and persist them."""
    
    def get_events(self) -> list[AuditEvent]:
        """Return all logged events."""
    
    def flush(self) -> None:
        """Write any buffered events to disk (JSONL)."""
```

### Event chain per cycle:
Each cycle produces a chain of AuditEvents linked by parent_event_id:

1. **observe** — payload: snapshot_id, instrument, timestamp, source
2. **propose** — payload: hypothesis_ids, count, factor_names; parent = observe
3. **evaluate** — payload: for each hypothesis: hypothesis_id, passed, rejection_reasons, sharpe, drawdown; parent = propose
4. **decide** — payload: decision_id (or null), selected_hypothesis_id (or null), rationale, status; parent = evaluate
5. **gate** — payload: gate_results (list of {gate_name, passed, reason}), all_passed; parent = decide
6. **execute** — payload: order_id, status, fill_price, fees, slippage, pre_balance, post_balance; OR rejection_reason; parent = gate
7. **learn** — payload: cycle_summary with cycle_id, status, instrument, side, pnl_estimate; parent = execute

### JSONL format:
Each line is a JSON object representing one AuditEvent serialized via `.model_dump(mode="json")`.

### Chain integrity:
- Every event except the first in a cycle has a parent_event_id
- Events within a cycle share the same cycle_id
- The chain is: observe → propose → evaluate → decide → gate → execute → learn

## Replay System

### Replay verifier:
```python
def verify_replay(
    snapshots: list[MarketSnapshot],
    ohlcv_data: dict[str, pd.DataFrame],
    proposer: Proposer,
    decision_provider: DecisionProvider,
    config: RiskConfig,
    original_events: list[AuditEvent],
) -> ReplayResult:
    """Re-run the same inputs and compare audit output for deterministic replay."""
```

### ReplayResult:
```python
@dataclass
class ReplayResult:
    matches: bool  # True if replay produces identical audit events
    original_count: int
    replay_count: int
    first_mismatch_index: int | None  # index of first differing event, if any
    mismatch_detail: str | None  # human-readable description
```

### Replay contract:
- Same snapshots + same OHLCV + same config → same audit events (ignoring event_id UUIDs and timestamps)
- Compare by: cycle_id, stage, payload content
- For deterministic comparison, use uuid5 seeded from cycle inputs

## Files to create/modify
- `src/factor_atlas/audit.py` — AuditLogger
- `src/factor_atlas/replay.py` — verify_replay, ReplayResult
- `src/factor_atlas/orchestrator.py` — (MODIFY) integrate AuditLogger into MultiCycleRunner
- `tests/test_audit.py` — JSONL output, chain integrity, all stages present
- `tests/test_replay.py` — deterministic replay verification

## Acceptance Criteria
1. One accepted and one rejected cycle are fully logged with all 7 stages
2. JSONL output is valid (each line parses as valid JSON)
3. Event chain integrity: parent_event_id links form a connected chain per cycle
4. Repeated input/configuration produces identical replay output
5. AuditLogger works both in-memory and to file
6. All prior tests still pass
7. `uv run ruff check .` clean
8. `uv run ruff format --check .` clean
9. `uv run mypy src/ tests/` clean

## Credential mode
Unused — pure fixtures, no network, no API.

## Verification commands
```bash
uv run pytest tests/test_audit.py tests/test_replay.py -v
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
```
