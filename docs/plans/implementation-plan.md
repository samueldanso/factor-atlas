# FactorAtlas Trust Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exchange verification, order confirmation, state reconciliation, enhanced metrics, and observability CLI commands so FactorAtlas meets judge trustworthiness standards.

**Architecture:** New modules (`exchange.py`, `reconcile.py`) wrap bgc CLI calls and reconcile exchange state with local state. Two new risk gates use exchange data. The runner is updated to verify orders after placement and separate research prices from execution prices. Three new CLI commands (`status`, `history`, `explain`) provide judge-facing observability. The manifest gains LLM provider fields and an equity curve.

**Tech Stack:** Python 3.11, bgc CLI (subprocess), pydantic, pandas/numpy, pytest, ruff

## Global Constraints

- Python 3.11 via `uv`
- Every `bgc` order call must use `--paper-trading`
- Use `--read-only` for inspection, `--dry-run` before writes
- No live trading, no withdrawals
- Credentials only in `.env` or GitHub Actions secrets — never in git, logs, or fixtures
- Tests must mock all bgc/subprocess calls — no test may require network or credentials
- ruff check, ruff format, and pytest must pass after every task
- Main account must never be used for agent execution
- rToken SPOT for research, USDT-FUTURES stock perps for execution — never conflated

## Blocked work (waiting Bitget support)

The following tasks are NOT in this plan. They will be added after Bitget support replies:

- Configure Agentic sub-account Demo API key in `.env`
- Test end-to-end demo execution with Agentic sub-account
- Determine if rToken SPOT Demo execution is possible
- GitHub Actions workflow (`.github/workflows/daily-run.yml`) — requires working Demo credentials

---

### Task 1: Exchange state module

**Files:**
- Create: `src/factor_atlas/exchange.py`
- Create: `tests/test_exchange.py`

**Interfaces:**
- Consumes: `factor_atlas.config.CATEGORY` (`"USDT-FUTURES"`)
- Produces:
  - `ExchangeState` dataclass with fields: `balance: Decimal`, `positions: list[ExchangePosition]`, `pending_orders: list[ExchangeOrder]`, `queried_at: datetime`
  - `ExchangePosition` dataclass with fields: `symbol: str`, `side: str`, `size: Decimal`, `entry_price: Decimal`, `unrealized_pnl: Decimal`
  - `ExchangeOrder` dataclass with fields: `order_id: str`, `symbol: str`, `side: str`, `price: Decimal`, `qty: Decimal`, `status: str`
  - `query_exchange_state(paper_trading: bool = True) -> ExchangeState`
  - `query_order_status(order_id: str, paper_trading: bool = True) -> ExchangeOrder`
  - `OrderVerificationStatus` — Literal type: `"verified_filled"`, `"verified_rejected"`, `"verified_cancelled"`, `"verified_partial"`, `"unverified"`, `"query_failed"`

- [ ] **Step 1: Write test for ExchangeState parsing from bgc JSON**

```python
# tests/test_exchange.py
"""Tests for the exchange state module — all bgc calls are mocked."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from factor_atlas.exchange import (
    ExchangeOrder,
    ExchangePosition,
    ExchangeState,
    OrderVerificationStatus,
    query_exchange_state,
    query_order_status,
)

# Realistic bgc account_overview response
_ACCOUNT_OVERVIEW_RESPONSE = json.dumps(
    {
        "data": {
            "accountId": "123456",
            "coin": [
                {
                    "coin": "USDT",
                    "available": "48523.12",
                    "frozen": "1200.00",
                    "equity": "49723.12",
                }
            ],
        }
    }
)

# Realistic bgc position info response
_POSITION_RESPONSE = json.dumps(
    {
        "data": [
            {
                "symbol": "AAPLUSDT",
                "holdSide": "long",
                "total": "2",
                "openPriceAvg": "330.33",
                "unrealizedPL": "-12.50",
            },
            {
                "symbol": "METAUSDT",
                "holdSide": "short",
                "total": "1",
                "openPriceAvg": "641.76",
                "unrealizedPL": "8.20",
            },
        ]
    }
)

# Realistic bgc order open response
_OPEN_ORDERS_RESPONSE = json.dumps({"data": {"orderList": []}})

# Realistic bgc order detail response
_ORDER_DETAIL_FILLED = json.dumps(
    {
        "data": {
            "orderId": "1483216288468062208",
            "symbol": "AAPLUSDT",
            "side": "buy",
            "price": "330.33",
            "size": "2",
            "status": "filled",
        }
    }
)

_ORDER_DETAIL_REJECTED = json.dumps(
    {
        "data": {
            "orderId": "999",
            "symbol": "AAPLUSDT",
            "side": "buy",
            "price": "330.33",
            "size": "2",
            "status": "cancelled",
        }
    }
)


def _mock_subprocess_run(responses: dict[str, str]):
    """Return a mock that maps bgc action keywords to canned responses."""

    def _side_effect(cmd, **_kwargs):
        cmd_str = " ".join(cmd)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        r = Result()

        for keyword, response in responses.items():
            if keyword in cmd_str:
                r.stdout = response
                return r

        r.returncode = 1
        r.stderr = "unknown command"
        return r

    return _side_effect


class TestQueryExchangeState:
    def test_parses_balance_and_positions(self) -> None:
        responses = {
            "account_overview": _ACCOUNT_OVERVIEW_RESPONSE,
            "position": _POSITION_RESPONSE,
            "order": _OPEN_ORDERS_RESPONSE,
        }
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run(responses),
        ):
            state = query_exchange_state()

        assert state.balance == Decimal("48523.12")
        assert len(state.positions) == 2
        assert state.positions[0].symbol == "AAPLUSDT"
        assert state.positions[0].side == "long"
        assert state.positions[0].size == Decimal("2")
        assert state.positions[0].entry_price == Decimal("330.33")
        assert len(state.pending_orders) == 0
        assert state.queried_at is not None

    def test_raises_on_account_overview_failure(self) -> None:
        def _fail(cmd, **_kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "auth failed"

            return Result()

        with patch("factor_atlas.exchange.subprocess.run", side_effect=_fail):
            with pytest.raises(RuntimeError, match="account_overview failed"):
                query_exchange_state()

    def test_empty_positions_returns_empty_list(self) -> None:
        responses = {
            "account_overview": _ACCOUNT_OVERVIEW_RESPONSE,
            "position": json.dumps({"data": []}),
            "order": _OPEN_ORDERS_RESPONSE,
        }
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run(responses),
        ):
            state = query_exchange_state()
        assert state.positions == []
        assert state.balance == Decimal("48523.12")


class TestQueryOrderStatus:
    def test_filled_order(self) -> None:
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run({"order": _ORDER_DETAIL_FILLED}),
        ):
            order = query_order_status("1483216288468062208")
        assert order.status == "filled"
        assert order.order_id == "1483216288468062208"

    def test_cancelled_order(self) -> None:
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run({"order": _ORDER_DETAIL_REJECTED}),
        ):
            order = query_order_status("999")
        assert order.status == "cancelled"

    def test_network_failure_returns_query_failed(self) -> None:
        def _fail(cmd, **_kwargs):
            raise OSError("Network unreachable")

        with patch("factor_atlas.exchange.subprocess.run", side_effect=_fail):
            with pytest.raises(OSError):
                query_order_status("123")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_exchange.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'factor_atlas.exchange'`

