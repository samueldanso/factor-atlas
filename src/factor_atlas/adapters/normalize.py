"""Instrument normalization: rToken research instruments → stock perp execution instruments."""

from __future__ import annotations

from factor_atlas.config import EXECUTION_INSTRUMENTS, RESEARCH_TO_EXECUTION


def research_to_execution(instrument: str) -> str:
    """Map rToken research instrument to stock perp execution instrument.

    RAAPLUSDT -> AAPLUSDT, RNVDAUSDT -> NVDAUSDT, etc.
    Execution instruments pass through unchanged.
    """
    if instrument in EXECUTION_INSTRUMENTS:
        return instrument
    return RESEARCH_TO_EXECUTION.get(instrument, instrument)


__all__ = [
    "research_to_execution",
]
