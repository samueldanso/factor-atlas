# FactorAtlas — Submission Form Draft

Copy-paste these into the Google Form. Fields marked [YOU] need your input.

---

## Basic Info

**Team Name:** FactorAtlas

**Team Lead Bitget UID (numbers only):** [YOU — your Bitget UID, numbers only]

**Team Lead Email:** me.samueldanso@gmail.com

**Team Lead Contact:** [YOU — your Telegram handle, e.g. @samueldanso]

**Member Background:** Developer, Entrepreneur

**University Name:** (leave blank)

**Apply for Demo Day:** Yes, I would like to apply

**How did you hear about this event?:** Twitter / X

---

## Project Info

**Competition Track:** Agentic Trading

**Competition Sub-theme:** Factor Discovery Agent

**Project Name:** FactorAtlas

**One-line Project Summary (140 chars max):**
Factor-discovery agent: mines rToken market data, validates hypotheses, executes stock perp paper trades on Bitget Demo autonomously.

---

## Project Description

**Part 1 · Thesis (highest weight)**

FactorAtlas is an autonomous factor-discovery agent built on Bitget's rToken and stock perpetual instruments. It uses a two-layer architecture: **rToken SPOT market data** (RAAPLUSDT, RNVDAUSDT, RTSLAUSDT, RMETAUSDT) for 24/7 factor research and hypothesis validation, and **USDT-FUTURES stock perpetuals** (AAPLUSDT, NVDAUSDT, TSLAUSDT, METAUSDT) for Demo paper-trading execution. Both layers track the same underlying US stocks (Apple, NVIDIA, Tesla, Meta).

The core hypothesis: an LLM can propose market factor hypotheses (momentum, mean reversion, volatility breakout), but every hypothesis must pass deterministic walk-forward validation on rToken price data before the agent is allowed to execute on stock perps.

Signal sources: live rToken SPOT price data fetched via Bitget API — 24/7 candles for continuous factor analysis. Decision logic: Claude Sonnet 4.6 (AWS Bedrock) proposes hypotheses from a fixed factor vocabulary, then selects the strongest validated candidate. Execution: orders placed on USDT-FUTURES stock perps via Bitget Demo API. Risk-control design: 14 deterministic gates check balance, position limits, exposure, cooldowns, concentration, and pending orders before any order reaches the exchange. The LLM cannot bypass gates — a veto is final.

The specific pain point: existing trading agents either (a) let the LLM make unchecked decisions, or (b) use hardcoded strategies with no adaptability. FactorAtlas separates the creative layer (LLM proposes) from the safety layer (deterministic validation + risk gates), so the agent adapts to market conditions while remaining auditable and bounded.

**Part 2 · Target user and product value**

Target segment: Retail VIP traders on Bitget who trade US stock perpetuals (USDT-margined), with $10K-$100K capital, medium risk appetite, trading daily to weekly frequency. These traders want systematic factor-based signals but lack the infrastructure to run walk-forward validation and risk management autonomously.

Why this segment needs it: manual factor research is time-consuming and prone to overfitting. Existing tools either provide raw signals without validation, or fully black-box "AI trading" with no explainability. FactorAtlas gives this segment a transparent, auditable factor-discovery process where every decision is traceable from market event through hypothesis, validation, risk check, to execution.

**Part 3 · Validation data and key metrics**

Test period: September 12–14, 2026 (competition period, Demo paper trading). All figures are observed from actual Demo execution, not backtests.

| Metric | Value | Label |
|--------|-------|-------|
| Total closed trades | 3 | observed |
| Win rate | 66.7% | observed |
| Sharpe ratio | 3.46 | observed |
| Sortino ratio | 4.79 | observed |
| Max drawdown | $7.11 | observed |
| Avg hold time | 25 hours | observed |
| Turnover | $1,548.64 | observed |
| Fees (simulated) | 0.1% per trade | estimated |
| Slippage (simulated) | 5 bps | estimated |

