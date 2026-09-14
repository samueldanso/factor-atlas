# Agent Operations Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the agent run autonomously every 4h with structured evidence logging, ATR-based position sizing, and clean artifact organization — so judges see a continuous 2-week paper trading trail with full event→decision→execution evidence.

**Architecture:** Add an evidence logger (4 JSONL + 1 human-readable log), ATR-based sizing/exits, a continuous runner loop, and deploy via GitHub Actions cron. Restructure artifacts to a single source of truth. Host evidence on GitHub Pages.

**Tech Stack:** Python 3.11, uv, bgc CLI, GitHub Actions, GitHub Pages

## Global Constraints

- All 312 existing tests must continue passing after every task
- `uv run ruff check .` and `uv run ruff format --check .` must pass
- `uv run mypy .` must pass
- Never commit credentials — `.env` only
- `bgc` orders always use `--paper-trading`
- No `as any`, `@ts-ignore`, or type suppression equivalents
- Commit after each task with `type(scope): description` format
- pandas and numpy are already in `pyproject.toml` dependencies — no `uv add` needed
- bgc CLI is `@bitget-ai/bitget-agent-cli` (npm global): `npm install -g @bitget-ai/bitget-agent-cli`
- Credentials are loaded via `source .env` — the `.env` file exists at project root
- Do NOT delete `docs/evidence/` until GitHub Pages is confirmed live and README/SUBMISSION links are updated

---

### Task 1: Evidence Logger Module

**Files:**
- Create: `src/factor_atlas/evidence.py`
- Create: `tests/test_evidence.py`

**Interfaces:**
- Produces: `EvidenceLogger` class with methods: `log_event()`, `log_decision()`, `log_risk()`, `log_trade()`, `log_agent()`, `log_error()`
- Consumed by: Task 4 (runner wiring)

The evidence logger manages 4 JSONL files + 1 human-readable `agent.log`. All files are append-only and live under a configurable `logs_dir`. Every record carries `run_id` + `cycle_id` + `timestamp` for cross-file tracing.

- [ ] **Step 1: Write the failing test for EvidenceLogger initialization**

```python
# tests/test_evidence.py
"""Tests for the structured evidence logger."""

from __future__ import annotations

from pathlib import Path

from factor_atlas.evidence import EvidenceLogger


def test_evidence_logger_creates_log_dir(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logger = EvidenceLogger(logs_dir=logs_dir, run_id="test-run-001")
    assert logs_dir.exists()
    assert logger.run_id == "test-run-001"


def test_evidence_logger_files_exist(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logger = EvidenceLogger(logs_dir=logs_dir, run_id="test-run-001")
    # Files created on first write, not on init — but paths should be set
    assert logger.events_path == logs_dir / "events.jsonl"
    assert logger.decisions_path == logs_dir / "decisions.jsonl"
    assert logger.risk_path == logs_dir / "risk.jsonl"
    assert logger.trades_path == logs_dir / "trades.jsonl"
    assert logger.agent_log_path == logs_dir / "agent.log"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evidence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'factor_atlas.evidence'`

- [ ] **Step 3: Implement EvidenceLogger skeleton**

