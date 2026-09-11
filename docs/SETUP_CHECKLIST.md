# FactorAtlas Setup Checklist

Track: Agentic Trading  
Sub-theme: Factor Discovery Agent  
Deadline: 2026-09-21  
Project: FactorAtlas

Use this document as the source of truth for setup. Check each item before handing the project to the coding agent.

## 1. Bitget web setup

- [ ] Bitget account logged in
- [ ] Demo Trading mode enabled
- [ ] Demo API key created
- [ ] Read permission enabled
- [ ] Trade permission enabled
- [ ] Withdrawal permission disabled
- [ ] Demo account funded with virtual balance
- [ ] Demo credentials stored locally only
- [ ] No credentials stored in Git, `resources/`, screenshots, or chat
- [ ] Optional: isolated Agentic account evaluated for the final demo

## 2. Local tools

- [x] Git repository initialized
- [x] Official Bitget Agent Hub installed
- [x] `bgc` CLI available
- [x] Bitget trading skill installed
- [x] Bitget signal MCP installed
- [x] Bitget skills available to Codex, Claude Code, and OpenCode
- [x] Bitget signal MCP configured for Codex, Claude Code, and OpenCode
- [ ] Demo credentials configured through environment variables
- [ ] Use local simulator for development/runnable demo
- [ ] Use Bitget Demo paper trading for competition-period evidence
- [ ] Do not substitute an Agentic account or local simulation for the required Demo paper log without organizer confirmation
- [ ] Start competition-period paper runner and record actual start timestamp
- [ ] Confirm paper logs are written under `artifacts/paper-trading/`
- [ ] Read-only account verification completed
- [ ] Public market-data request verified
- [x] Python 3.11 environment created with `uv`
- [x] Ruff lint command verified
- [ ] Test suite exists and passes

## 3. FactorAtlas implementation prerequisites

- [ ] Discover supported rToken instruments
- [ ] Confirm available candle history
- [ ] Define market-data adapter
- [ ] Define factor-hypothesis schema
- [ ] Define deterministic factor calculation
- [ ] Define validation and walk-forward split
- [ ] Define autonomous repeated cycle: event → hypothesis mining → validation iteration → decision
- [ ] Define risk gates
- [ ] Define paper-trading order schema
- [ ] Define automatic paper execution after a validated decision (no approval pause)
- [ ] Define event → decision → execution trace
- [ ] Define audit log format
- [ ] Review and approve `docs/specs/technical-spec.md`
- [ ] Review and approve `docs/plans/implementation-plan.md`

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
