# FactorAtlas PRD

## Thesis

Build an autonomous factor-discovery agent for 24/7 tokenized US-stock markets. The LLM proposes and explains hypotheses; deterministic code tests, risk-gates, and paper-executes them.

## Submission

- Track: Agentic Trading
- Sub-theme: Factor Discovery Agent
- Deadline: 2026-09-21

## MVP

1. Ingest supported rToken market data.
2. Generate factor hypotheses from a constrained factor library.
3. Run reproducible validation and risk checks.
4. Produce an event → decision → execution trace.
5. Record paper-trading logs with timestamps, instruments, decisions, quantities, and balances.

## Non-goals

- Live trading.
- Withdrawals or transfers.
- Unbounded LLM-generated trading code.