```python
# src/factor_atlas/evidence.py
"""Structured evidence logger for the FactorAtlas agent pipeline.

Produces 4 append-only JSONL files + 1 human-readable agent.log:
  events.jsonl    — observe + hypothesis + validation (judge: "Event")
  decisions.jsonl — LLM selection + rationale (judge: "Decision")
  risk.jsonl      — 14 gate verdicts (judge: "Risk control")
  trades.jsonl    — entry/exit orders + PnL (judge: "Execution")
  agent.log       — human-readable timeline (judge reads first)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class EvidenceLogger:
    """Append-only structured evidence logger.

    All log files live under ``logs_dir``. Each record carries ``run_id``
    and ``cycle_id`` so a judge can trace one trade across all 4 files.
    """

    def __init__(self, logs_dir: Path, run_id: str) -> None:
        self.logs_dir = logs_dir
        self.run_id = run_id
        logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def events_path(self) -> Path:
        return self.logs_dir / "events.jsonl"

    @property
    def decisions_path(self) -> Path:
        return self.logs_dir / "decisions.jsonl"

    @property
    def risk_path(self) -> Path:
        return self.logs_dir / "risk.jsonl"

    @property
    def trades_path(self) -> Path:
        return self.logs_dir / "trades.jsonl"

    @property
    def agent_log_path(self) -> Path:
        return self.logs_dir / "agent.log"

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        """Append one JSON record to a file."""
        with path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def _append_agent(self, line: str) -> None:
        """Append one human-readable line to agent.log."""
        ts = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        with self.agent_log_path.open("a") as f:
            f.write(f"[{ts}] {line}\n")

    def log_run_start(self, mode: str, interval: int, llm_model: str) -> None:
        """Log run start to agent.log."""
        self._append_agent(
            f"=== Run {self.run_id[:8]} started | Mode: {mode} "
            f"| Interval: {interval}s | LLM: {llm_model} ==="
        )

    def log_run_end(self, cycles: int, accepted: int, skipped: int) -> None:
        """Log run end to agent.log."""
        self._append_agent(
            f"=== Run {self.run_id[:8]} complete | "
            f"{cycles} cycles | {accepted} accepted, {skipped} skipped ==="
        )

    def log_event(
        self,
        cycle_id: str,
        instrument: str,
        price: str,
        source: str,
        hypothesis: dict[str, Any] | None,
        validation: dict[str, Any] | None,
    ) -> None:
        """Log an observe+hypothesis+validation event."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "instrument": instrument,
            "price": price,
            "source": source,
            "hypothesis": hypothesis,
            "validation": validation,
        }
        self._append_jsonl(self.events_path, record)

        # Human-readable
        if hypothesis:
            factor = hypothesis.get("factor_name", "?")
            direction = hypothesis.get("direction", "?")
            rationale = hypothesis.get("rationale", "")[:80]
            self._append_agent(
                f"🧠 {instrument} Hypothesis: {factor} → {direction} | \"{rationale}\""
            )
        if validation:
            sharpe = validation.get("sharpe", 0)
            drawdown = validation.get("max_drawdown", 0)
            passed = validation.get("passed", False)
            obs = validation.get("observations", 0)
            status = "PASSED" if passed else "FAILED"
            self._append_agent(
                f"📊 Validation: Sharpe={sharpe:.2f}, MaxDD={drawdown:.2%}, "
                f"{obs} obs → {status}"
            )
        if not hypothesis:
            self._append_agent(
                f"🔍 {instrument} close=${price} — no hypothesis proposed"
            )

    def log_decision(
        self,
        cycle_id: str,
        instrument: str,
        selected_hypothesis: str | None,
        side: str | None,
        quantity: str | None,
        price: str | None,
        rationale: str,
    ) -> None:
        """Log LLM decision (selection or decline)."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "instrument": instrument,
            "selected_hypothesis": selected_hypothesis,
            "side": side,
            "quantity": quantity,
            "price": price,
            "rationale": rationale,
        }
        self._append_jsonl(self.decisions_path, record)

        if selected_hypothesis:
            self._append_agent(
                f"🤖 Decision: {side!s} {instrument} @ ${price} qty={quantity} "
                f"| \"{rationale[:80]}\""
            )
        else:
            self._append_agent(f"⏭️ No trade for {instrument} — {rationale[:80]}")

    def log_risk(
        self,
        cycle_id: str,
        instrument: str,
        gates: list[dict[str, Any]],
        verdict: str,
    ) -> None:
        """Log risk gate verdicts."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "instrument": instrument,
            "gates": gates,
            "verdict": verdict,
        }
        self._append_jsonl(self.risk_path, record)

        passed_count = sum(1 for g in gates if g.get("passed"))
        total = len(gates)
        if verdict == "all_passed":
            self._append_agent(f"🛡️ Gates: {passed_count}/{total} passed")
        else:
            failed = [g for g in gates if not g.get("passed")]
            first_fail = failed[0] if failed else {}
            self._append_agent(
                f"🚫 Gates: BLOCKED by {first_fail.get('gate_name', '?')} "
                f"— {first_fail.get('reason', '?')}"
            )

    def log_trade(
        self,
        cycle_id: str,
        record_type: str,
        instrument: str,
        side: str,
        price: str,
        size: str,
        order_id: str | None,
        status: str,
        pnl: str | None = None,
        pnl_pct: float | None = None,
    ) -> None:
        """Log an entry or exit trade."""
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "cycle_id": cycle_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "record_type": record_type,
            "instrument": instrument,
            "side": side,
            "price": price,
            "size": size,
            "orderId": order_id,
            "orderStatus": status,
        }
        if pnl is not None:
            record["pnl"] = pnl
            record["pnl_pct"] = pnl_pct
        self._append_jsonl(self.trades_path, record)

        if record_type == "entry":
            emoji = "✅" if status == "filled" else "❌"
            self._append_agent(
                f"{emoji} Entry: {side} {instrument} @ ${price} size={size} "
                f"orderId={order_id or 'none'} status={status}"
            )
        elif record_type == "exit":
            self._append_agent(
                f"📤 Exit: {side} {instrument} @ ${price} size={size} "
                f"PnL={pnl} ({pnl_pct:.2%}) orderId={order_id or 'none'}"
            )

    def log_error(self, context: str, error: str) -> None:
        """Log an error to agent.log (no separate error file unless needed)."""
        self._append_agent(f"⚠️ ERROR [{context}]: {error}")


__all__ = ["EvidenceLogger"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_evidence.py -v`
Expected: 2 PASS

- [ ] **Step 5: Add tests for log_event, log_decision, log_risk, log_trade**

