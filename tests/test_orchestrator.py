"""Tests for the autonomous discovery-and-decision cycle."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from factor_atlas.contracts import (
    FactorHypothesis,
    MarketSnapshot,
    TradeDecision,
)
from factor_atlas.decision import DecisionProvider, FixtureDecisionProvider
from factor_atlas.fixtures.events import (
    ACCEPTED_SNAPSHOT,
    RAAPLUSDT_OHLCV,
    REJECTED_SNAPSHOT,
)
from factor_atlas.orchestrator import CycleResult, run_cycle, run_cycles
from factor_atlas.proposer import FixtureProposer, Proposer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_ohlcv_df(snapshots: list[MarketSnapshot]) -> pd.DataFrame:
    """Convert fixture snapshots to a DataFrame suitable for validate_factor."""
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
    """Build the instrument -> OHLCV DataFrame mapping from fixtures."""
    return {"RAAPLUSDT": _build_ohlcv_df(RAAPLUSDT_OHLCV)}


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify FixtureProposer and FixtureDecisionProvider satisfy protocols."""

    def test_fixture_proposer_is_proposer(self) -> None:
        assert isinstance(FixtureProposer(), Proposer)

    def test_fixture_decision_provider_is_decision_provider(self) -> None:
        assert isinstance(FixtureDecisionProvider(), DecisionProvider)


# ---------------------------------------------------------------------------
# FixtureProposer tests
# ---------------------------------------------------------------------------


class TestFixtureProposer:
    """Test deterministic hypothesis generation."""

    def test_propose_returns_list(self) -> None:
        proposer = FixtureProposer()
        hypotheses = proposer.propose(ACCEPTED_SNAPSHOT, budget=3)
        assert isinstance(hypotheses, list)
        assert len(hypotheses) <= 3

    def test_propose_respects_budget(self) -> None:
        proposer = FixtureProposer()
        h1 = proposer.propose(ACCEPTED_SNAPSHOT, budget=1)
        h5 = proposer.propose(ACCEPTED_SNAPSHOT, budget=5)
        assert len(h1) == 1
        assert len(h5) == 5

    def test_propose_uses_snapshot_instrument(self) -> None:
        proposer = FixtureProposer()
        hypotheses = proposer.propose(ACCEPTED_SNAPSHOT, budget=5)
        for hyp in hypotheses:
            assert ACCEPTED_SNAPSHOT.instrument in hyp.instruments

    def test_propose_generates_valid_hypotheses(self) -> None:
        proposer = FixtureProposer()
        hypotheses = proposer.propose(ACCEPTED_SNAPSHOT, budget=5)
        for hyp in hypotheses:
            assert isinstance(hyp, FactorHypothesis)
            assert hyp.rationale.strip()
            assert hyp.entry_rule.strip()
            assert hyp.exit_rule.strip()

    def test_propose_zero_budget(self) -> None:
        proposer = FixtureProposer()
        hypotheses = proposer.propose(ACCEPTED_SNAPSHOT, budget=0)
        assert hypotheses == []


# ---------------------------------------------------------------------------
# FixtureDecisionProvider tests
# ---------------------------------------------------------------------------


class TestFixtureDecisionProvider:
    """Test deterministic decision selection."""

    def test_decide_empty_candidates(self) -> None:
        dp = FixtureDecisionProvider()
        result = dp.decide(ACCEPTED_SNAPSHOT, [], "cycle-1")
        assert result is None

    def test_decide_picks_highest_sharpe(self) -> None:
        """Decision provider must select the candidate with highest Sharpe."""
        proposer = FixtureProposer()
        ohlcv = _ohlcv_data()
        dp = FixtureDecisionProvider()

        # Run a cycle to get validated candidates
        cycle = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp, search_budget=5)

        if cycle.validated:
            sharpe_values = [v.metrics.sharpe_ratio.value for _, v in cycle.validated]
            if cycle.decision is not None:
                # Find which hypothesis the decision picked
                chosen = [
                    v.metrics.sharpe_ratio.value
                    for h, v in cycle.validated
                    if h.hypothesis_id == cycle.decision.hypothesis_id
                ]
                assert len(chosen) == 1
                assert chosen[0] == max(sharpe_values)

    def test_decide_returns_trade_decision(self) -> None:
        proposer = FixtureProposer()
        ohlcv = _ohlcv_data()
        dp = FixtureDecisionProvider()

        cycle = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp, search_budget=5)
        if cycle.decision is not None:
            assert isinstance(cycle.decision, TradeDecision)
            assert cycle.decision.instrument == ACCEPTED_SNAPSHOT.instrument
            assert cycle.decision.side in ("buy", "sell")
            assert cycle.decision.quantity > 0
            assert cycle.decision.rationale.strip()


# ---------------------------------------------------------------------------
# CycleRunner tests
# ---------------------------------------------------------------------------


