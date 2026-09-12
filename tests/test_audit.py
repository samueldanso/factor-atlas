"""Tests for the append-only JSONL audit logger."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from factor_atlas.audit import AuditLogger
from factor_atlas.broker import BrokerState
from factor_atlas.contracts import AuditEvent, MarketSnapshot
from factor_atlas.decision import FixtureDecisionProvider
from factor_atlas.fixtures.events import (
    ACCEPTED_SNAPSHOT,
    RAAPLUSDT_OHLCV,
    REJECTED_SNAPSHOT,
)
from factor_atlas.orchestrator import CycleResult, run_cycle
from factor_atlas.proposer import FixtureProposer
from factor_atlas.risk import RiskConfig

_STAGE_ORDER = ["observe", "propose", "evaluate", "decide", "gate", "execute", "learn"]


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
    return {"RAAPLUSDT": _build_ohlcv_df(RAAPLUSDT_OHLCV)}


def _accepted_cycle() -> CycleResult:
    return run_cycle(
        ACCEPTED_SNAPSHOT,
        _ohlcv_data(),
        FixtureProposer(),
        FixtureDecisionProvider(),
        search_budget=5,
        broker_state=BrokerState(),
        risk_config=RiskConfig(),
    )


def _rejected_cycle() -> CycleResult:
    return run_cycle(
        REJECTED_SNAPSHOT,
        {},  # no OHLCV → no_candidate
        FixtureProposer(),
        FixtureDecisionProvider(),
        search_budget=5,
    )


# ---------------------------------------------------------------------------
# In-memory logging
# ---------------------------------------------------------------------------


class TestAuditLoggerInMemory:
    """AuditLogger with no file output."""

    def test_log_cycle_returns_seven_events(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        assert len(events) == 7

    def test_all_stages_present(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        stages = [e.stage for e in events]
        assert stages == _STAGE_ORDER

    def test_get_events_accumulates(self) -> None:
        logger = AuditLogger()
        logger.log_cycle(_accepted_cycle())
        logger.log_cycle(_rejected_cycle())
        assert len(logger.get_events()) == 14

    def test_events_are_audit_event_instances(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        for e in events:
            assert isinstance(e, AuditEvent)


# ---------------------------------------------------------------------------
# Chain integrity
# ---------------------------------------------------------------------------


class TestChainIntegrity:
    """parent_event_id links form a connected chain per cycle."""

    def test_first_event_has_no_parent(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        assert events[0].parent_event_id is None

    def test_subsequent_events_have_parent(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        for i in range(1, len(events)):
            assert events[i].parent_event_id == events[i - 1].event_id

    def test_all_events_share_cycle_id(self) -> None:
        logger = AuditLogger()
        cr = _accepted_cycle()
        events = logger.log_cycle(cr)
        for e in events:
            assert e.cycle_id == cr.cycle_id

    def test_chain_links_are_unique(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        event_ids = [e.event_id for e in events]
        assert len(event_ids) == len(set(event_ids))


# ---------------------------------------------------------------------------
# Accepted vs rejected cycle coverage
# ---------------------------------------------------------------------------


class TestAcceptedCycleAudit:
    """An accepted cycle has all 7 stages with meaningful payloads."""

    def test_observe_payload(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        obs = events[0]
        assert obs.stage == "observe"
        assert "snapshot_id" in obs.payload
        assert "instrument" in obs.payload

    def test_propose_payload(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        prop = events[1]
        assert prop.stage == "propose"
        assert "hypothesis_ids" in prop.payload
        assert "count" in prop.payload

    def test_evaluate_payload(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_accepted_cycle())
        ev = events[2]
        assert ev.stage == "evaluate"
        assert "evaluations" in ev.payload

    def test_decide_payload_accepted(self) -> None:
        logger = AuditLogger()
        cr = _accepted_cycle()
        events = logger.log_cycle(cr)
        dec = events[3]
        assert dec.stage == "decide"
        if cr.status == "accepted":
            assert dec.payload["decision_id"] is not None

    def test_gate_payload(self) -> None:
        logger = AuditLogger()
        cr = _accepted_cycle()
        events = logger.log_cycle(cr)
        gate = events[4]
        assert gate.stage == "gate"
        assert "gate_results" in gate.payload

    def test_execute_payload(self) -> None:
        logger = AuditLogger()
        cr = _accepted_cycle()
        events = logger.log_cycle(cr)
        exe = events[5]
        assert exe.stage == "execute"
        assert "status" in exe.payload

    def test_learn_payload(self) -> None:
        logger = AuditLogger()
        cr = _accepted_cycle()
        events = logger.log_cycle(cr)
        learn = events[6]
        assert learn.stage == "learn"
        assert "cycle_summary" in learn.payload
        summary = learn.payload["cycle_summary"]
        assert isinstance(summary, dict)
        assert "cycle_id" in summary


class TestRejectedCycleAudit:
    """A rejected (no_candidate) cycle also produces all 7 stages."""

    def test_seven_stages(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_rejected_cycle())
        assert len(events) == 7
        assert [e.stage for e in events] == _STAGE_ORDER

    def test_decide_null_decision(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_rejected_cycle())
        dec = events[3]
        assert dec.payload["decision_id"] is None
        assert dec.payload["status"] == "no_candidate"

    def test_execute_skipped(self) -> None:
        logger = AuditLogger()
        events = logger.log_cycle(_rejected_cycle())
        exe = events[5]
        assert exe.payload["status"] == "skipped"


# ---------------------------------------------------------------------------
# JSONL file output
# ---------------------------------------------------------------------------


class TestJSONLOutput:
    """AuditLogger writes valid JSONL to disk."""

    def test_jsonl_lines_are_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        logger = AuditLogger(output_path=path)
        logger.log_cycle(_accepted_cycle())

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 7
        for line in lines:
            obj = json.loads(line)
            assert "event_id" in obj
            assert "stage" in obj

    def test_flush_writes_all_events(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        logger = AuditLogger(output_path=path)
        logger.log_cycle(_accepted_cycle())
        logger.log_cycle(_rejected_cycle())
        logger.flush()  # overwrite with all events

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 14

    def test_append_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        logger = AuditLogger(output_path=path)
        logger.log_cycle(_accepted_cycle())
        logger.log_cycle(_rejected_cycle())

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 14

    def test_each_line_round_trips_to_audit_event(self, tmp_path: Path) -> None:
        path = tmp_path / "audit.jsonl"
        logger = AuditLogger(output_path=path)
        logger.log_cycle(_accepted_cycle())

        for line in path.read_text().strip().split("\n"):
            obj = json.loads(line)
            event = AuditEvent.model_validate(obj)
            assert event.stage in _STAGE_ORDER


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    """run_cycles with audit_logger parameter."""

    def test_run_cycles_logs_when_logger_provided(self) -> None:
        from factor_atlas.orchestrator import run_cycles

        logger = AuditLogger()
        run_cycles(
            [ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT],
            _ohlcv_data(),
            FixtureProposer(),
            FixtureDecisionProvider(),
            search_budget=5,
            audit_logger=logger,
        )
        assert len(logger.get_events()) == 14

    def test_run_cycles_works_without_logger(self) -> None:
        from factor_atlas.orchestrator import run_cycles

        results = run_cycles(
            [ACCEPTED_SNAPSHOT],
            _ohlcv_data(),
            FixtureProposer(),
            FixtureDecisionProvider(),
            search_budget=5,
        )
        assert len(results) == 1
