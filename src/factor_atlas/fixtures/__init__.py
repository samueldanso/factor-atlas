"""Deterministic fixtures for FactorAtlas testing."""

from __future__ import annotations

from factor_atlas.fixtures.events import (
    ACCEPTED_SNAPSHOT,
    RAAPLUSDT_OHLCV,
    REJECTED_SNAPSHOT,
)
from factor_atlas.fixtures.hypotheses import (
    REJECTED_HYPOTHESIS,
    VALID_HYPOTHESIS,
)

__all__ = [
    "ACCEPTED_SNAPSHOT",
    "RAAPLUSDT_OHLCV",
    "REJECTED_HYPOTHESIS",
    "REJECTED_SNAPSHOT",
    "VALID_HYPOTHESIS",
]
