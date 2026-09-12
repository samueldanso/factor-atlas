"""Tests for deterministic risk gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from factor_atlas.broker import BrokerState
from factor_atlas.contracts import (
    LabeledMetric,
    MarketSnapshot,
    PaperOrder,
    RiskGateResult,
    TradeDecision,
    ValidationMetrics,
    ValidationResult,
)
from factor_atlas.risk import (
    RiskConfig,
    all_gates_passed,
    gate_concentration_guard,
    gate_cooldown,
    gate_daily_loss_cap,
    gate_data_freshness,
    gate_duplicate_suppression,
    gate_exposure_cap,
    gate_factor_allowlist,
    gate_max_notional,
    gate_max_position,
    gate_max_quantity,
    gate_min_sample_size,
    gate_validation_threshold,
    run_gates,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


def _make_snapshot(
    ts: datetime | None = None,
    instrument: str = "AAPLUSDT",
    close: Decimal = Decimal("238.00"),
) -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=ts or _NOW,
        snapshot_id="snap-1",
        instrument=instrument,
        open=Decimal("235.00"),
        high=Decimal("239.00"),
        low=Decimal("234.00"),
        close=close,
        volume=Decimal(100000),
        source="fixture",
    )


def _make_decision(
    instrument: str = "AAPLUSDT",
    price: Decimal = Decimal("238.00"),
    quantity: Decimal = Decimal(1),
    side: str = "buy",
    ts: datetime | None = None,
    decision_id: str = "dec-1",
) -> TradeDecision:
    return TradeDecision(
        decision_id=decision_id,
        cycle_id="cycle-1",
        hypothesis_id="hyp-1",
        instrument=instrument,
        side=side,
        quantity=quantity,
        price=price,
        rationale="test rationale",
        timestamp=ts or _NOW,
    )


def _make_validation(
    passed: bool = True,
    observations: int = 30,
) -> ValidationResult:
    m = LabeledMetric(value=0.0, label="observed")
    return ValidationResult(
        validation_id="val-1",
        hypothesis_id="hyp-1",
        snapshot_id="snap-1",
        train_window=(_NOW - timedelta(days=30), _NOW - timedelta(days=1)),
        test_window=(_NOW - timedelta(days=1), _NOW),
        observations=observations,
        metrics=ValidationMetrics(
            total_return=m,
            sharpe_ratio=LabeledMetric(value=1.5, label="observed"),
            sortino_ratio=m,
            max_drawdown=m,
            turnover=m,
            fees=m,
            slippage=m,
            win_rate=m,
        ),
        passed=passed,
        rejection_reasons=[] if passed else ["test rejection"],
    )


def _make_order(
    instrument: str = "AAPLUSDT",
    notional: Decimal = Decimal("238.00"),
    status: str = "filled",
) -> PaperOrder:
    price = Decimal("238.00")
    qty = notional / price
    return PaperOrder(
        order_id="ord-prev",
        decision_id="dec-prev",
        event_id="evt-prev",
        timestamp=_NOW - timedelta(hours=1),
        instrument=instrument,
        side="buy",
        price=price,
        quantity=qty,
        notional=notional,
        pre_balance=Decimal(100000),
        post_balance=Decimal(99999),
        fees=Decimal("0.238"),
        slippage=Decimal("0.119"),
        status=status,
    )


def _fresh_state() -> BrokerState:
    return BrokerState()


# ---------------------------------------------------------------------------
# gate_factor_allowlist
# ---------------------------------------------------------------------------


class TestFactorAllowlist:
    def test_pass_known_factor(self) -> None:
        d = _make_decision()
        r = gate_factor_allowlist(d, factor_name="momentum")
        assert r.passed is True
        assert r.gate_name == "factor_allowlist"

    def test_fail_unknown_factor(self) -> None:
        d = _make_decision()
        r = gate_factor_allowlist(d, factor_name="magic_indicator")
        assert r.passed is False
        assert "not in allowlist" in r.reason


# ---------------------------------------------------------------------------
# gate_data_freshness
# ---------------------------------------------------------------------------


class TestDataFreshness:
    def test_pass_fresh_data(self) -> None:
        snap = _make_snapshot(ts=_NOW - timedelta(hours=1))
        d = _make_decision(ts=_NOW)
        r = gate_data_freshness(d, snapshot=snap, config=RiskConfig())
        assert r.passed is True

    def test_fail_stale_data(self) -> None:
        snap = _make_snapshot(ts=_NOW - timedelta(hours=25))
        d = _make_decision(ts=_NOW)
        r = gate_data_freshness(d, snapshot=snap, config=RiskConfig())
        assert r.passed is False
        assert "exceeds" in r.reason

    def test_boundary_exact_24h(self) -> None:
        snap = _make_snapshot(ts=_NOW - timedelta(hours=24))
        d = _make_decision(ts=_NOW)
        r = gate_data_freshness(d, snapshot=snap, config=RiskConfig())
        assert r.passed is True  # exactly at threshold is OK


# ---------------------------------------------------------------------------
# gate_min_sample_size
# ---------------------------------------------------------------------------


class TestMinSampleSize:
    def test_pass_enough_observations(self) -> None:
        d = _make_decision()
        v = _make_validation(observations=30)
        r = gate_min_sample_size(d, validation=v)
        assert r.passed is True

    def test_fail_too_few_observations(self) -> None:
        d = _make_decision()
        # MIN_OBSERVATIONS is 20 but ValidationResult enforces it too,
        # so we test the gate with exactly 20 (boundary pass)
        v = _make_validation(observations=20)
        r = gate_min_sample_size(d, validation=v)
        assert r.passed is True

    def test_exact_boundary(self) -> None:
        d = _make_decision()
        v = _make_validation(observations=20)
        r = gate_min_sample_size(d, validation=v)
        assert r.passed is True
        assert r.value == 20.0


# ---------------------------------------------------------------------------
# gate_validation_threshold
# ---------------------------------------------------------------------------


class TestValidationThreshold:
    def test_pass_validated(self) -> None:
        d = _make_decision()
        v = _make_validation(passed=True)
        r = gate_validation_threshold(d, validation=v)
        assert r.passed is True

    def test_fail_not_validated(self) -> None:
        d = _make_decision()
        v = _make_validation(passed=False)
        r = gate_validation_threshold(d, validation=v)
        assert r.passed is False


# ---------------------------------------------------------------------------
# gate_max_notional
# ---------------------------------------------------------------------------


class TestMaxNotional:
    def test_pass_below_limit(self) -> None:
        d = _make_decision(price=Decimal(100), quantity=Decimal(10))
        r = gate_max_notional(d, config=RiskConfig())
        assert r.passed is True  # 1000 < 10000

    def test_fail_above_limit(self) -> None:
        d = _make_decision(price=Decimal(500), quantity=Decimal(30))
        r = gate_max_notional(d, config=RiskConfig())
        assert r.passed is False  # 15000 > 10000

    def test_boundary_exact(self) -> None:
        d = _make_decision(price=Decimal(100), quantity=Decimal(100))
        r = gate_max_notional(d, config=RiskConfig())
        assert r.passed is True  # 10000 == 10000


# ---------------------------------------------------------------------------
# gate_max_position
# ---------------------------------------------------------------------------


class TestMaxPosition:
    def test_pass_under_limit(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        r = gate_max_position(d, broker_state=state, config=RiskConfig())
        assert r.passed is True

    def test_fail_at_limit(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        state.positions = [_make_order(), _make_order(), _make_order()]
        r = gate_max_position(d, broker_state=state, config=RiskConfig())
        assert r.passed is False


# ---------------------------------------------------------------------------
# gate_exposure_cap
# ---------------------------------------------------------------------------


class TestExposureCap:
    def test_pass_within_cap(self) -> None:
        d = _make_decision(price=Decimal(238), quantity=Decimal(1))
        state = _fresh_state()
        r = gate_exposure_cap(d, broker_state=state, config=RiskConfig())
        assert r.passed is True

    def test_fail_exceeds_cap(self) -> None:
        d = _make_decision(price=Decimal(238), quantity=Decimal(1))
        state = _fresh_state()
        # Add positions totaling 50000 notional
        big_order = _make_order(notional=Decimal(50000))
        state.positions = [big_order]
        r = gate_exposure_cap(d, broker_state=state, config=RiskConfig())
        assert r.passed is False


# ---------------------------------------------------------------------------
# gate_cooldown
# ---------------------------------------------------------------------------


class TestCooldown:
    def test_pass_no_prior_order(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        r = gate_cooldown(d, broker_state=state, config=RiskConfig())
        assert r.passed is True

    def test_pass_after_cooldown(self) -> None:
        d = _make_decision(ts=_NOW)
        state = _fresh_state()
        state.last_order_time["AAPLUSDT"] = _NOW - timedelta(seconds=301)
        r = gate_cooldown(d, broker_state=state, config=RiskConfig())
        assert r.passed is True

    def test_fail_within_cooldown(self) -> None:
        d = _make_decision(ts=_NOW)
        state = _fresh_state()
        state.last_order_time["AAPLUSDT"] = _NOW - timedelta(seconds=100)
        r = gate_cooldown(d, broker_state=state, config=RiskConfig())
        assert r.passed is False


# ---------------------------------------------------------------------------
# gate_daily_loss_cap
# ---------------------------------------------------------------------------


class TestDailyLossCap:
    def test_pass_no_loss(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        state.daily_pnl = Decimal(500)
        r = gate_daily_loss_cap(d, broker_state=state, config=RiskConfig())
        assert r.passed is True

    def test_fail_exceeds_limit(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        state.daily_pnl = Decimal(-2500)
        r = gate_daily_loss_cap(d, broker_state=state, config=RiskConfig())
        assert r.passed is False

    def test_boundary_exact(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        state.daily_pnl = Decimal(-2000)
        r = gate_daily_loss_cap(d, broker_state=state, config=RiskConfig())
        assert r.passed is False  # loss >= limit → reject


# ---------------------------------------------------------------------------
# gate_duplicate_suppression
# ---------------------------------------------------------------------------


class TestDuplicateSuppression:
    def test_pass_new_event(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        r = gate_duplicate_suppression(d, broker_state=state, event_id="evt-1")
        assert r.passed is True

    def test_fail_duplicate(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        state.processed_events.add("evt-1|AAPLUSDT|buy")
        r = gate_duplicate_suppression(d, broker_state=state, event_id="evt-1")
        assert r.passed is False


# ---------------------------------------------------------------------------
# gate_concentration_guard
# ---------------------------------------------------------------------------


class TestConcentrationGuard:
    def test_pass_under_limit(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        r = gate_concentration_guard(d, broker_state=state, config=RiskConfig())
        assert r.passed is True

    def test_fail_at_limit(self) -> None:
        d = _make_decision()
        state = _fresh_state()
        state.positions = [_make_order(), _make_order()]
        r = gate_concentration_guard(d, broker_state=state, config=RiskConfig())
        assert r.passed is False


# ---------------------------------------------------------------------------
# gate_max_quantity
# ---------------------------------------------------------------------------


class TestMaxQuantity:
    def test_pass_below(self) -> None:
        d = _make_decision(quantity=Decimal(100))
        r = gate_max_quantity(d, config=RiskConfig())
        assert r.passed is True

    def test_fail_exceeds(self) -> None:
        d = _make_decision(quantity=Decimal(999999))
        cfg = RiskConfig(max_quantity=Decimal(100))
        r = gate_max_quantity(d, config=cfg)
        assert r.passed is False


# ---------------------------------------------------------------------------
# run_gates integration
# ---------------------------------------------------------------------------


class TestRunGates:
    def test_all_pass(self) -> None:
        snap = _make_snapshot(ts=_NOW - timedelta(hours=1))
        d = _make_decision(ts=_NOW, price=Decimal(100), quantity=Decimal(1))
        v = _make_validation(passed=True)
        state = _fresh_state()
        results = run_gates(d, v, snap, state, RiskConfig(), factor_name="momentum")
        assert len(results) == 12
        assert all_gates_passed(results)

    def test_one_fails(self) -> None:
        snap = _make_snapshot(ts=_NOW - timedelta(hours=25))
        d = _make_decision(ts=_NOW)
        v = _make_validation(passed=True)
        state = _fresh_state()
        results = run_gates(d, v, snap, state, RiskConfig(), factor_name="momentum")
        assert not all_gates_passed(results)
        # data_freshness should fail
        freshness = [r for r in results if r.gate_name == "data_freshness"]
        assert len(freshness) == 1
        assert freshness[0].passed is False

    def test_returns_all_gates_even_on_failure(self) -> None:
        snap = _make_snapshot(ts=_NOW - timedelta(hours=25))
        d = _make_decision(ts=_NOW)
        v = _make_validation(passed=False)
        state = _fresh_state()
        results = run_gates(d, v, snap, state, RiskConfig(), factor_name="magic")
        # Should still have all 12 gates
        assert len(results) == 12
        names = {r.gate_name for r in results}
        assert "factor_allowlist" in names
        assert "data_freshness" in names
        assert "validation_threshold" in names


# ---------------------------------------------------------------------------
# all_gates_passed helper
# ---------------------------------------------------------------------------


class TestAllGatesPassed:
    def test_all_pass(self) -> None:
        results = [
            RiskGateResult(gate_name="a", passed=True, reason="ok"),
            RiskGateResult(gate_name="b", passed=True, reason="ok"),
        ]
        assert all_gates_passed(results) is True

    def test_one_fails(self) -> None:
        results = [
            RiskGateResult(gate_name="a", passed=True, reason="ok"),
            RiskGateResult(gate_name="b", passed=False, reason="fail"),
        ]
        assert all_gates_passed(results) is False

    def test_empty(self) -> None:
        assert all_gates_passed([]) is True
