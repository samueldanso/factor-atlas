"""Deterministic fixtures for FactorAtlas testing."""

from __future__ import annotations

from factor_atlas.fixtures.events import (
    AAPLUSDT_OHLCV,
    ACCEPTED_SNAPSHOT,
    REJECTED_SNAPSHOT,
)
from factor_atlas.fixtures.hypotheses import (
    REJECTED_HYPOTHESIS,
    VALID_HYPOTHESIS,
)

__all__ = [
    "AAPLUSDT_OHLCV",
    "ACCEPTED_SNAPSHOT",
    "REJECTED_HYPOTHESIS",
    "REJECTED_SNAPSHOT",
    "VALID_HYPOTHESIS",
]
