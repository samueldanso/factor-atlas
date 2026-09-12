"""Deterministic fixture market snapshots and OHLCV data."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.contracts import MarketSnapshot

# Deterministic UUIDs from a fixed namespace + name
_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


# ---------------------------------------------------------------------------
# Pre-built OHLCV series for AAPLUSDT (30 bars, 1h, synthetic)
# ---------------------------------------------------------------------------

_BASE_TS = datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC)

AAPLUSDT_OHLCV: list[MarketSnapshot] = []

# Seed a simple synthetic walk: open drifts from 230 upward
_opens = [
    Decimal("230.00"),
    Decimal("230.50"),
    Decimal("231.20"),
    Decimal("230.80"),
    Decimal("231.50"),
    Decimal("232.00"),
    Decimal("232.80"),
    Decimal("233.50"),
    Decimal("234.00"),
    Decimal("233.80"),
    Decimal("234.20"),
    Decimal("235.00"),
    Decimal("235.50"),
    Decimal("234.80"),
    Decimal("234.50"),
    Decimal("235.20"),
    Decimal("236.00"),
    Decimal("236.50"),
    Decimal("237.00"),
    Decimal("236.80"),
    Decimal("237.50"),
    Decimal("238.00"),
    Decimal("238.50"),
    Decimal("237.80"),
    Decimal("237.00"),
    Decimal("236.50"),
    Decimal("237.20"),
    Decimal("238.00"),
    Decimal("238.80"),
    Decimal("239.50"),
]

for i, o in enumerate(_opens):
    ts = _BASE_TS.replace(hour=i % 24)
    if i >= 24:
        ts = ts.replace(day=2, hour=i - 24)
    h = o + Decimal("1.50")
    low = o - Decimal("0.80")
    c = o + Decimal("0.60")
    vol = Decimal(50000) + Decimal(str(i * 1000))
    AAPLUSDT_OHLCV.append(
        MarketSnapshot(
            timestamp=ts,
            snapshot_id=_det_uuid(f"aapl-bar-{i}"),
            instrument="AAPLUSDT",
            category="USDT-FUTURES",
            open=o,
            high=h,
            low=low,
            close=c,
            volume=vol,
            source="fixture",
        )
    )


# ---------------------------------------------------------------------------
# Fixture snapshots for cycle testing
# ---------------------------------------------------------------------------

# Snapshot that leads to an accepted cycle (strong momentum signal)
ACCEPTED_SNAPSHOT = MarketSnapshot(
    timestamp=datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC),
    snapshot_id=_det_uuid("accepted-snapshot"),
    instrument="AAPLUSDT",
    category="USDT-FUTURES",
    open=Decimal("235.00"),
    high=Decimal("238.50"),
    low=Decimal("234.20"),
    close=Decimal("238.00"),
    volume=Decimal(120000),
    source="fixture",
)

# Snapshot that leads to a rejected cycle (low volume, narrow range)
REJECTED_SNAPSHOT = MarketSnapshot(
    timestamp=datetime(2026, 9, 1, 13, 0, 0, tzinfo=UTC),
    snapshot_id=_det_uuid("rejected-snapshot"),
    instrument="NVDAUSDT",
    category="USDT-FUTURES",
    open=Decimal("140.00"),
    high=Decimal("140.30"),
    low=Decimal("139.80"),
    close=Decimal("140.10"),
    volume=Decimal(5000),
    source="fixture",
)

__all__ = [
    "AAPLUSDT_OHLCV",
    "ACCEPTED_SNAPSHOT",
    "REJECTED_SNAPSHOT",
]
