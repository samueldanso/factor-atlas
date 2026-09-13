"""FactorAtlas — agentic factor discovery for tokenized stock markets."""

from __future__ import annotations

__version__ = "0.1.0"

from factor_atlas.config import (
    AUDIT_STAGES,
    CATEGORY,
    EXECUTION_INSTRUMENTS,
    FACTOR_VOCABULARY,
    INSTRUMENTS,
    METRIC_LABELS,
    RESEARCH_INSTRUMENTS,
)
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

__all__ = [
    "AUDIT_STAGES",
    "CATEGORY",
    "EXECUTION_INSTRUMENTS",
    "FACTOR_VOCABULARY",
    "INSTRUMENTS",
    "METRIC_LABELS",
    "RESEARCH_INSTRUMENTS",
    "AuditEvent",
    "FactorHypothesis",
    "LabeledMetric",
    "MarketSnapshot",
    "PaperOrder",
    "RiskGateResult",
    "TradeDecision",
    "ValidationMetrics",
    "ValidationResult",
    "__version__",
]
