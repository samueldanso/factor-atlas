# src/factor_atlas/reconcile.py
"""Reconcile local BrokerState with exchange truth."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from factor_atlas.config import RESEARCH_TO_EXECUTION

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

    # Build mapping from local instruments to their exchange-equivalent symbols.
    # Local positions may use research symbols (RAAPLUSDT) while exchange uses
    # execution symbols (AAPLUSDT).
    local_to_exec: dict[str, str] = {}
    for inst in broker_state.open_positions:
        local_to_exec[inst] = RESEARCH_TO_EXECUTION.get(inst, inst)

    matched_exchange: set[str] = set()

    # Local positions not on exchange — remove them
    to_remove: list[str] = []
    for inst, exec_sym in local_to_exec.items():
        if exec_sym in exchange_by_symbol:
            matched_exchange.add(exec_sym)
            _, ex_size = exchange_by_symbol[exec_sym]
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
        else:
            divergences.append(
                Divergence(
                    instrument=inst,
                    kind="local_only",
                    local_value=str(broker_state.open_positions[inst].quantity),
                    exchange_value="0",
                )
            )
            to_remove.append(inst)

    for inst in to_remove:
        del broker_state.open_positions[inst]

    # Exchange positions not matched by any local position
    for inst in set(exchange_by_symbol.keys()) - matched_exchange:
        _side, size = exchange_by_symbol[inst]
        divergences.append(
            Divergence(
                instrument=inst,
                kind="exchange_only",
                local_value="0",
                exchange_value=str(size),
            )
        )

    return divergences


__all__ = ["Divergence", "reconcile_positions"]