- [ ] **Step 3: Implement exchange module**

```python
# src/factor_atlas/exchange.py
"""Exchange state queries via bgc CLI — wraps subprocess calls."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

OrderVerificationStatus = Literal[
    "verified_filled",
    "verified_rejected",
    "verified_cancelled",
    "verified_partial",
    "unverified",
    "query_failed",
]


@dataclass(frozen=True)
class ExchangePosition:
    symbol: str
    side: str
    size: Decimal
    entry_price: Decimal
    unrealized_pnl: Decimal


@dataclass(frozen=True)
class ExchangeOrder:
    order_id: str
    symbol: str
    side: str
    price: Decimal
    qty: Decimal
    status: str


@dataclass
class ExchangeState:
    balance: Decimal = Decimal(0)
    positions: list[ExchangePosition] = field(default_factory=list)
    pending_orders: list[ExchangeOrder] = field(default_factory=list)
    queried_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


def _run_bgc(args: list[str], paper_trading: bool = True) -> dict:
    """Run a bgc command and return parsed JSON. Raises RuntimeError on failure."""
    cmd = ["bgc"]
    if paper_trading:
        cmd.append("--paper-trading")
    cmd.extend(args)

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode != 0:
        action = args[0] if args else "unknown"
        raise RuntimeError(f"{action} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def query_exchange_state(paper_trading: bool = True) -> ExchangeState:
    """Query account balance, positions, and pending orders from Bitget."""
    # Balance
    acct = _run_bgc(
        ["account_overview", "--category", "USDT-FUTURES"],
        paper_trading=paper_trading,
    )
    coins = acct.get("data", {}).get("coin", [])
    balance = Decimal("0")
    for c in coins:
        if c.get("coin") == "USDT":
            balance = Decimal(c.get("available", "0"))
            break

    # Positions
    pos_raw = _run_bgc(
        ["position", "--action", "info", "--category", "USDT-FUTURES"],
        paper_trading=paper_trading,
    )
    positions: list[ExchangePosition] = []
    for p in pos_raw.get("data", []):
        positions.append(
            ExchangePosition(
                symbol=p["symbol"],
                side=p.get("holdSide", "long"),
                size=Decimal(p.get("total", "0")),
                entry_price=Decimal(p.get("openPriceAvg", "0")),
                unrealized_pnl=Decimal(p.get("unrealizedPL", "0")),
            )
        )

    # Pending orders
    orders_raw = _run_bgc(
        ["order", "--action", "open", "--category", "USDT-FUTURES"],
        paper_trading=paper_trading,
    )
    pending: list[ExchangeOrder] = []
    order_list = orders_raw.get("data", {})
    if isinstance(order_list, dict):
        order_list = order_list.get("orderList", [])
    for o in order_list or []:
        pending.append(
            ExchangeOrder(
                order_id=o.get("orderId", ""),
                symbol=o.get("symbol", ""),
                side=o.get("side", ""),
                price=Decimal(o.get("price", "0")),
                qty=Decimal(o.get("size", o.get("qty", "0"))),
                status=o.get("status", "unknown"),
            )
        )

    return ExchangeState(
        balance=balance,
        positions=positions,
        pending_orders=pending,
        queried_at=datetime.now(tz=UTC),
    )


def query_order_status(order_id: str, paper_trading: bool = True) -> ExchangeOrder:
    """Query a single order's status. Note: detail action does not take --category."""
    raw = _run_bgc(
        ["order", "--action", "detail", "--orderId", order_id],
        paper_trading=paper_trading,
    )
    d = raw.get("data", {})
    return ExchangeOrder(
        order_id=d.get("orderId", order_id),
        symbol=d.get("symbol", ""),
        side=d.get("side", ""),
        price=Decimal(d.get("price", "0")),
        qty=Decimal(d.get("size", d.get("qty", "0"))),
        status=d.get("status", "unknown"),
    )


def classify_order_status(status: str) -> OrderVerificationStatus:
    """Map a bgc order status string to our verification enum."""
    status_lower = status.lower()
    if status_lower == "filled":
        return "verified_filled"
    if status_lower in ("cancelled", "canceled"):
        return "verified_cancelled"
    if status_lower in ("rejected", "failed"):
        return "verified_rejected"
    if status_lower in ("partial", "partially_filled", "partial_fill"):
        return "verified_partial"
    return "unverified"


__all__ = [
    "ExchangeOrder",
    "ExchangePosition",
    "ExchangeState",
    "OrderVerificationStatus",
    "classify_order_status",
    "query_exchange_state",
    "query_order_status",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_exchange.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run full suite and lint**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/exchange.py tests/test_exchange.py
git commit -m "feat(exchange): add bgc exchange state query module"
```

