"""Typed contracts for the FactorAtlas agent pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from factor_atlas.config import (
    AUDIT_STAGES,
    CATEGORY,
    FACTOR_VOCABULARY,
    INSTRUMENTS,
    MAX_LOOKBACK,
    MAX_QUANTITY,
    MIN_LOOKBACK,
    MIN_OBSERVATIONS,
)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

InstrumentType = Literal["AAPLUSDT", "NVDAUSDT", "TSLAUSDT", "METAUSDT"]
CategoryType = Literal["USDT-FUTURES"]
SideType = Literal["buy", "sell"]
DirectionType = Literal["long", "short"]
SourceType = Literal["fixture", "bitget-demo", "bitget-signal"]
MetricLabelType = Literal["observed", "estimated", "targeted"]
OrderStatusType = Literal["filled", "rejected", "error"]
AuditStageType = Literal[
    "observe", "propose", "evaluate", "decide", "gate", "execute", "learn"
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_instrument(v: str) -> str:
    if v not in INSTRUMENTS:
        msg = f"Unknown instrument '{v}'. Must be one of {sorted(INSTRUMENTS)}"
        raise ValueError(msg)
    return v


def _validate_utc(v: datetime) -> datetime:
    if v.tzinfo is None or v.tzinfo.utcoffset(v) != UTC.utcoffset(None):
        msg = "Timestamp must be UTC"
        raise ValueError(msg)
    return v


def _positive_decimal(v: Decimal, name: str) -> Decimal:
    if v <= 0:
        msg = f"{name} must be positive, got {v}"
        raise ValueError(msg)
    return v


def _non_negative_decimal(v: Decimal, name: str) -> Decimal:
    if v < 0:
        msg = f"{name} must be non-negative, got {v}"
        raise ValueError(msg)
    return v


# ---------------------------------------------------------------------------
# 1. MarketSnapshot
# ---------------------------------------------------------------------------


class MarketSnapshot(BaseModel):
    """A single OHLCV bar for a supported instrument."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    snapshot_id: str
    instrument: InstrumentType
    category: CategoryType = CATEGORY  # type: ignore[assignment]
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: SourceType

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @field_validator("instrument")
    @classmethod
    def _instrument(cls, v: str) -> str:
        return _validate_instrument(v)

    @field_validator("snapshot_id")
    @classmethod
    def _non_empty_id(cls, v: str) -> str:
        if not v.strip():
            msg = "snapshot_id must not be empty"
            raise ValueError(msg)
        return v

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _positive_price(cls, v: Decimal) -> Decimal:
        return _positive_decimal(v, "price")

    @field_validator("volume")
    @classmethod
    def _non_negative_volume(cls, v: Decimal) -> Decimal:
        return _non_negative_decimal(v, "volume")


# ---------------------------------------------------------------------------
# 2. FactorHypothesis
# ---------------------------------------------------------------------------


class FactorHypothesis(BaseModel):
    """A proposed factor hypothesis for validation."""

    model_config = ConfigDict(frozen=True)

    hypothesis_id: str
    factor_name: str
    parameters: dict[str, float | int | str]
    lookback: int
    instruments: list[InstrumentType]
    direction: DirectionType
    entry_rule: str
    exit_rule: str
    rationale: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @field_validator("factor_name")
    @classmethod
    def _known_factor(cls, v: str) -> str:
        if v not in FACTOR_VOCABULARY:
            msg = f"Unknown factor '{v}'. Must be one of {sorted(FACTOR_VOCABULARY)}"
            raise ValueError(msg)
        return v

    @field_validator("lookback")
    @classmethod
    def _bounded_lookback(cls, v: int) -> int:
        if v < MIN_LOOKBACK or v > MAX_LOOKBACK:
            msg = f"lookback must be between {MIN_LOOKBACK} and {MAX_LOOKBACK}, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("instruments")
    @classmethod
    def _non_empty_instruments(cls, v: list[str]) -> list[str]:
        if not v:
            msg = "instruments must not be empty"
            raise ValueError(msg)
        for inst in v:
            _validate_instrument(inst)
        return v

    @field_validator("rationale")
    @classmethod
    def _non_empty_rationale(cls, v: str) -> str:
        if not v.strip():
            msg = "rationale must not be empty"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# 3. LabeledMetric
# ---------------------------------------------------------------------------


class LabeledMetric(BaseModel):
    """A single metric value with its label."""

    model_config = ConfigDict(frozen=True)

    value: float
    label: MetricLabelType


# ---------------------------------------------------------------------------
# 4. ValidationMetrics
# ---------------------------------------------------------------------------


