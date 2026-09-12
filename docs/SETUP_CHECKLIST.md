# FactorAtlas Setup Checklist

Track: Agentic Trading  
Sub-theme: Factor Discovery Agent  
Deadline: 2026-09-21  
Project: FactorAtlas

Use this document as the source of truth for setup. Check each item before handing the project to the coding agent.

## 1. Bitget web setup

- [x] Bitget account logged in
- [x] Demo Trading mode enabled
- [x] Demo API key created (`factor-atlas-demo`)
- [x] Read permission enabled
- [x] Trade permission enabled
- [x] Withdrawal permission disabled
- [x] Demo account funded with virtual balance (100,000 USDT verified)
- [x] Demo credentials stored locally only
- [x] No credentials stored in Git, `resources/`, screenshots, or chat
- [ ] Optional: isolated Agentic account evaluated for the final demo

## 2. Local tools

- [x] Git repository initialized
- [x] Official Bitget Agent Hub installed
- [x] `bgc` CLI available
- [x] Bitget trading skill installed
- [x] Bitget signal MCP installed
- [x] Bitget skills available to Codex, Claude Code, and OpenCode
- [x] Bitget signal MCP configured for Codex, Claude Code, and OpenCode
- [x] Separate Demo credentials configured through environment variables in local `.env`
- [x] Use local simulator for development/runnable demo
- [x] Use Bitget Demo paper trading for competition-period evidence (stock perps AAPLUSDT/NVDAUSDT USDT-FUTURES — rToken SPOT Demo returns 404, confirmed by testing)
- [x] Do not substitute an Agentic account or local simulation for the required Demo paper log without organizer confirmation
- [ ] Start competition-period paper runner and record actual start timestamp
- [ ] Confirm paper logs are written under `artifacts/paper-trading/`
- [x] Read-only Demo account verification completed with `bgc --paper-trading account_overview`
- [x] Public market-data request verified (SPOT `RAAPLUSDT` instrument, ticker, and history)
- [x] Demo-supported stock-perp instrument and order path verified (`NVDAUSDT` USDT-FUTURES)
- [x] Python 3.11 environment created with `uv`
- [x] Ruff lint command verified
- [ ] Test suite exists and passes

## 3. FactorAtlas implementation prerequisites

- [x] Discover supported rToken instruments (`RAAPLUSDT` returned online with `isReality=yes`; optional comparison data)
- [x] Confirm available candle history (approximately 90 daily candles returned)
- [x] Discover Demo-supported stock-perp execution universe (`AAPLUSDT`, `NVDAUSDT`, `TSLAUSDT`, `METAUSDT` verified as USDT-FUTURES candidates)
- [x] Define market-data adapter
- [x] Define factor-hypothesis schema
- [x] Define deterministic factor calculation
- [x] Define validation and walk-forward split
- [x] Define autonomous repeated cycle: event → hypothesis mining → validation iteration → decision
- [x] Define risk gates
- [x] Define paper-trading order schema
- [x] Define automatic paper execution after a validated decision (no approval pause)
- [x] Define event → decision → execution trace
- [x] Define audit log format
- [x] Review and approve `docs/specs/technical-spec.md`
- [x] Review and approve `docs/plans/implementation-plan.md`

## 4. Required competition evidence

- [ ] Runnable demo
- [ ] Paper-trading log
- [ ] Paper log actually run during the competition period (target ≥2 weeks where feasible)
- [ ] Paper log contains accepted and rejected cycles with required evidence fields
- [ ] Paper-log manifest records actual start/end timestamps, timezone, code commit, and config hash
- [ ] Public paper-log/export link prepared for the form's Submission Materials Link field
- [ ] Complete event → decision → execution flow
- [ ] Public repository with README
- [ ] Demo video, preferably three minutes or less
- [ ] Project description written in the submission form
- [ ] LLM role documented honestly
- [ ] Public X post containing `#BitgetHackathon` and `@Bitget_AI`

## 5. Resource folder

Place collected public materials in `resources/`. This folder is intentionally ignored by Git.

Allowed: handbook exports, screenshots, public API notes, sample data, and research references.  
Never place: API keys, secret keys, passphrases, seed phrases, private keys, or personal identity documents.

## 6. Handoff gate

The coding agent may start only when Sections 1–3 are complete and the PRD has no unresolved implementation blocker.