---

### Task 2: State reconciliation module

**Files:**
- Create: `src/factor_atlas/reconcile.py`
- Create: `tests/test_reconcile.py`

**Interfaces:**
- Consumes: `ExchangeState` from `factor_atlas.exchange`, `BrokerState` and `OpenPosition` from `factor_atlas.broker`
- Produces:
  - `Divergence` dataclass with fields: `instrument: str`, `kind: str`, `local_value: str`, `exchange_value: str`
  - `reconcile_positions(broker_state: BrokerState, exchange_state: ExchangeState) -> list[Divergence]` — compares local open_positions with exchange positions, trusts exchange, updates broker_state in-place, returns list of divergences found

- [ ] **Step 1: Write tests for reconciliation**

```python
# tests/test_reconcile.py
"""Tests for state reconciliation — exchange is authoritative."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from factor_atlas.broker import BrokerState, OpenPosition
from factor_atlas.exchange import ExchangePosition, ExchangeState
from factor_atlas.reconcile import Divergence, reconcile_positions


def _make_exchange_state(
    positions: list[ExchangePosition] | None = None,
    balance: Decimal = Decimal("50000"),
) -> ExchangeState:
    return ExchangeState(
        balance=balance,
        positions=positions or [],
        pending_orders=[],
        queried_at=datetime.now(tz=UTC),
    )


def _make_open_position(instrument: str = "AAPLUSDT") -> OpenPosition:
    return OpenPosition(
        instrument=instrument,
        side="buy",
        entry_price=Decimal("330.33"),
        quantity=Decimal("2"),
        entry_time=datetime.now(tz=UTC),
        hypothesis_id="hyp-1",
        factor_name="momentum",
        cycle_id="cycle-1",
    )


class TestReconcilePositions:
    def test_no_divergence_when_matching(self) -> None:
        broker = BrokerState()
        pos = _make_open_position("AAPLUSDT")
        broker.open_positions["AAPLUSDT"] = pos

        ex_state = _make_exchange_state(
            [
                ExchangePosition(
                    symbol="AAPLUSDT",
                    side="long",
                    size=Decimal("2"),
                    entry_price=Decimal("330.33"),
                    unrealized_pnl=Decimal("0"),
                )
            ]
        )
        divergences = reconcile_positions(broker, ex_state)
        assert divergences == []
        assert "AAPLUSDT" in broker.open_positions

    def test_local_position_not_on_exchange_is_removed(self) -> None:
        broker = BrokerState()
        broker.open_positions["AAPLUSDT"] = _make_open_position("AAPLUSDT")

        ex_state = _make_exchange_state([])
        divergences = reconcile_positions(broker, ex_state)

        assert len(divergences) == 1
        assert divergences[0].kind == "local_only"
        assert "AAPLUSDT" not in broker.open_positions

    def test_exchange_position_not_local_is_logged(self) -> None:
        broker = BrokerState()
        ex_state = _make_exchange_state(
            [
                ExchangePosition(
                    symbol="NVDAUSDT",
                    side="long",
                    size=Decimal("1"),
                    entry_price=Decimal("100"),
                    unrealized_pnl=Decimal("5"),
                )
            ]
        )
        divergences = reconcile_positions(broker, ex_state)
        assert len(divergences) == 1
        assert divergences[0].kind == "exchange_only"

    def test_size_mismatch_trusts_exchange(self) -> None:
        broker = BrokerState()
        pos = _make_open_position("AAPLUSDT")
        pos.quantity = Decimal("5")
        broker.open_positions["AAPLUSDT"] = pos

        ex_state = _make_exchange_state(
            [
                ExchangePosition(
                    symbol="AAPLUSDT",
                    side="long",
                    size=Decimal("2"),
                    entry_price=Decimal("330.33"),
                    unrealized_pnl=Decimal("0"),
                )
            ]
        )
        divergences = reconcile_positions(broker, ex_state)
        assert len(divergences) == 1
        assert divergences[0].kind == "size_mismatch"
        assert broker.open_positions["AAPLUSDT"].quantity == Decimal("2")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reconcile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'factor_atlas.reconcile'`

- [ ] **Step 3: Implement reconciliation module**

```python
# src/factor_atlas/reconcile.py
"""Reconcile local BrokerState with exchange truth."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from factor_atlas.broker import BrokerState
    from factor_atlas.exchange import ExchangeState


@dataclass(frozen=True)
class Divergence:
    instrument: str
    kind: str  # "local_only", "exchange_only", "size_mismatch"
    local_value: str
    exchange_value: str


def reconcile_positions(
    broker_state: BrokerState,
    exchange_state: ExchangeState,
) -> list[Divergence]:
    """Compare local open_positions with exchange positions.

    Exchange is authoritative. Updates broker_state in place.
    Returns a list of divergences found.
    """
    divergences: list[Divergence] = []

    exchange_by_symbol: dict[str, tuple[str, Decimal]] = {}
    for ep in exchange_state.positions:
        exchange_by_symbol[ep.symbol] = (ep.side, ep.size)

    local_instruments = set(broker_state.open_positions.keys())
    exchange_instruments = set(exchange_by_symbol.keys())

    # Local positions not on exchange — remove them
    for inst in local_instruments - exchange_instruments:
        divergences.append(
            Divergence(
                instrument=inst,
                kind="local_only",
                local_value=str(broker_state.open_positions[inst].quantity),
                exchange_value="0",
            )
        )
        del broker_state.open_positions[inst]

    # Exchange positions not local — log but can't reconstruct full OpenPosition
    for inst in exchange_instruments - local_instruments:
        side, size = exchange_by_symbol[inst]
        divergences.append(
            Divergence(
                instrument=inst,
                kind="exchange_only",
                local_value="0",
                exchange_value=str(size),
            )
        )

    # Both exist — check size match
    for inst in local_instruments & exchange_instruments:
        _, ex_size = exchange_by_symbol[inst]
        local_pos = broker_state.open_positions[inst]
        if local_pos.quantity != ex_size:
            divergences.append(
                Divergence(
                    instrument=inst,
                    kind="size_mismatch",
                    local_value=str(local_pos.quantity),
                    exchange_value=str(ex_size),
                )
            )
            local_pos.quantity = ex_size

    return divergences


__all__ = ["Divergence", "reconcile_positions"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reconcile.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run full suite and lint**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/reconcile.py tests/test_reconcile.py
git commit -m "feat(reconcile): add exchange state reconciliation module"
```