```python
# Append to tests/test_evidence.py

import json


def test_log_event_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_event(
        cycle_id="cycle-001",
        instrument="RAAPLUSDT",
        price="231.45",
        source="bitget-demo",
        hypothesis={
            "factor_name": "momentum",
            "direction": "long",
            "parameters": {"lookback": 20, "threshold": 0.02},
            "rationale": "Strong upward trend over 20 bars",
        },
        validation={
            "sharpe": 1.82,
            "max_drawdown": -0.043,
            "passed": True,
            "observations": 60,
        },
    )
    lines = logger.events_path.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["run_id"] == "run-001"
    assert record["cycle_id"] == "cycle-001"
    assert record["instrument"] == "RAAPLUSDT"
    assert record["hypothesis"]["factor_name"] == "momentum"
    assert record["validation"]["sharpe"] == 1.82


def test_log_decision_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_decision(
        cycle_id="cycle-001",
        instrument="AAPLUSDT",
        selected_hypothesis="hyp-001",
        side="buy",
        quantity="3",
        price="231.45",
        rationale="Best risk-adjusted return from momentum factor",
    )
    lines = logger.decisions_path.read_text().strip().split("\n")
    record = json.loads(lines[0])
    assert record["side"] == "buy"
    assert record["rationale"] == "Best risk-adjusted return from momentum factor"


def test_log_risk_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    gates = [
        {"gate_name": "factor_allowlist", "passed": True, "reason": "ok"},
        {"gate_name": "max_notional", "passed": False, "reason": "exceeds $10000"},
    ]
    logger.log_risk(
        cycle_id="cycle-001",
        instrument="AAPLUSDT",
        gates=gates,
        verdict="blocked",
    )
    lines = logger.risk_path.read_text().strip().split("\n")
    record = json.loads(lines[0])
    assert record["verdict"] == "blocked"
    assert len(record["gates"]) == 2


def test_log_trade_writes_jsonl(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_trade(
        cycle_id="cycle-001",
        record_type="entry",
        instrument="AAPLUSDT",
        side="buy",
        price="231.45",
        size="3",
        order_id="1483325250270023680",
        status="filled",
    )
    lines = logger.trades_path.read_text().strip().split("\n")
    record = json.loads(lines[0])
    assert record["orderId"] == "1483325250270023680"
    assert record["orderStatus"] == "filled"


def test_agent_log_human_readable(tmp_path: Path) -> None:
    logger = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger.log_run_start(mode="demo", interval=14400, llm_model="claude-sonnet-4-6")
    logger.log_event(
        cycle_id="c1",
        instrument="RAAPLUSDT",
        price="231.45",
        source="bitget-demo",
        hypothesis=None,
        validation=None,
    )
    logger.log_run_end(cycles=4, accepted=1, skipped=3)

    content = logger.agent_log_path.read_text()
    assert "Run run-001" in content
    assert "RAAPLUSDT" in content
    assert "1 accepted, 3 skipped" in content


def test_append_only_across_calls(tmp_path: Path) -> None:
    """Two separate logger instances (simulating two runs) append to same files."""
    logger1 = EvidenceLogger(logs_dir=tmp_path, run_id="run-001")
    logger1.log_decision(
        cycle_id="c1", instrument="AAPLUSDT",
        selected_hypothesis="h1", side="buy", quantity="1",
        price="100", rationale="first",
    )
    logger2 = EvidenceLogger(logs_dir=tmp_path, run_id="run-002")
    logger2.log_decision(
        cycle_id="c2", instrument="METAUSDT",
        selected_hypothesis="h2", side="sell", quantity="2",
        price="200", rationale="second",
    )
    lines = tmp_path.joinpath("decisions.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["run_id"] == "run-001"
    assert json.loads(lines[1])["run_id"] == "run-002"
```

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/test_evidence.py -v && uv run pytest --tb=short -q`
Expected: All new tests pass, all 312 existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add src/factor_atlas/evidence.py tests/test_evidence.py
git commit -m "feat(evidence): add structured evidence logger with 4 JSONL files + agent.log"
```

---

### Task 2: ATR-Based Position Sizing Module

**Files:**
- Create: `src/factor_atlas/sizing.py`
- Create: `tests/test_sizing.py`
- Modify: `src/factor_atlas/config.py` — add sizing constants

**Interfaces:**
- Produces: `compute_atr(df, period) -> float`, `compute_position_size(price, atr, risk_config) -> Decimal`
- Consumed by: Task 4 (runner wiring)

Position sizing formula: `quantity = max_risk_per_trade / (sl_atr_mult × ATR)`, capped by `max_notional / price`. ATR is computed from the same 90-day OHLCV data already fetched.

- [ ] **Step 1: Add sizing constants to config.py**

Add after the existing `DAILY_LOSS_LIMIT` line in `src/factor_atlas/config.py`:

```python
# ATR-based sizing and exit thresholds
ATR_PERIOD: int = 14
MAX_RISK_PER_TRADE: str = "500"  # Risk $500 per trade on $100K account = 0.5%
SL_ATR_MULT: float = 3.0  # Stop-loss = 3 × ATR
TP_ATR_MULT: float = 6.0  # Take-profit = 6 × ATR (2:1 R:R)
MAX_MARGIN_PCT: float = 0.25  # Hard cap: 25% of balance per trade
```

- [ ] **Step 2: Write failing tests for ATR and sizing**

```python
# tests/test_sizing.py
"""Tests for ATR-based position sizing."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from factor_atlas.risk import RiskConfig
from factor_atlas.sizing import compute_atr, compute_position_size


def _make_ohlcv(n: int = 30, base_price: float = 200.0) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame."""
    import numpy as np
    rng = np.random.default_rng(42)
    closes = base_price + rng.standard_normal(n).cumsum()
    highs = closes + rng.uniform(1, 5, n)
    lows = closes - rng.uniform(1, 5, n)
    opens = closes + rng.uniform(-2, 2, n)
    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": rng.uniform(1000, 5000, n),
    })


def test_compute_atr_returns_positive() -> None:
    df = _make_ohlcv(30)
    atr = compute_atr(df, period=14)
    assert atr > 0


def test_compute_atr_period_longer_than_data() -> None:
    df = _make_ohlcv(5)
    atr = compute_atr(df, period=14)
    # Should still return a value (uses available data)
    assert atr > 0


def test_position_size_basic() -> None:
    """With known ATR, position size should be max_risk / (SL_mult * ATR)."""
    config = RiskConfig()
    qty = compute_position_size(
        price=Decimal("200"),
        atr=5.0,  # ATR = $5
        risk_config=config,
    )
    # SL distance = 3.0 * 5 = $15. qty = 500 / 15 = 33.33 → 33
    assert qty == Decimal("33")


def test_position_size_capped_by_notional() -> None:
    """Position size must not exceed max_notional / price."""
    config = RiskConfig()
    qty = compute_position_size(
        price=Decimal("200"),
        atr=0.5,  # Very low ATR → huge qty → should be capped
        risk_config=config,
    )
    # max_notional=10000, price=200 → max qty = 50
    assert qty <= Decimal("50")


def test_position_size_minimum_one() -> None:
    """Position size should be at least 1."""
    config = RiskConfig()
    qty = compute_position_size(
        price=Decimal("5000"),
        atr=100.0,  # High ATR, high price → tiny qty
        risk_config=config,
    )
    assert qty >= Decimal("1")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_sizing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'factor_atlas.sizing'`

