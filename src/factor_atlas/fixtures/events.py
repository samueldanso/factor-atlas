"""Deterministic fixture market snapshots and OHLCV data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_DNS, uuid5

from factor_atlas.contracts import MarketSnapshot

# Deterministic UUIDs from a fixed namespace + name
_NS = NAMESPACE_DNS


def _det_uuid(name: str) -> str:
    return str(uuid5(_NS, name))


# ---------------------------------------------------------------------------
# Pre-built OHLCV series for RAAPLUSDT rToken (80 bars, 1h, synthetic)
#
# 80 bars guarantees that a 70/30 split yields >= 24 test bars,
# comfortably above MIN_OBSERVATIONS (20).
# ---------------------------------------------------------------------------

_BASE_TS = datetime(2026, 8, 28, 0, 0, 0, tzinfo=UTC)  # start 4 days earlier
_BAR_COUNT = 80

# Deterministic price walk: start at 225, drift upward with oscillation
_base_price = Decimal("225.00")
_opens: list[Decimal] = []
for _i in range(_BAR_COUNT):
    # Trend component: +0.20 per bar on average
    trend = Decimal(str(_i)) * Decimal("0.20")
    # Oscillation: +/- up to ~1.5 using a simple modular pattern
    osc_val = ((_i * 7 + 3) % 11) - 5  # range roughly -5..5
    osc = Decimal(str(osc_val)) * Decimal("0.30")
    _opens.append(_base_price + trend + osc)

RAAPLUSDT_OHLCV: list[MarketSnapshot] = []

for _i, o in enumerate(_opens):
    ts = _BASE_TS + timedelta(hours=_i)
    h = o + Decimal("1.50")
    low = o - Decimal("0.80")
    c = o + Decimal("0.60")
    vol = Decimal(50000) + Decimal(str(_i * 1000))
    RAAPLUSDT_OHLCV.append(
        MarketSnapshot(
            timestamp=ts,
            snapshot_id=_det_uuid(f"aapl-bar-{_i}"),
            instrument="RAAPLUSDT",
            category="SPOT",
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
    instrument="RAAPLUSDT",
    category="SPOT",
    open=Decimal("235.00"),
    high=Decimal("238.50"),
    low=Decimal("234.20"),
    close=Decimal("238.00"),
    volume=Decimal(120000),
    source="fixture",
)

# Snapshot that leads to a rejected cycle (low volume, narrow range)
# Uses RNVDAUSDT which has no OHLCV data → no_candidate
REJECTED_SNAPSHOT = MarketSnapshot(
    timestamp=datetime(2026, 9, 1, 13, 0, 0, tzinfo=UTC),
    snapshot_id=_det_uuid("rejected-snapshot"),
    instrument="RNVDAUSDT",
    category="SPOT",
    open=Decimal("140.00"),
    high=Decimal("140.30"),
    low=Decimal("139.80"),
    close=Decimal("140.10"),
    volume=Decimal(5000),
    source="fixture",
)

__all__ = [
    "ACCEPTED_SNAPSHOT",
    "RAAPLUSDT_OHLCV",
    "REJECTED_SNAPSHOT",
]
