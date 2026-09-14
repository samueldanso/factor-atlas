# FactorAtlas — Submission Checklist

## Done

- [x] Core agent: event → hypothesis → validation → decision → gates → execution → audit
- [x] Real LLM decisions (Claude Sonnet 4.6 via AWS Bedrock)
- [x] Real Bitget Demo orders via bgc --paper-trading
- [x] 14 risk gates (all tested, exchange-verified)
- [x] Order verification against exchange
- [x] Position tracking with exit logic (stop-loss, take-profit, max-hold)
- [x] Performance metrics: Sharpe, Sortino, win rate, drawdown, equity curve
- [x] Reconciliation: local state vs exchange truth
- [x] Paper trading evidence with accepted + rejected + no-trade cycles
- [x] Closed trades with real PnL (win_rate=66.7%, sharpe=3.46)
- [x] 307 tests, mypy clean, ruff clean
- [x] README rewritten for judges
- [x] Bug fixes: gate counting, reconciliation symbol mapping, cycle status

## In Progress

- [ ] HTML evidence report generator (judges open one file, see everything)
- [ ] Clean CLI output (human-readable cycle summaries, not raw JSON)

## Remaining for Submission

- [ ] Merge PR #1
- [ ] Record demo video (≤3 min) showing: start agent, observe cycle, see decision, see order, see rejection
- [ ] Post to X with #BitgetHackathon @Bitget_AI
- [ ] Fill submission form with links

## Blocked — Bitget Support

- [ ] Agentic sub-account Demo API key (AG-WZR3S0G5)
- [ ] rToken SPOT Demo execution (HTTP 404)
