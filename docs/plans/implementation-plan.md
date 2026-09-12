# FactorAtlas Implementation Plan

## Gate 0 — confirm data and interfaces

- Inspect Bitget market discovery for the Demo-supported US-stock perpetual universe. Keep Reality rToken discovery as optional comparison research, not the qualification execution universe.
- Confirm candle granularity, history, symbol naming, and the exact `USDT-FUTURES` order contract.
- Freeze the normalized market snapshot contract.
- Confirm the first runnable demo uses fixtures and the competition runner uses the Bitget Demo adapter.

Verification: saved discovery output and a reviewed interface spec.

## Gate 1 — deterministic research kernel

- Add typed schemas for snapshots, hypotheses, validation results, decisions, orders, and audit events.
- Add a small factor registry with parameter validation.
- Implement factor evaluation and metrics with hand-calculated fixtures.
- Add walk-forward validation and leakage tests.

Verification: unit tests, Ruff, type check, deterministic replay.

## Gate 2 — autonomous orchestration, risk, and paper execution

- Implement the autonomous cycle runner: observe → propose → evaluate/iterate → decide → gate → execute → learn/log.
- Implement risk gates as pure functions; a veto must prevent execution and remain visible in the audit trace.
- Implement an in-memory paper broker with fee/slippage simulation and no approval pause after an accepted paper decision.
- Write append-only JSONL audit logs with stage IDs and cycle IDs.
- Add a CLI/demo command that runs multiple fixture cycles, including one accepted order and one rejection.

Verification: complete autonomous event → research → decision → risk → automatic paper execution trace; rejection cases are visible; repeated fixture replay is deterministic.

## Gate 3 — hypothesis discovery and LLM decision boundary

- Add a constrained proposer interface that can return multiple hypotheses per cycle.
- Implement deterministic factor mining/evaluation and a bounded iteration/search budget.
- Implement a deterministic fixture proposer first, then an LLM proposer behind the same interface.
- Add an LLM decision interface that can select only from validated candidates and emit a structured trade decision.
- Validate every proposal and decision through the same schema and factor registry.

Verification: malformed/unsafe proposals and unvalidated LLM decisions are rejected; the agent autonomously selects an accepted validated candidate; core tests pass without an LLM key.

## Gate 4 — Bitget access and competition-period paper run

- Add the verified USDT-FUTURES stock-perp market adapter and normalize the same instruments used for execution.
- Use the local simulator for deterministic development/demo, but use Bitget Demo stock-perp paper trading for the required competition-period evidence. An isolated Agentic account is optional and must not replace the Demo paper-log path unless organizers confirm it is accepted.
- Add a scheduled/continuous paper-run command that starts during the competition window and writes append-only logs under `artifacts/paper-trading/`.
- Ensure accepted and rejected cycles include all required evidence fields and software/config version.
- Keep any rToken comparison data in a separate artifact and never combine its metrics with stock-perp paper results.
- Generate a separate short reproducible demo artifact; do not confuse it with the competition-period log.
- Document actual model/tool/account mode used for the submission.

Verification: no live path; Bitget Demo paper-run smoke test writes valid records; README reproduces the simulator demo and explains how the competition-period Demo log was generated; no simulated backfill is presented as live paper history.

## Gate 5 — submission packaging

- Record observed metrics and limitations.
- Prepare public repository, paper-log export/link, and short demo video.
- Draft the form description from actual implementation results.
- Publish the compliant X post only after the demo is stable.
