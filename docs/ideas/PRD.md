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

## Research and platform decisions

- Agentic Trading is best demonstrated with Agent Hub Tools + MCP and, if authenticated execution is needed, an isolated Bitget Agentic account.
- The MVP must work without credentials through a deterministic paper broker.
- A Demo API key is optional for authenticated paper-trading verification; the existing Season 1 `GetAgent - Playbook` key is not assumed safe or reusable.
- `bitget-signal` research skills/MCP provide perception context but do not replace deterministic validation or risk gates.
- `resources/agent_hub/` is the local official reference. `resources/helios-terminal/` is an architectural reference only.

See `docs/specs/technical-spec.md` and `docs/plans/implementation-plan.md` for the implementation contract.