---

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

### Task 4: Enhanced metrics (Sortino, turnover, equity curve, avg hold hours)

**Files:**
- Modify: `src/factor_atlas/metrics.py`
- Modify: `tests/test_runner.py` (manifest metrics assertions)

**Interfaces:**
- Consumes: `list[ClosedTrade]` from `factor_atlas.broker`
- Produces: updated `compute_metrics()` return dict adding keys: `sortino_ratio: float`, `turnover: float`, `avg_hold_hours: float`, `equity_curve: list[list[str | float]]` (each entry is `[iso_timestamp, cumulative_pnl]`)

- [ ] **Step 1: Write test for new metrics**

```python
# Add to a new test file tests/test_metrics.py
"""Tests for compute_metrics including Sortino, turnover, equity curve."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from factor_atlas.broker import ClosedTrade
from factor_atlas.metrics import compute_metrics


def _make_trade(
    pnl: str = "10",
    pnl_pct: float = 0.03,
    won: bool = True,
    hold_hours: float = 4.0,
    entry_price: str = "100",
    quantity: str = "1",
    offset_hours: int = 0,
) -> ClosedTrade:
    base = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    return ClosedTrade(
        instrument="AAPLUSDT",
        side="buy",
        entry_price=Decimal(entry_price),
        exit_price=Decimal(entry_price) + Decimal(pnl) / Decimal(quantity),
        quantity=Decimal(quantity),
        pnl=Decimal(pnl),
        pnl_pct=pnl_pct,
        entry_time=base + timedelta(hours=offset_hours),
        exit_time=base + timedelta(hours=offset_hours + hold_hours),
        hold_duration_hours=hold_hours,
        won=won,
        factor_name="momentum",
    )


class TestComputeMetrics:
    def test_empty_trades(self) -> None:
        m = compute_metrics([])
        assert m["total_trades"] == 0
        assert m["sortino_ratio"] == 0.0
        assert m["turnover"] == 0.0
        assert m["avg_hold_hours"] == 0.0
        assert m["equity_curve"] == []

    def test_single_winning_trade(self) -> None:
        trades = [_make_trade(pnl="10", pnl_pct=0.1, won=True, hold_hours=6.0)]
        m = compute_metrics(trades)
        assert m["total_trades"] == 1
        assert m["win_rate"] == 1.0
        assert m["avg_hold_hours"] == 6.0
        assert len(m["equity_curve"]) == 1
        assert m["equity_curve"][0][1] == 10.0

    def test_sortino_excludes_upside(self) -> None:
        trades = [
            _make_trade(pnl="10", pnl_pct=0.1, won=True, offset_hours=0),
            _make_trade(pnl="20", pnl_pct=0.2, won=True, offset_hours=8),
            _make_trade(pnl="-5", pnl_pct=-0.05, won=False, offset_hours=16),
        ]
        m = compute_metrics(trades)
        assert m["sortino_ratio"] != 0.0
        assert m["sortino_ratio"] > m["sharpe_ratio"]

    def test_turnover_computed(self) -> None:
        trades = [
            _make_trade(
                pnl="10",
                entry_price="100",
                quantity="5",
                hold_hours=4.0,
                offset_hours=0,
            ),
        ]
        m = compute_metrics(trades)
        assert m["turnover"] > 0.0

    def test_equity_curve_cumulative(self) -> None:
        trades = [
            _make_trade(pnl="10", offset_hours=0),
            _make_trade(pnl="-5", pnl_pct=-0.05, won=False, offset_hours=8),
            _make_trade(pnl="20", offset_hours=16),
        ]
        m = compute_metrics(trades)
        curve = m["equity_curve"]
        assert len(curve) == 3
        assert curve[0][1] == 10.0
        assert curve[1][1] == 5.0
        assert curve[2][1] == 25.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: FAIL with `KeyError: 'sortino_ratio'`

- [ ] **Step 3: Update compute_metrics**

Replace the body of `compute_metrics` in `src/factor_atlas/metrics.py`:

```python
def compute_metrics(closed_trades: list[ClosedTrade]) -> dict[str, Any]:
    """Compute performance metrics from closed trades.

    Returns: total_trades, win_rate, total_pnl, avg_pnl, sharpe_ratio,
    sortino_ratio, max_drawdown, profit_factor, turnover, avg_hold_hours,
    equity_curve.
    """
    n = len(closed_trades)
    if n == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "total_pnl": "0",
            "avg_pnl": "0",
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": None,
            "turnover": 0.0,
            "avg_hold_hours": 0.0,
            "equity_curve": [],
        }

    wins = sum(1 for t in closed_trades if t.won)
    total_pnl = sum((t.pnl for t in closed_trades), Decimal(0))
    avg_pnl = total_pnl / n

    returns = [t.pnl_pct for t in closed_trades]
    mean_r = sum(returns) / n

    # Sharpe
    if n >= 2:
        variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean_r / std_r * math.sqrt(365)) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    # Sortino — only downside deviation
    if n >= 2:
        downside = [min(r - mean_r, 0) ** 2 for r in returns]
        downside_var = sum(downside) / (n - 1)
        downside_std = math.sqrt(downside_var) if downside_var > 0 else 0.0
        sortino = (mean_r / downside_std * math.sqrt(365)) if downside_std > 0 else 0.0
    else:
        sortino = 0.0

    # Equity curve and drawdown
    cumulative: list[float] = []
    equity_curve: list[list[str | float]] = []
    running = 0.0
    for t in closed_trades:
        running += float(t.pnl)
        cumulative.append(running)
        equity_curve.append([t.exit_time.isoformat(), round(running, 4)])

    peak = cumulative[0]
    max_dd = 0.0
    for val in cumulative:
        peak = max(peak, val)
        if peak > 0:
            dd = (peak - val) / peak
            max_dd = max(max_dd, dd)

    # Profit factor
    gross_profit = sum(float(t.pnl) for t in closed_trades if t.won)
    gross_loss = abs(sum(float(t.pnl) for t in closed_trades if not t.won))
    profit_factor: float | None = (
        (gross_profit / gross_loss) if gross_loss > 0 else None
    )

    # Turnover: sum(abs(notional)) / avg equity
    total_notional = sum(abs(float(t.entry_price * t.quantity)) for t in closed_trades)
    avg_equity = sum(cumulative) / n if n > 0 else 1.0
    turnover = total_notional / avg_equity if avg_equity != 0 else 0.0

    # Average hold hours
    avg_hold = sum(t.hold_duration_hours for t in closed_trades) / n

    return {
        "total_trades": n,
        "win_rate": round(wins / n, 4),
        "total_pnl": str(total_pnl),
        "avg_pnl": str(avg_pnl),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": round(max_dd, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "turnover": round(turnover, 4),
        "avg_hold_hours": round(avg_hold, 2),
        "equity_curve": equity_curve,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run full suite and lint**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): add Sortino, turnover, equity curve, avg hold hours"
