# FactorAtlas

**Factor Discovery Agent** for Bitget AI Genesis Season 2 — Agentic Trading track.

An autonomous agent that proposes factor hypotheses for continuously traded Bitget US-stock markets, validates them with deterministic Python research code, applies explicit risk gates, and records a complete paper-trading event → decision → execution trace.

## Quick start

```bash
# Install dependencies
uv sync

# Validate configuration (no execution)
uv run python -m factor_atlas run --dry-run

# Run the full demo (deterministic fixture mode, 2 cycles)
uv run python -m factor_atlas run --mode fixture --cycles 2

# Run tests
uv run pytest
```

## Architecture

The autonomous loop runs without human approval between a validated decision and paper execution:

```
observe event
  → propose hypotheses (factor library)
    → mine / evaluate factors (walk-forward validation)
      → select validated candidate
        → risk gate (data freshness, notional, exposure, concentration, cooldown, daily loss)
          → paper execution (simulated broker)
            → audit log (append-only JSONL)
              → next cycle
```

### Modules

| Module | Purpose |
|--------|---------|
| `config` | Instruments (rToken research + stock perp execution), factor vocabulary, thresholds |
| `contracts` | Typed Pydantic schemas: `MarketSnapshot`, `FactorHypothesis`, `ValidationResult`, `TradeDecision`, `PaperOrder`, `AuditEvent` |
| `factors` | Deterministic factor library: momentum, mean reversion, volatility breakout, volume spike, EMA crossover |
| `validation` | Walk-forward validation with fees, slippage, turnover, and drawdown |
| `proposer` | Hypothesis generation (fixture or LLM-backed) |
| `decision` | Trade selection from validated candidates (fixture or LLM-backed) |
| `risk` | Six risk gates: data freshness, max notional, max exposure, concentration, cooldown, daily loss limit |
| `broker` | Paper broker: simulated fills with configurable fees and slippage |
| `orchestrator` | Cycle runner: wires observe → propose → evaluate → decide → gate → execute |
| `audit` | Append-only JSONL audit logger with stage-level events |
| `replay` | Deterministic replay from audit logs |
| `runner` | CLI paper-trading session: writes paper logs, audit trail, and manifest |
| `adapters` | rToken → stock perp instrument normalization; Bitget Demo adapter (optional) |
| `llm` | Provider-neutral LLM boundary: prompt construction, safety validation, fixture fallback |

### Instrument design

FactorAtlas uses two instrument layers:

- **Research**: rToken SPOT instruments (`RAAPLUSDT`, `RNVDAUSDT`, etc.) for 24/7 market data and factor evaluation.
- **Execution**: Stock perp instruments (`AAPLUSDT`, `NVDAUSDT`, etc.) for Bitget Demo USDT-margined futures paper orders.

The adapter layer normalizes research instruments to execution instruments transparently.

## CLI

```bash
# Dry run — validate config, print settings, exit
uv run python -m factor_atlas run --dry-run

# Fixture mode — deterministic, no credentials required
uv run python -m factor_atlas run --mode fixture --cycles 2

# Custom output directory
uv run python -m factor_atlas run --mode fixture --output ./my-run
```

## LLM / model disclosure

- **Fixture mode** (`--mode fixture`): fully deterministic, uses no LLM. Hypothesis proposals and trade decisions are produced by typed fixture providers. This is the default and the mode used for reproducible demos.
- **LLM adapter** (optional): a provider-neutral `LLMProvider` protocol in `factor_atlas.llm` supports plugging in any LLM (OpenAI, Anthropic, etc.) for hypothesis generation and decision selection. The LLM layer is bounded: it may propose hypotheses and select from validated candidates, but cannot generate runtime code, bypass risk gates, or invent data.
- **No LLM is called** unless explicitly configured. All competition evidence can be produced without any LLM API key.

## Competition evidence

Paper logs are written to `artifacts/paper-trading/<run-id>/`:

```
artifacts/paper-trading/<run-id>/
  paper_log.jsonl    # Order-level records: instrument, side, price, quantity, balance, status
  audit_log.jsonl    # Stage-level events: observe, propose, evaluate, decide, gate, execute
  manifest.json      # Run metadata: timestamps, cycle counts, config hash, git commit
```

Each paper log record includes:
- Event timestamp, instrument, category (`USDT-FUTURES`)
- Factor ID, hypothesis ID, validation Sharpe ratio
- Risk gate results (per-gate pass/fail with reasons)
- Direction, price, quantity, notional, fees, slippage
- Pre/post balance, fill status (accepted or rejection reason)
- Software version and config hash for reproducibility

## Safety

- **No live trading.** All execution uses the paper broker or Bitget Demo (`--paper-trading`).
- **No withdrawals.** The agent cannot enable or execute withdrawals.
- **No credentials in code.** API keys are loaded from environment variables only, never committed.
- **Risk gates are authoritative.** A gate veto prevents execution; the LLM cannot override.
- **Append-only audit.** Every decision is logged; logs cannot be edited retroactively.

## Development

```bash
# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Type check
uv run mypy src/ tests/

# Full test suite (250 tests)
uv run pytest tests/ -v
```

## License

Competition submission — not open-source licensed.
