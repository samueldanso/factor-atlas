# FactorAtlas

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-326%20passing-brightgreen.svg)](tests/)
[![Bitget Demo](https://img.shields.io/badge/Bitget-Demo%20Paper%20Trading-00C087.svg)](https://www.bitget.com/)
[![LLM](https://img.shields.io/badge/LLM-Qwen%203.8%20Max-blueviolet.svg)](https://hackathon.bitgetops.com/v1)
[![Track](https://img.shields.io/badge/Track%202-Agentic%20Trading-orange.svg)](#track-alignment)

**Bitget AI Genesis Season 2 — Track 2: Agentic Trading → Factor Discovery Agent**

Autonomous agent that discovers market factors on Bitget **rToken** US stocks, validates trading hypotheses, and executes paper trades on **stock perpetuals** via Bitget Demo — with no human in the loop.

> **Judges — start here:**
> - [Live Dashboard](https://samueldanso.github.io/factor-atlas/) — stats, pipeline, agent timeline, trade history, risk control
> - [Evidence Logs](https://samueldanso.github.io/factor-atlas/logs/) — raw JSONL: events, decisions, risk, trades
> - [Previous Evidence Report](https://htmlpreview.github.io/?https://github.com/samueldanso/factor-atlas/blob/main/docs/evidence/evidence_report.html) — visual proof of full cycle (pre-upgrade)
> - [Submission Form](docs/SUBMISSION.md) — all form answers ready to paste
> - [Run It Yourself](#quickstart) — `uv sync && uv run python -m factor_atlas run --mode fixture --cycles 2`

---

## How It Works — Event → Decision → Execution

> *"How does the Agent autonomously propose hypotheses, discover alpha factors, and translate into tradable decisions?"*

The agent runs an autonomous cycle every 4 hours. Each cycle scans 4 US stock rTokens and proceeds through 8 stages with no human intervention:

```
OBSERVE → PROPOSE → VALIDATE → DECIDE → GATE → EXECUTE → VERIFY → LOG
```

### 1. Observe (Event)

The agent fetches 90 daily candles for each rToken instrument (`RAAPLUSDT`, `RNVDAUSDT`, `RTSLAUSDT`, `RMETAUSDT`) from Bitget's SPOT API. This is the raw market event — 24/7 price data for US stocks (Apple, NVIDIA, Tesla, Meta).

**Evidence:** `events.jsonl` — every observation with instrument, price, timestamp, data source.

### 2. Propose (Hypothesis)

Qwen 3.8 Max (via Bitget's hackathon endpoint) receives the latest market snapshot and proposes up to 5 factor hypotheses from a **fixed vocabulary**:

| Factor | What it detects |
|--------|----------------|
| `momentum` | Price trend continuation over lookback period |
| `mean_reversion` | Price deviation from rolling mean, expect revert |
| `volatility_breakout` | Bollinger Band expansion signals directional move |
| `volume_spike` | Abnormal volume indicates institutional activity |
| `ema_crossover` | Fast/slow EMA crossover signals trend change |

The LLM proposes specific parameters (lookback, thresholds), direction (long/short), and a written rationale. It cannot invent new factors or generate code.

**Evidence:** `events.jsonl` — each hypothesis with factor name, parameters, direction, LLM rationale.

### 3. Validate (Backtest)

Each hypothesis is tested with a **deterministic walk-forward backtest** on the 90-day OHLCV data:
- 70% train / 30% test split
- Leakage detection (train/test overlap check)
- Computes: Sharpe ratio, Sortino ratio, max drawdown, win rate, turnover
- Applies simulated fees (0.1%) and slippage (5 bps)
- Pass criteria: Sharpe >= 0.5, drawdown > -20%, minimum 20 observations

Failed hypotheses are rejected with specific reasons. The LLM cannot override validation.

**Evidence:** `events.jsonl` — validation results (Sharpe, drawdown, passed/failed, observations) attached to each hypothesis.

### 4. Decide (LLM Selection)

The LLM reviews all validated (passed) candidates and selects the best one — or explicitly declines to trade. It outputs:
- Which hypothesis to trade (by index)
- Written rationale explaining why

If no hypothesis passed validation, the agent decides **not to trade** and logs the reason.

**Evidence:** `decisions.jsonl` — selected hypothesis, side, quantity, price, full LLM rationale (or decline reason).

### 5. Gate (Risk Control)

The selected trade must pass **all 14 deterministic risk gates**. The LLM has no influence over gates — a single failure vetoes the trade:

| Gate | Checks | Threshold |
|------|--------|-----------|
| `factor_allowlist` | Factor in approved vocabulary | in set |
| `data_freshness` | Market data age | < 24h |
| `min_sample_size` | Sufficient backtest observations | >= 20 |
| `validation_threshold` | Hypothesis passed walk-forward | passed |
| `max_notional` | Single order size | < $10,000 |
| `max_position` | Open positions count | < 3 |
| `exposure_cap` | Total open exposure | < $50,000 |
| `cooldown` | Time between orders (same instrument) | >= 300s |
| `daily_loss_cap` | Realized daily loss | < $2,000 |
| `duplicate_suppression` | No duplicate event processing | unique |
| `concentration_guard` | Positions per instrument | < 2 |
| `max_quantity` | Order quantity | < 1,000,000 |
| `balance_check` | Sufficient exchange balance | >= notional |
| `pending_order_check` | No conflicting pending orders | 0 pending |

**Evidence:** `risk.jsonl` — all 14 gate verdicts per decision, with pass/fail, reason, value, threshold.

### 6. Execute (Paper Trade)

If all gates pass, the agent places a **limit order** on the corresponding stock perpetual via Bitget Demo API (`--paper-trading`):
- Research symbol `RAAPLUSDT` maps to execution symbol `AAPLUSDT`
- Position size is **ATR-based**: `quantity = max_risk / (SL_ATR_MULT * ATR)`, capped by notional limits
- Stop-loss and take-profit are volatility-aware: SL = 3x ATR, TP = 6x ATR (2:1 reward/risk)
- Orders rounded to Bitget's precision (price: 0.01, quantity: integer)

### 7. Verify

The agent queries Bitget Demo for the actual order status (`filled`, `cancelled`, `rejected`) and logs the exchange-confirmed result.

### 8. Log

Every stage is logged to structured, append-only evidence files:

**Evidence:** `trades.jsonl` — entry/exit orders with Bitget `orderId`, `orderStatus`, side, price, size, PnL.

---

## Evidence Structure

The agent produces structured evidence that judges can trace end-to-end:

```
artifacts/paper-trading/
├── logs/                              # Append-only evidence (continuous timeline)
│   ├── agent.log                      # Human-readable timeline — read this first
│   ├── events.jsonl                   # Observe + hypothesis + validation
│   ├── decisions.jsonl                # LLM selection + rationale
│   ├── risk.jsonl                     # 14 gate verdicts per decision
│   └── trades.jsonl                   # Entry/exit orders + PnL + Bitget orderIds
├── positions_state.json               # Current open positions
└── runs/                              # Per-run snapshots
    └── <run-id>/
        ├── manifest.json              # Run summary + aggregate metrics
        └── report.html                # Visual evidence report
```

Every record carries `run_id` + `cycle_id` + `timestamp` — trace any trade across all 4 log files.

Evidence logs: [GitHub Pages](https://samueldanso.github.io/factor-atlas/logs/) · [`artifacts/paper-trading/logs/`](artifacts/paper-trading/logs/)

---

## Autonomous Runner

The agent runs continuously on a 4-hour interval via GitHub Actions. Each round:

1. Fetches live rToken SPOT data for all 4 instruments
2. Evaluates exits on open positions (ATR-based SL/TP or max-hold 24h)
3. Runs the full propose → validate → decide → gate → execute cycle
4. Commits evidence back to the repository

```bash
# Run locally (single round)
uv run python -m factor_atlas run --mode demo --cycles 4

# Run continuously (every 4 hours)
uv run python -m factor_atlas run --mode demo --cycles 4 --continuous --interval 14400

# GitHub Actions: runs automatically every 4h, commits evidence to repo
```

---

## Two-Layer Instrument Architecture

| Layer | Symbols | Category | Purpose |
|-------|---------|----------|---------|
| **Research** (rToken SPOT) | `RAAPLUSDT` · `RNVDAUSDT` · `RTSLAUSDT` · `RMETAUSDT` | SPOT | 24/7 market data, factor analysis, hypothesis validation |
| **Execution** (Stock Perps) | `AAPLUSDT` · `NVDAUSDT` · `TSLAUSDT` · `METAUSDT` | USDT-FUTURES | Demo paper trading, order placement, fill verification |

rTokens provide 24/7 price data for US stocks — ideal for continuous factor research. Execution routes through USDT-margined stock perpetual contracts (rToken SPOT orders not available in Demo). The agent maps `RAAPLUSDT` → `AAPLUSDT` automatically.

---

## Track Alignment

How FactorAtlas maps to [Bitget AI Genesis S2 — Agentic Trading](https://www.bitget.com/ai-genesis) judging criteria:

| Criterion | How FactorAtlas addresses it |
|-----------|------------------------------|
| **Paper trading Sharpe, drawdown, win rate** | Observed from Demo execution, accumulating daily via automated runner |
| **Decision explainability** | Every cycle: market data → LLM hypothesis + rationale → validation scores → LLM selection rationale → 14 gate verdicts → order outcome. All in structured JSONL. |
| **Agent architecture quality** | Typed Python, 326 tests, mypy clean; LLM bounded by factor vocabulary and risk gates; ATR-based sizing; structured evidence logging |
| **Risk control layer effectiveness** | 14 deterministic gates; LLM cannot bypass; exchange-verified balances/positions; ATR-based stop-loss/take-profit |
| **Autonomous loop** | Runs every 4h via GitHub Actions; `observe → propose → validate → decide → gate → execute → verify → log` — no human approval |
| **Event → decision → execution flow** | 4 structured log files: `events.jsonl` → `decisions.jsonl` → `risk.jsonl` → `trades.jsonl`, linked by `run_id` + `cycle_id` |

---

## Quickstart

```bash
# Install
uv sync

# Fixture mode — no credentials needed, deterministic
uv run python -m factor_atlas run --mode fixture --cycles 2

# Demo mode — requires Bitget Demo API + Qwen API key
uv run python -m factor_atlas run --mode demo --cycles 4

# Continuous mode — autonomous runner
uv run python -m factor_atlas run --mode demo --cycles 4 --continuous --interval 14400

# Generate evidence report from a run
uv run python -m factor_atlas report --run-dir artifacts/paper-trading/runs/<run-id>

# Check system status
uv run python -m factor_atlas status

# Run tests
uv run pytest
```

### Environment Variables (Demo mode)

```bash
BITGET_API_KEY=...          # Bitget Demo API
BITGET_SECRET_KEY=...       # Bitget Demo API
BITGET_PASSPHRASE=...       # Bitget Demo API
BITGET_QWEN_API_KEY=...     # Qwen 3.8 Max (Bitget hackathon endpoint)
```

AWS Bedrock (Claude Sonnet 4.6) is supported as fallback if `BITGET_QWEN_API_KEY` is not set.

---

## Safety

- **No live trading.** Every order uses `--paper-trading`. The agent cannot access live funds.
- **No withdrawals.** Withdrawal API is not implemented or exposed.
- **No credentials in code.** API keys loaded from environment variables only.
- **Risk gates are authoritative.** The LLM proposes; gates decide. A veto is final.
- **Append-only evidence.** Every decision is logged to structured JSONL and cannot be edited retroactively.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11 (`uv` managed) |
| LLM (primary) | Qwen 3.8 Max via Bitget hackathon endpoint (`hackathon.bitgetops.com/v1`) |
| LLM (fallback) | Claude Sonnet 4.6 via AWS Bedrock |
| Exchange | Bitget Demo API via `bgc` CLI (`--paper-trading`) |
| Position sizing | ATR-based: `max_risk / (SL_ATR_MULT * ATR)`, capped by notional limits |
| Exit management | ATR-based SL (3x ATR) / TP (6x ATR) / max-hold (24h) |
| Scheduling | GitHub Actions cron (every 4h) + `--continuous` CLI mode |
| Evidence | 4 structured JSONL files + human-readable `agent.log` |
| Research layer | rToken SPOT: `RAAPLUSDT`, `RNVDAUSDT`, `RTSLAUSDT`, `RMETAUSDT` |
| Execution layer | USDT-FUTURES perps: `AAPLUSDT`, `NVDAUSDT`, `TSLAUSDT`, `METAUSDT` |
| Tests | 326 passing (`pytest`), `mypy` clean, `ruff` clean |

---

## LLM Disclosure

- **Primary model**: Qwen 3.8 Max via Bitget hackathon endpoint (`hackathon.bitgetops.com/v1`)
- **Fallback model**: Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) via AWS Bedrock
- **Role**: Proposes factor hypotheses and selects trades from validated candidates
- **Bounded**: Fixed factor vocabulary, deterministic validation, 14 risk gates
- **Cannot**: Generate code, bypass gates, invent data, place orders directly, access live funds
- **Fixture mode**: Fully deterministic, no LLM — for reproducible demos without credentials

---

## License

Competition submission — Bitget AI Genesis Season 2.
