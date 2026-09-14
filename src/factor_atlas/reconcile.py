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
        _side, size = exchange_by_symbol[inst]
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
