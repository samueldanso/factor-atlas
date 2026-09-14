"""Deterministic risk gates for the FactorAtlas agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from factor_atlas.config import (
    COOLDOWN_SECONDS,
    DAILY_LOSS_LIMIT,
    FACTOR_VOCABULARY,
    MAX_CONCENTRATION_PER_INSTRUMENT,
    MAX_CONCURRENT_POSITIONS,
    MAX_DATA_AGE_HOURS,
    MAX_EXPOSURE,
    MAX_NOTIONAL,
    MAX_QUANTITY,
    MIN_OBSERVATIONS,
)
from factor_atlas.contracts import (
    MarketSnapshot,
    RiskGateResult,
    TradeDecision,
    ValidationResult,
)

if TYPE_CHECKING:
    from factor_atlas.broker import BrokerState


# ---------------------------------------------------------------------------
# RiskConfig — typed bundle of gate thresholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskConfig:
    """Typed configuration for all risk-gate thresholds."""

    max_data_age_hours: int = MAX_DATA_AGE_HOURS
    max_notional: Decimal = Decimal(MAX_NOTIONAL)
    max_concurrent_positions: int = MAX_CONCURRENT_POSITIONS
    max_exposure: Decimal = Decimal(MAX_EXPOSURE)
    cooldown_seconds: int = COOLDOWN_SECONDS
    daily_loss_limit: Decimal = Decimal(DAILY_LOSS_LIMIT)
    max_concentration_per_instrument: int = MAX_CONCENTRATION_PER_INSTRUMENT
    max_quantity: Decimal = Decimal(MAX_QUANTITY)
    # Exit management
    max_hold_hours: int = 24
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.05


# ---------------------------------------------------------------------------
# Individual gates — pure functions returning RiskGateResult
# ---------------------------------------------------------------------------


def gate_factor_allowlist(
    decision: TradeDecision,
    *,
    factor_name: str = "",
    **_kw: object,
) -> RiskGateResult:
    """Reject if the hypothesis's factor is not in FACTOR_VOCABULARY."""
    passed = factor_name in FACTOR_VOCABULARY
    return RiskGateResult(
        gate_name="factor_allowlist",
        passed=passed,
        reason=(
            f"factor '{factor_name}' is in allowlist"
            if passed
            else f"factor '{factor_name}' not in allowlist"
        ),
    )