class ValidationMetrics(BaseModel):
    """Walk-forward validation metrics for a hypothesis."""

    model_config = ConfigDict(frozen=True)

    total_return: LabeledMetric
    sharpe_ratio: LabeledMetric
    sortino_ratio: LabeledMetric
    max_drawdown: LabeledMetric
    turnover: LabeledMetric
    fees: LabeledMetric
    slippage: LabeledMetric
    win_rate: LabeledMetric


# ---------------------------------------------------------------------------
# 5. ValidationResult
# ---------------------------------------------------------------------------


class ValidationResult(BaseModel):
    """Result of a walk-forward validation."""

    model_config = ConfigDict(frozen=True)

    validation_id: str
    hypothesis_id: str
    snapshot_id: str
    train_window: tuple[datetime, datetime]
    test_window: tuple[datetime, datetime]
    observations: int
    metrics: ValidationMetrics
    passed: bool
    rejection_reasons: list[str] = Field(default_factory=list)

    @field_validator("observations")
    @classmethod
    def _min_observations(cls, v: int) -> int:
        if v < MIN_OBSERVATIONS:
            msg = f"observations must be >= {MIN_OBSERVATIONS}, got {v}"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _consistent_pass(self) -> ValidationResult:
        if self.passed and self.rejection_reasons:
            msg = "passed=True but rejection_reasons is non-empty"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# 6. TradeDecision
# ---------------------------------------------------------------------------


class TradeDecision(BaseModel):
    """An agent's trade decision based on a validated hypothesis."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    cycle_id: str
    hypothesis_id: str
    instrument: InstrumentType
    side: SideType
    quantity: Decimal
    price: Decimal
    rationale: str
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @field_validator("instrument")
    @classmethod
    def _instrument(cls, v: str) -> str:
        return _validate_instrument(v)

    @field_validator("quantity")
    @classmethod
    def _positive_quantity(cls, v: Decimal) -> Decimal:
        v = _positive_decimal(v, "quantity")
        if v > Decimal(MAX_QUANTITY):
            msg = f"quantity exceeds max {MAX_QUANTITY}, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("price")
    @classmethod
    def _positive_price(cls, v: Decimal) -> Decimal:
        return _positive_decimal(v, "price")

    @field_validator("rationale")
    @classmethod
    def _non_empty_rationale(cls, v: str) -> str:
        if not v.strip():
            msg = "rationale must not be empty"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# 7. PaperOrder
# ---------------------------------------------------------------------------


class PaperOrder(BaseModel):
    """A simulated order execution record."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    decision_id: str
    event_id: str
    timestamp: datetime
    instrument: InstrumentType
    category: CategoryType = CATEGORY  # type: ignore[assignment]
    side: SideType
    price: Decimal
    quantity: Decimal
    notional: Decimal
    pre_balance: Decimal
    post_balance: Decimal
    fees: Decimal
    slippage: Decimal
    status: OrderStatusType
    rejection_reason: str | None = None
    fill_price: Decimal | None = None

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @field_validator("instrument")
    @classmethod
    def _instrument(cls, v: str) -> str:
        return _validate_instrument(v)

    @field_validator("price", "quantity")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        return _positive_decimal(v, "price/quantity")

    @field_validator("pre_balance", "post_balance", "fees", "slippage")
    @classmethod
    def _non_negative(cls, v: Decimal) -> Decimal:
        return _non_negative_decimal(v, "balance/fees/slippage")

    @model_validator(mode="after")
    def _notional_check(self) -> PaperOrder:
        expected = self.price * self.quantity
        if self.notional != expected:
            msg = (
                f"notional must equal price * quantity "
                f"({self.price} * {self.quantity} = {expected}), "
                f"got {self.notional}"
            )
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# 8. RiskGateResult
# ---------------------------------------------------------------------------


class RiskGateResult(BaseModel):
    """Outcome of a single risk gate check."""

    model_config = ConfigDict(frozen=True)

    gate_name: str
    passed: bool
    reason: str
    value: float | None = None
    threshold: float | None = None

    @field_validator("gate_name", "reason")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "field must not be empty"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# 9. AuditEvent
# ---------------------------------------------------------------------------


class AuditEvent(BaseModel):
    """An append-only audit log entry."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    cycle_id: str
    stage: AuditStageType
    timestamp: datetime
    parent_event_id: str | None = None
    payload: dict[str, object]

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @field_validator("stage")
    @classmethod
    def _valid_stage(cls, v: str) -> str:
        if v not in AUDIT_STAGES:
            msg = f"Unknown stage '{v}'. Must be one of {sorted(AUDIT_STAGES)}"
            raise ValueError(msg)
        return v

    @field_validator("event_id", "cycle_id")
    @classmethod
    def _non_empty_id(cls, v: str) -> str:
        if not v.strip():
            msg = "id must not be empty"
            raise ValueError(msg)
        return v
