"""Real PnL metrics computed from closed trades."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from factor_atlas.broker import ClosedTrade, OpenPosition


def make_closed_trade(
    position: OpenPosition,
    exit_price: Decimal,
    exit_time: datetime,
) -> ClosedTrade:
    """Build a ClosedTrade from an open position and its exit price."""
    from factor_atlas.broker import ClosedTrade  # avoid circular at module level

    qty = position.quantity
    if position.side == "buy":
        pnl = (exit_price - position.entry_price) * qty
    else:
        pnl = (position.entry_price - exit_price) * qty

    cost_basis = position.entry_price * qty
    pnl_pct = float(pnl / cost_basis) if cost_basis != 0 else 0.0
    hold_hours = (exit_time - position.entry_time).total_seconds() / 3600

    return ClosedTrade(
        instrument=position.instrument,
        side=position.side,
        entry_price=position.entry_price,
        exit_price=exit_price,
        quantity=qty,
        pnl=pnl,
        pnl_pct=pnl_pct,
        entry_time=position.entry_time,
        exit_time=exit_time,
        hold_duration_hours=hold_hours,
        won=pnl > Decimal(0),
        factor_name=position.factor_name,
    )


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


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


__all__ = [
    "compute_metrics",
    "make_closed_trade",
    "now_utc",
]
