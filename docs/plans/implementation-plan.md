# FactorAtlas Implementation Plan

## Gate 0 — confirm data and interfaces

- Inspect Bitget market discovery for supported rToken instruments.
- Confirm candle granularity, history, and symbol naming.
- Freeze the normalized market snapshot contract.
- Decide whether the first demo uses fixtures only or also a Demo adapter.

Verification: saved discovery output and a reviewed interface spec.

## Gate 1 — deterministic research kernel

- Add typed schemas for snapshots, hypotheses, validation results, decisions, orders, and audit events.
- Add a small factor registry with parameter validation.
- Implement factor evaluation and metrics with hand-calculated fixtures.
- Add walk-forward validation and leakage tests.

Verification: unit tests, Ruff, type check, deterministic replay.

## Gate 2 — risk and paper execution

- Implement risk gates as pure functions.
- Implement an in-memory paper broker with fee/slippage simulation.
- Write append-only JSONL audit logs.
- Add a CLI/demo command that runs the full flow from a fixture.

Verification: complete event → decision → execution trace; rejection cases are visible.

## Gate 3 — hypothesis agent boundary

- Add a constrained proposer interface.
- Implement a deterministic fixture proposer first.
- Add an LLM adapter only behind the interface.
- Validate every LLM result through the same schema and factor registry.

Verification: malformed/unsafe proposals are rejected; core tests pass without an LLM key.

## Gate 4 — Bitget and evidence integration

- Add read-only market adapter if the verified API surface is sufficient.
- Add Demo paper adapter only with explicit user approval.
- Generate paper logs and a reproducible demo artifact.
- Document actual model/tool usage for the submission.

Verification: no live path; logs contain all required fields; README reproduces the demo.

## Gate 5 — submission packaging

- Record observed metrics and limitations.
- Prepare public repository and short demo video.
- Draft the form description from actual implementation results.
- Publish the compliant X post only after the demo is stable.
