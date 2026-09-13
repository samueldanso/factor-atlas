"""Competition-period paper-trading runner for FactorAtlas."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from factor_atlas.adapters.normalize import research_to_execution
from factor_atlas.audit import AuditLogger
from factor_atlas.broker import BrokerState
from factor_atlas.config import (
    CATEGORY,
    EXECUTION_INSTRUMENTS,
    FACTOR_VOCABULARY,
    RESEARCH_INSTRUMENTS,
)
from factor_atlas.decision import FixtureDecisionProvider
from factor_atlas.fixtures import ACCEPTED_SNAPSHOT, RAAPLUSDT_OHLCV, REJECTED_SNAPSHOT
from factor_atlas.orchestrator import CycleResult, run_cycles
from factor_atlas.proposer import FixtureProposer
from factor_atlas.risk import RiskConfig

SOFTWARE_VERSION = "0.1.0"

_DEFAULT_OUTPUT_DIR = Path("artifacts/paper-trading")


# ---------------------------------------------------------------------------
# Config hash
# ---------------------------------------------------------------------------


def compute_config_hash(risk_config: RiskConfig) -> str:
    """Compute a deterministic hash from risk config, factors, and instruments."""
    risk_dict: dict[str, Any] = {
        "max_data_age_hours": risk_config.max_data_age_hours,
        "max_notional": str(risk_config.max_notional),
        "max_concurrent_positions": risk_config.max_concurrent_positions,
        "max_exposure": str(risk_config.max_exposure),
        "cooldown_seconds": risk_config.cooldown_seconds,
        "daily_loss_limit": str(risk_config.daily_loss_limit),
        "max_concentration_per_instrument": risk_config.max_concentration_per_instrument,
        "max_quantity": str(risk_config.max_quantity),
    }
    config_data = json.dumps(
        {
            "risk": risk_dict,
            "factors": sorted(FACTOR_VOCABULARY),
            "research_instruments": sorted(RESEARCH_INSTRUMENTS),
            "execution_instruments": sorted(EXECUTION_INSTRUMENTS),
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(config_data.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Git commit hash
# ---------------------------------------------------------------------------


def get_git_commit() -> str:
    """Get the short git commit hash, or 'unknown' if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


# ---------------------------------------------------------------------------
# Paper log record builder
# ---------------------------------------------------------------------------


def _build_paper_record(
    cycle_result: CycleResult,
    config_hash: str,
) -> dict[str, Any]:
    """Build a paper log record dict from a CycleResult."""
    order = cycle_result.order
    decision = cycle_result.decision

    # Determine execution instrument (normalize rToken -> perp)
    raw_instrument = cycle_result.snapshot.instrument
    exec_instrument = research_to_execution(raw_instrument)

    # Find hypothesis and validation info
    hypothesis_id = ""
    factor_name = ""
    validation_sharpe: float | None = None
    rationale = ""

    if decision is not None:
        hypothesis_id = decision.hypothesis_id
        rationale = decision.rationale
        # Find matching hypothesis
        for hyp, val in cycle_result.validated:
            if hyp.hypothesis_id == decision.hypothesis_id:
                factor_name = hyp.factor_name
                validation_sharpe = val.metrics.sharpe_ratio.value
                break

    # Build gate results list
    gate_results_list: list[dict[str, Any]] = []
    if cycle_result.gate_results is not None:
        gate_results_list = [
            {
                "gate_name": g.gate_name,
                "passed": g.passed,
                "reason": g.reason,
            }
            for g in cycle_result.gate_results
        ]

    if order is not None:
        return {
            "order_id": order.order_id,
            "decision_id": order.decision_id,
            "event_id": order.event_id,
            "timestamp": order.timestamp.isoformat(),
            "instrument": exec_instrument,
            "category": CATEGORY,
            "side": order.side,
            "price": str(order.price),
            "quantity": str(order.quantity),
            "notional": str(order.notional),
            "pre_balance": str(order.pre_balance),
            "post_balance": str(order.post_balance),
            "fees": str(order.fees),
            "slippage": str(order.slippage),
            "status": order.status,
            "fill_price": str(order.fill_price) if order.fill_price else None,
            "rejection_reason": order.rejection_reason,
            "cycle_id": cycle_result.cycle_id,
            "hypothesis_id": hypothesis_id,
            "factor_name": factor_name,
            "risk_gate_results": gate_results_list,
            "validation_sharpe": validation_sharpe,
            "rationale": rationale,
            "software_version": SOFTWARE_VERSION,
            "config_hash": config_hash,
        }

    # No order (no_candidate / no_hypothesis)
    return {
        "order_id": None,
        "decision_id": decision.decision_id if decision else None,
        "event_id": None,
        "timestamp": cycle_result.snapshot.timestamp.isoformat(),
        "instrument": exec_instrument,
        "category": CATEGORY,
        "side": decision.side if decision else None,
        "price": str(cycle_result.snapshot.close),
        "quantity": "0",
        "notional": "0",
        "pre_balance": None,
        "post_balance": None,
        "fees": "0",
        "slippage": "0",
        "status": cycle_result.status,
        "fill_price": None,
        "rejection_reason": cycle_result.status,
        "cycle_id": cycle_result.cycle_id,
        "hypothesis_id": hypothesis_id,
        "factor_name": factor_name,
        "risk_gate_results": gate_results_list,
        "validation_sharpe": validation_sharpe,
        "rationale": rationale,
        "software_version": SOFTWARE_VERSION,
        "config_hash": config_hash,
    }


