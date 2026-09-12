# Task T4 Brief: Deterministic Risk Gates and Automatic Paper Broker

## Spec Section
Technical spec → Risk gates; tasks/plan.md T4

## Scope
Add sizing, exposure, freshness, loss, cooldown, duplicate, concentration, fee, and slippage controls. Execute accepted decisions automatically in an in-memory paper broker with fee/slippage simulation and no approval pause.

## Dependencies
- T1: contracts (TradeDecision, PaperOrder, RiskGateResult)
- T3: CycleResult with decision

## Risk Gates

Implement each gate as a pure function: `(decision, state) -> RiskGateResult`

All gates are imported from `factor_atlas.config` thresholds (add new constants there).

### Required gates:

1. **factor_allowlist**: Reject if the hypothesis's factor_name is not in FACTOR_VOCABULARY. Always checked.

2. **data_freshness**: Reject if the snapshot timestamp is older than `MAX_DATA_AGE_HOURS` (default: 24) from current time. In fixture mode, compare against the decision timestamp.

3. **min_sample_size**: Reject if validation observations < MIN_OBSERVATIONS (20). Reads from the validation result.

4. **validation_threshold**: Reject if validation did not pass (passed=False).

5. **max_notional**: Reject if price * quantity > MAX_NOTIONAL (default: 10_000 USDT).

6. **max_position**: Reject if adding this order would exceed MAX_CONCURRENT_POSITIONS (default: 3) open positions.

7. **exposure_cap**: Reject if total open notional + this order's notional > MAX_EXPOSURE (default: 50_000 USDT).

8. **cooldown**: Reject if the same instrument had an order within COOLDOWN_SECONDS (default: 300).

9. **daily_loss_cap**: Reject if realized daily loss exceeds DAILY_LOSS_LIMIT (default: 2_000 USDT).

10. **duplicate_suppression**: Reject if the same event_id + instrument + side was already processed in this session.

11. **concentration_guard**: Reject if the same instrument would have more than MAX_CONCENTRATION_PER_INSTRUMENT (default: 2) open positions.

### Gate runner:
```python
def run_gates(
    decision: TradeDecision,
    validation: ValidationResult,
    snapshot: MarketSnapshot,
    broker_state: BrokerState,
    config: RiskConfig,
) -> list[RiskGateResult]:
```
Run all gates. Return results for ALL gates (not just failing). If ANY gate fails, the decision is vetoed.

### RiskConfig (dataclass):
All threshold constants in one typed config. Defaults match the values above.

## Paper Broker

### BrokerState (mutable state):
```python
@dataclass
class BrokerState:
    balance: Decimal  # current USDT balance
    positions: list[PaperOrder]  # open filled orders
    order_history: list[PaperOrder]  # all orders (filled + rejected)
    daily_pnl: Decimal  # running daily P&L
    processed_events: set[str]  # (event_id, instrument, side) tuples for dedup
    last_order_time: dict[str, datetime]  # instrument -> last order time for cooldown
```

### Execute function:
```python
def execute_paper_order(
    decision: TradeDecision,
    gate_results: list[RiskGateResult],
    broker_state: BrokerState,
    fee_rate: Decimal = Decimal("0.001"),
    slippage_bps: Decimal = Decimal("0.0005"),
) -> PaperOrder:
```

If all gates passed:
- Calculate fees = notional * fee_rate
- Calculate slippage = notional * slippage_bps
- Deduct fees + slippage from balance
- Create PaperOrder with status="filled", fill_price = decision.price
- Update broker state (add to positions, order_history, update balance, etc.)

If any gate failed:
- Create PaperOrder with status="rejected", rejection_reason = first failing gate reason
- Add to order_history but NOT positions
- Do NOT deduct from balance

### Constraints:
- Balance must never go negative. If insufficient balance, reject with reason "insufficient_balance"
- No approval pause between decision and execution
- fee_rate and slippage_bps are configurable

## Integration with Orchestrator

Add to CycleResult in orchestrator.py:
```python
gate_results: list[RiskGateResult] | None = None
order: PaperOrder | None = None
```

Update the orchestrator to run gates and execute after a decision is made.

## Config additions (add to config.py):
```python
MAX_DATA_AGE_HOURS: int = 24
MAX_NOTIONAL: str = "10000"  # Decimal string
MAX_CONCURRENT_POSITIONS: int = 3
MAX_EXPOSURE: str = "50000"  # Decimal string
COOLDOWN_SECONDS: int = 300
DAILY_LOSS_LIMIT: str = "2000"  # Decimal string
MAX_CONCENTRATION_PER_INSTRUMENT: int = 2
DEFAULT_FEE_RATE: str = "0.001"
DEFAULT_SLIPPAGE_BPS: str = "0.0005"
INITIAL_BALANCE: str = "100000"  # 100k USDT
```

## Files to create/modify
- `src/factor_atlas/risk.py` — risk gates + RiskConfig + gate runner
- `src/factor_atlas/broker.py` — BrokerState + execute_paper_order
- `src/factor_atlas/config.py` — add new constants (MODIFY)
- `src/factor_atlas/orchestrator.py` — integrate gates + broker into cycle (MODIFY)
- `tests/test_risk.py` — test each gate individually
- `tests/test_broker.py` — test execution, rejection, balance, fee math

## Acceptance Criteria
1. A passing decision is submitted automatically (no pause)
2. Any veto prevents execution and is visible in gate results
3. Balances never become negative
4. Each gate has its own test verifying pass and fail paths
5. Fee and slippage math is tested with hand-calculated values
6. Bounded quantity check (reject if quantity exceeds some maximum)
7. All prior tests still pass
8. `uv run ruff check .` clean
9. `uv run ruff format --check .` clean
10. `uv run mypy src/ tests/` clean

## Credential mode
Unused — pure fixtures, no network, no API.

## Verification commands
```bash
uv run pytest tests/test_risk.py tests/test_broker.py -v
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
```
