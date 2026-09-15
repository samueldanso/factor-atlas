# FactorAtlas — Dashboard Rebuild Handoff (2026-09-15)

## Read these files first
- `AGENTS.md` — project contract, instruments, safety rules
- `README.md` — judge-facing docs (recently rewritten)
- `artifacts/paper-trading/index.html` — current dashboard (needs rebuild)
- `artifacts/paper-trading/logs/agent.log` — real agent output to model from
- `src/factor_atlas/report.py` — old evidence report generator (has stat cards to absorb)
- `resources/helios-buildx` — winning OKX dashboard reference (Next.js)
- `resources/liquidmesh-buildx` — winning OKX dashboard reference (Next.js)

## What happened this session

1. Built the full agent operations upgrade (evidence logging, ATR sizing, continuous runner, Qwen LLM)
2. Deployed GitHub Actions cron (every 4h) — first real run succeeded with Qwen 3.8 Max
3. Set up GitHub Pages at `https://samueldanso.github.io/factor-atlas/`
4. Built a v1 dashboard — functional but NOT judge-ready

## The problem

The dashboard is the submission. Judges do not:
- Run code
- Download JSON files
- Have access to the Bitget Demo account (no UID login)
- Read GitHub source code
- Have time to piece together multiple URLs

The dashboard must show **everything** judges need to score. If it's not visible on the dashboard, it doesn't exist to judges. 100+ submissions, 1 winner for Factor Discovery Agent.

## What judges score (from the handbook)

**Track 2: Agentic Trading — Factor Discovery Agent**

> Judging focus: Paper trading Sharpe, max drawdown, win rate; decision explainability; Agent architecture quality; risk control layer effectiveness.
> Scoring mechanism: 50% quantitative + 50% judge scoring.

**Required materials for this track:**
1. Runnable Demo (the dashboard IS the demo)
2. Event → decision → execution flow demonstration
3. Paper trading log (timestamp, instrument, direction, price, quantity, balance change)
4. Compliant X post link

## What the dashboard must show (rebuild spec)

### Header
- "FactorAtlas" + "Autonomous Factor Discovery Agent"
- "Track 2: Agentic Trading — Bitget AI Genesis S2" badge
- PAPER TRADING indicator (green pulsing dot)
- "Powered by Qwen 3.8 Max via Bitget" label
- Last updated timestamp
- **"Run Cycle Now" button** — judges can trigger one cycle and watch results appear live

### Stats Strip (mirror the old evidence report cards + Bitget account view)
Must include ALL of these — they're what judges score quantitatively:
- **Account Balance** — from positions_state.json or computed
- **Total PnL** (realized) — green/red colored
- **Unrealized PnL** — from open positions
- **Open Positions** — count
- **Total Cycles** — how many times the agent has run
- **Accepted / Rejected** — trades accepted vs blocked by risk gates
- **Win Rate** — percentage of profitable closed trades
- **Sharpe Ratio** — annualized
- **Sortino Ratio** — annualized
- **Max Drawdown** — dollar amount
- **Profit Factor** — gross profit / gross loss
- **Avg Hold Time** — hours
- **Next Cycle** — countdown or "Every 4h" with last run timestamp

### Pipeline Visualization
```
OBSERVE → PROPOSE → VALIDATE → DECIDE → GATE → EXECUTE → VERIFY → LOG
```
Label: "Autonomous Agent Pipeline — no human approval between stages"
Each step described in one line below the pill.

### Tabs

**Agent Timeline** (default tab)
- Terminal-style log from agent.log
- Full text, not truncated
- Grouped by run with separator lines
- Most recent at top
- Emojis preserved for visual scanning

**Factor Discovery** (events.jsonl)
For each cycle, show a full card:
- Instrument (use Bitget name: "AAPLUSDT Perpetual")
- Market price at observation
- Hypothesis: factor name, direction, full parameters
- **Full LLM rationale** — do NOT truncate, show entire text
- Validation results: Sharpe, Sortino, Max Drawdown, Win Rate, Observations, Passed/Failed
- If multiple hypotheses per cycle, show all with pass/fail

**Decisions** (decisions.jsonl)
- Instrument, Side (BUY green / SELL red), Order quantity, Order price
- **Full LLM decision rationale** — entire text, not truncated
- Selected hypothesis ID linked back to the factor discovery card
- "No trade" decisions shown clearly with the decline reason

**Risk Control** (risk.jsonl)
- Per-decision: verdict banner (ALL 14 PASSED / BLOCKED BY X)
- All 14 gates listed with: gate name, passed/failed, reason, value vs threshold
- Failed gates highlighted in red
- This section directly answers "risk control layer effectiveness"

**Paper Trading Log** (trades.jsonl) — **USE BITGET TERMINOLOGY**
Table columns must match Bitget Demo UI language:
| Column | Maps to |
|--------|---------|
| Time | timestamp |
| Trading pair | instrument + " Perpetual" (e.g., "AAPLUSDT Perpetual") |
| Direction | side mapped to Bitget terms: "Open long" / "Open short" / "Close long" / "Close short" |
| Order type | "Limit" (we use limit orders) |
| Order quantity | size (full number, not truncated) |
| Order value | price * quantity in USDT |
| Order price | price |
| Filled quantity | same as order quantity if filled |
| Filled value | actual filled value |
| Status | "Filled" / "Rejected" with color |
| **Bitget Order ID** | Full orderId — NOT truncated. This is the proof link. |
| Fee | transaction fee |
| PnL | profit/loss (only for close records) — green positive, red negative |
| Balance change | post_balance - pre_balance |

