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
