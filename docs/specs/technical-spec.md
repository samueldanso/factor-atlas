# FactorAtlas Technical Specification

## Objective

Build a runnable Factor Discovery Agent for Bitget’s Agentic Trading track. Given a market/event snapshot, the system proposes a constrained factor hypothesis, evaluates it through deterministic research code, applies risk gates, and records a paper-trading decision. The LLM explains and ranks hypotheses; it never emits arbitrary executable trading code.

## Competition contract

- Track: Agentic Trading
- Sub-theme: Factor Discovery Agent
- Required demonstration: runnable demo with event → decision → execution flow
- Evidence: paper-trading log with timestamp, instrument, direction, price, quantity, and balance change
- Execution mode: deterministic simulator first; Bitget Demo adapter optional

## Proposed stack

- Python 3.11
- `uv` for environments and lockfile
- `pydantic` for contracts
- `pandas`/`numpy` for deterministic research
- `httpx` for controlled data adapters
- `pytest` for tests
- `ruff` for lint/format
- `bgc` for Bitget discovery and optional Demo access
- `bitget-signal` skills/MCP for research context only

Do not add an LLM framework until the agent boundary is clear. A small provider interface is preferred over coupling the core research engine to one framework.

## System boundaries

```text
market/event inputs
        ↓
normalizer + snapshot manifest
        ↓
constrained hypothesis proposer (LLM or fixture)
        ↓
deterministic factor registry + validator
        ↓
risk gates
        ↓
paper executor
        ↓
append-only audit log + demo output
```

The deterministic path must run with a fixture and no credentials. Every external adapter must be replaceable by a fixture provider.

## Core contracts

### Factor hypothesis

Must include: stable ID, factor name, formula/configuration, lookback, target instrument universe, direction, entry/exit rule, rationale, and creation timestamp. Reject unknown factor names and out-of-range parameters.

### Validation result

Must include: input snapshot ID, train/test windows, observations, return, Sharpe, Sortino, drawdown, turnover, fees, slippage, and rejection reasons. Metrics must identify whether they are observed, estimated, or targeted.

### Paper order

Must include: event ID, decision ID, timestamp, instrument, side, price, quantity, notional, pre/post balance, simulated fees, simulated slippage, and status.

### Audit event

Use append-only JSON Lines. Every record references the previous stage by ID so a reviewer can replay event → hypothesis → validation → gate → execution.

## Risk gates

Minimum gates: factor allowlist, data freshness, minimum sample size, validation threshold, maximum notional, maximum position, exposure cap, cooldown, daily loss cap, duplicate-event suppression, and correlation/concentration guard. A rejected decision must be logged, not silently discarded.

## Testing strategy

- Unit tests for schemas, factor calculations, metrics, and every gate.
- Fixture tests for the complete event-to-paper-order flow.
- Property-style checks for no negative balances and bounded quantities.
- Replay test: identical fixture and config produce identical audit output.
- Adapter tests must mock network responses; no test may require live credentials.

## Acceptance criteria

1. A clean checkout can run the simulator with `uv sync` and `uv run pytest`.
2. A fixture event produces a complete trace and either a valid paper order or a logged rejection.
3. The LLM cannot introduce a factor outside the registry or bypass a gate.
4. No live order path exists in the MVP.
5. The demo clearly shows the event, proposed factor, validation, risk decision, and simulated execution.

## Open questions

- Exact Bitget rToken symbols and history availability must be confirmed before implementing the adapter.
- Final LLM provider/model must be selected and recorded only after the coding agent verifies available credentials and SDK behavior.
- Whether to add a Bitget Demo adapter depends on API access and time; the simulator is mandatory regardless.

## Sources

- Local official reference: `resources/agent_hub/docs/architecture.md`
- Local official reference: `resources/agent_hub/docs/getting-started.md`
- Bitget Agent Hub: https://www.bitget.com/activity-hub/agent-hub
- Bitget Demo API: https://www.bitget.com/docs/classic/demo-trading/rest-api
