# FactorAtlas Agent Contract

Read this file before changing code. `CLAUDE.md` points here, and OpenCode/Codex agents should treat this file as the project-level operating contract.

## Mission

FactorAtlas is a Bitget AI Genesis Season 2 submission for **Agentic Trading → Factor Discovery Agent**, deadline **2026-09-21 UTC+8**.

Build an agent that proposes factor hypotheses for continuously traded tokenized US-stock markets, validates them with deterministic Python research code, applies explicit risk gates, and records a complete paper-trading event → decision → execution trace.

The differentiator is not an LLM chat wrapper. It is a reproducible factor-discovery and execution loop whose decisions can be inspected, replayed, and rejected by risk controls.

## Source of truth

1. This file: persistent rules, safety, tooling, and handoff contract.
2. `docs/ideas/PRD.md`: product thesis and competition context.
3. `docs/specs/`: approved technical behavior and interfaces.
4. `docs/plans/`: ordered implementation work.
5. Source code and tests.
6. `resources/`: external reference material only.

If these conflict, stop and report the conflict. Do not silently choose.

## Required reading

- `docs/ideas/PRD.md`
- `docs/SETUP_CHECKLIST.md`
- the current document in `docs/specs/`
- the current document in `docs/plans/`
- `resources/agent_hub/docs/architecture.md`
- `resources/agent_hub/docs/getting-started.md`
- relevant files under `resources/helios-terminal/` only as reference

Never edit, vendor, or import code directly from `resources/`. It is git-ignored research material.

## Commands and stack

Python 3.11 is managed by `uv`. Use `uv add` for dependencies; never use global pip for project dependencies.

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy .
```

Smoke checks:

```bash
bgc --version
bgc discover
bgc discover --tool market
```

Do not claim authenticated Bitget access until a real command succeeds. Public calls can fail because of network/API availability; record the exact failure and use fixtures or cached data rather than inventing data.

## Bitget tools and skills

These are installed for Codex, Claude Code, and OpenCode:

- `bgc`: Bitget Agent CLI for market, account, and trading operations.
- `bitget`: Bitget trading skill; use it for any Bitget exchange/account/trading task.
- `macro-analyst`: macro and cross-asset context.
- `market-intel`: on-chain and institutional market context.
- `news-briefing`: news aggregation and narrative synthesis.
- `sentiment-analyst`: sentiment, positioning, funding, and Fear & Greed context.
- `technical-analysis`: indicator and chart analysis.
- `bitget-signal`: public research MCP; no account or API key is required.

Use Signal skills/MCP for perception and research, never as the sole source of executable order truth. Use `bgc discover` before non-trivial calls. Never guess parameters.

The layers are separate:

- CLI: `bgc`, used by terminal agents and scripts.
- Skills: instructions for using CLI and research tools.
- MCP: tools exposed to an MCP host. `bitget-signal` is public research; Agentic trading MCP is separate and must not be assumed configured.
- Agentic account: optional isolated Bitget account for agent execution; not a wallet.
- Playbook: supporting strategy/backtesting product, not a replacement for this repository.

## Credentials and execution safety

- No live trading.
- Every `bgc` order call must use `--paper-trading`.
- Use `--read-only` for inspection and `--dry-run` before writes.
- Never enable withdrawals.
- Never ask the user to paste credentials into chat.
- Credentials may exist only in the user’s local environment or approved secret store, never Git, `resources/`, screenshots, logs, or fixtures.
- Do not use the existing Season 1 `GetAgent - Playbook` key; its environment is unconfirmed.
- A separate Demo API key is optional for authenticated paper-trading verification. An Agentic account is optional for a final autonomous-execution demo.
- Playbook login/key/subaccount is not required for FactorAtlas. Use Playbook for Alpha Factory research only; do not use a Playbook credential as a substitute for Agentic paper-execution evidence.
- The competition-period paper runner must write actual run records under `artifacts/paper-trading/`. Never manufacture or backfill competition-period history from fixtures.

Expected local variable names:

```text
BITGET_API_KEY
BITGET_SECRET_KEY
BITGET_PASSPHRASE
```

## Architecture contract

### LLM layer

The LLM is the agent’s research-orchestration and decision layer. It may propose bounded hypotheses, select deterministic research routines, summarize iterative factor-mining results, and choose a trade only from validated candidates. It may not generate arbitrary runtime trading code, bypass risk gates, invent data or metrics, place live orders, or turn failed validation into a recommendation.

### Mandatory autonomous cycle

The Agentic Trading submission must demonstrate an unattended paper-trading loop:

`observe event → propose hypotheses → mine/evaluate factors → iterate/backtest → select validated candidate → risk gate → automatic paper execution → audit/next cycle`

There must be no human approval pause between a validated decision and paper execution. Deterministic validation, sizing, risk gates, and the paper broker remain authoritative; a gate veto prevents execution. The demo must include both an accepted cycle and a rejected cycle.

### Deterministic research layer

Implement typed, testable modules for rToken market-data ingestion/caching, a constrained factor library, walk-forward validation, fees/slippage/turnover/drawdown, risk gates, and experiment metadata.

### Execution and audit layer

The simulator must produce an append-only trace containing event timestamp/source, market snapshot ID, factor ID, decision/rationale, risk-gate results, instrument/direction/price/quantity, simulated balance change, and execution/rejection result. It must work without credentials; Demo Bitget is an optional adapter.

## Helios reference boundary

`resources/helios-terminal/` is a prior Python autopilot reference. Adapt only its useful patterns: typed config, polling/heartbeat loops, layered guardrails, append-only event logs, and explicit position/daily limits. Do not copy its exchange assumptions or autonomous behavior without documenting a decision in the spec.

## Competition evidence

The final project must demonstrate a runnable demo, complete event → decision → execution flow, paper logs with timestamps/instrument/direction/price/quantity/balance change, public code/README, honest LLM/model disclosure, a short demo video, and a compliant X post. Label every metric observed, estimated, or targeted.

## Boundaries

Always: update the spec before architecture changes; add tests with deterministic behavior; use typed schemas; run Ruff, type checks, and tests before reporting completion.

Ask first: before adding dependencies, changing submission interfaces, enabling authenticated/external writes, or resolving missing/conflicting requirements.

Never: commit credentials; edit `resources/` as implementation; use live trading; suppress type errors; delete failing tests.

## Handoff contract

Before implementing a task, OpenCode must state the spec section, files, acceptance criteria, tests, external-data assumptions, and whether Bitget access is read-only, Demo paper-trading, or unused. Stop at unresolved product/API ambiguity. After implementation, run verification commands and report exact results.
