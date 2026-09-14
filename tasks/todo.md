# FactorAtlas Execution Checklist

## Blocked — waiting Bitget support reply

- [ ] rToken Demo execution — SPOT orders return 404 on Demo. Skye said "will try the demo account for the rtoken first" (2026-09-13). Determines if we unify to USDT-FUTURES only.
- [ ] Demo API key for Agentic sub-account — AG-WZR3S0G5 returns "account prohibited operation" when creating Demo API key. Need confirmation if Demo keys are supported for Agentic sub-accounts.

## Temporary fallback (active)

Using the main Demo account for competition evidence. This is the `factor-atlas-demo` API key — Demo-only, no live-fund access, `--paper-trading` enforced on every order. The Agentic sub-account path remains the intended design; this fallback will be replaced if Bitget confirms isolated Demo keys. All logs label `account: main-demo` to distinguish from future Agentic runs.

## Planning gate

- [x] Human approves `docs/specs/technical-spec.md`
- [x] Human approves implementation plan
- [ ] Confirm exact rToken instruments and data availability (blocked by Bitget reply)

## Completed

- [x] T1 — typed contracts and fixture event stream
- [x] T2 — factor registry and deterministic validation
- [x] T3 — autonomous discovery-and-decision cycle
- [x] Checkpoint A — review autonomous loop
- [x] T4 — risk gates and automatic paper broker
- [x] T5 — audit and deterministic replay
- [x] Checkpoint B — review simulator evidence
- [x] T6 — safe LLM proposer/decision boundary
- [x] T7 — optional read-only/Demo adapter
- [x] T8 — runnable demo and submission evidence
- [x] Wire Bedrock as real LLM decision-maker in demo mode
- [x] Add exit strategy, position tracking, and real PnL metrics
- [x] Auto-load .env and add python-dotenv dependency
- [x] Fix ruff format in runner.py (3 long lines)
- [x] Fix CLI error handling — catch RuntimeError/OSError at CLI boundary, return exit code 1
- [x] Replace flaky demo test with deterministic mocked tests (bgc failure + network error)

## Verification gate

- [x] `uv sync`
- [x] `uv run pytest` — 251 passed (2026-09-14, after fixing flaky demo test)
- [x] `uv run ruff check .`
- [x] `uv run ruff format --check .` — passes after runner.py fix (2026-09-14)
- [x] Type check passes (`uv run mypy src/factor_atlas/` — 0 errors, 30 files, 2026-09-14)
- [x] Accepted autonomous cycle recorded
- [x] Rejected autonomous cycle recorded
- [x] No live trading or withdrawal path

## Trust layer — completed (Tasks 1–8)

- [x] Add exchange state module (`exchange.py`) — bgc wrappers for positions, balances, orders
- [x] Add reconciliation module (`reconcile.py`) — compare exchange vs local state
- [x] Add balance_check and pending_order_check risk gates
- [x] Add Sortino, turnover, equity curve, avg hold hours to metrics
- [x] Remove silent LLM fallback in demo mode
- [x] Separate rToken SPOT research prices from perp execution prices in exit logic
- [x] Add CLI commands: `status`, `history`, `explain`
- [x] Wire exchange verification, reconciliation, and pre-flight into runner
- [x] Add manifest fields: llm_provider, llm_model, llm_mode
- [x] Fix final review findings (turnover edge case, TimeoutExpired, pre-flight fail-loud, assert→TypeError)

## Remaining — can proceed now (not blocked by Bitget)

- [ ] Create GitHub Actions workflow (`.github/workflows/daily-run.yml`) — scaffold can be built now; activation blocked until Demo credentials work
- [ ] Merge PR #1
- [ ] Record demo video (≤3 min)
- [ ] Post to X with `#BitgetHackathon` and `@Bitget_AI`

## Remaining — blocked until Bitget replies

- [ ] Configure Agentic sub-account Demo API key in `.env`
- [ ] Test end-to-end demo execution with Agentic sub-account
- [ ] Determine if rToken SPOT Demo execution is possible (fallback: perps only)
