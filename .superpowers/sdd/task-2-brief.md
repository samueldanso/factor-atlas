### Task 2: State reconciliation module

**Files:**
- Create: `src/factor_atlas/reconcile.py`
- Create: `tests/test_reconcile.py`

**Interfaces:**
- Consumes: `ExchangeState` from `factor_atlas.exchange`, `BrokerState` and `OpenPosition` from `factor_atlas.broker`
- Produces:
  - `Divergence` dataclass with fields: `instrument: str`, `kind: str`, `local_value: str`, `exchange_value: str`
  - `reconcile_positions(broker_state: BrokerState, exchange_state: ExchangeState) -> list[Divergence]` — compares local open_positions with exchange positions, trusts exchange, updates broker_state in-place, returns list of divergences found

- [ ] **Step 1: Write tests for reconciliation**

```python
# tests/test_reconcile.py
"""Tests for state reconciliation — exchange is authoritative."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from factor_atlas.broker import BrokerState, OpenPosition
from factor_atlas.exchange import ExchangePosition, ExchangeState
from factor_atlas.reconcile import Divergence, reconcile_positions


def _make_exchange_state(
    positions: list[ExchangePosition] | None = None,
    balance: Decimal = Decimal("50000"),
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
        quantity=Decimal("2"),
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
                    size=Decimal("2"),
                    entry_price=Decimal("330.33"),
                    unrealized_pnl=Decimal("0"),
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
                    size=Decimal("1"),
                    entry_price=Decimal("100"),
                    unrealized_pnl=Decimal("5"),
                )
            ]
        )
        divergences = reconcile_positions(broker, ex_state)
        assert len(divergences) == 1
        assert divergences[0].kind == "exchange_only"

    def test_size_mismatch_trusts_exchange(self) -> None:
        broker = BrokerState()
        pos = _make_open_position("AAPLUSDT")
        pos.quantity = Decimal("5")
        broker.open_positions["AAPLUSDT"] = pos

        ex_state = _make_exchange_state(
            [
                ExchangePosition(
                    symbol="AAPLUSDT",
                    side="long",
                    size=Decimal("2"),
                    entry_price=Decimal("330.33"),
                    unrealized_pnl=Decimal("0"),
                )
            ]
        )
        divergences = reconcile_positions(broker, ex_state)
        assert len(divergences) == 1
        assert divergences[0].kind == "size_mismatch"
        assert broker.open_positions["AAPLUSDT"].quantity == Decimal("2")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reconcile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'factor_atlas.reconcile'`

- [ ] **Step 3: Implement reconciliation module**

```python
# src/factor_atlas/reconcile.py
"""Reconcile local BrokerState with exchange truth."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from factor_atlas.broker import BrokerState
    from factor_atlas.exchange import ExchangeState


@dataclass(frozen=True)
class Divergence:
    instrument: str
    kind: str  # "local_only", "exchange_only", "size_mismatch"
    local_value: str
    exchange_value: str


def reconcile_positions(
    broker_state: BrokerState,
    exchange_state: ExchangeState,
) -> list[Divergence]:
    """Compare local open_positions with exchange positions.

    Exchange is authoritative. Updates broker_state in place.
    Returns a list of divergences found.
    """
    divergences: list[Divergence] = []

    exchange_by_symbol: dict[str, tuple[str, Decimal]] = {}
    for ep in exchange_state.positions:
        exchange_by_symbol[ep.symbol] = (ep.side, ep.size)

    local_instruments = set(broker_state.open_positions.keys())
    exchange_instruments = set(exchange_by_symbol.keys())

    # Local positions not on exchange — remove them
    for inst in local_instruments - exchange_instruments:
        divergences.append(
            Divergence(
                instrument=inst,
                kind="local_only",
                local_value=str(broker_state.open_positions[inst].quantity),
                exchange_value="0",
            )
        )
        del broker_state.open_positions[inst]

    # Exchange positions not local — log but can't reconstruct full OpenPosition
    for inst in exchange_instruments - local_instruments:
        side, size = exchange_by_symbol[inst]
        divergences.append(
            Divergence(
                instrument=inst,
                kind="exchange_only",
                local_value="0",
                exchange_value=str(size),
            )
        )

    # Both exist — check size match
    for inst in local_instruments & exchange_instruments:
        _, ex_size = exchange_by_symbol[inst]
        local_pos = broker_state.open_positions[inst]
        if local_pos.quantity != ex_size:
            divergences.append(
                Divergence(
                    instrument=inst,
                    kind="size_mismatch",
                    local_value=str(local_pos.quantity),
                    exchange_value=str(ex_size),
                )
            )
            local_pos.quantity = ex_size

    return divergences


__all__ = ["Divergence", "reconcile_positions"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reconcile.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run full suite and lint**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/reconcile.py tests/test_reconcile.py
git commit -m "feat(reconcile): add exchange state reconciliation module"
```

---
