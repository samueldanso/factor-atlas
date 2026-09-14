"""In-memory paper broker for FactorAtlas — executes accepted decisions automatically."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.config import DEFAULT_FEE_RATE, DEFAULT_SLIPPAGE_BPS, INITIAL_BALANCE
from factor_atlas.contracts import PaperOrder, RiskGateResult, TradeDecision
from factor_atlas.risk import all_gates_passed

_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


# ---------------------------------------------------------------------------
# Position tracking types
# ---------------------------------------------------------------------------


@dataclass
class OpenPosition:
    """A currently open paper position."""

    instrument: str
    side: str  # "buy" = long entry, "sell" = short entry
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime
    hypothesis_id: str
    factor_name: str
    cycle_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "side": self.side,
            "entry_price": str(self.entry_price),
            "quantity": str(self.quantity),
            "entry_time": self.entry_time.isoformat(),
            "hypothesis_id": self.hypothesis_id,
            "factor_name": self.factor_name,
            "cycle_id": self.cycle_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OpenPosition:
        return cls(
            instrument=d["instrument"],
            side=d["side"],
            entry_price=Decimal(d["entry_price"]),
            quantity=Decimal(d["quantity"]),
            entry_time=datetime.fromisoformat(d["entry_time"]),
            hypothesis_id=d["hypothesis_id"],
            factor_name=d["factor_name"],
            cycle_id=d["cycle_id"],
        )


@dataclass
class ClosedTrade:
    """A completed round-trip trade with realized PnL."""

    instrument: str
    side: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    pnl: Decimal
    pnl_pct: float
    entry_time: datetime
    exit_time: datetime
    hold_duration_hours: float
    won: bool
    factor_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "side": self.side,
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price),
            "quantity": str(self.quantity),
            "pnl": str(self.pnl),
            "pnl_pct": self.pnl_pct,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "hold_duration_hours": self.hold_duration_hours,
            "won": self.won,
            "factor_name": self.factor_name,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ClosedTrade:
        return cls(
            instrument=d["instrument"],
            side=d["side"],
            entry_price=Decimal(d["entry_price"]),
            exit_price=Decimal(d["exit_price"]),
            quantity=Decimal(d["quantity"]),
            pnl=Decimal(d["pnl"]),
            pnl_pct=float(d["pnl_pct"]),
            entry_time=datetime.fromisoformat(d["entry_time"]),
            exit_time=datetime.fromisoformat(d["exit_time"]),
            hold_duration_hours=float(d["hold_duration_hours"]),
            won=bool(d["won"]),
            factor_name=d["factor_name"],
        )


# ---------------------------------------------------------------------------
# BrokerState — mutable session state
# ---------------------------------------------------------------------------


@dataclass
class BrokerState:
    """Mutable paper-broker state for one session."""

    balance: Decimal = Decimal(INITIAL_BALANCE)
    positions: list[PaperOrder] = field(default_factory=list)
    order_history: list[PaperOrder] = field(default_factory=list)
    daily_pnl: Decimal = Decimal(0)
    processed_events: set[str] = field(default_factory=set)
    last_order_time: dict[str, datetime] = field(default_factory=dict)
    open_positions: dict[str, OpenPosition] = field(default_factory=dict)
    closed_trades: list[ClosedTrade] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Execute function
# ---------------------------------------------------------------------------


def execute_paper_order(
    decision: TradeDecision,
    gate_results: list[RiskGateResult],
    broker_state: BrokerState,
    fee_rate: Decimal = Decimal(DEFAULT_FEE_RATE),
    slippage_bps: Decimal = Decimal(DEFAULT_SLIPPAGE_BPS),
    *,
    event_id: str = "",
) -> PaperOrder:
    """Execute or reject a paper order based on gate results.

    If all gates passed and sufficient balance exists, the order is filled
    automatically — no approval pause.  Otherwise it is rejected.
    """
    notional = decision.price * decision.quantity
    fees = notional * fee_rate
    slippage = notional * slippage_bps
    order_id = _det_uuid(f"order-{decision.decision_id}")
    eid = event_id or decision.decision_id

    if not all_gates_passed(gate_results):
        # Find first failing gate
        first_fail = next(r for r in gate_results if not r.passed)
        order = PaperOrder(
            order_id=order_id,
            decision_id=decision.decision_id,
            event_id=eid,
            timestamp=decision.timestamp,
            instrument=decision.instrument,
            side=decision.side,
            price=decision.price,
            quantity=decision.quantity,
            notional=notional,
            pre_balance=broker_state.balance,
            post_balance=broker_state.balance,
            fees=Decimal(0),
            slippage=Decimal(0),
            status="rejected",
            rejection_reason=first_fail.reason,
        )
        broker_state.order_history.append(order)
        return order

    # Check sufficient balance for fees + slippage
    total_cost = fees + slippage
    if broker_state.balance < total_cost:
        order = PaperOrder(
            order_id=order_id,
            decision_id=decision.decision_id,
            event_id=eid,
            timestamp=decision.timestamp,
            instrument=decision.instrument,
            side=decision.side,
            price=decision.price,
            quantity=decision.quantity,
            notional=notional,
            pre_balance=broker_state.balance,
            post_balance=broker_state.balance,
            fees=Decimal(0),
            slippage=Decimal(0),
            status="rejected",
            rejection_reason="insufficient_balance",
        )
        broker_state.order_history.append(order)
        return order

    # Execute fill
    pre_balance = broker_state.balance
    broker_state.balance -= total_cost
    post_balance = broker_state.balance

    order = PaperOrder(
        order_id=order_id,
        decision_id=decision.decision_id,
        event_id=eid,
        timestamp=decision.timestamp,
        instrument=decision.instrument,
        side=decision.side,
        price=decision.price,
        quantity=decision.quantity,
        notional=notional,
        pre_balance=pre_balance,
        post_balance=post_balance,
        fees=fees,
        slippage=slippage,
        status="filled",
        fill_price=decision.price,
    )

    broker_state.positions.append(order)
    broker_state.order_history.append(order)
    broker_state.last_order_time[decision.instrument] = decision.timestamp

    # Record dedup key
    key = f"{eid}|{decision.instrument}|{decision.side}"
    broker_state.processed_events.add(key)

    return order


__all__ = [
    "BrokerState",
    "ClosedTrade",
    "OpenPosition",
    "execute_paper_order",
]
