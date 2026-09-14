# FactorAtlas Agent Contract

Read this file before changing code. `CLAUDE.md` points here.

## Mission

FactorAtlas is a Bitget AI Genesis Season 2 submission for **Agentic Trading → Factor Discovery Agent**, deadline **2026-09-21 UTC+8**.

Build an agent that proposes factor hypotheses for Bitget US-stock perpetuals, validates them with deterministic Python, applies risk gates, and records a complete paper-trading event → decision → execution trace.

## Source of truth

1. This file: persistent rules, safety, tooling.
2. `docs/ideas/PRD.md`: product thesis and competition context.
3. `docs/specs/technical-spec.md`: approved technical behavior.
4. `docs/plans/implementation-plan.md`: ordered implementation work.
5. Source code and tests.

If these conflict, stop and report the conflict.

## Commands

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy .
```

Bitget CLI:

```bash
bgc --version
bgc discover
bgc discover --tool market
```

## Instrument policy

Research instruments (rToken SPOT, 24/7 market data):

| Symbol | Underlying |
|--------|-----------|
| `RAAPLUSDT` | Apple |
| `RNVDAUSDT` | NVIDIA |
| `RTSLAUSDT` | Tesla |
| `RMETAUSDT` | Meta |

Execution instruments (USDT-FUTURES stock perpetuals, Demo paper trading):

| Symbol | Underlying |
|--------|-----------|
| `AAPLUSDT` | Apple |
| `NVDAUSDT` | NVIDIA |
| `TSLAUSDT` | Tesla |
| `METAUSDT` | Meta |

- Research uses rToken SPOT data. Execution routes through USDT-FUTURES perps.
- Never claim perp orders are rToken orders. Label instrument and category in every log.
- Mapping: `RAAPLUSDT` → `AAPLUSDT`, `RNVDAUSDT` → `NVDAUSDT`, etc.

## Credentials and safety

- No live trading. Every `bgc` order call uses `--paper-trading`.
- Use `--read-only` for inspection, `--dry-run` before writes.
- Never enable withdrawals.
- Never commit credentials. Keys loaded from env vars only:

```
BITGET_API_KEY
BITGET_SECRET_KEY
BITGET_PASSPHRASE
```

- Competition-period paper runner writes run records under `artifacts/paper-trading/`. Never manufacture or backfill history from fixtures.

## Architecture contract

### LLM layer

The LLM proposes hypotheses from a fixed factor vocabulary and selects trades from validated candidates. It cannot generate code, bypass risk gates, invent data, place live orders, or turn failed validation into a recommendation.

### Autonomous cycle

```
observe → propose → validate → decide → gate → execute → verify → log
```

No human approval pause between validated decision and paper execution. Risk gates are authoritative; a veto prevents execution.

### Risk gates (14)

`factor_allowlist`, `data_freshness`, `min_sample_size`, `validation_threshold`, `max_notional`, `max_position`, `exposure_cap`, `cooldown`, `daily_loss_cap`, `duplicate_suppression`, `concentration_guard`, `max_quantity`, `balance_check`, `pending_order_check`

## Boundaries

**Always:** update spec before architecture changes; add tests; use typed schemas; run ruff + mypy + pytest before reporting done.

**Ask first:** adding dependencies, changing submission interfaces, enabling authenticated writes.

**Never:** commit credentials; use live trading; suppress type errors; delete failing tests.

## Handoff contract

Before implementing: state spec section, files, acceptance criteria, tests, and whether Bitget access is read-only, Demo, or unused. After: run verification commands and report exact results.
