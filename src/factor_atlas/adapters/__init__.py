"""Adapters for external data sources and execution venues."""

from __future__ import annotations

from factor_atlas.adapters.bitget_demo import BitgetDemoAdapter
from factor_atlas.adapters.normalize import research_to_execution

__all__ = [
    "BitgetDemoAdapter",
    "research_to_execution",
]
