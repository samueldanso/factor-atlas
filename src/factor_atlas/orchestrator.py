"""Autonomous cycle runner: observe → propose → evaluate → decide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import NAMESPACE_DNS, uuid5

import pandas as pd

from factor_atlas.contracts import (
    FactorHypothesis,
    MarketSnapshot,
    TradeDecision,
    ValidationResult,
)
from factor_atlas.decision import DecisionProvider
from factor_atlas.proposer import Proposer
from factor_atlas.validation import validate_factor

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


# ---------------------------------------------------------------------------
# Single-cycle runner
# ---------------------------------------------------------------------------


def run_cycle(
    snapshot: MarketSnapshot,
    ohlcv_data: dict[str, pd.DataFrame],
    proposer: Proposer,
    decision_provider: DecisionProvider,
    search_budget: int = 5,
) -> CycleResult:
    """Run one autonomous cycle: observe → propose → evaluate → decide.

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
            # Build param dict matching the factor schema
            params: dict[str, Any] = dict(hyp.parameters)
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

    return CycleResult(
        cycle_id=cycle_id,
        snapshot=snapshot,
        hypotheses=hypotheses,
        evaluations=evaluations,
        validated=validated,
        decision=decision,
        status="accepted" if decision is not None else "no_candidate",
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
) -> list[CycleResult]:
    """Run multiple autonomous cycles without human approval between them.

    Each cycle is independent. No pause between cycles.
    """
    results: list[CycleResult] = []
    for snapshot in snapshots:
        result = run_cycle(
            snapshot=snapshot,
            ohlcv_data=ohlcv_data,
            proposer=proposer,
            decision_provider=decision_provider,
            search_budget=search_budget,
        )
        results.append(result)
    return results


__all__ = [
    "CycleResult",
    "run_cycle",
    "run_cycles",
]
