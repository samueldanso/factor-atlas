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


def _extract_nested(raw: dict[str, Any], *keys: str) -> Any:
    """Walk into bgc composite responses: data -> section -> ok/data -> list."""
    node: Any = raw
    for k in keys:
        if isinstance(node, dict):
            node = node.get(k)
        else:
            return None
    return node


def query_exchange_state(paper_trading: bool = True) -> ExchangeState:
    """Query account balance, positions, and pending orders from Bitget."""
    acct = _run_bgc(
        ["account_overview", "--category", "USDT-FUTURES"],
        paper_trading=paper_trading,
    )

    # Balance — composite response: data.assets.data.usdtEquity
    balance = Decimal(0)
    assets_data = _extract_nested(acct, "data", "assets", "data")
    if isinstance(assets_data, dict):
        balance = Decimal(assets_data.get("usdtEquity", "0"))

    # Positions — composite response: data.positions.data.list[]
    positions: list[ExchangePosition] = []
    pos_data = _extract_nested(acct, "data", "positions", "data")
    pos_list: list[Any] = []
    if isinstance(pos_data, dict):
        pos_list = pos_data.get("list", [])
    elif isinstance(pos_data, list):
        pos_list = pos_data
    for p in pos_list:
        if not isinstance(p, dict):
            continue
        side_val: str = p.get("holdSide") or p.get("posSide") or "long"
        size_val: str = p.get("total") or p.get("holdAmount") or "0"
        price_val: str = p.get("avgPrice") or p.get("averageOpenPrice") or "0"
        pnl_val: str = p.get("unrealizedPL") or p.get("unrealisedPnl") or "0"
        positions.append(
            ExchangePosition(
                symbol=p.get("symbol", ""),
                side=side_val,
                size=Decimal(size_val),
                entry_price=Decimal(price_val),
                unrealized_pnl=Decimal(pnl_val),
            )
        )

    # Pending orders — separate call: data.list[]
    orders_raw = _run_bgc(
        ["order", "--action", "open", "--category", "USDT-FUTURES"],
        paper_trading=paper_trading,
    )
    pending: list[ExchangeOrder] = []
    order_data = orders_raw.get("data", {})
    order_list: list[Any] = []
    if isinstance(order_data, dict):
        raw_list = order_data.get("list") or order_data.get("orderList") or []
        order_list = list(raw_list) if isinstance(raw_list, list) else []
    elif isinstance(order_data, list):
        order_list = order_data
    for o in order_list or []:
        if not isinstance(o, dict):
            continue
        qty_val: str = o.get("size") or o.get("qty") or "0"
        status_val: str = o.get("orderStatus") or o.get("status") or "unknown"
        pending.append(
            ExchangeOrder(
                order_id=o.get("orderId", ""),
                symbol=o.get("symbol", ""),
                side=o.get("side", ""),
                price=Decimal(o.get("price", "0")),
                qty=Decimal(qty_val),
                status=status_val,
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
    if not isinstance(d, dict):
        d = {}
    return ExchangeOrder(
        order_id=d.get("orderId", order_id),
        symbol=d.get("symbol", ""),
        side=d.get("side", ""),
        price=Decimal(d.get("price", "0")),
        qty=Decimal(d.get("qty", d.get("size", "0"))),
        status=d.get("orderStatus", d.get("status", "unknown")),
    )


def classify_order_status(status: str) -> OrderVerificationStatus:
    """Map a bgc order status string to our verification enum."""
    status_lower = status.lower()
    if status_lower in ("filled", "full_fill"):
        return "verified_filled"
    if status_lower in ("cancelled", "canceled"):
        return "verified_cancelled"
    if status_lower in ("rejected", "failed"):
        return "verified_rejected"
    if status_lower in ("partial", "partially_filled", "partial_fill"):
        return "verified_partial"
    if status_lower in ("new", "live", "init"):
        return "unverified"
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
