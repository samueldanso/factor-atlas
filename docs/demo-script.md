# FactorAtlas Demo Script

Step-by-step script for recording a ~3-minute demo video showing the FactorAtlas factor discovery agent.

## Setup (before recording)

1. Clean terminal, dark theme, readable font size (14pt+).
2. Ensure `uv sync` has been run.
3. Clear any previous test runs: the demo creates fresh output.

## Recording script

### Part 1: Introduction (30 seconds)

**Show the terminal. Type or narrate:**

> "FactorAtlas is a factor discovery agent for Bitget's Agentic Trading track. It autonomously proposes factor hypotheses, validates them with deterministic research code, applies risk gates, and executes paper trades — all without human intervention."

### Part 2: Configuration check (30 seconds)

```bash
uv run python -m factor_atlas run --dry-run
```

**Narrate the output:**

> "The dry-run validates the configuration. We see the factor vocabulary — momentum, mean reversion, volatility breakout, volume spike, EMA crossover. The research instruments are rToken SPOT pairs, and execution uses USDT-margined stock perpetuals. Six risk gates enforce notional limits, exposure caps, and daily loss limits."

### Part 3: Run the autonomous loop (60 seconds)

```bash
uv run python -m factor_atlas run --mode fixture --cycles 2
```

**Narrate while it runs:**

> "Now we run the full autonomous loop in fixture mode — deterministic, no API keys needed. Two cycles will execute."

**After it completes, highlight the output:**

> "Cycle 1 was accepted: a momentum factor on AAPL passed walk-forward validation with a Sharpe above 0.5 and cleared all six risk gates. The paper broker executed a buy order. Cycle 2 was rejected: a mean-reversion factor failed validation, so no order was placed. This demonstrates both the accept and reject paths."

### Part 4: Inspect the paper log (30 seconds)

```bash
# Show the accepted order
cat artifacts/paper-trading/*/paper_log.jsonl | python -m json.tool --json-lines | head -60
```

**Narrate key fields:**

> "Each paper log record contains the full execution trace: the instrument, direction, price, quantity, fees, pre- and post-balance, the factor name and validation Sharpe, and every risk gate result with pass/fail and reason."

### Part 5: Inspect the audit trail (30 seconds)

```bash
# Show audit events
cat artifacts/paper-trading/*/audit_log.jsonl | python -m json.tool --json-lines | head -40
```

**Narrate:**

> "The audit log records every stage of every cycle — observe, propose, evaluate, decide, gate, execute. Each event has a timestamp, stage, event type, and full payload. This is append-only and enables deterministic replay."

### Part 6: Show the manifest (15 seconds)

```bash
cat artifacts/paper-trading/*/manifest.json | python -m json.tool
```

**Narrate:**

> "The manifest records the run metadata: timestamps, cycle counts, config hash, git commit, and software version for full reproducibility."

### Part 7: Test suite (15 seconds)

```bash
uv run pytest tests/ -q
```

**Narrate:**

> "250 tests cover every module: contracts, factors, validation, risk gates, broker, orchestrator, audit, replay, CLI, and the LLM boundary. All pass."

## Key points to emphasize

1. **No human in the loop**: the agent runs observe → decide → execute autonomously.
2. **Both accept and reject**: the demo shows a successful trade and a risk-gated rejection.
3. **Deterministic**: fixture mode produces identical results every time, no LLM calls.
4. **Full audit trail**: every decision is logged with enough detail to replay.
5. **Safety**: paper-only execution, risk gates are authoritative, no credential exposure.
6. **Reproducible**: config hash + git commit pin the exact state.

## After recording

- Verify the video shows both accepted and rejected cycles clearly.
- Ensure no credentials or sensitive data appear on screen.
- Trim to ~3 minutes. The core demo (parts 2–6) should be under 2.5 minutes.