def gate_data_freshness(
    decision: TradeDecision,
    *,
    snapshot: MarketSnapshot,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if the snapshot timestamp is stale."""
    age = decision.timestamp - snapshot.timestamp
    max_age = timedelta(hours=config.max_data_age_hours)
    passed = age <= max_age
    age_hours = age.total_seconds() / 3600
    return RiskGateResult(
        gate_name="data_freshness",
        passed=passed,
        reason=(
            f"data age {age_hours:.1f}h within {config.max_data_age_hours}h"
            if passed
            else f"data age {age_hours:.1f}h exceeds {config.max_data_age_hours}h"
        ),
        value=age_hours,
        threshold=float(config.max_data_age_hours),
    )


def gate_min_sample_size(
    decision: TradeDecision,
    *,
    validation: ValidationResult,
    **_kw: object,
) -> RiskGateResult:
    """Reject if validation observations are below minimum."""
    passed = validation.observations >= MIN_OBSERVATIONS
    return RiskGateResult(
        gate_name="min_sample_size",
        passed=passed,
        reason=(
            f"observations {validation.observations} >= {MIN_OBSERVATIONS}"
            if passed
            else f"observations {validation.observations} < {MIN_OBSERVATIONS}"
        ),
        value=float(validation.observations),
        threshold=float(MIN_OBSERVATIONS),
    )


def gate_validation_threshold(
    decision: TradeDecision,
    *,
    validation: ValidationResult,
    **_kw: object,
) -> RiskGateResult:
    """Reject if the validation did not pass."""
    return RiskGateResult(
        gate_name="validation_threshold",
        passed=validation.passed,
        reason="validation passed" if validation.passed else "validation did not pass",
    )


def gate_max_notional(
    decision: TradeDecision,
    *,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if order notional exceeds MAX_NOTIONAL."""
    notional = decision.price * decision.quantity
    passed = notional <= config.max_notional
    return RiskGateResult(
        gate_name="max_notional",
        passed=passed,
        reason=(
            f"notional {notional} <= {config.max_notional}"
            if passed
            else f"notional {notional} exceeds {config.max_notional}"
        ),
        value=float(notional),
        threshold=float(config.max_notional),
    )


def gate_max_position(
    decision: TradeDecision,
    *,
    broker_state: BrokerState,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if open positions would exceed MAX_CONCURRENT_POSITIONS."""
    current = len(broker_state.positions)
    passed = current < config.max_concurrent_positions
    return RiskGateResult(
        gate_name="max_position",
        passed=passed,
        reason=(
            f"positions {current} < {config.max_concurrent_positions}"
            if passed
            else f"positions {current} >= {config.max_concurrent_positions}"
        ),
        value=float(current),
        threshold=float(config.max_concurrent_positions),
    )


def gate_exposure_cap(
    decision: TradeDecision,
    *,
    broker_state: BrokerState,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if total open notional + this order exceeds MAX_EXPOSURE."""
    open_notional = sum((o.notional for o in broker_state.positions), Decimal(0))
    order_notional = decision.price * decision.quantity
    total = open_notional + order_notional
    passed = total <= config.max_exposure
    return RiskGateResult(
        gate_name="exposure_cap",
        passed=passed,
        reason=(
            f"total exposure {total} <= {config.max_exposure}"
            if passed
            else f"total exposure {total} exceeds {config.max_exposure}"
        ),
        value=float(total),
        threshold=float(config.max_exposure),
    )


def gate_cooldown(
    decision: TradeDecision,
    *,
    broker_state: BrokerState,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if the same instrument had an order within COOLDOWN_SECONDS."""
    last = broker_state.last_order_time.get(decision.instrument)
    if last is None:
        return RiskGateResult(
            gate_name="cooldown",
            passed=True,
            reason="no prior order for instrument",
        )
    elapsed = (decision.timestamp - last).total_seconds()
    passed = elapsed >= config.cooldown_seconds
    return RiskGateResult(
        gate_name="cooldown",
        passed=passed,
        reason=(
            f"elapsed {elapsed:.0f}s >= {config.cooldown_seconds}s"
            if passed
            else f"elapsed {elapsed:.0f}s < {config.cooldown_seconds}s"
        ),
        value=elapsed,
        threshold=float(config.cooldown_seconds),
    )


def gate_daily_loss_cap(
    decision: TradeDecision,
    *,
    broker_state: BrokerState,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if realized daily loss exceeds DAILY_LOSS_LIMIT."""
    loss = -broker_state.daily_pnl if broker_state.daily_pnl < 0 else Decimal(0)
    passed = loss < config.daily_loss_limit
    return RiskGateResult(
        gate_name="daily_loss_cap",
        passed=passed,
        reason=(
            f"daily loss {loss} < {config.daily_loss_limit}"
            if passed
            else f"daily loss {loss} >= {config.daily_loss_limit}"
        ),
        value=float(loss),
        threshold=float(config.daily_loss_limit),
    )


def gate_duplicate_suppression(
    decision: TradeDecision,
    *,
    broker_state: BrokerState,
    event_id: str = "",
    **_kw: object,
) -> RiskGateResult:
    """Reject if the same event_id + instrument + side was already processed."""
    eid = event_id or decision.decision_id
    key = f"{eid}|{decision.instrument}|{decision.side}"
    passed = key not in broker_state.processed_events
    return RiskGateResult(
        gate_name="duplicate_suppression",
        passed=passed,
        reason="not a duplicate" if passed else f"duplicate event: {key}",
    )


def gate_concentration_guard(
    decision: TradeDecision,
    *,
    broker_state: BrokerState,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if the instrument would have too many open positions."""
    current = sum(
        1 for o in broker_state.positions if o.instrument == decision.instrument
    )
    passed = current < config.max_concentration_per_instrument
    return RiskGateResult(
        gate_name="concentration_guard",
        passed=passed,
        reason=(
            f"instrument positions {current} < {config.max_concentration_per_instrument}"
            if passed
            else (
                f"instrument positions {current}"
                f" >= {config.max_concentration_per_instrument}"
            )
        ),
        value=float(current),
        threshold=float(config.max_concentration_per_instrument),
    )


def gate_max_quantity(
    decision: TradeDecision,
    *,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if quantity exceeds the bounded maximum."""
    passed = decision.quantity <= config.max_quantity
    return RiskGateResult(
        gate_name="max_quantity",
        passed=passed,
        reason=(
            f"quantity {decision.quantity} <= {config.max_quantity}"
            if passed
            else f"quantity {decision.quantity} exceeds {config.max_quantity}"
        ),
        value=float(decision.quantity),
        threshold=float(config.max_quantity),
    )


def gate_balance_check(
    decision: TradeDecision,
    *,
    exchange_state: object | None = None,
    config: RiskConfig,
    **_kw: object,
) -> RiskGateResult:
    """Reject if available exchange balance < order notional."""
    if exchange_state is None:
        return RiskGateResult(
            gate_name="balance_check",
            passed=True,
            reason="skipped: no exchange state (fixture mode)",
        )
    from factor_atlas.exchange import ExchangeState

    if not isinstance(exchange_state, ExchangeState):
        raise TypeError(f"Expected ExchangeState, got {type(exchange_state)}")
    notional = decision.price * decision.quantity
    passed = exchange_state.balance >= notional
    return RiskGateResult(
        gate_name="balance_check",
        passed=passed,
        reason=(
            f"balance {exchange_state.balance} >= notional {notional}"
            if passed
            else f"balance {exchange_state.balance} < notional {notional}"
        ),
        value=float(exchange_state.balance),
        threshold=float(notional),
    )


def gate_pending_order_check(
    decision: TradeDecision,
    *,
    exchange_state: object | None = None,
    **_kw: object,
) -> RiskGateResult:
    """Reject if a pending order exists for the same instrument."""
    if exchange_state is None:
        return RiskGateResult(
            gate_name="pending_order_check",
            passed=True,
            reason="skipped: no exchange state (fixture mode)",
        )
    from factor_atlas.exchange import ExchangeState

    if not isinstance(exchange_state, ExchangeState):
        raise TypeError(f"Expected ExchangeState, got {type(exchange_state)}")
    conflicting = [
        o for o in exchange_state.pending_orders if o.symbol == decision.instrument
    ]
    passed = len(conflicting) == 0
    return RiskGateResult(
        gate_name="pending_order_check",
        passed=passed,
        reason=(
            "no pending orders for instrument"
            if passed
            else f"{len(conflicting)} pending order(s) for {decision.instrument}"
        ),
        value=float(len(conflicting)),
        threshold=0.0,
    )


# ---------------------------------------------------------------------------
# Gate runner
# ---------------------------------------------------------------------------

_GATE_ORDER: list[str] = [
    "factor_allowlist",
    "data_freshness",
    "min_sample_size",
    "validation_threshold",
    "max_notional",
    "max_position",
    "exposure_cap",
    "cooldown",
    "daily_loss_cap",
    "duplicate_suppression",
    "concentration_guard",
    "max_quantity",
    "balance_check",
    "pending_order_check",
]

_GATE_FNS = {
    "factor_allowlist": gate_factor_allowlist,
    "data_freshness": gate_data_freshness,
    "min_sample_size": gate_min_sample_size,
    "validation_threshold": gate_validation_threshold,
    "max_notional": gate_max_notional,
    "max_position": gate_max_position,
    "exposure_cap": gate_exposure_cap,
    "cooldown": gate_cooldown,
    "daily_loss_cap": gate_daily_loss_cap,
    "duplicate_suppression": gate_duplicate_suppression,
    "concentration_guard": gate_concentration_guard,
    "max_quantity": gate_max_quantity,
    "balance_check": gate_balance_check,
    "pending_order_check": gate_pending_order_check,
}


def run_gates(
    decision: TradeDecision,
    validation: ValidationResult,
    snapshot: MarketSnapshot,
    broker_state: BrokerState,
    config: RiskConfig,
    *,
    factor_name: str = "",
    event_id: str = "",
    exchange_state: object | None = None,
) -> list[RiskGateResult]:
    """Run all risk gates. Returns results for ALL gates (pass and fail)."""
    kwargs = {
        "decision": decision,
        "validation": validation,
        "snapshot": snapshot,
        "broker_state": broker_state,
        "config": config,
        "factor_name": factor_name,
        "event_id": event_id or decision.decision_id,
        "exchange_state": exchange_state,
    }

    results: list[RiskGateResult] = []
    for name in _GATE_ORDER:
        fn = _GATE_FNS[name]
        result = fn(**kwargs)  # type: ignore[operator]
        results.append(result)
    return results


def all_gates_passed(results: list[RiskGateResult]) -> bool:
    """Return True if every gate in the list passed."""
    return all(r.passed for r in results)


__all__ = [
    "RiskConfig",
    "all_gates_passed",
    "gate_balance_check",
    "gate_concentration_guard",
    "gate_cooldown",
    "gate_daily_loss_cap",
    "gate_data_freshness",
    "gate_duplicate_suppression",
    "gate_exposure_cap",
    "gate_factor_allowlist",
    "gate_max_notional",
    "gate_max_position",
    "gate_max_quantity",
    "gate_min_sample_size",
    "gate_pending_order_check",
    "gate_validation_threshold",
    "run_gates",
]