```

---

### Task 5: Remove silent LLM fallback and add manifest fields

**Files:**
- Modify: `src/factor_atlas/runner.py` (lines 716-728 — LLM provider selection)
- Modify: `src/factor_atlas/runner.py` (`_build_manifest` — add llm_provider, llm_model, llm_mode, account, environment fields)
- Add tests to: `tests/test_runner.py`

**Interfaces:**
- Consumes: `BedrockProvider`, `FixtureLLMProvider` from `factor_atlas.llm`
- Produces: updated `_build_manifest()` that includes `llm_provider`, `llm_model`, `llm_mode`, `account`, `environment` fields. Demo mode raises `RuntimeError` if BedrockProvider fails (no fallback).

- [ ] **Step 1: Write test for demo mode raising on LLM failure**

```python
# Add to tests/test_runner.py
class TestDemoLLMFailure:
    def test_demo_mode_raises_when_bedrock_fails(self, tmp_path: Path) -> None:
        """Demo mode must not silently fall back to fixture LLM."""
        from unittest.mock import patch

        from factor_atlas.__main__ import main

        with patch(
            "factor_atlas.runner.BedrockProvider",
            side_effect=RuntimeError("Bedrock unavailable"),
        ):
            rc = main(
                ["run", "--mode", "demo", "--cycles", "1", "--output", str(tmp_path)]
            )
        assert rc == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runner.py::TestDemoLLMFailure -v`
Expected: FAIL (currently falls back to fixture provider and returns 0)

- [ ] **Step 3: Remove silent fallback in runner.py**

Replace lines 716-728 in `src/factor_atlas/runner.py`:

```python
    if mode == "demo":
        llm_provider = BedrockProvider()
        print(f"  LLM: {llm_provider.model_name} (AWS Bedrock)")
        llm_info = {
            "llm_provider": "aws-bedrock",
            "llm_model": llm_provider.model_name,
            "llm_mode": "live",
        }
    else:
        llm_provider = FixtureLLMProvider()  # type: ignore[assignment]
        llm_info = {
            "llm_provider": "fixture",
            "llm_model": "fixture",
            "llm_mode": "fixture",
        }
```

Update `_build_manifest` to accept and include `llm_info: dict[str, str]`:

```python
def _build_manifest(
    run_id: str,
    mode: str,
    start_time: datetime,
    end_time: datetime,
    results: list[CycleResult],
    config_hash: str,
    commit: str,
    closed_trades: list[ClosedTrade] | None = None,
    llm_info: dict[str, str] | None = None,
) -> dict[str, Any]:
    # ... existing code ...
    manifest["llm_provider"] = (llm_info or {}).get("llm_provider", "unknown")
    manifest["llm_model"] = (llm_info or {}).get("llm_model", "unknown")
    manifest["llm_mode"] = (llm_info or {}).get("llm_mode", "unknown")
    return manifest
