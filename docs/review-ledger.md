# FactorAtlas — Claude Code Review Ledger

Reviewer: Claude Code (sonnet-4-6)  
Role: Auditor / instrument-policy enforcer  
Started: 2026-09-12

---

## T1 — Typed Contracts and Fixture Event Stream
**Commit:** `2066c49`  
**Verdict: ✅ CLEAN**

Key checks:
- `config.py`: `INSTRUMENTS = {"AAPLUSDT","NVDAUSDT","TSLAUSDT","METAUSDT"}`, `CATEGORY = "USDT-FUTURES"` — correct, no rToken symbols in execution layer
- `contracts.py`: `InstrumentType` and `CategoryType` locked to perp instruments; `PaperOrder` always defaults to `USDT-FUTURES` — instrument policy baked into types
- All 9 models frozen, Decimal for financials, UTC enforced
- 39 tests passing, ruff + mypy clean
- No type suppressions except one noted `# type: ignore[assignment]` on category field (acceptable)

Flags: none

---

## T2 — Registered Factors and Deterministic Validation
**Commit:** `79e098b`  
**Verdict: ✅ CLEAN**

Key checks:
- 5 registered factors: `momentum`, `mean_reversion`, `volatility_breakout`, `volume_spike`, `ema_crossover`
- Signals return `{-1, 0, +1}` only — enforced by tests
- Unknown factor names raise `ValueError` before any computation
- Walk-forward validation: leakage detection, Sharpe/Sortino/drawdown/turnover all labeled `observed`/`estimated`
- Hand-calculated Sharpe fixture test — not just "it runs" but math verified
- 85 tests, all pass, ruff + mypy clean

Flags: none

---

## T3 — Autonomous Discovery-and-Decision Cycle
**Commit:** `95c6f46`  
**Verdict: ✅ CLEAN**

Key checks:
- `Proposer` and `DecisionProvider` are protocols — LLM can be swapped in behind same interface
- `run_cycle()` has no human-approval pause (tested explicitly)
- No validated candidate → `no_candidate` status, no order, no crash
- Decision only selects from validated candidates (tested: `test_cannot_select_non_validated`)
- Both `accepted` and `no_candidate` cycle statuses demonstrated
- 108 tests, ruff + mypy clean

Flags: none

---

## T4 — Deterministic Risk Gates and Automatic Paper Broker
**Commit:** `e0dea1f`  
**Verdict: ✅ CLEAN**

Key checks:
- 12 pure-function risk gates, each with pass + fail test
- `execute_paper_order` fires immediately after all gates pass — no approval pause
- Balance safety: `insufficient_balance` gate prevents negative balance
- Fee/slippage math tested with hand-calculated values
- Broker is **in-memory only** — correct, this is the simulator (Bitget Demo adapter deferred to T7)
- No live paths anywhere
- 160 tests, ruff + mypy clean

Flags: none

---

## T5 — Auditable Cycles and Deterministic Replay
**Commit:** `32f436f`  
**Verdict: ✅ CLEAN**

Key checks:
- Append-only JSONL — each line is a valid `AuditEvent`, round-trips cleanly
- 7-stage chain: `observe→propose→evaluate→decide→gate→execute→learn` verified for both accepted and rejected cycles
- `parent_event_id` linkage tested — full chain reconstructable
- Deterministic replay: same inputs → identical event signatures (UUID/timestamp excluded correctly)
- Writes to file path (relevant: T7 will write to `artifacts/paper-trading/`)
- 190 tests, ruff + mypy clean

Flags: none

---

## T6 — LLM Behind Safe Interfaces
**Commit:** `0a11ddb`  
**Verdict: ✅ CLEAN**

Key checks:
- `LLMProvider` is a `typing.Protocol` — provider-neutral, no vendor lock yet
- LLM output is schema-validated via Pydantic before any execution path
- Unknown factors, bad params, unknown instruments all rejected before reaching orchestrator
- LLM **cannot** control gate outcomes or place orders directly
- Malformed/garbage LLM output handled gracefully (returns None/empty, no crash)
- Full propose→decide cycle works with `FixtureLLMProvider` (no API key needed)
- Prompt templates built from `FACTOR_VOCABULARY` constants — vocabulary drift impossible
- No OpenAI adapter yet (deferred per brief — correct)
- 213 tests total, ruff + mypy clean

Flags: none

---

## T7 — Competition-period Paper Runner + Bitget Demo Adapter
**Status: NOT YET STARTED — stopped for review**

### What T7 must get right (pre-brief checklist)

**Market data adapter:**
- ✅ Confirmed: `bgc market --action candles --category USDT-FUTURES --symbol NVDAUSDT --interval 1D` returns data
- ✅ Confirmed: same for AAPLUSDT, TSLAUSDT, METAUSDT
- Category must be `USDT-FUTURES` (matches `MarketSnapshot.category` default)

**Bitget Demo order placement (confirmed working params):**
```bash
bgc --paper-trading order --action place \
  --category USDT-FUTURES \
  --symbol NVDAUSDT \
  --side buy \
  --orderType limit \
  --price <price> \
  --qty <qty> \
  --timeInForce gtc \
  --posSide long
```
- `--posSide long` is REQUIRED (account is in hedge mode) — without it: `Incorrect position open type`
- `--paper-trading` flag REQUIRED on every write

**Bitget Demo cancel (confirmed working):**
```bash
bgc --paper-trading order --action cancel \
  --category USDT-FUTURES \
  --symbol NVDAUSDT \
  --orderId <orderId from place response>
```

**What must NOT appear in T7:**
- No `category=SPOT` for orders
- No `rAAPLUSDT`, `RAAPLUSDT`, or any r-prefix symbol as an order symbol
- No order call without `--paper-trading`
- No rToken SPOT candles used as primary market data input (use USDT-FUTURES candles)
- No `place-reality-order` endpoint

**Output requirements:**
- Writes to `artifacts/paper-trading/` (JSONL)
- Each record: event_id, cycle_id, instrument, side, price, qty, pre/post balance, fees, slippage, status, risk gate results, software version
- Rejected cycles also written with rejection reason
- Manifest file: actual start/end timestamps, timezone, code commit, config hash

---

## Summary

| Task | Verdict | Tests | Notes |
|------|---------|-------|-------|
| T1 | ✅ Clean | 39 | Foundations solid |
| T2 | ✅ Clean | +46 = 85 | Math verified |
| T3 | ✅ Clean | +23 = 108 | No approval pause confirmed |
| T4 | ✅ Clean | +52 = 160 | Broker in-memory correct |
| T5 | ✅ Clean | +30 = 190 | JSONL chain integrity |
| T6 | ✅ Clean | +23 = 213 | LLM fully sandboxed |
| T7 | ⏳ Pending | — | Pre-brief checklist above |