- [ ] **Step 4: Implement sizing module**

```python
# src/factor_atlas/sizing.py
"""ATR-based position sizing for FactorAtlas.

Sizing formula:
  sl_distance = SL_ATR_MULT × ATR
  quantity = MAX_RISK_PER_TRADE / sl_distance
  quantity = min(quantity, max_notional / price)
  quantity = max(quantity, 1)
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

import pandas as pd

from factor_atlas.config import MAX_RISK_PER_TRADE, SL_ATR_MULT
from factor_atlas.risk import RiskConfig


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Compute Average True Range from OHLCV data.

    Uses the standard Wilder method: TR = max(H-L, |H-Cprev|, |L-Cprev|),
    ATR = EWM of TR over ``period`` bars.

    Returns the last ATR value. If the DataFrame has fewer rows than
    ``period``, uses all available data.
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    return float(atr.iloc[-1])


def compute_position_size(
    price: Decimal,
    atr: float,
    risk_config: RiskConfig,
) -> Decimal:
    """Compute position size based on ATR and risk budget.

    Returns integer quantity (Bitget stock perps require whole numbers).
    Minimum 1, capped by max_notional / price.
    """
    sl_distance = Decimal(str(SL_ATR_MULT * atr))
    if sl_distance <= 0:
        return Decimal("1")

    max_risk = Decimal(MAX_RISK_PER_TRADE)
    raw_qty = max_risk / sl_distance

    # Cap by max_notional
    max_qty_by_notional = risk_config.max_notional / price
    qty = min(raw_qty, max_qty_by_notional)

    # Floor to integer, minimum 1
    qty = qty.to_integral_value(rounding=ROUND_DOWN)
    return max(qty, Decimal("1"))


__all__ = ["compute_atr", "compute_position_size"]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_sizing.py -v && uv run pytest --tb=short -q`
Expected: All new + existing tests pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/config.py src/factor_atlas/sizing.py tests/test_sizing.py
git commit -m "feat(sizing): add ATR-based position sizing module"
```

---

### Task 3: Update RiskConfig with ATR Exit Params + Wire Sizing into Decisions

**Files:**
- Modify: `src/factor_atlas/risk.py:39-53` — add ATR fields to RiskConfig
- Modify: `src/factor_atlas/runner.py:562-584` — ATR-based exit evaluation
- Modify: `src/factor_atlas/llm/decision.py:77-83` — use sized quantity
- Modify: `src/factor_atlas/decision.py:78-91` — use sized quantity in fixture
- Modify: `tests/test_sizing.py` — add exit tests

**Interfaces:**
- Consumes: `compute_atr()` and `compute_position_size()` from Task 2
- Produces: Updated `_should_exit()` using ATR, updated decision providers using sized quantities

- [ ] **Step 1: Update RiskConfig in risk.py**

Replace the exit management block at `risk.py:50-53`:

```python
    # Exit management (ATR-based)
    max_hold_hours: int = 24
    stop_loss_pct: float = 0.03  # Fallback if ATR unavailable
    take_profit_pct: float = 0.05  # Fallback if ATR unavailable
    sl_atr_mult: float = 3.0
    tp_atr_mult: float = 6.0
    atr_period: int = 14
```

- [ ] **Step 2: Update `_should_exit` in runner.py to use ATR when available**

Replace `runner.py:562-584`:

```python
def _should_exit(
    pos: OpenPosition,
    current_price: Decimal,
    now: datetime,
    risk_config: RiskConfig,
    atr: float | None = None,
) -> tuple[bool, str]:
    """Return (should_exit, reason) for an open position.

    Uses ATR-based SL/TP when ``atr`` is provided, otherwise falls back
    to percentage-based thresholds.
    """
    cost = pos.entry_price
    if cost == 0:
        return False, ""

    if pos.side == "buy":
        unrealized = current_price - pos.entry_price
    else:
        unrealized = pos.entry_price - current_price

    # ATR-based exits (preferred)
    if atr is not None and atr > 0:
        sl_distance = Decimal(str(risk_config.sl_atr_mult * atr))
        tp_distance = Decimal(str(risk_config.tp_atr_mult * atr))
        if unrealized <= -sl_distance:
            pct = float(unrealized / cost)
            return True, f"stop_loss_atr ({pct:.2%}, SL={sl_distance:.2f})"
        if unrealized >= tp_distance:
            pct = float(unrealized / cost)
            return True, f"take_profit_atr ({pct:.2%}, TP={tp_distance:.2f})"
    else:
        # Percentage fallback
        unrealized_pct = float(unrealized / cost)
        if unrealized_pct <= -risk_config.stop_loss_pct:
            return True, f"stop_loss ({unrealized_pct:.2%})"
        if unrealized_pct >= risk_config.take_profit_pct:
            return True, f"take_profit ({unrealized_pct:.2%})"

    hold_h = (now - pos.entry_time).total_seconds() / 3600
    if hold_h >= risk_config.max_hold_hours:
        return True, f"max_hold ({hold_h:.1f}h)"
    return False, ""
```

- [ ] **Step 3: Update fixture decision provider to accept quantity parameter**

In `src/factor_atlas/decision.py`, update `FixtureDecisionProvider.decide()` to accept an optional `quantity` param:

```python
    def decide(
        self,
        snapshot: MarketSnapshot,
        candidates: list[tuple[FactorHypothesis, ValidationResult]],
        cycle_id: str,
        quantity: Decimal | None = None,
    ) -> TradeDecision | None:
        # ... existing logic ...
        return TradeDecision(
            decision_id=decision_id,
            cycle_id=cycle_id,
            hypothesis_id=best_hyp.hypothesis_id,
            instrument=snapshot.instrument,
            side=side,
            quantity=quantity or Decimal(1),
            price=snapshot.close,
            rationale=(
                f"Best Sharpe={best_val.metrics.sharpe_ratio.value:.4f} "
                f"from {best_hyp.factor_name} on {snapshot.instrument}"
            ),
            timestamp=datetime.now(tz=UTC),
        )
