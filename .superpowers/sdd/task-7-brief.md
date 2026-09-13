# Task T7 Brief: Competition-Period Paper Runner + Bitget Demo Adapter

## Spec Section
Technical spec → Competition-period paper run; tasks/plan.md T7

## Scope
1. Add a CLI entry point (`__main__.py`) with `run` and `demo` subcommands
2. Add a Bitget Demo adapter for market data and paper-order submission
3. Add instrument normalization (rToken research → stock perp execution)
4. Add the competition-period paper runner that writes append-only JSONL under `artifacts/paper-trading/`
5. Add a paper-run manifest with timestamps, timezone, commit, config hash

## Dependencies
- T1-T6 complete (213 tests)
- `src/factor_atlas/config.py` — RESEARCH_TO_EXECUTION, RESEARCH_INSTRUMENTS, EXECUTION_INSTRUMENTS
- `src/factor_atlas/orchestrator.py` — run_cycle, run_cycles, CycleResult
- `src/factor_atlas/audit.py` — AuditLogger
- `src/factor_atlas/broker.py` — BrokerState

## Architecture

### CLI Entry Point (`src/factor_atlas/__main__.py`)
```python
"""Factor Atlas CLI — `uv run python -m factor_atlas <command>`"""

# Commands:
# run          — run the full autonomous loop (fixture or demo mode)
# run --mode fixture    — deterministic fixture run (default, no credentials)
# run --mode demo       — Bitget Demo paper trading (requires credentials)
# run --dry-run         — validate config and exit without executing
# run --cycles N        — number of cycles (default: 2 for fixture, continuous for demo)
# run --output PATH     — output directory for paper logs (default: artifacts/paper-trading/)
```

Use `argparse` only (no click/typer dependency).

### Bitget Demo Adapter (`src/factor_atlas/adapters/__init__.py`, `src/factor_atlas/adapters/bitget_demo.py`)

```python
class BitgetDemoAdapter:
    """Adapter for Bitget Demo USDT-FUTURES stock perpetuals.

    Uses httpx for REST calls to Bitget's Demo API.
    All calls use paper-trading mode.
    """

    def __init__(self, api_key: str, secret_key: str, passphrase: str): ...

    async def get_market_snapshot(self, instrument: str) -> MarketSnapshot:
        """Fetch latest ticker + recent candles for a USDT-FUTURES instrument."""
        ...

    async def place_paper_order(
        self, instrument: str, side: str, quantity: Decimal, price: Decimal
    ) -> dict:
        """Place a paper order on Bitget Demo. Returns order response dict."""
        ...

    async def get_account_balance(self) -> Decimal:
        """Get Demo account USDT balance."""
        ...
```

**IMPORTANT:** The adapter must:
- Only call Bitget Demo endpoints (not live)
- Use USDT-FUTURES category for orders
- Handle HTTP errors gracefully (return error status, not crash)
- Be fully replaceable by fixture data (tests never need credentials)

### Instrument Normalization (`src/factor_atlas/adapters/normalize.py`)
```python
def research_to_execution(instrument: str) -> str:
    """Map rToken research instrument to stock perp execution instrument.

    RAAPLUSDT -> AAPLUSDT, RNVDAUSDT -> NVDAUSDT, etc.
    Execution instruments pass through unchanged.
    """
    from factor_atlas.config import RESEARCH_TO_EXECUTION, EXECUTION_INSTRUMENTS

    if instrument in EXECUTION_INSTRUMENTS:
        return instrument
    return RESEARCH_TO_EXECUTION.get(instrument, instrument)
```

### Paper Run Output

Each run writes to `artifacts/paper-trading/<run_id>/`:
- `paper_log.jsonl` — append-only JSONL of PaperOrder records
- `audit_log.jsonl` — full audit trail (AuditLogger output)
- `manifest.json` — run metadata

#### Paper log record format (one JSON per line):
Each line = PaperOrder.model_dump(mode="json") + additional fields:
```json
{
    "order_id": "...",
    "decision_id": "...",
    "event_id": "...",
    "timestamp": "2026-09-12T10:00:00+00:00",
    "instrument": "AAPLUSDT",
    "category": "USDT-FUTURES",
    "side": "buy",
    "price": "152.50",
    "quantity": "10",
    "notional": "1525.00",
    "pre_balance": "100000.00",
    "post_balance": "99998.24",
    "fees": "1.525",
    "slippage": "0.7625",
    "status": "filled",
    "fill_price": "152.50",
    "cycle_id": "...",
    "hypothesis_id": "...",
    "factor_name": "momentum",
    "risk_gate_results": [{"gate_name": "...", "passed": true, "reason": "..."}],
    "validation_sharpe": 1.23,
    "rationale": "...",
    "software_version": "0.1.0",
    "config_hash": "abc123..."
}
```

