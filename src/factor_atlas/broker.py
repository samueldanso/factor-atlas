"""In-memory paper broker for FactorAtlas — executes accepted decisions automatically."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.config import DEFAULT_FEE_RATE, DEFAULT_SLIPPAGE_BPS, INITIAL_BALANCE
from factor_atlas.contracts import PaperOrder, RiskGateResult, TradeDecision
from factor_atlas.risk import all_gates_passed

_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


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
    "execute_paper_order",
]