```

Update the `DecisionProvider` protocol to include the optional `quantity`:

```python
    def decide(
        self,
        snapshot: MarketSnapshot,
        candidates: list[tuple[FactorHypothesis, ValidationResult]],
        cycle_id: str,
        quantity: Decimal | None = None,
    ) -> TradeDecision | None: ...
```

Do the same for `LLMDecisionProvider.decide()` in `src/factor_atlas/llm/decision.py:113-145` — add `quantity: Decimal | None = None` parameter, use `quantity or Decimal(1)` when building TradeDecision at line 82.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest --tb=short -q && uv run mypy .`
Expected: All pass. Some existing tests may need `quantity` parameter added — fix any failures.

- [ ] **Step 5: Commit**

```bash
git add src/factor_atlas/risk.py src/factor_atlas/runner.py \
  src/factor_atlas/decision.py src/factor_atlas/llm/decision.py
git commit -m "feat(risk): add ATR-based exits and sized quantity to decision providers"
```

---

### Task 4: Wire Evidence Logger + Sizing into Runner

**Files:**
- Modify: `src/factor_atlas/runner.py` — integrate EvidenceLogger and compute_position_size
- Modify: `src/factor_atlas/orchestrator.py` — thread sized_quantities through to decision providers

**Interfaces:**
- Consumes: `EvidenceLogger` from Task 1, `compute_atr` + `compute_position_size` from Task 2, ATR exits from Task 3
- Produces: Runner that writes structured evidence + uses ATR sizing

This is the main wiring task, split into two phases: (A) evidence logging and (B) sizing integration.

**PHASE A: Wire evidence logging**

- [ ] **Step 1: Import evidence in runner.py and create logger in `run_paper_session`**

Add to imports at top of `runner.py`:

```python
from factor_atlas.evidence import EvidenceLogger
from factor_atlas.sizing import compute_atr, compute_position_size
```

After `audit_logger` creation (~line 794), add:

```python
    # Evidence logger (append-only structured logs)
    logs_dir = (output_dir or _DEFAULT_OUTPUT_DIR) / "logs"
    evidence = EvidenceLogger(logs_dir=logs_dir, run_id=run_id)
```

- [ ] **Step 2: Log run start after LLM provider setup**

After the LLM provider is set up (~line 847), add:

```python
    evidence.log_run_start(
        mode=mode,
        interval=0,  # Will be set by continuous runner
        llm_model=llm_info.get("llm_model", "unknown"),
    )
```

- [ ] **Step 3: Log evidence at each cycle stage**

After each cycle result, inside the `for result in results:` loop that calls `_print_cycle_summary` (~line 883), add evidence logging calls for event, decision, and risk. See the EvidenceLogger methods from Task 1 — call `log_event()` with the hypothesis/validation data from `result`, `log_decision()` with the decision or status, and `log_risk()` with gate_results if present.

For each accepted cycle that gets a bgc order (~line 891-914), also call `evidence.log_trade()` with the order details.

- [ ] **Step 4: Log run end**

After the run summary print (~line 1000):

```python
    evidence.log_run_end(
        cycles=len(results),
        accepted=manifest["accepted_count"],
        skipped=manifest["rejected_count"],
    )
```

- [ ] **Step 5: Run tests to verify evidence wiring doesn't break existing tests**

Run: `uv run pytest --tb=short -q`
Expected: All 312 existing tests pass (evidence logger writes to files but tests use tmp_path or fixture mode)

- [ ] **Step 6: Commit evidence wiring**

```bash
git add src/factor_atlas/runner.py
git commit -m "feat(runner): wire evidence logging into paper session"
```

**PHASE B: Wire ATR sizing**

- [ ] **Step 7: Compute ATR per instrument before run_cycles**

Before calling `run_cycles` (~line 869), add:

```python
    # Compute ATR per instrument for sizing
    atr_values: dict[str, float] = {}
    for sym, df in ohlcv_data.items():
        if not df.empty and len(df) >= risk_config.atr_period:
            atr_values[sym] = compute_atr(df, risk_config.atr_period)

    # Compute sized quantities per instrument
    sized_quantities: dict[str, Decimal] = {}
    for sym, df in ohlcv_data.items():
        if sym in atr_values and not df.empty:
            price = Decimal(str(df.iloc[-1]["close"]))
            sized_quantities[sym] = compute_position_size(
                price=price, atr=atr_values[sym], risk_config=risk_config,
            )
```

- [ ] **Step 8: Thread sized_quantities through orchestrator**

Update `run_cycles()` and `run_cycle()` in `orchestrator.py` to accept `sized_quantities: dict[str, Decimal] | None = None`. Pass it through to the decision provider's `decide()` call at line 126:

```python
    # In run_cycle, before calling decision_provider.decide():
    qty = None
    if sized_quantities:
        qty = sized_quantities.get(snapshot.instrument)

    decision = decision_provider.decide(snapshot, validated, cycle_id, quantity=qty)
```

Update `run_cycles` to forward `sized_quantities` to each `run_cycle` call.

- [ ] **Step 9: Update `_process_demo_exits` to use ATR**

Add `atr_values` parameter to `_process_demo_exits` and pass it through to `_should_exit`:

