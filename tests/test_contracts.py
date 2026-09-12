"""Tests for FactorAtlas typed contracts and fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from factor_atlas.config import INSTRUMENTS, MIN_OBSERVATIONS
from factor_atlas.contracts import (
    AuditEvent,
    FactorHypothesis,
    LabeledMetric,
    MarketSnapshot,
    PaperOrder,
    RiskGateResult,
    TradeDecision,
    ValidationMetrics,
    ValidationResult,
)
from factor_atlas.fixtures import (
    ACCEPTED_SNAPSHOT,
    RAAPLUSDT_OHLCV,
    REJECTED_HYPOTHESIS,
    REJECTED_SNAPSHOT,
    VALID_HYPOTHESIS,
)

_NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)


# -----------------------------------------------------------------------
# MarketSnapshot
# -----------------------------------------------------------------------


class TestMarketSnapshot:
    def test_valid_construction(self) -> None:
        snap = MarketSnapshot(
            timestamp=_NOW,
            snapshot_id="snap-1",
            instrument="RAAPLUSDT",
            open=Decimal("230.00"),
            high=Decimal("231.50"),
            low=Decimal("229.20"),
            close=Decimal("230.60"),
            volume=Decimal(50000),
            source="fixture",
        )
        assert snap.instrument == "RAAPLUSDT"
        assert snap.category == "SPOT"
        assert snap.close == Decimal("230.60")

    def test_invalid_instrument(self) -> None:
        with pytest.raises(ValidationError):
            MarketSnapshot(
                timestamp=_NOW,
                snapshot_id="snap-1",
                instrument="BTCUSDT",
                open=Decimal("230.00"),
                high=Decimal("231.50"),
                low=Decimal("229.20"),
                close=Decimal("230.60"),
                volume=Decimal(50000),
                source="fixture",
            )

    def test_missing_timestamp_tzinfo(self) -> None:
        with pytest.raises(ValidationError, match="UTC"):
            MarketSnapshot(
                timestamp=datetime(2026, 9, 1, 12, 0, 0),  # naive  # noqa: DTZ001
                snapshot_id="snap-1",
                instrument="AAPLUSDT",
                open=Decimal("230.00"),
                high=Decimal("231.50"),
                low=Decimal("229.20"),
                close=Decimal("230.60"),
                volume=Decimal(50000),
                source="fixture",
            )

    def test_negative_price(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            MarketSnapshot(
                timestamp=_NOW,
                snapshot_id="snap-1",
                instrument="AAPLUSDT",
                open=Decimal("-1.00"),
                high=Decimal("231.50"),
                low=Decimal("229.20"),
                close=Decimal("230.60"),
                volume=Decimal(50000),
                source="fixture",
            )

    def test_empty_snapshot_id(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            MarketSnapshot(
                timestamp=_NOW,
                snapshot_id="   ",
                instrument="AAPLUSDT",
                open=Decimal("230.00"),
                high=Decimal("231.50"),
                low=Decimal("229.20"),
                close=Decimal("230.60"),
                volume=Decimal(50000),
                source="fixture",
            )

    def test_frozen(self) -> None:
        snap = ACCEPTED_SNAPSHOT
        with pytest.raises(ValidationError):
            snap.close = Decimal(999)  # type: ignore[misc]


# -----------------------------------------------------------------------
# FactorHypothesis
# -----------------------------------------------------------------------


class TestFactorHypothesis:
    def test_valid_construction(self) -> None:
        h = VALID_HYPOTHESIS
        assert h.factor_name == "momentum"
        assert h.instruments == ["AAPLUSDT"]

    def test_invalid_factor_name(self) -> None:
        with pytest.raises(ValidationError, match="Unknown factor"):
            FactorHypothesis(
                hypothesis_id="h-1",
                factor_name="magic_indicator",
                parameters={},
                lookback=30,
                instruments=["AAPLUSDT"],
                direction="long",
                entry_rule="buy when magic",
                exit_rule="sell when not magic",
                rationale="Trust the magic",
                created_at=_NOW,
            )

    def test_out_of_range_lookback(self) -> None:
        with pytest.raises(ValidationError, match="lookback"):
            FactorHypothesis(
                hypothesis_id="h-1",
                factor_name="momentum",
                parameters={},
                lookback=0,
                instruments=["AAPLUSDT"],
                direction="long",
                entry_rule="rule",
                exit_rule="rule",
                rationale="Reason",
                created_at=_NOW,
            )

    def test_lookback_too_large(self) -> None:
        with pytest.raises(ValidationError, match="lookback"):
            FactorHypothesis(
                hypothesis_id="h-1",
                factor_name="momentum",
                parameters={},
                lookback=999,
                instruments=["AAPLUSDT"],
                direction="long",
                entry_rule="rule",
                exit_rule="rule",
                rationale="Reason",
                created_at=_NOW,
            )

    def test_empty_instruments(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            FactorHypothesis(
                hypothesis_id="h-1",
                factor_name="momentum",
                parameters={},
                lookback=30,
                instruments=[],
                direction="long",
                entry_rule="rule",
                exit_rule="rule",
                rationale="Reason",
                created_at=_NOW,
            )

    def test_empty_rationale(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            FactorHypothesis(
                hypothesis_id="h-1",
                factor_name="momentum",
                parameters={},
                lookback=30,
                instruments=["AAPLUSDT"],
                direction="long",
                entry_rule="rule",
                exit_rule="rule",
                rationale="  ",
                created_at=_NOW,
            )

    def test_invalid_instrument_in_list(self) -> None:
        with pytest.raises(ValidationError):
            FactorHypothesis(
                hypothesis_id="h-1",
                factor_name="momentum",
                parameters={},
                lookback=30,
                instruments=["BTCUSDT"],
                direction="long",
                entry_rule="rule",
                exit_rule="rule",
                rationale="Reason",
                created_at=_NOW,
            )


# -----------------------------------------------------------------------
# ValidationResult
# -----------------------------------------------------------------------


def _make_metrics(
    label_obs: str = "observed", label_est: str = "estimated"
) -> ValidationMetrics:
    return ValidationMetrics(
        total_return=LabeledMetric(value=0.05, label=label_obs),
        sharpe_ratio=LabeledMetric(value=1.2, label=label_obs),
        sortino_ratio=LabeledMetric(value=1.5, label=label_obs),
        max_drawdown=LabeledMetric(value=-0.08, label=label_obs),
        turnover=LabeledMetric(value=0.3, label=label_obs),
        fees=LabeledMetric(value=0.001, label=label_est),
        slippage=LabeledMetric(value=0.0005, label=label_est),
        win_rate=LabeledMetric(value=0.55, label=label_obs),
    )


class TestValidationResult:
    def test_valid_construction(self) -> None:
        vr = ValidationResult(
            validation_id="v-1",
            hypothesis_id="h-1",
            snapshot_id="s-1",
            train_window=(_NOW, _NOW),
            test_window=(_NOW, _NOW),
            observations=25,
            metrics=_make_metrics(),
            passed=True,
        )
        assert vr.passed is True

    def test_observations_below_minimum(self) -> None:
        with pytest.raises(ValidationError, match="observations"):
            ValidationResult(
                validation_id="v-1",
                hypothesis_id="h-1",
                snapshot_id="s-1",
                train_window=(_NOW, _NOW),
                test_window=(_NOW, _NOW),
                observations=MIN_OBSERVATIONS - 1,
                metrics=_make_metrics(),
                passed=True,
            )

    def test_passed_with_rejection_reasons_fails(self) -> None:
        with pytest.raises(ValidationError, match="passed=True"):
            ValidationResult(
                validation_id="v-1",
                hypothesis_id="h-1",
                snapshot_id="s-1",
                train_window=(_NOW, _NOW),
                test_window=(_NOW, _NOW),
                observations=25,
                metrics=_make_metrics(),
                passed=True,
                rejection_reasons=["should not be here"],
            )

    def test_invalid_metric_label(self) -> None:
        with pytest.raises(ValidationError):
            LabeledMetric(value=0.05, label="made_up")


# -----------------------------------------------------------------------
# TradeDecision
# -----------------------------------------------------------------------


class TestTradeDecision:
    def test_valid_construction(self) -> None:
        td = TradeDecision(
            decision_id="d-1",
            cycle_id="c-1",
            hypothesis_id="h-1",
            instrument="TSLAUSDT",
            side="buy",
            quantity=Decimal(10),
            price=Decimal("250.00"),
            rationale="Momentum signal confirmed",
            timestamp=_NOW,
        )
        assert td.side == "buy"

    def test_negative_quantity(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            TradeDecision(
                decision_id="d-1",
                cycle_id="c-1",
                hypothesis_id="h-1",
                instrument="TSLAUSDT",
                side="buy",
                quantity=Decimal(-5),
                price=Decimal("250.00"),
                rationale="Reason",
                timestamp=_NOW,
            )

    def test_negative_price(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            TradeDecision(
                decision_id="d-1",
                cycle_id="c-1",
                hypothesis_id="h-1",
                instrument="TSLAUSDT",
                side="sell",
                quantity=Decimal(10),
                price=Decimal(0),
                rationale="Reason",
                timestamp=_NOW,
            )

    def test_empty_rationale(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            TradeDecision(
                decision_id="d-1",
                cycle_id="c-1",
                hypothesis_id="h-1",
                instrument="TSLAUSDT",
                side="buy",
                quantity=Decimal(10),
                price=Decimal("250.00"),
                rationale="",
                timestamp=_NOW,
            )


# -----------------------------------------------------------------------
# PaperOrder
# -----------------------------------------------------------------------


class TestPaperOrder:
    def test_valid_construction(self) -> None:
        po = PaperOrder(
            order_id="o-1",
            decision_id="d-1",
            event_id="e-1",
            timestamp=_NOW,
            instrument="METAUSDT",
            side="buy",
            price=Decimal("500.00"),
            quantity=Decimal(2),
            notional=Decimal("1000.00"),
            pre_balance=Decimal("10000.00"),
            post_balance=Decimal("9000.00"),
            fees=Decimal("1.00"),
            slippage=Decimal("0.50"),
            status="filled",
            fill_price=Decimal("500.25"),
        )
        assert po.notional == Decimal("1000.00")

    def test_wrong_notional(self) -> None:
        with pytest.raises(ValidationError, match="notional"):
            PaperOrder(
                order_id="o-1",
                decision_id="d-1",
                event_id="e-1",
                timestamp=_NOW,
                instrument="METAUSDT",
                side="buy",
                price=Decimal("500.00"),
                quantity=Decimal(2),
                notional=Decimal("999.00"),
                pre_balance=Decimal("10000.00"),
                post_balance=Decimal("9000.00"),
                fees=Decimal("1.00"),
                slippage=Decimal("0.50"),
                status="filled",
            )

    def test_negative_fees(self) -> None:
        with pytest.raises(ValidationError, match="non-negative"):
            PaperOrder(
                order_id="o-1",
                decision_id="d-1",
                event_id="e-1",
                timestamp=_NOW,
                instrument="METAUSDT",
                side="buy",
                price=Decimal("500.00"),
                quantity=Decimal(2),
                notional=Decimal("1000.00"),
                pre_balance=Decimal("10000.00"),
                post_balance=Decimal("9000.00"),
                fees=Decimal("-1.00"),
                slippage=Decimal("0.50"),
                status="filled",
            )


# -----------------------------------------------------------------------
# RiskGateResult
# -----------------------------------------------------------------------


class TestRiskGateResult:
    def test_valid(self) -> None:
        rg = RiskGateResult(
            gate_name="max_position_size",
            passed=True,
            reason="Position within 5% of portfolio",
            value=0.03,
            threshold=0.05,
        )
        assert rg.passed is True

    def test_empty_gate_name(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            RiskGateResult(gate_name="  ", passed=True, reason="ok")

    def test_empty_reason(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            RiskGateResult(gate_name="gate", passed=True, reason="")


# -----------------------------------------------------------------------
# AuditEvent
# -----------------------------------------------------------------------


class TestAuditEvent:
    def test_valid_construction(self) -> None:
        ae = AuditEvent(
            event_id="e-1",
            cycle_id="c-1",
            stage="observe",
            timestamp=_NOW,
            payload={"snapshot_id": "s-1"},
        )
        assert ae.stage == "observe"

    def test_invalid_stage(self) -> None:
        with pytest.raises(ValidationError):
            AuditEvent(
                event_id="e-1",
                cycle_id="c-1",
                stage="invalid_stage",
                timestamp=_NOW,
                payload={},
            )

    def test_chaining(self) -> None:
        parent = AuditEvent(
            event_id="e-1",
            cycle_id="c-1",
            stage="observe",
            timestamp=_NOW,
            payload={},
        )
        child = AuditEvent(
            event_id="e-2",
            cycle_id="c-1",
            stage="propose",
            timestamp=_NOW,
            parent_event_id=parent.event_id,
            payload={"hypothesis_id": "h-1"},
        )
        assert child.parent_event_id == "e-1"

    def test_empty_event_id(self) -> None:
        with pytest.raises(ValidationError, match="empty"):
            AuditEvent(
                event_id="  ",
                cycle_id="c-1",
                stage="observe",
                timestamp=_NOW,
                payload={},
            )


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


class TestFixtures:
    def test_ohlcv_length(self) -> None:
        assert len(RAAPLUSDT_OHLCV) == 30

    def test_ohlcv_instruments(self) -> None:
        for snap in RAAPLUSDT_OHLCV:
            assert snap.instrument == "RAAPLUSDT"
            assert snap.instrument in INSTRUMENTS

    def test_accepted_snapshot(self) -> None:
        assert ACCEPTED_SNAPSHOT.instrument == "RAAPLUSDT"
        assert ACCEPTED_SNAPSHOT.volume > Decimal(100000)

    def test_rejected_snapshot(self) -> None:
        assert REJECTED_SNAPSHOT.instrument == "RNVDAUSDT"
        assert REJECTED_SNAPSHOT.volume < Decimal(10000)

    def test_valid_hypothesis(self) -> None:
        assert VALID_HYPOTHESIS.factor_name == "momentum"

    def test_rejected_hypothesis(self) -> None:
        assert REJECTED_HYPOTHESIS.factor_name == "mean_reversion"

    def test_deterministic_serialization(self) -> None:
        """Same fixture serializes identically across calls."""
        json_a = ACCEPTED_SNAPSHOT.model_dump_json()
        json_b = ACCEPTED_SNAPSHOT.model_dump_json()
        assert json_a == json_b

        json_c = VALID_HYPOTHESIS.model_dump_json()
        json_d = VALID_HYPOTHESIS.model_dump_json()
        assert json_c == json_d

    def test_fixture_snapshot_ids_deterministic(self) -> None:
        """UUID5 produces the same IDs each run."""
        from factor_atlas.fixtures.events import _det_uuid

        assert _det_uuid("accepted-snapshot") == ACCEPTED_SNAPSHOT.snapshot_id
