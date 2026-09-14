### Task 3: New risk gates (balance_check, pending_order_check)

**Files:**
- Modify: `src/factor_atlas/risk.py`
- Modify: `tests/test_risk.py`

**Interfaces:**
- Consumes: `ExchangeState` from `factor_atlas.exchange`, `TradeDecision` from `factor_atlas.contracts`, `RiskConfig` from `factor_atlas.risk`
- Produces:
  - `gate_balance_check(decision, *, exchange_state, config, **_kw) -> RiskGateResult`
  - `gate_pending_order_check(decision, *, exchange_state, **_kw) -> RiskGateResult`
  - Updated `run_gates()` signature accepts optional `exchange_state: ExchangeState | None` kwarg
  - Gates 13 and 14 are skipped when `exchange_state is None` (fixture mode)

- [ ] **Step 1: Write tests for the two new gates**

```python
# Add to tests/test_risk.py — append these test classes


class TestGateBalanceCheck:
    def test_passes_when_balance_sufficient(self) -> None:
        from factor_atlas.exchange import ExchangeState

        ex = ExchangeState(balance=Decimal("50000"))
        result = gate_balance_check(
            _decision(price=Decimal("100"), quantity=Decimal("5")),
            exchange_state=ex,
            config=RiskConfig(),
        )
        assert result.passed is True
        assert result.gate_name == "balance_check"

    def test_fails_when_balance_insufficient(self) -> None:
        from factor_atlas.exchange import ExchangeState

        ex = ExchangeState(balance=Decimal("100"))
        result = gate_balance_check(
            _decision(price=Decimal("100"), quantity=Decimal("50")),
            exchange_state=ex,
            config=RiskConfig(),
        )
        assert result.passed is False


class TestGatePendingOrderCheck:
    def test_passes_when_no_pending_orders(self) -> None:
        from factor_atlas.exchange import ExchangeState

        ex = ExchangeState(pending_orders=[])
        result = gate_pending_order_check(_decision(), exchange_state=ex)
        assert result.passed is True

    def test_fails_when_conflicting_pending_order(self) -> None:
        from factor_atlas.exchange import ExchangeOrder, ExchangeState

        ex = ExchangeState(
            pending_orders=[
                ExchangeOrder(
                    order_id="123",
                    symbol="RAAPLUSDT",
                    side="buy",
                    price=Decimal("330"),
                    qty=Decimal("1"),
                    status="open",
                )
            ]
        )
        result = gate_pending_order_check(_decision(), exchange_state=ex)
        assert result.passed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_risk.py::TestGateBalanceCheck -v`
Expected: FAIL with `ImportError: cannot import name 'gate_balance_check'`

- [ ] **Step 3: Implement the two new gates**

Add to `src/factor_atlas/risk.py` after the existing `gate_max_quantity` function:

```python
def gate_balance_check(
    decision: TradeDecision,
    *,
    exchange_state: object | None = None,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if available exchange balance < order notional."""
    if exchange_state is None:
        return RiskGateResult(
            gate_name="balance_check",
            passed=True,
            reason="skipped: no exchange state (fixture mode)",
        )
    from factor_atlas.exchange import ExchangeState

    assert isinstance(exchange_state, ExchangeState)
    notional = decision.price * decision.quantity
    passed = exchange_state.balance >= notional
    return RiskGateResult(
        gate_name="balance_check",
        passed=passed,
        reason=(
            f"balance {exchange_state.balance} >= notional {notional}"
            if passed
            else f"balance {exchange_state.balance} < notional {notional}"
        ),
        value=float(exchange_state.balance),
        threshold=float(notional),
    )


def gate_pending_order_check(
    decision: TradeDecision,
    *,
    exchange_state: object | None = None,
    **_kw: object,
) -> RiskGateResult:
    """Reject if a pending order exists for the same instrument."""
    if exchange_state is None:
        return RiskGateResult(
            gate_name="pending_order_check",
            passed=True,
            reason="skipped: no exchange state (fixture mode)",
        )
    from factor_atlas.exchange import ExchangeState

    assert isinstance(exchange_state, ExchangeState)
    conflicting = [
        o for o in exchange_state.pending_orders if o.symbol == decision.instrument
    ]
    passed = len(conflicting) == 0
    return RiskGateResult(
        gate_name="pending_order_check",
        passed=passed,
        reason=(
            "no pending orders for instrument"
            if passed
            else f"{len(conflicting)} pending order(s) for {decision.instrument}"
        ),
        value=float(len(conflicting)),
        threshold=0.0,
    )
```

Then update `_GATE_ORDER` and `_GATE_FNS`:

```python
_GATE_ORDER: list[str] = [
    "factor_allowlist",
    "data_freshness",
    "min_sample_size",
    "validation_threshold",
    "max_notional",
    "max_position",
    "exposure_cap",
    "cooldown",
    "daily_loss_cap",
    "duplicate_suppression",
    "concentration_guard",
    "max_quantity",
    "balance_check",
    "pending_order_check",
]

_GATE_FNS = {
    # ... existing entries ...
    "balance_check": gate_balance_check,
    "pending_order_check": gate_pending_order_check,
}
```

Update `run_gates` signature to accept `exchange_state`:

```python
def run_gates(
    decision: TradeDecision,
    validation: ValidationResult,
    snapshot: MarketSnapshot,
    broker_state: BrokerState,
    config: RiskConfig,
    *,
    factor_name: str = "",
    event_id: str = "",
    exchange_state: object | None = None,
) -> list[RiskGateResult]:
    kwargs = {
        "decision": decision,
        "validation": validation,
        "snapshot": snapshot,
        "broker_state": broker_state,
        "config": config,
        "factor_name": factor_name,
        "event_id": event_id or decision.decision_id,
        "exchange_state": exchange_state,
    }
    # ... rest unchanged ...
```

Update `__all__` to include the new gate functions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_risk.py -v`
Expected: all tests PASS (existing gates still pass since exchange_state defaults to None)

- [ ] **Step 5: Run full suite and lint**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/risk.py tests/test_risk.py
git commit -m "feat(risk): add balance_check and pending_order_check exchange gates"
```

---
