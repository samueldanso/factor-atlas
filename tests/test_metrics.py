"""Tests for compute_metrics including Sortino, turnover, equity curve."""

from __future__ import annotations

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
