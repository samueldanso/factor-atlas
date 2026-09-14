# src/factor_atlas/exchange.py
"""Exchange state queries via bgc CLI — wraps subprocess calls."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

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


@dataclass(frozen=True)
class ExchangeState:
    balance: Decimal = Decimal(0)
    positions: list[ExchangePosition] = field(default_factory=list)
    pending_orders: list[ExchangeOrder] = field(default_factory=list)
    queried_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


def _run_bgc(args: list[str], paper_trading: bool = True) -> dict[str, Any]:
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
    return dict(json.loads(result.stdout))


def query_exchange_state(paper_trading: bool = True) -> ExchangeState:
    """Query account balance, positions, and pending orders from Bitget."""
    # Balance
    acct = _run_bgc(
        ["account_overview", "--category", "USDT-FUTURES"],
        paper_trading=paper_trading,
    )
    coins = acct.get("data", {}).get("coin", [])
    balance = Decimal(0)
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
    if not re.fullmatch(r"\d{1,32}", order_id):
        raise ValueError(f"Invalid order_id {order_id!r}: must be 1–32 decimal digits")
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
