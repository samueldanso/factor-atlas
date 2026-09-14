# FactorAtlas

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-312%20passing-brightgreen.svg)](tests/)
[![Bitget Demo](https://img.shields.io/badge/Bitget-Demo%20Paper%20Trading-00C087.svg)](https://www.bitget.com/)
[![LLM](https://img.shields.io/badge/LLM-Claude%20Sonnet%204.6-blueviolet.svg)](https://aws.amazon.com/bedrock/)
[![Track](https://img.shields.io/badge/Track%202-Agentic%20Trading-orange.svg)](#track-alignment)

**Bitget AI Genesis Season 2 — Track 2: Agentic Trading → Factor Discovery Agent**

Autonomous agent that discovers market factors on Bitget **rToken** US stocks, validates trading hypotheses, and executes paper trades on **stock perpetuals** via Bitget Demo — with no human in the loop.

> **Judges — start here:**
> - [Evidence Report](https://htmlpreview.github.io/?https://github.com/samueldanso/factor-atlas/blob/main/docs/evidence/evidence_report.html) — open in browser, visual proof of full cycle
> - [Gate Rejection Evidence](https://htmlpreview.github.io/?https://github.com/samueldanso/factor-atlas/blob/main/docs/evidence/evidence_report_gate_rejection.html) — risk gate blocking a trade
> - [Paper Log (JSONL)](docs/evidence/paper_log.jsonl) — raw trade records with Bitget `orderId`, `orderStatus`, `symbol`
> - [Submission Form](docs/SUBMISSION.md) — all form answers ready to paste
> - [Run It Yourself](#quickstart) — `uv sync && uv run python -m factor_atlas run --mode fixture --cycles 2`

---

## Two-Layer Instrument Architecture

FactorAtlas uses **two instrument layers** — rToken SPOT for research, stock perpetuals for execution:

| Layer | Symbols | Category | Purpose |
|-------|---------|----------|---------|
| **Research** (rToken SPOT) | `RAAPLUSDT` · `RNVDAUSDT` · `RTSLAUSDT` · `RMETAUSDT` | SPOT | 24/7 market data, factor analysis, hypothesis validation |
| **Execution** (Stock Perps) | `AAPLUSDT` · `NVDAUSDT` · `TSLAUSDT` · `METAUSDT` | USDT-FUTURES | Demo paper trading, order placement, fill verification |

**Why two layers?** rTokens (Reality tokens) provide 24/7 price data for US stocks on Bitget — ideal for continuous factor research. Execution routes through USDT-margined stock perpetual contracts because rToken SPOT order placement is not available in the Demo environment. Both layers track the same underlying assets (Apple, NVIDIA, Tesla, Meta). The agent maps `RAAPLUSDT` → `AAPLUSDT` automatically during reconciliation.

---

## What It Does

Every cycle, the agent autonomously:

1. **Observes** — pulls live rToken SPOT price data (`RAAPLUSDT`, `RNVDAUSDT`, etc.) via Bitget API
2. **Proposes** — Claude Sonnet 4.6 (AWS Bedrock) proposes factor hypotheses from a fixed vocabulary
3. **Validates** — walk-forward backtest on historical data → Sharpe, Sortino, drawdown, win rate
4. **Decides** — LLM selects the strongest validated hypothesis and proposes a trade
5. **Risk gates** — 14 deterministic gates verify: positions, balance, exposure, cooldowns, concentration
6. **Executes** — if all gates pass, places a limit order on stock perp (`AAPLUSDT`) via Bitget Demo (`--paper-trading`)
7. **Verifies** — queries Bitget Demo for actual `orderStatus` (`filled`, `cancelled`, `rejected`)
8. **Records** — logs full trace: event → hypothesis → decision rationale → gate results → order outcome

If factors don't support a trade, the agent explicitly decides **not to trade** and logs why.

---

## Paper Trading Results

| Metric | Value | Label |
|--------|-------|-------|
| Total closed trades | 3 | observed |
| Win rate | 66.7% | observed |
| Sharpe ratio | 3.46 | observed |
| Sortino ratio | 4.79 | observed |
| Max drawdown | $7.11 | observed |
| Avg hold time | 25 hours | observed |
| Turnover | $1,548.64 | observed |

Test period: September 12–14, 2026 (Demo paper trading). All values observed from actual execution, not backtests.

### Sample Cycle — Accepted Trade

```
Cycle: AAPLUSDT
  timestamp:    2026-09-12T03:50:00Z
  Hypothesis:   mean_reversion — price below EMA, expect bounce
  Validation:   Sharpe 0.42 (walk-forward, 90-day window)
  Decision:     BUY @ $330.77, qty 1
  Gates:        14/14 passed (positions 0 < 3, balance OK, exposure OK)
  orderStatus:  filled (orderId 1483324512122851328)
  Result:       Position opened, balance updated
```

### Sample Cycle — Rejected Trade

```
Cycle: TSLAUSDT
  timestamp:    2026-09-12T04:15:00Z
  Hypothesis:   volatility_breakout — ATR expansion signals directional move
  Validation:   Sharpe 0.31 (walk-forward, 90-day window)
  Decision:     BUY @ $357.99, qty 1
  Gates:        FAILED — max_position: positions 3 >= 3
  orderStatus:  rejected (risk gate veto)
  Result:       No position opened. Agent waiting for next cycle.
```

### Sample Cycle — No Trade

```
Cycle: NVDAUSDT
  timestamp:    2026-09-12T04:30:00Z
  Hypothesis:   None — LLM found no factor with sufficient evidence
  Decision:     NO TRADE
  Result:       Agent chose not to trade. Factors did not align.
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Market Event                          │
│  rToken SPOT data: RAAPLUSDT, RNVDAUSDT, RTSLAUSDT ...  │
│         (24/7 price data from Bitget SPOT API)           │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│              LLM Factor Proposer                         │
│    Claude Sonnet 4.6 proposes from fixed vocabulary:     │
│    momentum · mean_reversion · volatility_breakout       │
│    volume_spike · ema_crossover                          │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│           Deterministic Validation                       │
│    Walk-forward backtest on historical data               │
│    Sharpe · Sortino · drawdown · win rate · turnover     │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│              LLM Trade Decision                          │
│    Selects strongest validated hypothesis                 │
│    Outputs: instrument, side, price, quantity, rationale │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│              Risk Gate Layer (14 gates)                   │
│    balance_check ✓  max_position ✓  exposure_cap ✓       │
│    cooldown ✓  concentration ✓  pending_order_check ✓    │
│    daily_loss_cap ✓  data_freshness ✓  max_notional ✓    │
│    max_quantity ✓  duplicate ✓  validation ✓  ...         │
└─────────────┬──────────────────────┬────────────────────┘
              │ ALL PASS             │ ANY FAIL
              ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│   Bitget Demo API    │  │   Order Rejected             │
│   Stock perp order   │  │   Log gate + reason          │
│   AAPLUSDT (FUTURES) │  │   "positions 3 >= 3"         │
│   --paper-trading    │  │                              │
└─────────┬────────────┘  └──────────────────────────────┘
          ▼
┌──────────────────────┐
│   Verify Order       │
│   Query orderStatus  │
│   filled/cancelled?  │
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│   Audit Log (JSONL)  │
│   + Evidence Report  │
└──────────────────────┘
```

---

## Track Alignment

How FactorAtlas maps to [Bitget AI Genesis S2 — Agentic Trading](https://www.bitget.com/ai-genesis) judging criteria:

| Criterion | How FactorAtlas addresses it |
|-----------|------------------------------|
| **Paper trading metrics** (Sharpe, drawdown, win rate) | Observed from Demo execution: Sharpe 3.46, drawdown $7.11, win rate 66.7% |
| **Decision explainability** | Every cycle logs: market data → hypothesis → validation scores → LLM rationale → gate results → order outcome |
| **Agent architecture quality** | Typed Python modules, 312 tests, mypy clean; LLM bounded by factor vocabulary and risk gates |
| **Risk control layer** | 14 deterministic gates; LLM cannot bypass; exchange-verified balances and positions |
| **Autonomous loop** | `observe → propose → validate → decide → gate → execute → verify → log` — no human approval pause |
| **Complete event→decision→execution flow** | Full JSONL audit trail with `timestamp`, `orderId`, `orderStatus`, instrument, side, price, quantity |

---

## Quickstart

```bash
# Install
uv sync

# Fixture mode — no credentials needed, deterministic
uv run python -m factor_atlas run --mode fixture --cycles 2

# Demo mode — requires Bitget Demo API + AWS Bedrock credentials
uv run python -m factor_atlas run --mode demo --cycles 4

# Generate evidence report from a run
uv run python -m factor_atlas report --run-dir artifacts/paper-trading/<run-id>

# Check system status
uv run python -m factor_atlas status

# View trade history
uv run python -m factor_atlas history

# Run tests
uv run pytest
```

### Environment Variables (Demo mode)

```bash
BITGET_API_KEY=...
BITGET_SECRET_KEY=...
BITGET_PASSPHRASE=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
```

---

## Evidence Files

Each run produces:

```
artifacts/paper-trading/<run-id>/
  paper_log.jsonl       # Every order: instrument, side, price, qty, gates, orderStatus
  audit_log.jsonl       # Full event chain: observe → propose → evaluate → decide → gate → execute
  manifest.json         # Run metadata: timestamp, LLM model, metrics, config hash
  evidence_report.html  # Visual report for judges (open in browser)
```

Committed evidence: [`docs/evidence/`](docs/evidence/)

---

## Risk Controls

The agent cannot bypass risk gates. If any gate fails, the trade is rejected — the LLM has no override.

| Gate | What it checks | Threshold |
|------|---------------|-----------|
| `max_position` | Open positions count | < 3 |
| `balance_check` | Sufficient balance on exchange | ≥ order notional |
| `exposure_cap` | Total open exposure | < $50,000 |
| `max_notional` | Single order size | < $10,000 |
| `max_quantity` | Order quantity | < 1,000,000 |
| `concentration_guard` | Positions per instrument | < 2 |
| `cooldown` | Time between orders (same instrument) | ≥ 300s |
| `daily_loss_cap` | Realized daily loss | < $2,000 |
| `data_freshness` | Market data age | < 24h |
| `pending_order_check` | No conflicting pending orders | 0 pending |
| `duplicate_suppression` | No duplicate event processing | unique |
| `validation_threshold` | Hypothesis must pass walk-forward | passed |
| `min_sample_size` | Sufficient observations | ≥ 20 |
| `factor_allowlist` | Factor in approved vocabulary | in set |

---

## Factor Vocabulary

| Factor | Description |
|--------|------------|
| `momentum` | Price trend continuation based on lookback returns |
| `mean_reversion` | Price deviation from moving average, expect revert |
| `volatility_breakout` | ATR expansion signals directional move |
| `volume_spike` | Abnormal volume indicates institutional activity |
| `ema_crossover` | Short/long EMA crossover signals trend change |

The LLM can only propose from this fixed set. It cannot invent factors or generate arbitrary code.

---

## Safety

- **No live trading.** Every order uses `--paper-trading`. The agent cannot access live funds.
- **No withdrawals.** Withdrawal API is not implemented or exposed.
- **No credentials in code.** API keys loaded from environment variables only.
- **Risk gates are authoritative.** The LLM proposes; gates decide. A veto is final.
- **Append-only audit.** Every decision is logged and cannot be edited retroactively.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11 (`uv` managed) |
| LLM | Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6` via AWS Bedrock) |
| Exchange | Bitget Demo API via `bgc` CLI (`--paper-trading`) |
| Research layer | rToken SPOT: `RAAPLUSDT`, `RNVDAUSDT`, `RTSLAUSDT`, `RMETAUSDT` (24/7 market data) |
| Execution layer | USDT-FUTURES stock perps: `AAPLUSDT`, `NVDAUSDT`, `TSLAUSDT`, `METAUSDT` (Demo orders) |
| Symbol mapping | `RAAPLUSDT` → `AAPLUSDT`, `RNVDAUSDT` → `NVDAUSDT`, etc. (auto-reconciled) |
| Tests | 312 passing (`pytest`), `mypy` clean, `ruff` clean |

---

## LLM Disclosure

- **Model**: Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) via AWS Bedrock
- **Role**: Proposes factor hypotheses and selects trades from validated candidates
- **Bounded**: Fixed factor vocabulary, deterministic validation, 14 risk gates
- **Cannot**: Generate code, bypass gates, invent data, place orders directly, access live funds
- **Fixture mode**: Fully deterministic, no LLM — for reproducible demos without credentials

---

## License

Competition submission — Bitget AI Genesis Season 2.