```python
def _process_demo_exits(
    broker_state: BrokerState,
    perp_prices: dict[str, Decimal],
    risk_config: RiskConfig,
    config_hash: str,
    paper_log_f: Any,
    atr_values: dict[str, float] | None = None,
    evidence: EvidenceLogger | None = None,
) -> None:
```

For each position, look up `atr = (atr_values or {}).get(instrument)` and pass to `_should_exit(pos, current_price, now, risk_config, atr=atr)`.

When a position is closed and `evidence` is not None, call `evidence.log_trade()` with record_type="exit".

- [ ] **Step 10: Update the caller in `run_paper_session` to pass atr_values and evidence**

```python
            _process_demo_exits(
                broker_state, perp_prices, risk_config, config_hash, paper_log_f,
                atr_values=atr_values, evidence=evidence,
            )
```

- [ ] **Step 11: Run full test suite + type check**

Run: `uv run pytest --tb=short -q && uv run mypy . && uv run ruff check .`
Expected: All pass. Fix any signature mismatches in tests (some test mocks may need `quantity` param added).

- [ ] **Step 12: Commit sizing wiring**

```bash
git add src/factor_atlas/runner.py src/factor_atlas/orchestrator.py
git commit -m "feat(runner): wire ATR sizing and exits into paper session"
```

---

### Task 5: Add Continuous Runner Mode to CLI

**Files:**
- Modify: `src/factor_atlas/__main__.py` — add `--continuous` and `--interval` flags
- Modify: `src/factor_atlas/runner.py` — add `run_continuous` function
- Create: `tests/test_continuous.py`

**Interfaces:**
- Consumes: `run_paper_session()` from Task 4
- Produces: `run_continuous()` — while-loop with sleep, graceful shutdown

- [ ] **Step 1: Write test for continuous mode (one-shot)**

```python
# tests/test_continuous.py
"""Tests for continuous runner mode."""

from __future__ import annotations

from unittest.mock import patch

from factor_atlas.runner import run_continuous


def test_continuous_single_round(tmp_path) -> None:
    """Continuous mode with max_rounds=1 runs exactly one session."""
    with patch("factor_atlas.runner.run_paper_session") as mock_run:
        mock_run.return_value = tmp_path / "fake-run"
        run_continuous(
            mode="fixture",
            cycles=2,
            interval=60,
            output_dir=tmp_path,
            max_rounds=1,
        )
        assert mock_run.call_count == 1
```

- [ ] **Step 2: Implement `run_continuous` in runner.py**

Add at the end of `runner.py`, before `__all__`:

```python
def run_continuous(
    mode: str = "demo",
    cycles: int = 4,
    interval: int = 14400,
    output_dir: Path | None = None,
    max_rounds: int | None = None,
) -> None:
    """Run paper sessions in a loop with sleep between rounds.

    Handles SIGINT/SIGTERM for graceful shutdown. If ``max_rounds`` is set,
    stops after that many rounds (useful for GitHub Actions cron).
    """
    import signal
    import threading

    shutdown_event = threading.Event()

    def _handle_signal(signum: int, frame: object) -> None:
        print(f"\nReceived signal {signum}, finishing current round...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    round_num = 0
    while not shutdown_event.is_set():
        round_num += 1
        print(f"\n{'=' * 60}")
        print(f"  Continuous round {round_num} | interval={interval}s")
        print(f"{'=' * 60}")
        try:
            run_paper_session(mode=mode, cycles=cycles, output_dir=output_dir)
        except Exception as e:
            print(f"  Round {round_num} failed: {e}", file=sys.stderr)

        if max_rounds is not None and round_num >= max_rounds:
            print(f"  Reached max_rounds={max_rounds}, stopping.")
            break

        if not shutdown_event.is_set():
            print(f"  Sleeping {interval}s until next round...")
            shutdown_event.wait(timeout=interval)
```

Update `__all__` to include `run_continuous`.

- [ ] **Step 3: Add CLI flags in __main__.py**

Add to the `run_parser` arguments:

```python
    run_parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run in continuous loop mode with --interval between rounds.",
    )
    run_parser.add_argument(
        "--interval",
        type=int,
        default=14400,
        help="Seconds between rounds in continuous mode. Default: 14400 (4 hours).",
    )
    run_parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Stop after N rounds (useful for cron). Default: unlimited.",
    )
```

Update the `run` command handler:

```python
    if args.command == "run":
        from pathlib import Path
        from factor_atlas.runner import run_continuous, run_paper_session, validate_config

        if args.dry_run:
            validate_config()
            return 0

        output_dir = Path(args.output) if args.output else None
        try:
            if args.continuous:
                run_continuous(
                    mode=args.mode,
                    cycles=args.cycles,
                    interval=args.interval,
                    output_dir=output_dir,
                    max_rounds=args.max_rounds,
                )
            else:
                run_paper_session(
                    mode=args.mode,
                    cycles=args.cycles,
                    output_dir=output_dir,
                )
        except (NotImplementedError, RuntimeError, OSError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_continuous.py -v && uv run pytest --tb=short -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/factor_atlas/__main__.py src/factor_atlas/runner.py tests/test_continuous.py
git commit -m "feat(cli): add --continuous and --interval flags for autonomous running"
```

---

### Task 6: Archive Stale Runs + Clean Exchange State

**Files:**
- Create: `scripts/archive_stale_runs.py` — one-time migration script
- Modify: `artifacts/paper-trading/positions_state.json` — reconcile with exchange

This task cleans up the messy artifact state. Run manually once, then commit.

- [ ] **Step 1: Create archive script**