For rejected cycles, include:
```json
{
    "status": "rejected",
    "rejection_reason": "daily_loss_cap exceeded",
    ...same fields...
}
```

#### Manifest format (`manifest.json`):
```json
{
    "run_id": "...",
    "start_timestamp": "2026-09-12T10:00:00+00:00",
    "end_timestamp": "2026-09-12T10:05:00+00:00",
    "timezone": "UTC",
    "mode": "fixture",
    "instruments": ["RAAPLUSDT"],
    "execution_instruments": ["AAPLUSDT"],
    "cycles_completed": 2,
    "accepted_count": 1,
    "rejected_count": 1,
    "code_commit": "abc1234",
    "config_hash": "sha256:...",
    "software_version": "0.1.0"
}
```

### Runner (`src/factor_atlas/runner.py`)
```python
def run_paper_session(
    mode: str = "fixture",  # "fixture" or "demo"
    cycles: int = 2,
    output_dir: Path | None = None,  # default: artifacts/paper-trading/
) -> Path:
    """Run a paper-trading session and write results.

    Returns the path to the run output directory.
    """
```

For fixture mode:
- Use existing fixture snapshots and OHLCV data
- Use FixtureProposer and FixtureDecisionProvider
- Use in-memory BrokerState
- Write output to artifacts/paper-trading/<run_id>/

For demo mode:
- Use BitgetDemoAdapter for market data
- Use in-memory BrokerState (paper orders tracked locally)
- Optionally submit paper orders via the adapter
- Write output to artifacts/paper-trading/<run_id>/

## Config hash
Compute from a deterministic serialization of RiskConfig + factor vocabulary + instruments:
```python
import hashlib, json
config_data = json.dumps({"risk": risk_config_dict, "factors": sorted(FACTOR_VOCABULARY), ...}, sort_keys=True)
config_hash = "sha256:" + hashlib.sha256(config_data.encode()).hexdigest()[:16]
```

## Git commit hash
```python
import subprocess

result = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
)
commit = result.stdout.strip() or "unknown"
```

## Files to create
- `src/factor_atlas/__main__.py` — CLI entry point
- `src/factor_atlas/runner.py` — run_paper_session
- `src/factor_atlas/adapters/__init__.py` — exports
- `src/factor_atlas/adapters/bitget_demo.py` — Bitget Demo adapter (httpx)
- `src/factor_atlas/adapters/normalize.py` — instrument normalization
- `tests/test_runner.py` — runner tests (fixture mode only)
- `tests/test_adapters.py` — adapter tests with mocked HTTP

## Acceptance Criteria
1. `uv run python -m factor_atlas run --dry-run` validates config and exits cleanly
2. `uv run python -m factor_atlas run --mode fixture --cycles 2` produces:
   - `artifacts/paper-trading/<run_id>/paper_log.jsonl` with ≥2 records
   - `artifacts/paper-trading/<run_id>/audit_log.jsonl` with audit events
   - `artifacts/paper-trading/<run_id>/manifest.json` with required fields
3. Paper log includes both accepted and rejected cycles
4. Each paper log record has all required fields (timestamp, instrument, category, direction, price, quantity, balance, fees, risk gates, config hash, commit)
5. Bitget Demo adapter handles missing credentials gracefully (ValueError, not crash)
6. Adapter tests use mocked HTTP (no real API calls in tests)
7. Fixture mode works without any credentials
8. All prior tests still pass (213)
9. `uv run ruff check .` clean
10. `uv run ruff format --check .` clean
11. `uv run mypy src/ tests/` clean

## Credential mode
Tests: Unused (mocked HTTP)
CLI fixture run: Unused
CLI demo run: Demo paper-trading (reads from env BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE)

## Verification commands
```bash
uv run pytest tests/test_runner.py tests/test_adapters.py -v
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
uv run python -m factor_atlas run --dry-run
uv run python -m factor_atlas run --mode fixture --cycles 2
```
