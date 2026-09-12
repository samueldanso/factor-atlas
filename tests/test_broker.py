"""Tests for the in-memory paper broker."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from factor_atlas.broker import BrokerState, execute_paper_order
from factor_atlas.contracts import (
    RiskGateResult,
    TradeDecision,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


def _make_decision(
    price: Decimal = Decimal("238.00"),
    quantity: Decimal = Decimal(10),
    instrument: str = "AAPLUSDT",
    side: str = "buy",
    decision_id: str = "dec-1",
) -> TradeDecision:
    return TradeDecision(
        decision_id=decision_id,
        cycle_id="cycle-1",
        hypothesis_id="hyp-1",
        instrument=instrument,
        side=side,
        quantity=quantity,
        price=price,
        rationale="test rationale",
        timestamp=_NOW,
    )


def _all_pass() -> list[RiskGateResult]:
    return [
        RiskGateResult(gate_name="g1", passed=True, reason="ok"),
        RiskGateResult(gate_name="g2", passed=True, reason="ok"),
    ]


def _one_fails() -> list[RiskGateResult]:
    return [
        RiskGateResult(gate_name="g1", passed=True, reason="ok"),
        RiskGateResult(gate_name="g2", passed=False, reason="exceeded limit"),
    ]


# ---------------------------------------------------------------------------
# BrokerState basics
# ---------------------------------------------------------------------------


class TestBrokerState:
    def test_default_balance(self) -> None:
        state = BrokerState()
        assert state.balance == Decimal(100000)

    def test_empty_initial(self) -> None:
        state = BrokerState()
        assert state.positions == []
        assert state.order_history == []
        assert state.daily_pnl == Decimal(0)
        assert state.processed_events == set()
        assert state.last_order_time == {}


# ---------------------------------------------------------------------------
# Filled order
# ---------------------------------------------------------------------------


class TestFilledOrder:
    def test_basic_fill(self) -> None:
        """A passing decision is executed automatically with no pause."""
        state = BrokerState()
        d = _make_decision(price=Decimal(100), quantity=Decimal(10))
        order = execute_paper_order(d, _all_pass(), state)

        assert order.status == "filled"
        assert order.fill_price == Decimal(100)
        assert order.rejection_reason is None

    def test_fee_math(self) -> None:
        """Hand-calculated: notional=1000, fee=1000*0.001=1, slip=1000*0.0005=0.5."""
        state = BrokerState(balance=Decimal(10000))
        d = _make_decision(price=Decimal(100), quantity=Decimal(10))
        order = execute_paper_order(
            d,
            _all_pass(),
            state,
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("0.0005"),
        )

        assert order.notional == Decimal(1000)
        assert order.fees == Decimal("1.000")
        assert order.slippage == Decimal("0.5000")
        assert order.pre_balance == Decimal(10000)
        assert order.post_balance == Decimal(10000) - Decimal("1.000") - Decimal(
            "0.5000"
        )

    def test_fee_custom_rates(self) -> None:
        """Custom fee_rate=0.002, slippage_bps=0.001, notional=5000."""
        state = BrokerState(balance=Decimal(50000))
        d = _make_decision(price=Decimal(500), quantity=Decimal(10))
        order = execute_paper_order(
            d,
            _all_pass(),
            state,
            fee_rate=Decimal("0.002"),
            slippage_bps=Decimal("0.001"),
        )

        # notional = 500 * 10 = 5000
        assert order.notional == Decimal(5000)
        # fees = 5000 * 0.002 = 10
        assert order.fees == Decimal("10.000")
        # slippage = 5000 * 0.001 = 5
        assert order.slippage == Decimal("5.000")
        # balance deducted by fees + slippage = 15
        assert order.post_balance == Decimal(50000) - Decimal("15.000")

    def test_balance_deducted(self) -> None:
        state = BrokerState(balance=Decimal(10000))
        d = _make_decision(price=Decimal(100), quantity=Decimal(10))
        execute_paper_order(d, _all_pass(), state)
        # balance should have decreased
        assert state.balance < Decimal(10000)

    def test_positions_updated(self) -> None:
        state = BrokerState()
        d = _make_decision()
        execute_paper_order(d, _all_pass(), state)

        assert len(state.positions) == 1
        assert len(state.order_history) == 1
        assert state.positions[0].status == "filled"

    def test_last_order_time_updated(self) -> None:
        state = BrokerState()
        d = _make_decision()
        execute_paper_order(d, _all_pass(), state)
        assert state.last_order_time["AAPLUSDT"] == _NOW

    def test_processed_events_updated(self) -> None:
        state = BrokerState()
        d = _make_decision()
        execute_paper_order(d, _all_pass(), state, event_id="evt-1")
        assert "evt-1|AAPLUSDT|buy" in state.processed_events


# ---------------------------------------------------------------------------
# Rejected order
# ---------------------------------------------------------------------------


class TestRejectedOrder:
    def test_gate_rejection(self) -> None:
        """Any veto prevents execution and is visible in gate results."""
        state = BrokerState()
        d = _make_decision()
        order = execute_paper_order(d, _one_fails(), state)

        assert order.status == "rejected"
        assert order.rejection_reason == "exceeded limit"
        assert order.fill_price is None

    def test_balance_unchanged_on_rejection(self) -> None:
        state = BrokerState(balance=Decimal(10000))
        d = _make_decision()
        execute_paper_order(d, _one_fails(), state)
        assert state.balance == Decimal(10000)

    def test_not_added_to_positions(self) -> None:
        state = BrokerState()
        d = _make_decision()
        execute_paper_order(d, _one_fails(), state)
        assert len(state.positions) == 0
        assert len(state.order_history) == 1

    def test_rejected_fees_zero(self) -> None:
        state = BrokerState()
        d = _make_decision()
        order = execute_paper_order(d, _one_fails(), state)
        assert order.fees == Decimal(0)
        assert order.slippage == Decimal(0)


# ---------------------------------------------------------------------------
# Balance safety
# ---------------------------------------------------------------------------


class TestBalanceSafety:
    def test_insufficient_balance_rejects(self) -> None:
        """Balance must never go negative."""
        state = BrokerState(balance=Decimal("0.001"))
        d = _make_decision(price=Decimal(100), quantity=Decimal(10))
        order = execute_paper_order(d, _all_pass(), state)

        assert order.status == "rejected"
        assert order.rejection_reason == "insufficient_balance"
        assert state.balance == Decimal("0.001")  # unchanged

    def test_balance_never_negative(self) -> None:
        """Execute many orders — balance should never go below zero."""
        state = BrokerState(balance=Decimal(5))
        for i in range(10):
            d = _make_decision(
                price=Decimal(100),
                quantity=Decimal(10),
                decision_id=f"dec-{i}",
            )
            execute_paper_order(d, _all_pass(), state)
        assert state.balance >= Decimal(0)


# ---------------------------------------------------------------------------
# Multiple orders
# ---------------------------------------------------------------------------


class TestMultipleOrders:
    def test_sequential_fills(self) -> None:
        state = BrokerState(balance=Decimal(100000))
        for i in range(3):
            d = _make_decision(
                price=Decimal(100),
                quantity=Decimal(1),
                decision_id=f"dec-{i}",
            )
            order = execute_paper_order(d, _all_pass(), state)
            assert order.status == "filled"
        assert len(state.positions) == 3
        assert len(state.order_history) == 3

    def test_mix_filled_and_rejected(self) -> None:
        state = BrokerState(balance=Decimal(100000))
        d1 = _make_decision(decision_id="d1")
        d2 = _make_decision(decision_id="d2")

        o1 = execute_paper_order(d1, _all_pass(), state)
        o2 = execute_paper_order(d2, _one_fails(), state)

        assert o1.status == "filled"
        assert o2.status == "rejected"
        assert len(state.positions) == 1
        assert len(state.order_history) == 2