```python
# scripts/archive_stale_runs.py
"""One-time script to archive stale runs and reset positions_state.json.

Stale = fixture mode OR demo mode with zero Bitget orderIds.
Real = demo mode with at least one orderId in paper_log.jsonl.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ARTIFACTS_DIR = Path("artifacts/paper-trading")
ARCHIVE_DIR = Path("artifacts/archive")

STALE_RUN_IDS = [
    "a8fcc980-4aa0-4452-840c-cbe6b6b59b89",
    "50fb2b14-b925-4999-96f2-e9be7643abad",
    "bbc51c19-8934-460b-a261-4f81ab9ae7bc",
    "199ac5d2-b42c-494f-a481-f735cbaca21c",
    "1b35e00a-f4f6-43eb-b2b9-4075a1267d38",
    "0a0fc56b-a92a-4eec-95b4-4ac1113a33db",
    "88eaf22f-1329-45a8-9542-8c55dc5e7431",
    "41ea91ca-3121-4375-886c-8281231a2cf6",
    "919104fc-fd1c-44af-adec-0526fe107424",
]


def main() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    moved = 0
    for run_id in STALE_RUN_IDS:
        src = ARTIFACTS_DIR / run_id
        if src.exists():
            dst = ARCHIVE_DIR / run_id
            shutil.move(str(src), str(dst))
            print(f"  Archived: {run_id}")
            moved += 1
        else:
            print(f"  Not found: {run_id}")

    print(f"\nArchived {moved} stale runs to {ARCHIVE_DIR}/")

    # Create logs/ directory
    logs_dir = ARTIFACTS_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    print(f"Created {logs_dir}/")

    # Move remaining runs to runs/ subdirectory
    runs_dir = ARTIFACTS_DIR / "runs"
    runs_dir.mkdir(exist_ok=True)
    for item in ARTIFACTS_DIR.iterdir():
        if item.is_dir() and item.name not in ("logs", "runs") and len(item.name) == 36:
            dst = runs_dir / item.name
            shutil.move(str(item), str(dst))
            print(f"  Moved to runs/: {item.name}")

    print("Done. Restructured artifacts/paper-trading/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the archive script**

Run: `uv run python scripts/archive_stale_runs.py`
Expected: 9 runs archived, remaining 12 moved to `runs/`

NOTE: The 12 real runs under `runs/` still use old field names (`bgc_order_id`, `category`, `quantity`) in their `paper_log.jsonl` files. This is acceptable — those are historical artifacts. The NEW `logs/trades.jsonl` (written by the evidence logger going forward) uses Bitget field names (`orderId`, `productType`, `size`). Judges will see the new logs. Do NOT rewrite old JSONL files — that would falsify history.

- [ ] **Step 3: Reset positions_state.json to match Bitget Demo**

The exchange was verified on Sep 14 12:24 UTC and shows 7 open positions:
- AAPLUSDT short 15 @ $331.71 (unrealized -$16.90)
- METAUSDT short 7 @ $640.90 (unrealized -$142.95)
- METAUSDT long 7 @ $640.14 (unrealized +$148.26)
- NVDAUSDT short 1 @ $213.10 (unrealized -$1.44)
- NVDAUSDT long 1 @ $218.07 (unrealized -$3.53)
- TSLAUSDT short 1 @ $358.73 (unrealized -$0.23)
- TSLAUSDT long 1 @ $358.18 (unrealized +$0.78)

0 pending orders. 21 filled orders in history.

Before resetting, re-verify with:
```bash
set -a && source .env && set +a
bgc --paper-trading position --action info --category USDT-FUTURES
```

If exchange state matches, write a fresh `positions_state.json`. If credentials fail, skip this step and flag it — do NOT guess.

- [ ] **Step 4: Commit the restructuring**

NOTE: Do NOT delete `docs/evidence/` here — those htmlpreview links are the only working evidence URLs judges have. Deletion happens in Task 8 AFTER GitHub Pages is confirmed live and all links are updated.

```bash
git add artifacts/ scripts/archive_stale_runs.py
git commit -m "chore: archive stale runs, restructure artifacts directory"
```

---

### Task 7: GitHub Actions Cron Workflow

**Files:**
- Create: `.github/workflows/paper-runner.yml`

- [ ] **Step 1: Create the workflow**

```yaml
# .github/workflows/paper-runner.yml
name: Paper Trading Runner

on:
  schedule:
    # Every 4 hours
    - cron: '0 */4 * * *'
  workflow_dispatch: # Manual trigger

permissions:
  contents: write

jobs:
  paper-run:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Install bgc CLI
        run: npm install -g @bitget-ai/bitget-agent-cli

      - name: Install dependencies
        run: uv sync

      - name: Run paper session (1 round, 4 cycles)
        env:
          BITGET_API_KEY: ${{ secrets.BITGET_API_KEY }}
          BITGET_SECRET_KEY: ${{ secrets.BITGET_SECRET_KEY }}
          BITGET_PASSPHRASE: ${{ secrets.BITGET_PASSPHRASE }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION }}
        run: |
          uv run python -m factor_atlas run \
            --mode demo \
            --cycles 4 \
            --continuous \
            --max-rounds 1

      - name: Generate report for latest run
        run: |
          LATEST_RUN=$(ls -t artifacts/paper-trading/runs/ | head -1)
          if [ -n "$LATEST_RUN" ]; then
            uv run python -m factor_atlas report \
              --run-dir "artifacts/paper-trading/runs/$LATEST_RUN"
          fi

      - name: Commit evidence
        run: |
          git config user.name "FactorAtlas Bot"
          git config user.email "bot@factor-atlas.dev"
          git add artifacts/paper-trading/logs/ artifacts/paper-trading/runs/ artifacts/paper-trading/positions_state.json
          git diff --cached --quiet || git commit -m "evidence: paper trading run $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git pull --rebase origin main || true
          git push