Validation plan: Continue accumulating daily paper-trading records through September 21 deadline. Each run generates timestamped JSONL logs with full event→decision→execution traces, verifiable against Bitget Demo order history. Evidence report (HTML) provides visual proof for judges.

**Part 4 · Progress**

Built and working:
- Complete autonomous cycle: observe → propose → validate → decide → gate → execute → verify → log
- Real LLM decisions via Claude Sonnet 4.6 on AWS Bedrock
- Real Bitget Demo orders via bgc CLI (--paper-trading)
- 14 risk gates with exchange state verification
- Order verification against Bitget Demo API
- Position tracking with stop-loss, take-profit, and max-hold exits
- HTML evidence report generator for judges
- 312 passing tests, mypy clean, ruff clean

Tools and APIs used: Bitget Demo API (via bgc CLI), Bitget Signal MCP (market research), AWS Bedrock (Claude Sonnet 4.6), Python 3.11, uv package manager.

Problems hit and solved:
- Bitget rToken SPOT orders return 404 in Demo — switched to USDT-FUTURES stock perpetuals for execution, kept rToken SPOT for research data
- Bitget requires price multiples of 0.01 and integer quantities — added price/qty rounding
- bgc returns composite nested JSON responses — rewrote parser to handle real response format
- Max-position gate wasn't counting cross-run positions — fixed reconciliation to normalize research/execution symbols

Not yet built: Persistent scheduled runner (currently runs N cycles per command), Agentic sub-account isolation (awaiting Bitget support reply).

**Part 5 · Your take on AI Trading (optional)**

Agentic trading's biggest challenge isn't making the LLM smarter — it's making it accountable. The most valuable pattern from building FactorAtlas: separate the creative layer (LLM proposes hypotheses) from the safety layer (deterministic validation + risk gates). The LLM adapts; the gates protect. Every decision is logged with full rationale, and a judge or user can trace any trade back to the exact market data, hypothesis, validation result, and risk check that produced it.

Bitget's bgc CLI and Signal MCP tools are solid for building autonomous agents. The Demo paper-trading environment works well for USDT-FUTURES. Suggestion: enable Demo API keys for Agentic sub-accounts and support rToken SPOT orders in Demo, so agents can be fully isolated from the user's main account.

---

## Submission Material Links

```
Project link: https://github.com/samueldanso/factor-atlas
Run records (paper log): https://github.com/samueldanso/factor-atlas/blob/main/docs/evidence/paper_log.jsonl
Evidence report (HTML): https://github.com/samueldanso/factor-atlas/blob/main/docs/evidence/evidence_report.html
Gate rejection evidence: https://github.com/samueldanso/factor-atlas/blob/main/docs/evidence/evidence_report_gate_rejection.html
Demo video: [YOU — record and upload, then paste URL here]
X post: [YOU — post and paste URL here]
```

---

## Role of the LLM / AI in Your Project

Claude Sonnet 4.6 (via AWS Bedrock) serves as the agent's research and decision layer. It performs two bounded tasks:

1. **Factor hypothesis generation**: Given live market data for US stock perpetuals, the LLM proposes factor hypotheses (momentum, mean reversion, volatility breakout, volume spike, EMA crossover) with specific parameters. It selects from a fixed vocabulary — it cannot invent arbitrary strategies or generate runtime code.

2. **Trade decision selection**: After deterministic walk-forward validation scores each hypothesis, the LLM selects the strongest validated candidate and proposes a trade (direction, instrument, price, quantity) with a written rationale.

The LLM cannot: bypass risk gates, place orders directly, generate trading code, invent data, or access live funds. All 14 risk gates are deterministic Python functions that the LLM has no influence over. A gate veto is final.

Model: Claude Sonnet 4.6 (us.anthropic.claude-sonnet-4-6) via AWS Bedrock.

---

## X Project Post URL

[YOU — post to X with #BitgetHackathon @Bitget_AI and paste URL]

---

## Other Fields

**Did this team participate in S1?:** No

**Material Additions Since S1:** (leave blank)

**Apply for Post-event Kimi K3 Token Credits:** Yes

**Open to Playbook Review and Listing Discussion:** Yes
