# FactorAtlas Runbook

Operational guide for running the FactorAtlas factor discovery agent.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Git (for commit hash in manifests)

```bash
uv sync
```

## Running the fixture demo

The fixture demo is fully deterministic and requires no API keys or network access.

```bash
# Validate configuration first
uv run python -m factor_atlas run --dry-run

# Run 2 cycles (1 accepted, 1 rejected)
uv run python -m factor_atlas run --mode fixture --cycles 2
```

Output is written to `artifacts/paper-trading/<run-id>/`. Each run gets a unique UUID directory.

### What the fixture demo does

1. **Cycle 1 (accepted)**: Observes an RAAPLUSDT snapshot → proposes a momentum hypothesis → validates with walk-forward (Sharpe > 0.5) → passes all 6 risk gates → executes a paper buy order → logs balance change.
2. **Cycle 2 (rejected)**: Observes a second snapshot → proposes a mean-reversion hypothesis → validates (Sharpe < 0.5, fails threshold) → no valid candidate → logs rejection.

This demonstrates both the accept and reject paths of the autonomous loop.

## Starting the competition-period paper runner

For competition evidence, run multiple sessions and keep the output under `artifacts/paper-trading/`:

```bash
# Default output location
uv run python -m factor_atlas run --mode fixture --cycles 2

# Multiple runs accumulate under artifacts/paper-trading/
uv run python -m factor_atlas run --mode fixture --cycles 2
uv run python -m factor_atlas run --mode fixture --cycles 2
```

Each run produces a separate `<run-id>/` directory. Never delete or modify existing run directories — the audit trail is append-only.

### Demo mode (Bitget Demo API)

Demo mode requires Bitget credentials in environment variables:

```bash
export BITGET_API_KEY="your-demo-api-key"
export BITGET_SECRET_KEY="your-demo-secret"
export BITGET_PASSPHRASE="your-demo-passphrase"
```

Demo mode is not yet integrated into the autonomous loop. Use fixture mode for all current evidence.

## Inspecting paper logs

### Paper log (order-level)

```bash
# Pretty-print the paper log
cat artifacts/paper-trading/<run-id>/paper_log.jsonl | python -m json.tool --json-lines

# Filter accepted orders
cat artifacts/paper-trading/<run-id>/paper_log.jsonl | python -c "
import json, sys
for line in sys.stdin:
    r = json.loads(line)
    if r['status'] == 'accepted':
        print(json.dumps(r, indent=2))
"
```

Key fields per record:
- `order_id`, `timestamp` — unique order and time
- `instrument` — execution instrument (e.g., `AAPLUSDT`)
- `side`, `price`, `quantity`, `notional` — trade details
- `pre_balance`, `post_balance`, `fees` — balance impact
- `status` — `accepted` or rejection reason
- `factor_name`, `validation_sharpe` — which factor and its score
- `risk_gate_results` — per-gate pass/fail

### Audit log (stage-level)

```bash
# View all audit events
cat artifacts/paper-trading/<run-id>/audit_log.jsonl | python -m json.tool --json-lines

# Filter by stage
cat artifacts/paper-trading/<run-id>/audit_log.jsonl | python -c "
import json, sys
for line in sys.stdin:
    e = json.loads(line)
    if e['stage'] == 'gate':
        print(json.dumps(e, indent=2))
"
```

Stages: `observe`, `propose`, `evaluate`, `decide`, `gate`, `execute`, `learn`.

### Manifest

```bash
cat artifacts/paper-trading/<run-id>/manifest.json | python -m json.tool
```

Contains: run ID, timestamps, mode, instruments, cycle counts, config hash, git commit, software version.

## Deterministic replay

Replay a previous run from its audit log:

```python
from factor_atlas.replay import replay_audit_log

events = replay_audit_log("artifacts/paper-trading/<run-id>/audit_log.jsonl")
for event in events:
    print(f"{event.stage}: {event.event_type} — {event.summary}")
```

## Troubleshooting

### `uv sync` fails

Ensure Python 3.11+ is available. Check with `python --version`. If using pyenv:

```bash
pyenv install 3.11
pyenv local 3.11
uv sync
```

### `--dry-run` shows unexpected config

Config is defined in `src/factor_atlas/config.py`. The config hash changes if any threshold, instrument, or factor vocabulary changes.

### Fixture run produces 0 accepted cycles

The fixture is deterministic — cycle 1 always accepts, cycle 2 always rejects. If `--cycles 1`, only the accepted cycle runs. If both reject, check that fixtures haven't been modified.

### mypy errors after edits

Run strict type checking:

```bash
uv run mypy src/ tests/
```

Common fix: ensure all Pydantic models use explicit type annotations and `Decimal` fields use string constructors.

### Tests fail

```bash
# Run with verbose output
uv run pytest tests/ -v --tb=short

# Run a specific test file
uv run pytest tests/test_runner.py -v
```

All 250 tests should pass on a clean checkout. If a test fails, check for uncommitted changes to fixtures or config.