```

- [ ] **Step 2: Commit the workflow**

```bash
git add .github/workflows/paper-runner.yml
git commit -m "ci: add GitHub Actions cron workflow for daily paper trading"
```

- [ ] **Step 3: Add secrets to GitHub repo**

Run (manual — needs user):
```bash
gh secret set BITGET_API_KEY
gh secret set BITGET_SECRET_KEY
gh secret set BITGET_PASSPHRASE
gh secret set AWS_ACCESS_KEY_ID
gh secret set AWS_SECRET_ACCESS_KEY
gh secret set AWS_DEFAULT_REGION
```

---

### Task 8: GitHub Pages + Update Links

**Files:**
- Create: `.github/workflows/pages.yml`
- Create: `artifacts/paper-trading/logs/index.html` — simple log viewer page
- Modify: `README.md` — update evidence links
- Modify: `docs/SUBMISSION.md` — update evidence links

- [ ] **Step 1: Create GitHub Pages workflow**

```yaml
# .github/workflows/pages.yml
name: Deploy Evidence to GitHub Pages

on:
  push:
    branches: [main]
    paths: ['artifacts/paper-trading/**']
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Pages
        uses: actions/configure-pages@v4

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: 'artifacts/paper-trading'

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Create a simple index.html for the logs directory**

```html
<!-- artifacts/paper-trading/logs/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>FactorAtlas — Evidence Logs</title>
  <style>
    body { font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 2rem; }
    h1 { color: #58a6ff; }
    a { color: #58a6ff; }
    .log-list { list-style: none; padding: 0; }
    .log-list li { margin: 0.5rem 0; }
    .desc { color: #8b949e; margin-left: 1rem; }
  </style>
</head>
<body>
  <h1>FactorAtlas — Evidence Logs</h1>
  <p>Structured evidence from the autonomous factor-discovery agent.</p>
  <ul class="log-list">
    <li><a href="agent.log">agent.log</a><span class="desc"> — Human-readable timeline (start here)</span></li>
    <li><a href="events.jsonl">events.jsonl</a><span class="desc"> — Observe + hypothesis + validation</span></li>
    <li><a href="decisions.jsonl">decisions.jsonl</a><span class="desc"> — LLM selection + rationale</span></li>
    <li><a href="risk.jsonl">risk.jsonl</a><span class="desc"> — 14 risk gate verdicts</span></li>
    <li><a href="trades.jsonl">trades.jsonl</a><span class="desc"> — Entry/exit orders + PnL</span></li>
  </ul>
  <p style="margin-top: 2rem; color: #8b949e;">
    Each record carries run_id + cycle_id for cross-file tracing.
    <br>Visual reports: <a href="../runs/">runs/</a>
  </p>
</body>
</html>
```

- [ ] **Step 3: Enable GitHub Pages (source: GitHub Actions)**

The workflow uses `actions/deploy-pages` which requires Pages source set to "GitHub Actions" (NOT "deploy from branch"). Set it via API:

```bash
gh api repos/samueldanso/factor-atlas/pages -X PUT \
  -f build_type=workflow \
  --silent 2>/dev/null || \
gh api repos/samueldanso/factor-atlas/pages -X POST \
  -f build_type=workflow \
  --silent 2>/dev/null || \
echo "Pages may need manual config: Settings → Pages → Source: GitHub Actions"
```

If the API call fails, configure manually: GitHub repo → Settings → Pages → Build and deployment → Source: "GitHub Actions".

- [ ] **Step 4: Update README.md evidence links**

Replace the existing htmlpreview links with GitHub Pages URLs:

```markdown
> - [Evidence Logs](https://samueldanso.github.io/factor-atlas/logs/) — agent.log, events, decisions, risk, trades
> - [Paper Log (JSONL)](https://samueldanso.github.io/factor-atlas/logs/trades.jsonl) — raw trade records with Bitget `orderId`
```

- [ ] **Step 5: Update SUBMISSION.md evidence links**

Replace the `Submission Material Links` section:

```markdown
Project link: https://github.com/samueldanso/factor-atlas
Evidence logs: https://samueldanso.github.io/factor-atlas/logs/
Agent timeline: https://samueldanso.github.io/factor-atlas/logs/agent.log
Trade records: https://samueldanso.github.io/factor-atlas/logs/trades.jsonl
Demo video: [YOU — record and upload, then paste URL here]
X post: [YOU — post and paste URL here]
```

- [ ] **Step 6: Confirm GitHub Pages is live, then delete docs/evidence/**

First verify Pages is serving at `https://samueldanso.github.io/factor-atlas/logs/`:
```bash
curl -s -o /dev/null -w "%{http_code}" https://samueldanso.github.io/factor-atlas/logs/index.html
```
Expected: 200

Only AFTER confirming Pages is live:
```bash
git rm -r docs/evidence/
```

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/pages.yml artifacts/paper-trading/logs/index.html \
  README.md docs/SUBMISSION.md
git diff --cached --quiet || true
git commit -m "ci: add GitHub Pages deployment, update evidence links, remove old docs/evidence"
```

---

## Verification Checklist

After all tasks, run:

```bash
uv run pytest --tb=short -q          # All tests pass (312 + new)
uv run ruff check .                   # No lint errors
uv run ruff format --check .          # Formatted
uv run mypy .                         # Type-clean
uv run python -m factor_atlas run --dry-run  # Config valid
uv run python -m factor_atlas run --mode fixture --cycles 2  # Fixture works
# Demo test (needs credentials):
uv run python -m factor_atlas run --mode demo --cycles 4
```

Check that `artifacts/paper-trading/logs/` contains all 5 log files after a demo run.
