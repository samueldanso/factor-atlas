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
            side_effect=_mock_subprocess_run(
                {"order": _ORDER_DETAIL_FILLED}
            ),
        ):
            order = query_order_status("1483216288468062208")
        assert order.status == "filled"
        assert order.order_id == "1483216288468062208"

    def test_cancelled_order(self) -> None:
        with patch(
            "factor_atlas.exchange.subprocess.run",
            side_effect=_mock_subprocess_run(
                {"order": _ORDER_DETAIL_REJECTED}
            ),
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
    for o in (order_list or []):
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


def query_order_status(
    order_id: str, paper_trading: bool = True
) -> ExchangeOrder:
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
