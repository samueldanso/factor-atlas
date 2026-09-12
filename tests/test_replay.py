"""Tests for deterministic replay verification."""

from __future__ import annotations

import pandas as pd

from factor_atlas.audit import AuditLogger
from factor_atlas.broker import BrokerState
from factor_atlas.contracts import MarketSnapshot
from factor_atlas.decision import FixtureDecisionProvider
from factor_atlas.fixtures.events import (
    AAPLUSDT_OHLCV,
    ACCEPTED_SNAPSHOT,
    REJECTED_SNAPSHOT,
)
from factor_atlas.orchestrator import run_cycles
from factor_atlas.proposer import FixtureProposer
from factor_atlas.replay import ReplayResult, verify_replay
from factor_atlas.risk import RiskConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_ohlcv_df(snapshots: list[MarketSnapshot]) -> pd.DataFrame:
    rows = []
    for s in snapshots:
        rows.append(
            {
                "timestamp": s.timestamp,
                "open": float(s.open),
                "high": float(s.high),
                "low": float(s.low),
                "close": float(s.close),
                "volume": float(s.volume),
            }
        )
    return pd.DataFrame(rows)


def _ohlcv_data() -> dict[str, pd.DataFrame]:
    return {"AAPLUSDT": _build_ohlcv_df(AAPLUSDT_OHLCV)}


def _run_and_log(
    snapshots: list[MarketSnapshot],
) -> tuple[list[object], AuditLogger]:
    """Run cycles and return (snapshots, logger with events)."""
    ohlcv = _ohlcv_data()
    proposer = FixtureProposer()
    dp = FixtureDecisionProvider()
    broker = BrokerState()
    config = RiskConfig()
    logger = AuditLogger()

    run_cycles(
        snapshots,
        ohlcv,
        proposer,
        dp,
        search_budget=5,
        broker_state=broker,
        risk_config=config,
        audit_logger=logger,
    )
    return list(snapshots), logger


# ---------------------------------------------------------------------------
# Deterministic replay
# ---------------------------------------------------------------------------


class TestDeterministicReplay:
    """Same inputs → same audit events (ignoring UUIDs/timestamps)."""

    def test_single_accepted_cycle_replays(self) -> None:
        snaps, logger = _run_and_log([ACCEPTED_SNAPSHOT])
        result = verify_replay(
            snapshots=snaps,
            ohlcv_data=_ohlcv_data(),
            proposer=FixtureProposer(),
            decision_provider=FixtureDecisionProvider(),
            config=RiskConfig(),
            original_events=logger.get_events(),
        )
        assert isinstance(result, ReplayResult)
        assert result.matches is True
        assert result.first_mismatch_index is None

    def test_single_rejected_cycle_replays(self) -> None:
        snaps, logger = _run_and_log([REJECTED_SNAPSHOT])
        result = verify_replay(
            snapshots=snaps,
            ohlcv_data=_ohlcv_data(),
            proposer=FixtureProposer(),
            decision_provider=FixtureDecisionProvider(),
            config=RiskConfig(),
            original_events=logger.get_events(),
        )
        assert result.matches is True

    def test_multi_cycle_replays(self) -> None:
        snaps, logger = _run_and_log([ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT])
        result = verify_replay(
            snapshots=snaps,
            ohlcv_data=_ohlcv_data(),
            proposer=FixtureProposer(),
            decision_provider=FixtureDecisionProvider(),
            config=RiskConfig(),
            original_events=logger.get_events(),
        )
        assert result.matches is True
        assert result.original_count == 14
        assert result.replay_count == 14


# ---------------------------------------------------------------------------
# ReplayResult structure
# ---------------------------------------------------------------------------


class TestReplayResult:
    """ReplayResult fields are populated correctly."""

    def test_matching_result_fields(self) -> None:
        snaps, logger = _run_and_log([ACCEPTED_SNAPSHOT])
        result = verify_replay(
            snapshots=snaps,
            ohlcv_data=_ohlcv_data(),
            proposer=FixtureProposer(),
            decision_provider=FixtureDecisionProvider(),
            config=RiskConfig(),
            original_events=logger.get_events(),
        )
        assert result.matches is True
        assert result.original_count == 7
        assert result.replay_count == 7
        assert result.first_mismatch_index is None
        assert result.mismatch_detail is None

    def test_count_mismatch_detected(self) -> None:
        """If we pass fewer original events, the replay detects a count mismatch."""
        snaps, logger = _run_and_log([ACCEPTED_SNAPSHOT])
        events = logger.get_events()
        # Remove last event to force a count mismatch
        truncated = events[:5]
        result = verify_replay(
            snapshots=snaps,
            ohlcv_data=_ohlcv_data(),
            proposer=FixtureProposer(),
            decision_provider=FixtureDecisionProvider(),
            config=RiskConfig(),
            original_events=truncated,
        )
        assert result.matches is False
        assert result.original_count == 5
        assert result.replay_count == 7
        assert result.first_mismatch_index == 5
        assert "count differs" in (result.mismatch_detail or "")


# ---------------------------------------------------------------------------
# Replay idempotency
# ---------------------------------------------------------------------------


class TestReplayIdempotency:
    """Running replay multiple times produces the same result."""

    def test_double_replay_matches(self) -> None:
        snaps, logger = _run_and_log([ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT])
        kwargs = {
            "snapshots": snaps,
            "ohlcv_data": _ohlcv_data(),
            "proposer": FixtureProposer(),
            "decision_provider": FixtureDecisionProvider(),
            "config": RiskConfig(),
            "original_events": logger.get_events(),
        }
        r1 = verify_replay(**kwargs)  # type: ignore[arg-type]
        r2 = verify_replay(**kwargs)  # type: ignore[arg-type]
        assert r1.matches is True
        assert r2.matches is True
        assert r1.original_count == r2.original_count
