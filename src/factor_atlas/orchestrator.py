"""Autonomous cycle runner: observe -> propose -> evaluate -> decide -> gate -> execute."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from uuid import NAMESPACE_DNS, uuid5

import pandas as pd

from factor_atlas.broker import BrokerState, execute_paper_order
from factor_atlas.contracts import (
    FactorHypothesis,
    MarketSnapshot,
    PaperOrder,
    RiskGateResult,
    TradeDecision,
    ValidationResult,
)
from factor_atlas.decision import DecisionProvider
from factor_atlas.proposer import Proposer
from factor_atlas.risk import RiskConfig, run_gates
from factor_atlas.validation import validate_factor

if TYPE_CHECKING:
    from factor_atlas.audit import AuditLogger

_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


# ---------------------------------------------------------------------------
# CycleResult
# ---------------------------------------------------------------------------


@dataclass
class CycleResult:
    """Complete result of one autonomous discovery-and-decision cycle."""

    cycle_id: str
    snapshot: MarketSnapshot
    hypotheses: list[FactorHypothesis]
    evaluations: list[tuple[FactorHypothesis, ValidationResult]]
    validated: list[tuple[FactorHypothesis, ValidationResult]]
    decision: TradeDecision | None
    status: Literal["accepted", "no_candidate", "no_hypothesis"]
    gate_results: list[RiskGateResult] | None = None
    order: PaperOrder | None = None


# ---------------------------------------------------------------------------
# Single-cycle runner
# ---------------------------------------------------------------------------


def run_cycle(
    snapshot: MarketSnapshot,
    ohlcv_data: dict[str, pd.DataFrame],
    proposer: Proposer,
    decision_provider: DecisionProvider,
    search_budget: int = 5,
    broker_state: BrokerState | None = None,
    risk_config: RiskConfig | None = None,
    exchange_state: object | None = None,
) -> CycleResult:
    """Run one autonomous cycle: observe -> propose -> evaluate -> decide -> gate -> execute.

    No human approval pause. The cycle proceeds deterministically.
    """
    cycle_id = _det_uuid(f"cycle-{snapshot.snapshot_id}")

    # 1. Observe — snapshot already provided

    # 2. Propose
    hypotheses = proposer.propose(snapshot, search_budget)

    if not hypotheses:
        return CycleResult(
            cycle_id=cycle_id,
            snapshot=snapshot,
            hypotheses=[],
            evaluations=[],
            validated=[],
            decision=None,
            status="no_hypothesis",
        )

    # 3. Evaluate each hypothesis
    evaluations: list[tuple[FactorHypothesis, ValidationResult]] = []
    instrument = snapshot.instrument
    df = ohlcv_data.get(instrument)

    if df is not None and not df.empty:
        for hyp in hypotheses:
            # Build param dict: merge parameters + lookback (all factors require it).
            params: dict[str, Any] = dict(hyp.parameters)
            params.setdefault("lookback", hyp.lookback)
            result = validate_factor(
                factor_name=hyp.factor_name,
                df=df,
                params=params,
                hypothesis_id=hyp.hypothesis_id,
                snapshot_id=snapshot.snapshot_id,
            )
            evaluations.append((hyp, result))

    # 4. Filter — keep only passed=True
    validated = [(h, v) for h, v in evaluations if v.passed]

    # 5. Decide
    if not validated:
        return CycleResult(
            cycle_id=cycle_id,
            snapshot=snapshot,
            hypotheses=hypotheses,
            evaluations=evaluations,
            validated=[],
            decision=None,
            status="no_candidate",
        )

    decision = decision_provider.decide(snapshot, validated, cycle_id)

    if decision is None:
        return CycleResult(
            cycle_id=cycle_id,
            snapshot=snapshot,
            hypotheses=hypotheses,
            evaluations=evaluations,
            validated=validated,
            decision=None,
            status="no_candidate",
        )

    # 6. Gate + Execute (if broker_state is provided)
    gate_results: list[RiskGateResult] | None = None
    order: PaperOrder | None = None

    if broker_state is not None:
        cfg = risk_config or RiskConfig()
        # Find the hypothesis for this decision to get factor_name
        factor_name = ""
        best_validation: ValidationResult | None = None
        for hyp, val in validated:
            if hyp.hypothesis_id == decision.hypothesis_id:
                factor_name = hyp.factor_name
                best_validation = val
                break

        if best_validation is not None:
            gate_results = run_gates(
                decision=decision,
                validation=best_validation,
                snapshot=snapshot,
                broker_state=broker_state,
                config=cfg,
                factor_name=factor_name,
                event_id=decision.decision_id,
                exchange_state=exchange_state,
            )

            order = execute_paper_order(
                decision=decision,
                gate_results=gate_results,
                broker_state=broker_state,
                event_id=decision.decision_id,
            )

    return CycleResult(
        cycle_id=cycle_id,
        snapshot=snapshot,
        hypotheses=hypotheses,
        evaluations=evaluations,
        validated=validated,
        decision=decision,
        status="accepted" if decision is not None else "no_candidate",
        gate_results=gate_results,
        order=order,
    )


# ---------------------------------------------------------------------------
# Multi-cycle runner
# ---------------------------------------------------------------------------


def run_cycles(
    snapshots: list[MarketSnapshot],
    ohlcv_data: dict[str, pd.DataFrame],
    proposer: Proposer,
    decision_provider: DecisionProvider,
    search_budget: int = 5,
    broker_state: BrokerState | None = None,
    risk_config: RiskConfig | None = None,
    audit_logger: AuditLogger | None = None,
    exchange_state: object | None = None,
) -> list[CycleResult]:
    """Run multiple autonomous cycles without human approval between them.

    Each cycle is independent. No pause between cycles.
    If *audit_logger* is provided, each cycle is logged automatically.
    """
    results: list[CycleResult] = []
    for snapshot in snapshots:
        result = run_cycle(
            snapshot=snapshot,
            ohlcv_data=ohlcv_data,
            proposer=proposer,
            decision_provider=decision_provider,
            search_budget=search_budget,
            broker_state=broker_state,
            risk_config=risk_config,
            exchange_state=exchange_state,
        )
        results.append(result)
        if audit_logger is not None:
            audit_logger.log_cycle(result)
    return results


__all__ = [
    "CycleResult",
    "run_cycle",
    "run_cycles",
]
