# FactorAtlas — Autonomous Factor Discovery Agent

**Bitget AI Genesis Season 2 — Track 2: Agentic Trading**

FactorAtlas is an autonomous trading agent that discovers market factors, validates trading hypotheses, and executes paper trades on Bitget Demo — with no human in the loop.

## What It Does

Every cycle, the agent:

1. **Observes** — pulls live price data for US stock perpetuals (AAPL, NVDA, TSLA, META)
2. **Proposes** — Claude Sonnet (AWS Bedrock) analyzes the data and proposes factor hypotheses (e.g. "AAPL shows mean reversion — price dropped 2% below 20-day EMA, expect bounce")
3. **Validates** — runs walk-forward backtest on historical data, computes Sharpe ratio, drawdown, win rate
4. **Decides** — LLM selects the strongest validated hypothesis and proposes a trade (direction, price, size)
5. **Risk checks** — 14 gates verify: position limits, balance, exposure, cooldowns, concentration, pending orders
6. **Executes** — if all gates pass, places a limit order on Bitget Demo via `bgc --paper-trading`
7. **Verifies** — queries Bitget Demo for the actual order status (filled, rejected, cancelled)
8. **Records** — logs the full trace: event, hypothesis, factors, decision rationale, gate results, order outcome

If the factors don't support a trade, the agent explicitly decides **not to trade** and logs why. A no-trade decision is evidence of discipline, not a failure.

## Evidence

### Paper Trading Results

| Metric | Value |
|--------|-------|
| Total trades | 3 |
| Win rate | 66.7% |
| Sharpe ratio | 3.46 |
| Sortino ratio | 4.79 |
| Max drawdown | 7.11 |

### Sample Cycle — Accepted Trade

```
Cycle: AAPLUSDT
  Event:      Live SPOT candle data (90 days, 1D interval)
  Hypothesis: "mean_reversion — price below EMA, expect bounce"
  Validation: Sharpe 0.42 (walk-forward, 90-day window)
  Decision:   BUY @ $330.77, qty 1
  Gates:      14/14 passed (positions 0 < 3, balance OK, exposure OK)
  Execution:  Bitget Demo order 1483324512122851328 — filled
  Result:     Position opened, balance updated
```

### Sample Cycle — Rejected Trade

```
Cycle: TSLAUSDT
  Event:      Live SPOT candle data (90 days, 1D interval)
  Hypothesis: "volatility_breakout — ATR expansion signals directional move"
  Validation: Sharpe 0.31 (walk-forward, 90-day window)
  Decision:   BUY @ $357.99, qty 1
  Gates:      FAILED — max_position: positions 3 >= 3
  Execution:  Order rejected by risk gate
  Result:     No position opened. Agent waiting for next cycle.
```

### Sample Cycle — No Trade

```
Cycle: NVDAUSDT
  Event:      Live SPOT candle data (90 days, 1D interval)
  Hypothesis: None — LLM found no factor with sufficient evidence
  Decision:   NO TRADE
  Result:     Agent chose not to trade. Factors did not align strongly enough.
```

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    Market Event                          │
│         (live price data from Bitget SPOT API)           │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│              LLM Factor Proposer                         │
│    Claude Sonnet analyzes data, proposes hypotheses      │
│    "momentum", "mean_reversion", "volatility_breakout"   │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│           Deterministic Validation                       │
│    Walk-forward backtest on historical data               │
│    Sharpe, Sortino, drawdown, win rate, turnover          │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│              LLM Trade Decision                          │
│    Selects strongest validated hypothesis                 │
│    Chooses: long, short, or NO TRADE                     │
└─────────────┬───────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────┐
│              Risk Gate Layer (14 gates)                   │
│    Balance ✓  Positions ✓  Exposure ✓  Cooldown ✓        │
│    Concentration ✓  Pending orders ✓  Daily loss ✓       │
│    Data freshness ✓  Notional ✓  Quantity ✓  ...         │
└─────────────┬──────────────────────┬────────────────────┘
              │ ALL PASS             │ ANY FAIL
              ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│   Bitget Demo API    │  │   Order Rejected             │
│   Place limit order  │  │   Log reason: "positions     │
│   --paper-trading    │  │   3 >= 3" (max_position)     │
└─────────┬────────────┘  └──────────────────────────────┘
          ▼
┌──────────────────────┐
│   Verify Order       │
│   Query order status │
│   filled/rejected?   │
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│   Audit Log          │
│   Full trace in JSONL│
│   + Evidence Report  │
└──────────────────────┘
```

## Run It Yourself

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
```

## Evidence Files

Each run produces:

```
artifacts/paper-trading/<run-id>/
  paper_log.jsonl       # Every order: instrument, side, price, qty, gates, status
  audit_log.jsonl       # Full event chain: observe → propose → evaluate → decide → gate → execute
  manifest.json         # Run metadata: timestamps, LLM model, performance metrics, config hash
  evidence_report.html  # Visual report for judges (open in browser)
```

## Risk Controls

The agent cannot bypass risk gates. If any gate fails, the trade is rejected — the LLM has no override.

| Gate | What it checks |
|------|---------------|
| max_position | Open positions < 3 |
| balance_check | Sufficient balance on exchange |
| exposure_cap | Total exposure < $50,000 |
| max_notional | Single order < $10,000 |
| max_quantity | Order size < 100 |
| concentration | Max 1 position per instrument |
| cooldown | 60s between orders on same instrument |
| daily_loss | Daily loss < $1,000 |
| data_freshness | Market data < 24h old |
| pending_orders | No conflicting pending orders |
| duplicate | No duplicate event processing |
| validation | Hypothesis must pass walk-forward validation |
| min_samples | Sufficient data for statistical significance |

## Safety

- **No live trading.** Every order uses `--paper-trading`. The agent cannot access live funds.
- **No withdrawals.** Withdrawal API is not implemented or exposed.
- **No credentials in code.** API keys loaded from environment variables only.
- **Risk gates are authoritative.** The LLM proposes; gates decide. A veto is final.
- **Append-only audit.** Every decision is logged and cannot be edited retroactively.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11 |
| LLM | Claude Sonnet 4.6 (AWS Bedrock) |
| Exchange | Bitget Demo API via `bgc` CLI |
| Factors | momentum, mean_reversion, volatility_breakout, volume_spike, ema_crossover |
| Instruments | AAPL, NVDA, TSLA, META (USDT-margined stock perpetuals) |
| Risk | 14 deterministic gates, exchange-verified |
| Tests | 307 passing (pytest), mypy clean, ruff clean |

## LLM Disclosure

- **Decision maker**: Claude Sonnet 4.6 via AWS Bedrock — proposes hypotheses and selects trades
- **Bounded**: LLM can only propose from a fixed factor vocabulary and select from validated candidates
- **Cannot**: generate code, bypass gates, invent data, place orders directly, or access live funds
- **Fixture mode**: fully deterministic, no LLM used — for reproducible demos without credentials

## License

Competition submission — Bitget AI Genesis Season 2.