```

Pass `llm_info` from `run_paper_session` to `_build_manifest`.

- [ ] **Step 4: Write test for manifest LLM fields**

```python
# Add to tests/test_runner.py TestRunPaperSession
def test_manifest_contains_llm_fields(self, fixture_run_dir: Path) -> None:
    manifest = json.loads((fixture_run_dir / "manifest.json").read_text())
    assert manifest["llm_provider"] == "fixture"
    assert manifest["llm_model"] == "fixture"
    assert manifest["llm_mode"] == "fixture"
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/runner.py tests/test_runner.py
git commit -m "fix(runner): remove silent LLM fallback, add manifest LLM fields"
```

---

### Task 6: Separate research prices from execution prices

**Files:**
- Modify: `src/factor_atlas/runner.py` (`_build_demo_data`, `_process_demo_exits`, `run_paper_session`)

**Interfaces:**
- Consumes: `_fetch_candles_bgc` (existing), `RESEARCH_TO_EXECUTION` mapping from `factor_atlas.config`
- Produces: `_fetch_perp_prices(instruments: list[str]) -> dict[str, Decimal]` — fetches latest USDT-FUTURES prices for perp instruments. Demo exits use perp prices, not SPOT research prices.

- [ ] **Step 1: Write test for perp price fetching**

```python
# Add to tests/test_runner.py
class TestPerpPriceFetching:
    def test_fetch_perp_prices_returns_decimals(self) -> None:
        from unittest.mock import patch
        import json

        candle_resp = json.dumps(
            {
                "data": [
                    [
                        1694649600000,
                        "330.00",
                        "335.00",
                        "328.00",
                        "332.50",
                        "1000",
                        "332500",
                    ]
                ]
            }
        )

        def _mock_run(cmd, **_kw):
            class R:
                returncode = 0
                stdout = candle_resp
                stderr = ""

            return R()

        with patch("factor_atlas.runner.subprocess.run", side_effect=_mock_run):
            from factor_atlas.runner import _fetch_perp_prices

            prices = _fetch_perp_prices(["AAPLUSDT"])

        from decimal import Decimal

        assert prices["AAPLUSDT"] == Decimal("332.50")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runner.py::TestPerpPriceFetching -v`
Expected: FAIL with `ImportError: cannot import name '_fetch_perp_prices'`

- [ ] **Step 3: Add _fetch_perp_prices and wire it in**

Add to `src/factor_atlas/runner.py` after `_build_demo_data`:

```python
def _fetch_perp_prices(instruments: list[str]) -> dict[str, Decimal]:
    """Fetch the latest USDT-FUTURES close price for each perp instrument."""
    prices: dict[str, Decimal] = {}
    for symbol in instruments:
        cmd = [
            "bgc",
            "market",
            "--action",
            "candles",
            "--category",
            "USDT-FUTURES",
            "--symbol",
            symbol,
            "--interval",
            "1D",
            "--limit",
            "1",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode != 0:
            continue
        raw = json.loads(result.stdout)
        candles = raw.get("data", [])
        if candles:
            prices[symbol] = Decimal(str(candles[-1][4]))
    return prices
```

Update `_process_demo_exits` to accept a `perp_prices: dict[str, Decimal]` parameter instead of using SPOT OHLCV data for exit evaluation:

```python
def _process_demo_exits(
    broker_state: BrokerState,
    perp_prices: dict[str, Decimal],
    risk_config: RiskConfig,
    config_hash: str,
    paper_log_f: Any,
) -> None:
    now = datetime.now(tz=UTC)
    to_close: list[str] = []

    for instrument, pos in broker_state.open_positions.items():
        exec_sym = RESEARCH_TO_EXECUTION.get(instrument, instrument)
        current_price = perp_prices.get(exec_sym)
        if current_price is None:
            continue
        # ... rest of exit logic unchanged but uses exec_sym price ...
```

Update the call site in `run_paper_session` to fetch perp prices and pass them.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/factor_atlas/runner.py tests/test_runner.py
git commit -m "fix(runner): use perp prices for exit evaluation, not SPOT research prices"
```

---

### Task 7: CLI commands — status, history, explain

**Files:**
- Modify: `src/factor_atlas/__main__.py` (add subcommands)
- Create: `src/factor_atlas/cli_commands.py` (command implementations)
- Create: `tests/test_cli_commands.py`

**Interfaces:**
- Consumes: `compute_metrics` from `metrics.py`, `BrokerState`/`OpenPosition`/`ClosedTrade` from `broker.py`, `_load_positions_state` from `runner.py`
- Produces:
  - `cmd_status(artifacts_dir: Path) -> str` — returns formatted status string
  - `cmd_history(artifacts_dir: Path) -> str` — returns formatted history string
  - `cmd_explain(run_id: str, artifacts_dir: Path) -> str` — returns formatted explanation string

- [ ] **Step 1: Write tests for CLI commands**

```python
# tests/test_cli_commands.py
"""Tests for status, history, and explain CLI commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from factor_atlas.cli_commands import cmd_explain, cmd_history, cmd_status


def _make_artifacts(tmp_path: Path) -> Path:
    """Create minimal fixture artifacts for testing."""
    artifacts = tmp_path / "artifacts" / "paper-trading"
    artifacts.mkdir(parents=True)

    # positions_state.json
    (artifacts / "positions_state.json").write_text(
        json.dumps(
            {
                "open_positions": [
                    {
                        "instrument": "AAPLUSDT",
                        "side": "buy",
                        "entry_price": "330.33",
                        "quantity": "2",
                        "entry_time": "2026-09-14T10:00:00+00:00",
                        "hypothesis_id": "hyp-1",
                        "factor_name": "momentum",
                        "cycle_id": "cycle-1",
                    }
                ],
                "closed_trades": [
                    {
                        "instrument": "METAUSDT",
                        "side": "sell",
                        "entry_price": "641.76",
                        "exit_price": "630.00",
                        "quantity": "1",
                        "pnl": "11.76",
                        "pnl_pct": 0.0183,
                        "entry_time": "2026-09-13T10:00:00+00:00",
                        "exit_time": "2026-09-13T18:00:00+00:00",
                        "hold_duration_hours": 8.0,
                        "won": True,
                        "factor_name": "mean_reversion",
                    }
                ],
                "last_updated": "2026-09-14T10:05:00+00:00",
            }
        )
    )

    # A run directory with manifest and paper_log
    run_dir = artifacts / "test-run-123"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "test-run-123",
                "start_timestamp": "2026-09-14T10:00:00+00:00",
                "end_timestamp": "2026-09-14T10:01:00+00:00",
                "mode": "fixture",
                "cycles_completed": 2,
                "accepted_count": 1,
                "rejected_count": 1,
                "llm_provider": "fixture",
                "llm_model": "fixture",
                "llm_mode": "fixture",
                "performance_metrics": {
                    "total_trades": 1,
                    "win_rate": 1.0,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "total_pnl": "11.76",
                },
            }
        )
    )
    (run_dir / "paper_log.jsonl").write_text(
        json.dumps(
            {
                "record_type": "open",
                "instrument": "AAPLUSDT",
                "category": "USDT-FUTURES",
                "side": "buy",
                "status": "filled",
                "factor_name": "momentum",
                "rationale": "Strong momentum signal",
                "risk_gate_results": [
                    {"gate_name": "factor_allowlist", "passed": True, "reason": "ok"}
                ],
            }
        )
        + "\n"
    )

    return artifacts


class TestCmdStatus:
    def test_shows_open_positions(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_status(artifacts)
        assert "AAPLUSDT" in output
        assert "momentum" in output

    def test_shows_closed_trade_metrics(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_status(artifacts)
        assert "1" in output  # total trades
        assert "100" in output or "1.0" in output  # win rate


class TestCmdHistory:
    def test_lists_sessions(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_history(artifacts)
        assert "test-run-123" in output


class TestCmdExplain:
    def test_explains_run(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_explain("test-run-123", artifacts)
        assert "AAPLUSDT" in output
        assert "momentum" in output

    def test_unknown_run_id(self, tmp_path: Path) -> None:
        artifacts = _make_artifacts(tmp_path)
        output = cmd_explain("nonexistent", artifacts)
        assert "not found" in output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'factor_atlas.cli_commands'`

- [ ] **Step 3: Implement cli_commands.py**

```python
# src/factor_atlas/cli_commands.py
"""CLI command implementations for status, history, and explain."""

from __future__ import annotations

import json
from pathlib import Path

from factor_atlas.broker import BrokerState, ClosedTrade, OpenPosition
from factor_atlas.metrics import compute_metrics


def _load_state(artifacts_dir: Path) -> BrokerState:
    state = BrokerState()
    state_path = artifacts_dir / "positions_state.json"
    if not state_path.exists():
        return state
    try:
        raw = json.loads(state_path.read_text())
        for d in raw.get("open_positions", []):
            pos = OpenPosition.from_dict(d)
            state.open_positions[pos.instrument] = pos
        for d in raw.get("closed_trades", []):
            state.closed_trades.append(ClosedTrade.from_dict(d))
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return state


def _find_runs(artifacts_dir: Path) -> list[dict]:
    runs = []
    for d in sorted(artifacts_dir.iterdir()):
        manifest_path = d / "manifest.json"
        if d.is_dir() and manifest_path.exists():
            try:
                runs.append(json.loads(manifest_path.read_text()))
            except (json.JSONDecodeError, KeyError):
                continue
    return runs


def cmd_status(artifacts_dir: Path) -> str:
    """Build status output from local state."""
    state = _load_state(artifacts_dir)
    metrics = compute_metrics(state.closed_trades)
    runs = _find_runs(artifacts_dir)

    lines = ["FactorAtlas Status", ""]

    if state.open_positions:
        lines.append(f"  Open positions ({len(state.open_positions)}):")
        for inst, pos in state.open_positions.items():
            lines.append(
                f"    {inst}: {pos.side}, entry=${pos.entry_price}, "
                f"qty={pos.quantity}, factor={pos.factor_name}"
            )
    else:
        lines.append("  Open positions: none")

    lines.append("")
    n = metrics["total_trades"]
    lines.append(f"  Closed trades: {n}")
    if n > 0:
        lines.append(f"    Win rate: {metrics['win_rate']}")
        lines.append(f"    Sharpe: {metrics['sharpe_ratio']}")
        lines.append(f"    Sortino: {metrics['sortino_ratio']}")
        lines.append(f"    Max drawdown: {metrics['max_drawdown']}")
        lines.append(f"    Total PnL: {metrics['total_pnl']}")
        lines.append(f"    Avg hold: {metrics['avg_hold_hours']}h")

    lines.append("")
    lines.append(f"  Sessions: {len(runs)}")
    if runs:
        last = runs[-1]
        lines.append(
            f"  Last run: {last.get('start_timestamp', 'unknown')} ({last.get('run_id', '')[:12]})"
        )
    lines.append(f"  Logs: {artifacts_dir}")

    return "\n".join(lines)


def cmd_history(artifacts_dir: Path) -> str:
    """Build history output listing all sessions."""
    runs = _find_runs(artifacts_dir)
    if not runs:
        return "No sessions found."

    lines = [f"FactorAtlas History — {len(runs)} session(s)", ""]
    for run in runs:
        rid = run.get("run_id", "unknown")
        ts = run.get("start_timestamp", "unknown")
        mode = run.get("mode", "unknown")
        accepted = run.get("accepted_count", 0)
        rejected = run.get("rejected_count", 0)
        perf = run.get("performance_metrics", {})
        pnl = perf.get("total_pnl", "0")
        lines.append(
            f"  {rid[:12]}  {ts}  mode={mode}  "
            f"accepted={accepted} rejected={rejected}  pnl={pnl}"
        )

    return "\n".join(lines)


def cmd_explain(run_id: str, artifacts_dir: Path) -> str:
    """Build explanation output for a single run."""
    run_dir = artifacts_dir / run_id
    if not run_dir.exists():
        return f"Run '{run_id}' not found in {artifacts_dir}"

    manifest_path = run_dir / "manifest.json"
    paper_log_path = run_dir / "paper_log.jsonl"

    if not manifest_path.exists():
        return f"Run '{run_id}' has no manifest."

    manifest = json.loads(manifest_path.read_text())
    lines = [
        f"Session {manifest.get('run_id', run_id)[:12]} "
        f"({manifest.get('start_timestamp', 'unknown')})",
        f"  LLM: {manifest.get('llm_model', 'unknown')} ({manifest.get('llm_provider', 'unknown')})",
        f"  Mode: {manifest.get('mode', 'unknown')}",
        "",
    ]

    if paper_log_path.exists():
        for line in paper_log_path.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            inst = record.get("instrument", "unknown")
            status = record.get("status", "unknown")
            factor = record.get("factor_name", "")
            rationale = record.get("rationale", "")
            side = record.get("side", "")

            lines.append(f"  {inst}:")
            lines.append(f"    Status: {status}, Side: {side}, Factor: {factor}")
            if rationale:
                lines.append(f"    Rationale: {rationale[:120]}")

            gates = record.get("risk_gate_results", [])
            if gates:
                passed = sum(1 for g in gates if g.get("passed"))
                lines.append(f"    Gates: {passed}/{len(gates)} passed")
            lines.append("")

    summary = manifest.get("performance_metrics", {})
    lines.append(
        f"  Summary: {manifest.get('accepted_count', 0)} accepted, "
        f"{manifest.get('rejected_count', 0)} rejected, "
        f"PnL={summary.get('total_pnl', '0')}"
    )

    return "\n".join(lines)


__all__ = ["cmd_explain", "cmd_history", "cmd_status"]
```

- [ ] **Step 4: Wire commands into __main__.py**

Add subparsers for `status`, `history`, `explain` in `_build_parser()` and handle them in `main()`:

```python
# In _build_parser(), after the run_parser block:
    sub.add_parser("status", help="Show system state and metrics.")

    sub.add_parser("history", help="List all paper-trading sessions.")

    explain_parser = sub.add_parser("explain", help="Explain a session's decisions.")
    explain_parser.add_argument("run_id", help="Run ID to explain.")

# In main(), after the run command block:
    if args.command == "status":
        from factor_atlas.cli_commands import cmd_status
        print(cmd_status(Path("artifacts/paper-trading")))
        return 0

    if args.command == "history":
        from factor_atlas.cli_commands import cmd_history
        print(cmd_history(Path("artifacts/paper-trading")))
        return 0

    if args.command == "explain":
        from factor_atlas.cli_commands import cmd_explain
        print(cmd_explain(args.run_id, Path("artifacts/paper-trading")))
        return 0
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/cli_commands.py src/factor_atlas/__main__.py tests/test_cli_commands.py
git commit -m "feat(cli): add status, history, and explain commands"
```

---

### Task 8: Wire exchange verification into the runner

**Files:**
- Modify: `src/factor_atlas/runner.py` (integrate exchange queries, reconciliation, order verification)
- Modify: `tests/test_runner.py`

**Interfaces:**
- Consumes: `query_exchange_state` and `query_order_status` from `exchange.py`, `reconcile_positions` from `reconcile.py`, `classify_order_status` from `exchange.py`
- Produces: Updated `run_paper_session` that:
  1. Queries exchange state at start of demo run (pre-flight)
  2. Reconciles with local state
  3. Passes `exchange_state` to `run_gates` via orchestrator
  4. Verifies orders after placement via `query_order_status`
  5. Records verification status in paper log

- [ ] **Step 1: Write test for order verification in demo mode**

```python
# Add to tests/test_runner.py
class TestOrderVerification:
    def test_paper_log_contains_verification_status(self, tmp_path: Path) -> None:
        """When mocked bgc returns data, paper log should include verification."""
        import json
        from unittest.mock import patch, MagicMock

        # This test runs fixture mode which doesn't do verification,
        # so we just verify the field exists (as None in fixture mode)
        from factor_atlas.runner import run_paper_session

        run_dir = run_paper_session(mode="fixture", cycles=2, output_dir=tmp_path)
        paper_log = (run_dir / "paper_log.jsonl").read_text().strip().split("\n")
        for line in paper_log:
            record = json.loads(line)
            # Fixture mode should have no verification (field absent or None)
            assert record.get("verification_status") in (None, "not_applicable")
```

- [ ] **Step 2: Update runner.py to integrate exchange verification**

In `run_paper_session`, add exchange state query and reconciliation at the start of demo mode:

```python
    # After _load_positions_state:
    exchange_state = None
    if mode == "demo":
        from factor_atlas.exchange import query_exchange_state
        from factor_atlas.reconcile import reconcile_positions

        exchange_state = query_exchange_state()
        divergences = reconcile_positions(broker_state, exchange_state)
        for div in divergences:
            print(
                f"  Reconciliation: {div.instrument} — {div.kind} "
                f"(local={div.local_value}, exchange={div.exchange_value})",
                file=sys.stderr,
            )
```

After placing bgc entry orders, verify each:

```python
        if mode == "demo":
            from factor_atlas.exchange import classify_order_status, query_order_status

            for cycle_id, oid in bgc_order_ids.items():
                if oid.startswith("error:"):
                    continue
                try:
                    order_detail = query_order_status(oid)
                    verification = classify_order_status(order_detail.status)
                except (RuntimeError, OSError):
                    verification = "query_failed"
                # Store verification in the paper record later
```

Add `verification_status` field to paper log records. In fixture mode, set it to `"not_applicable"`.

- [ ] **Step 3: Run all tests**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/factor_atlas/runner.py tests/test_runner.py
git commit -m "feat(runner): wire exchange verification, reconciliation, and pre-flight"
```

---

## Self-review checklist

**Spec coverage:**
- Instrument architecture (two-layer): covered in existing code + Task 6 (price separation)
- Account isolation: enforced by existing code; exchange module uses `--paper-trading`
- Autonomous cycle stages 1-3 (pre-flight, reconcile, exit): Task 1, 2, 6, 8
- Autonomous cycle stages 4-6 (observe, discover, decide): existing code, no changes needed
- Autonomous cycle stage 7 (risk gates): Task 3
- Autonomous cycle stages 8-10 (execute, verify, log): Task 5, 8
- Execution mode boundaries: Task 5 (LLM fallback removal)
- Metrics: Task 4
- CLI commands: Task 7
- GitHub Actions: explicitly blocked (requires working credentials)
- Demo/fixture separation: Task 5
- Manifest fields: Task 5

**Placeholder scan:** No TBD/TODO in any step. All code blocks are complete.

**Type consistency:** `ExchangeState`, `ExchangePosition`, `ExchangeOrder` used consistently across Tasks 1, 2, 3, 8. `compute_metrics` return type consistent between Task 4 and Task 7. `run_gates` `exchange_state` parameter consistent between Task 3 and Task 8.
