"""Tests for the LLM boundary layer: safety validation and constraint enforcement."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from factor_atlas.contracts import (
    FactorHypothesis,
    LabeledMetric,
    MarketSnapshot,
    TradeDecision,
    ValidationMetrics,
    ValidationResult,
)
from factor_atlas.decision import DecisionProvider
from factor_atlas.fixtures.events import ACCEPTED_SNAPSHOT
from factor_atlas.llm import (
    FixtureLLMProvider,
    LLMDecisionProvider,
    LLMProposer,
    LLMProvider,
    validate_llm_hypothesis,
)
from factor_atlas.proposer import Proposer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


def _make_snapshot() -> MarketSnapshot:
    return ACCEPTED_SNAPSHOT


def _make_hypothesis(
    factor_name: str = "momentum",
    direction: str = "long",
    hyp_id: str = "hyp-001",
) -> FactorHypothesis:
    return FactorHypothesis(
        hypothesis_id=hyp_id,
        factor_name=factor_name,
        parameters={"lookback": 10, "threshold": 0.02},
        lookback=30,
        instruments=["AAPLUSDT"],
        direction=direction,
        entry_rule="signal > 0",
        exit_rule="signal reverses",
        rationale="Test hypothesis",
        created_at=_NOW,
    )


def _make_validation(
    hyp_id: str = "hyp-001",
    passed: bool = True,
    sharpe: float = 1.5,
) -> ValidationResult:
    return ValidationResult(
        validation_id="val-001",
        hypothesis_id=hyp_id,
        snapshot_id="snap-001",
        train_window=(_NOW, _NOW),
        test_window=(_NOW, _NOW),
        observations=30,
        metrics=ValidationMetrics(
            total_return=LabeledMetric(value=0.15, label="observed"),
            sharpe_ratio=LabeledMetric(value=sharpe, label="observed"),
            sortino_ratio=LabeledMetric(value=1.8, label="observed"),
            max_drawdown=LabeledMetric(value=0.05, label="observed"),
            turnover=LabeledMetric(value=0.3, label="observed"),
            fees=LabeledMetric(value=0.001, label="estimated"),
            slippage=LabeledMetric(value=0.0005, label="estimated"),
            win_rate=LabeledMetric(value=0.55, label="observed"),
        ),
        passed=passed,
        rejection_reasons=[] if passed else ["sharpe below threshold"],
    )


class _MalformedProvider:
    """Provider that returns garbage text."""

    @property
    def model_name(self) -> str:
        return "malformed-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return "this is not json {{{{"


class _ExplodingProvider:
    """Provider that raises on complete()."""

    @property
    def model_name(self) -> str:
        return "exploding-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        msg = "API key invalid"
        raise RuntimeError(msg)


class _BadFactorProvider:
    """Provider that returns an unregistered factor name."""

    @property
    def model_name(self) -> str:
        return "bad-factor-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "hypotheses": [
                    {
                        "factor_name": "magic_ai_alpha",
                        "parameters": {"lookback": 10},
                        "lookback": 30,
                        "instruments": ["AAPLUSDT"],
                        "direction": "long",
                        "entry_rule": "vibes",
                        "exit_rule": "more vibes",
                        "rationale": "Trust the LLM",
                    }
                ]
            }
        )


class _BadParamsProvider:
    """Provider that returns out-of-range parameters."""

    @property
    def model_name(self) -> str:
        return "bad-params-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "hypotheses": [
                    {
                        "factor_name": "momentum",
                        "parameters": {"lookback": 9999, "threshold": 0.02},
                        "lookback": 30,
                        "instruments": ["AAPLUSDT"],
                        "direction": "long",
                        "entry_rule": "signal > 0",
                        "exit_rule": "signal reverses",
                        "rationale": "Out of range params",
                    }
                ]
            }
        )


class _BadInstrumentProvider:
    """Provider that returns an unknown instrument."""

    @property
    def model_name(self) -> str:
        return "bad-instrument-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(
            {
                "hypotheses": [
                    {
                        "factor_name": "momentum",
                        "parameters": {"lookback": 10, "threshold": 0.02},
                        "lookback": 30,
                        "instruments": ["DOGEUSDT"],
                        "direction": "long",
                        "entry_rule": "signal > 0",
                        "exit_rule": "signal reverses",
                        "rationale": "Unknown instrument",
                    }
                ]
            }
        )


class _NonValidatedDecisionProvider:
    """Provider that tries to select a non-validated (failed) candidate."""

    @property
    def model_name(self) -> str:
        return "non-validated-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # Select index 1 which will be the failed candidate
        return json.dumps({"selected_index": 1, "rationale": "I like the failed one"})


class _OutOfRangeDecisionProvider:
    """Provider that selects an index beyond candidate list."""

    @property
    def model_name(self) -> str:
        return "out-of-range-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return json.dumps({"selected_index": 99, "rationale": "nonexistent candidate"})


# ===========================================================================
# Protocol conformance
# ===========================================================================


class TestProtocolConformance:
    """LLMProposer satisfies Proposer; LLMDecisionProvider satisfies DecisionProvider."""

    def test_llm_proposer_is_proposer(self) -> None:
        provider = FixtureLLMProvider()
        proposer = LLMProposer(provider)
        assert isinstance(proposer, Proposer)

    def test_llm_decision_provider_is_decision_provider(self) -> None:
        provider = FixtureLLMProvider()
        dp = LLMDecisionProvider(provider)
        assert isinstance(dp, DecisionProvider)

    def test_fixture_llm_provider_is_llm_provider(self) -> None:
        assert isinstance(FixtureLLMProvider(), LLMProvider)


# ===========================================================================
# 1. Valid LLM proposal
# ===========================================================================


class TestValidProposal:
    """FixtureLLMProvider returns valid hypotheses through the boundary."""

    def test_propose_returns_valid_hypotheses(self) -> None:
        provider = FixtureLLMProvider()
        proposer = LLMProposer(provider)
        snapshot = _make_snapshot()
        results = proposer.propose(snapshot, budget=3)
        assert len(results) > 0
        for hyp in results:
            assert isinstance(hyp, FactorHypothesis)

    def test_propose_factors_are_registered(self) -> None:
        from factor_atlas.config import FACTOR_VOCABULARY

        provider = FixtureLLMProvider()
        proposer = LLMProposer(provider)
        results = proposer.propose(_make_snapshot(), budget=5)
        for hyp in results:
            assert hyp.factor_name in FACTOR_VOCABULARY

    def test_propose_instruments_are_valid(self) -> None:
        from factor_atlas.config import INSTRUMENTS

        provider = FixtureLLMProvider()
        proposer = LLMProposer(provider)
        results = proposer.propose(_make_snapshot(), budget=3)
        for hyp in results:
            for inst in hyp.instruments:
                assert inst in INSTRUMENTS


# ===========================================================================
# 2. Invalid factor name rejection
# ===========================================================================


class TestInvalidFactorRejection:
    """LLM suggests unknown factor → dropped."""

    def test_unknown_factor_dropped(self) -> None:
        proposer = LLMProposer(_BadFactorProvider())
        results = proposer.propose(_make_snapshot(), budget=3)
        assert results == []

    def test_validate_unknown_factor_returns_none(self) -> None:
        data: dict[str, object] = {
            "factor_name": "magic_alpha",
            "parameters": {},
            "lookback": 30,
            "instruments": ["AAPLUSDT"],
            "direction": "long",
            "entry_rule": "x",
            "exit_rule": "y",
            "rationale": "trust me",
        }
        assert validate_llm_hypothesis(data, _make_snapshot()) is None


# ===========================================================================
# 3. Invalid parameters rejection
# ===========================================================================


class TestInvalidParamsRejection:
    """LLM suggests out-of-range params → dropped."""

    def test_out_of_range_params_dropped(self) -> None:
        proposer = LLMProposer(_BadParamsProvider())
        results = proposer.propose(_make_snapshot(), budget=3)
        assert results == []

    def test_validate_bad_params_returns_none(self) -> None:
        data: dict[str, object] = {
            "factor_name": "momentum",
            "parameters": {"lookback": 9999, "threshold": 0.02},
            "lookback": 30,
            "instruments": ["AAPLUSDT"],
            "direction": "long",
            "entry_rule": "signal > 0",
            "exit_rule": "stop loss",
            "rationale": "out of range",
        }
        assert validate_llm_hypothesis(data, _make_snapshot()) is None


# ===========================================================================
# 4. Invalid instrument rejection
# ===========================================================================


class TestInvalidInstrumentRejection:
    """LLM suggests unknown instrument → dropped."""

    def test_unknown_instrument_dropped(self) -> None:
        proposer = LLMProposer(_BadInstrumentProvider())
        results = proposer.propose(_make_snapshot(), budget=3)
        assert results == []


# ===========================================================================
# 5. Valid LLM decision
# ===========================================================================


class TestValidDecision:
    """FixtureLLMProvider selects from validated candidates."""

    def test_decide_returns_trade_decision(self) -> None:
        provider = FixtureLLMProvider()
        dp = LLMDecisionProvider(provider)
        snapshot = _make_snapshot()
        hyp = _make_hypothesis()
        val = _make_validation(passed=True)
        result = dp.decide(snapshot, [(hyp, val)], cycle_id="cycle-001")
        assert isinstance(result, TradeDecision)
        assert result.hypothesis_id == hyp.hypothesis_id
        assert result.instrument == snapshot.instrument

    def test_decide_empty_candidates_returns_none(self) -> None:
        provider = FixtureLLMProvider()
        dp = LLMDecisionProvider(provider)
        result = dp.decide(_make_snapshot(), [], cycle_id="cycle-001")
        assert result is None


# ===========================================================================
# 6. Non-validated candidate rejection
# ===========================================================================


class TestNonValidatedCandidateRejection:
    """LLM tries to select a non-validated candidate → rejected."""

    def test_non_validated_candidate_rejected(self) -> None:
        dp = LLMDecisionProvider(_NonValidatedDecisionProvider())
        snapshot = _make_snapshot()
        hyp_good = _make_hypothesis(hyp_id="hyp-good")
        val_good = _make_validation(hyp_id="hyp-good", passed=True)
        hyp_bad = _make_hypothesis(hyp_id="hyp-bad")
        val_bad = _make_validation(hyp_id="hyp-bad", passed=False)
        # Index 0 = passed, index 1 = failed; provider selects index 1
        result = dp.decide(
            snapshot,
            [(hyp_good, val_good), (hyp_bad, val_bad)],
            cycle_id="cycle-001",
        )
        assert result is None

    def test_out_of_range_index_rejected(self) -> None:
        dp = LLMDecisionProvider(_OutOfRangeDecisionProvider())
        snapshot = _make_snapshot()
        hyp = _make_hypothesis()
        val = _make_validation(passed=True)
        result = dp.decide(snapshot, [(hyp, val)], cycle_id="cycle-001")
        assert result is None


# ===========================================================================
# 7. Malformed JSON rejection
# ===========================================================================


class TestMalformedJSONRejection:
    """Provider returns garbage → handled gracefully."""

    def test_malformed_propose_returns_empty(self) -> None:
        proposer = LLMProposer(_MalformedProvider())
        results = proposer.propose(_make_snapshot(), budget=3)
        assert results == []

    def test_malformed_decide_returns_none(self) -> None:
        dp = LLMDecisionProvider(_MalformedProvider())
        snapshot = _make_snapshot()
        hyp = _make_hypothesis()
        val = _make_validation(passed=True)
        result = dp.decide(snapshot, [(hyp, val)], cycle_id="cycle-001")
        assert result is None

    def test_exploding_propose_returns_empty(self) -> None:
        proposer = LLMProposer(_ExplodingProvider())
        results = proposer.propose(_make_snapshot(), budget=3)
        assert results == []

    def test_exploding_decide_returns_none(self) -> None:
        dp = LLMDecisionProvider(_ExplodingProvider())
        snapshot = _make_snapshot()
        hyp = _make_hypothesis()
        val = _make_validation(passed=True)
        result = dp.decide(snapshot, [(hyp, val)], cycle_id="cycle-001")
        assert result is None


# ===========================================================================
# 8. No-credential fixture run
# ===========================================================================


class TestCredentialFreeRun:
    """Entire propose→decide cycle works without any API key."""

    def test_full_cycle_no_credentials(self) -> None:
        provider = FixtureLLMProvider()
        proposer = LLMProposer(provider)
        dp = LLMDecisionProvider(provider)

        snapshot = _make_snapshot()

        # Propose
        hypotheses = proposer.propose(snapshot, budget=3)
        assert len(hypotheses) > 0

        # Build synthetic validated candidates
        candidates = []
        for hyp in hypotheses:
            val = _make_validation(hyp_id=hyp.hypothesis_id, passed=True)
            candidates.append((hyp, val))

        # Decide
        decision = dp.decide(snapshot, candidates, cycle_id="cycle-e2e")
        assert isinstance(decision, TradeDecision)
        assert decision.hypothesis_id in [h.hypothesis_id for h in hypotheses]


# ===========================================================================
# 9. Model name appears in audit trail
# ===========================================================================


class TestModelNameTraceability:
    """The LLM provider name is traceable for audit."""

    def test_fixture_model_name(self) -> None:
        provider = FixtureLLMProvider()
        assert provider.model_name == "fixture-llm-v1"

    def test_proposer_exposes_model_name(self) -> None:
        provider = FixtureLLMProvider()
        proposer = LLMProposer(provider)
        assert proposer.model_name == "fixture-llm-v1"

    def test_decision_exposes_model_name(self) -> None:
        provider = FixtureLLMProvider()
        dp = LLMDecisionProvider(provider)
        assert dp.model_name == "fixture-llm-v1"