**Open Positions** (computed from trades — entries without matching exits)
Mirror Bitget's position view:
| Column | Value |
|--------|-------|
| Trading pair | "AAPLUSDT Perpetual" |
| Direction | "Cross · Long · 20x" (match Bitget format) |
| Position | quantity + underlying (e.g., "25 AAPL") |
| Avg. holding price | entry price |
| Unrealized PnL | computed from current data if available, else "—" |
| Entry time | timestamp |
| Factor | which factor hypothesis triggered this position |

### Footer
- "Built for Bitget AI Genesis Season 2 — Track 2: Agentic Trading"
- "Agent runs autonomously every 4 hours via GitHub Actions"
- Link to GitHub repo (for judges who want to inspect)
- Link to raw JSONL evidence files (backup, not primary)

## What to REMOVE from the current dashboard
- "Submission Form" link (internal doc, not for judges)
- "Previous Evidence Report" link (absorbed into this dashboard)
- "fallback" links (confusing)
- Any truncated text (show full content or don't show at all)
- Any reference to "fixture mode" (judges only care about demo)

## Design requirements
- Single self-contained HTML file (Tailwind CDN, inline JS)
- Dark theme matching Bitget's UI (#0d1117 background)
- Monospace font for all data
- All data loaded via fetch() from relative JSONL paths
- Mobile-responsive
- Handle empty data gracefully ("Awaiting first autonomous run")
- Use judge terminology throughout:
  - "Factor Discovery" not "hypothesis proposal"
  - "Decision Explainability" not "LLM rationale"
  - "Risk Control Layer" not "gate checker"
  - "Paper Trading Log" not "trade records"
  - "Event → Decision → Execution" as the flow description

## Bitget UI language mapping

The dashboard must use Bitget's exact terminology so judges see consistency:

| Our code term | Bitget Demo UI term | Use in dashboard |
|---------------|-------------------|------------------|
| instrument | Trading pair | "AAPLUSDT Perpetual" |
| side: buy | Direction | "Open long" |
| side: sell | Direction | "Open short" |
| quantity / size | Order quantity | "25 AAPL" |
| price | Order price | "$331.63" |
| price * qty | Order value | "8,290.75 USDT" |
| orderId | Order ID | Full ID, never truncated |
| status: filled | Status | "Filled" |
| status: rejected | Status | "Rejected" |
| orderType: limit | Order type | "GTC / Limit" |
| USDT-FUTURES | Category | "USDT-M perpetual" |
| balance | Available | "48,132 USDT" |
| stop_loss | TP/SL | Show SL and TP prices |

## Data sources on disk

All at `artifacts/paper-trading/`:
```
logs/agent.log          — human timeline (text, one line per entry)
logs/events.jsonl       — {run_id, cycle_id, timestamp, instrument, price, hypothesis:{...}, validation:{...}}
logs/decisions.jsonl    — {run_id, cycle_id, timestamp, instrument, selected_hypothesis, side, quantity, price, rationale}
logs/risk.jsonl         — {run_id, cycle_id, timestamp, instrument, gates:[{gate_name, passed, reason}], verdict}
logs/trades.jsonl       — {run_id, cycle_id, timestamp, record_type, instrument, side, price, size, orderId, orderStatus, pnl?, pnl_pct?}
positions_state.json    — current open positions
```

## Reference dashboards to study

1. `/Users/samueldanso/Workspace/hacks/factor-atlas/resources/helios-buildx` — Next.js, won OKX BuildX
   - Key pattern: stats strip, agent swarm panel, activity feed, positions sidebar
   - Gold accent, monospace everything, LIVE indicator

2. `/Users/samueldanso/Workspace/hacks/factor-atlas/resources/liquidmesh-buildx` — Next.js, won OKX BuildX
   - Key pattern: terminal-style log, agent cards with colored dots, expandable trade rows
   - Cyan accent, opacity-based text hierarchy, GSAP typewriter

3. Bitget Demo account screenshots — the paper trading UI language and layout
   - Positions tab, Open orders tab, Order history tab, Transaction history tab, Assets tab
   - See the screenshots in this handoff conversation for exact column names and formats

## "Run Cycle Now" button (stretch goal)

The killer feature: a button on the dashboard that triggers `gh workflow run paper-runner.yml` via GitHub API. Judge clicks it, sees "Cycle running..." then results appear. This requires a GitHub personal access token stored as a query param or in the page — security is acceptable for a hackathon demo.

Alternatively: the button could trigger a lightweight API endpoint (Vercel serverless function) that dispatches the GitHub Action. But for a hackathon, even showing "Last run: 2 hours ago — Next run in: 1h 47m" with a manual dispatch link is sufficient.

## Cron status

- GitHub Actions cron runs every 4h — working, first run succeeded
- GitHub secrets set: BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE, BITGET_QWEN_API_KEY
- Evidence accumulating in `artifacts/paper-trading/logs/`
- Pages auto-deploys on push to main

## Priority

1. Rebuild the dashboard with ALL the above
2. Ensure paper trading log matches Bitget terminology exactly
3. Full, untruncated content everywhere
4. Stats cards with all quantitative metrics judges score
5. Update README to point only to the dashboard (remove clutter)
6. Remove docs/evidence/ (absorbed into dashboard)
7. Update SUBMISSION.md with dashboard URL as the primary submission link
