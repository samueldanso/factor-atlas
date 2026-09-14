"""Tests for state reconciliation — exchange is authoritative."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from factor_atlas.broker import BrokerState, OpenPosition
from factor_atlas.exchange import ExchangePosition, ExchangeState
from factor_atlas.reconcile import reconcile_positions


def _make_exchange_state(
    positions: list[ExchangePosition] | None = None,
    balance: Decimal = Decimal(50000),
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
        quantity=Decimal(2),
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
                    size=Decimal(2),
                    entry_price=Decimal("330.33"),
                    unrealized_pnl=Decimal(0),
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
                    size=Decimal(1),
                    entry_price=Decimal(100),
                    unrealized_pnl=Decimal(5),
                )
            ]
        )
        divergences = reconcile_positions(broker, ex_state)
        assert len(divergences) == 1
        assert divergences[0].kind == "exchange_only"

    def test_size_mismatch_trusts_exchange(self) -> None:
        broker = BrokerState()
        pos = _make_open_position("AAPLUSDT")
        pos.quantity = Decimal(5)
        broker.open_positions["AAPLUSDT"] = pos

        ex_state = _make_exchange_state(
            [
                ExchangePosition(
                    symbol="AAPLUSDT",
                    side="long",
                    size=Decimal(2),
                    entry_price=Decimal("330.33"),
                    unrealized_pnl=Decimal(0),
                )
            ]
        )
        divergences = reconcile_positions(broker, ex_state)
        assert len(divergences) == 1
        assert divergences[0].kind == "size_mismatch"
        assert broker.open_positions["AAPLUSDT"].quantity == Decimal(2)
