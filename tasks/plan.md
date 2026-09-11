# FactorAtlas Task Plan

This plan is dependency-ordered for the Factor Discovery Agent. It is intentionally implementation-ready but keeps unresolved Bitget/API choices behind adapters. The simulator is the mandatory path; authenticated Demo access is optional.

## Dependency graph

`T1 contracts/fixtures → T2 factor registry/metrics → T3 autonomous cycle → T4 risk/paper broker → T5 audit/replay → T6 LLM boundary → T7 competition-period paper runner/optional Bitget adapter → T8 demo/evidence`

## T1 — establish typed contracts and fixture event stream

- **Scope:** Define event, market snapshot, hypothesis, candidate, decision, order, and audit contracts; create accepted/rejected fixture events.
- **Likely files:** `src/**/contracts.py`, `src/**/fixtures/**`, `tests/test_contracts.py`.
- **Dependencies:** none.
- **Acceptance:** invalid IDs, instruments, timestamps, quantities, and factor names fail validation; fixtures are credential-free and replayable.
- **Verification:** `uv run pytest tests/test_contracts.py`; Ruff; deterministic fixture serialization.

## T2 — implement registered factors and deterministic validation

- **Scope:** Build the closed factor registry, factor calculation, walk-forward/backtest loop, and metrics including fees, slippage, turnover, and drawdown.
- **Likely files:** `src/**/factors.py`, `src/**/validation.py`, `tests/test_factors.py`, `tests/test_validation.py`.
- **Dependencies:** T1.
- **Acceptance:** only registered factors execute; candidates receive observed/estimated/targeted metric labels; leakage and insufficient-sample cases are rejected.
- **Verification:** hand-calculated fixtures, leakage tests, and deterministic replay.

## T3 — implement the autonomous discovery-and-decision cycle

- **Scope:** Add the runner that observes an event, proposes multiple bounded hypotheses, iterates evaluation/backtesting within a search budget, and asks a decision provider to select only from validated candidates.
- **Likely files:** `src/**/orchestrator.py`, `src/**/proposer.py`, `src/**/decision.py`, `tests/test_orchestrator.py`.
- **Dependencies:** T1, T2.
- **Acceptance:** the runner proceeds without a human approval pause; no passing candidate produces no order; the decision contains instrument, side, quantity, and rationale.
- **Verification:** accepted and no-candidate cycles; candidate allowlist test; multi-cycle fixture run.

### Checkpoint A — review before execution wiring

Confirm the cycle genuinely demonstrates `event → hypothesis mining → iterative validation → LLM/decision selection`, and that the LLM cannot invent factors or code.

## T4 — add deterministic risk gates and automatic paper broker

- **Scope:** Add sizing, exposure, freshness, loss, cooldown, duplicate, concentration, fee, and slippage controls; execute accepted decisions automatically in an in-memory paper broker.
- **Likely files:** `src/**/risk.py`, `src/**/broker.py`, `tests/test_risk.py`, `tests/test_broker.py`.
- **Dependencies:** T3.
- **Acceptance:** a passing decision is submitted automatically; any veto prevents execution; balances never become negative.
- **Verification:** accepted fill, each veto path, fee/slippage math, and bounded-quantity tests.

## T5 — persist auditable cycles and deterministic replay

- **Scope:** Write append-only JSONL records linking event, hypothesis, validation, decision, gates, execution/rejection, and next-cycle summary.
- **Likely files:** `src/**/audit.py`, `src/**/replay.py`, `tests/test_audit.py`, `tests/test_replay.py`.
- **Dependencies:** T4.
- **Acceptance:** one accepted and one rejected cycle are replayable; repeated input/configuration produces identical output.
- **Verification:** JSONL schema validation, event-chain integrity, and byte-for-byte replay comparison.

### Checkpoint B — review before external adapters

Confirm the simulator already satisfies the strict track flow and evidence requirements without any Bitget credential.

## T6 — connect the LLM behind safe interfaces

- **Scope:** Add provider-neutral proposer and decision interfaces; implement fixture provider first and optional configured LLM adapter second.
- **Likely files:** `src/**/llm/**`, `tests/test_llm_boundary.py`, `.env.example`.
- **Dependencies:** T3, T5.
- **Acceptance:** LLM output is schema-validated, limited to registered factors and validated candidates, and never controls gate outcomes or raw order placement.
- **Verification:** malformed-output tests, unvalidated-candidate test, credential-free fixture run.

## T7 — run competition-period paper evidence and add optional Bitget adapter

- **Scope:** Discover and normalize verified rToken data; add the scheduled/continuous paper-run command; add an optional paper-trading adapter only if Demo credentials are available and explicitly configured.
- **Likely files:** `src/**/adapters/**`, `src/**/runner.py`, `tests/test_adapters.py`, `tests/test_paper_runner.py`, `docs/runbook.md`.
- **Dependencies:** T5; exact symbol/API confirmation.
- **Acceptance:** fixtures remain the default demo path; competition-period runs write actual timestamped records under `artifacts/paper-trading/`; adapter failures degrade to a visible rejection/error; no live or withdrawal path exists.
- **Verification:** mocked HTTP tests, paper-run smoke test, `bgc --read-only` discovery, and `bgc --paper-trading` only when explicitly enabled.

## T8 — package the runnable demo and submission evidence

- **Scope:** Add CLI demo, README run command, accepted/rejected recordings, competition-period paper-log export/link, model/tool/account-mode disclosure, and short demo script.
- **Likely files:** `src/**/cli.py`, `README.md`, `docs/demo-script.md`, `artifacts/**`.
- **Dependencies:** T1–T7, with T7 optional.
- **Acceptance:** a clean checkout runs the complete autonomous demo; separate paper evidence includes actual competition-period records with timestamp, instrument, direction, price, quantity, balance change, and rejection reason.
- **Verification:** `uv sync`, `uv run pytest`, Ruff, type check, clean checkout smoke run.

## Human review gate

OpenCode must stop after this plan is accepted and before implementing T1. For every task it must report the spec section, files touched, acceptance criteria, tests, external-data assumptions, and credential mode.