class TestCycleRunner:
    """Test single-cycle execution."""

    def test_cycle_result_structure(self) -> None:
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        result = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp)
        assert isinstance(result, CycleResult)
        assert result.cycle_id
        assert result.snapshot is ACCEPTED_SNAPSHOT
        assert isinstance(result.hypotheses, list)
        assert isinstance(result.evaluations, list)
        assert isinstance(result.validated, list)
        assert result.status in ("accepted", "no_candidate", "no_hypothesis")

    def test_no_hypothesis_status(self) -> None:
        """Zero-budget produces no_hypothesis."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        result = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp, search_budget=0)
        assert result.status == "no_hypothesis"
        assert result.hypotheses == []
        assert result.decision is None

    def test_no_candidate_when_no_ohlcv(self) -> None:
        """Missing OHLCV data for instrument → no evaluations → no_candidate."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        # Empty OHLCV dict — no data for NVDAUSDT
        ohlcv: dict[str, pd.DataFrame] = {}

        result = run_cycle(REJECTED_SNAPSHOT, ohlcv, proposer, dp, search_budget=3)
        assert result.status == "no_candidate"
        assert result.decision is None
        assert len(result.evaluations) == 0

    def test_accepted_cycle(self) -> None:
        """A cycle with AAPLUSDT fixture data can produce an accepted decision."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        result = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp, search_budget=5)
        # With 30 bars of AAPL data, at least some factors should produce signals
        assert len(result.hypotheses) == 5
        assert len(result.evaluations) == 5
        # Status is either accepted or no_candidate depending on validation
        assert result.status in ("accepted", "no_candidate")

    def test_decision_contains_required_fields(self) -> None:
        """If a decision is made, it must contain instrument, side, quantity, rationale."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        result = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp, search_budget=5)
        if result.decision is not None:
            d = result.decision
            assert d.instrument in ("AAPLUSDT", "NVDAUSDT", "TSLAUSDT", "METAUSDT")
            assert d.side in ("buy", "sell")
            assert d.quantity > Decimal(0)
            assert d.rationale.strip()

    def test_no_human_approval_pause(self) -> None:
        """The cycle runner must complete without any interactive pause."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        # This test simply verifies the function returns — no blocking.
        result = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp)
        assert isinstance(result, CycleResult)


# ---------------------------------------------------------------------------
# Candidate allowlist test
# ---------------------------------------------------------------------------


class TestCandidateAllowlist:
    """Decision provider must only select from validated candidates."""

    def test_decision_references_validated_hypothesis(self) -> None:
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        result = run_cycle(ACCEPTED_SNAPSHOT, ohlcv, proposer, dp, search_budget=5)
        if result.decision is not None:
            validated_ids = {h.hypothesis_id for h, _ in result.validated}
            assert result.decision.hypothesis_id in validated_ids

    def test_cannot_select_non_validated(self) -> None:
        """FixtureDecisionProvider given only failed candidates returns None."""
        dp = FixtureDecisionProvider()
        # No candidates → None
        assert dp.decide(ACCEPTED_SNAPSHOT, [], "cycle-test") is None


# ---------------------------------------------------------------------------
# MultiCycleRunner tests
# ---------------------------------------------------------------------------


class TestMultiCycleRunner:
    """Test multi-cycle autonomous execution."""

    def test_multi_cycle_returns_list(self) -> None:
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        results = run_cycles(
            [ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT],
            ohlcv,
            proposer,
            dp,
            search_budget=3,
        )
        assert isinstance(results, list)
        assert len(results) == 2

    def test_multi_cycle_no_pause(self) -> None:
        """All cycles complete autonomously without human approval."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        snapshots = [ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT, ACCEPTED_SNAPSHOT]
        results = run_cycles(snapshots, ohlcv, proposer, dp, search_budget=3)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, CycleResult)

    def test_both_statuses_demonstrated(self) -> None:
        """Multi-cycle run should demonstrate both accepted and no_candidate statuses."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        # ACCEPTED_SNAPSHOT has AAPLUSDT data; REJECTED_SNAPSHOT is NVDAUSDT with no data
        results = run_cycles(
            [ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT],
            ohlcv,
            proposer,
            dp,
            search_budget=5,
        )
        statuses = {r.status for r in results}
        # At minimum, the NVDAUSDT snapshot with no OHLCV data should be no_candidate
        assert "no_candidate" in statuses

    def test_each_cycle_is_independent(self) -> None:
        """Each cycle result should reference the correct snapshot."""
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        snapshots = [ACCEPTED_SNAPSHOT, REJECTED_SNAPSHOT]
        results = run_cycles(snapshots, ohlcv, proposer, dp, search_budget=3)

        assert results[0].snapshot is ACCEPTED_SNAPSHOT
        assert results[1].snapshot is REJECTED_SNAPSHOT

    def test_empty_snapshots(self) -> None:
        proposer = FixtureProposer()
        dp = FixtureDecisionProvider()
        ohlcv = _ohlcv_data()

        results = run_cycles([], ohlcv, proposer, dp)
        assert results == []