# ---------------------------------------------------------------------------
# Fixture mode data builder
# ---------------------------------------------------------------------------


def _build_fixture_data() -> tuple[
    list[Any],
    dict[str, pd.DataFrame],
]:
    """Build snapshots and OHLCV data from fixtures.

    Returns (snapshots, ohlcv_dict).
    """
    snapshots = [ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT]

    # Build OHLCV DataFrame from fixture bars
    records = []
    for bar in RAAPLUSDT_OHLCV:
        records.append(
            {
                "timestamp": bar.timestamp,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
        )
    df = pd.DataFrame(records)
    ohlcv_data: dict[str, pd.DataFrame] = {"RAAPLUSDT": df}

    return snapshots, ohlcv_data


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------


def _build_manifest(
    run_id: str,
    mode: str,
    start_time: datetime,
    end_time: datetime,
    results: list[CycleResult],
    config_hash: str,
    commit: str,
) -> dict[str, Any]:
    """Build the run manifest dict."""
    accepted = sum(1 for r in results if r.status == "accepted")
    rejected = sum(1 for r in results if r.status != "accepted")
    research_insts = sorted({r.snapshot.instrument for r in results})
    exec_insts = sorted({research_to_execution(i) for i in research_insts})

    return {
        "run_id": run_id,
        "start_timestamp": start_time.isoformat(),
        "end_timestamp": end_time.isoformat(),
        "timezone": "UTC",
        "mode": mode,
        "instruments": research_insts,
        "execution_instruments": exec_insts,
        "cycles_completed": len(results),
        "accepted_count": accepted,
        "rejected_count": rejected,
        "code_commit": commit,
        "config_hash": config_hash,
        "software_version": SOFTWARE_VERSION,
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_paper_session(
    mode: str = "fixture",
    cycles: int = 2,
    output_dir: Path | None = None,
) -> Path:
    """Run a paper-trading session and write results.

    Returns the path to the run output directory.
    """
    if mode not in ("fixture", "demo"):
        msg = f"Unknown mode '{mode}'. Must be 'fixture' or 'demo'."
        raise ValueError(msg)

    if mode == "demo":
        print(
            "Demo mode requires Bitget credentials and is not yet integrated.",
            file=sys.stderr,
        )
        print("Use --mode fixture for deterministic runs.", file=sys.stderr)
        msg = "Demo mode not yet implemented for autonomous loop."
        raise NotImplementedError(msg)

    # Setup output
    run_id = str(uuid4())
    base_dir = output_dir or _DEFAULT_OUTPUT_DIR
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Config
    risk_config = RiskConfig()
    config_hash = compute_config_hash(risk_config)
    commit = get_git_commit()
    start_time = datetime.now(tz=UTC)

    # Audit logger
    audit_path = run_dir / "audit_log.jsonl"
    audit_logger = AuditLogger(output_path=audit_path)

    # Fixture mode: use fixture data, proposer, and decision provider
    snapshots_all, ohlcv_data = _build_fixture_data()

    # Trim to requested cycle count
    snapshots = snapshots_all[:cycles]

    broker_state = BrokerState()
    proposer = FixtureProposer()
    decision_provider = FixtureDecisionProvider()

    results = run_cycles(
        snapshots=snapshots,
        ohlcv_data=ohlcv_data,
        proposer=proposer,
        decision_provider=decision_provider,
        broker_state=broker_state,
        risk_config=risk_config,
        audit_logger=audit_logger,
    )

    end_time = datetime.now(tz=UTC)

    # Write paper log
    paper_log_path = run_dir / "paper_log.jsonl"
    with paper_log_path.open("a") as f:
        for result in results:
            record = _build_paper_record(result, config_hash)
            f.write(json.dumps(record) + "\n")

    # Write manifest
    manifest = _build_manifest(
        run_id=run_id,
        mode=mode,
        start_time=start_time,
        end_time=end_time,
        results=results,
        config_hash=config_hash,
        commit=commit,
    )
    manifest_path = run_dir / "manifest.json"
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Paper run complete: {run_dir}")
    print(f"  Cycles: {len(results)}")
    print(f"  Accepted: {manifest['accepted_count']}")
    print(f"  Rejected: {manifest['rejected_count']}")
    print(f"  Paper log: {paper_log_path}")
    print(f"  Audit log: {audit_path}")
    print(f"  Manifest: {manifest_path}")

    return run_dir


# ---------------------------------------------------------------------------
# Dry-run validation
# ---------------------------------------------------------------------------


def validate_config() -> None:
    """Validate configuration and exit. Used by --dry-run."""
    risk_config = RiskConfig()
    config_hash = compute_config_hash(risk_config)
    commit = get_git_commit()

    print("FactorAtlas configuration valid.")
    print(f"  Software version: {SOFTWARE_VERSION}")
    print(f"  Config hash: {config_hash}")
    print(f"  Git commit: {commit}")
    print(f"  Research instruments: {sorted(RESEARCH_INSTRUMENTS)}")
    print(f"  Execution instruments: {sorted(EXECUTION_INSTRUMENTS)}")
    print(f"  Factor vocabulary: {sorted(FACTOR_VOCABULARY)}")
    print(
        f"  Risk config: max_notional={risk_config.max_notional}, "
        f"max_positions={risk_config.max_concurrent_positions}, "
        f"daily_loss_limit={risk_config.daily_loss_limit}"
    )


__all__ = [
    "SOFTWARE_VERSION",
    "compute_config_hash",
    "get_git_commit",
    "run_paper_session",
    "validate_config",
]
