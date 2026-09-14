# Task 8 Report — Runnable Demo and Submission Packaging

## Status: COMPLETE

## Changes

### Created
- `docs/runbook.md` — operational guide: fixture demo, paper runner, log inspection, troubleshooting
- `docs/demo-script.md` — step-by-step 3-minute demo video script with narration cues

### Modified
- `README.md` — replaced placeholder with full submission README: quick start, architecture, CLI, LLM disclosure, evidence, safety
- `src/factor_atlas/__init__.py` — added `__version__`, expanded public API with `EXECUTION_INSTRUMENTS`, `RESEARCH_INSTRUMENTS`

## Commit
- `922df3b` — `docs: add README, runbook, and demo script for submission`

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/ -q` | 250 passed (0.74s) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 65 files already formatted |
| `uv run mypy src/ tests/` | Success: no issues found in 37 source files |
| `uv run python -m factor_atlas run --dry-run` | Config valid, prints instruments + risk config |
| `uv run python -m factor_atlas run --mode fixture --cycles 2` | 2 cycles, 1 accepted, 1 rejected, paper logs written |
| Credential scan | No credentials in committed files |

## Acceptance Criteria

1. README contains all required sections — done
2. `uv sync && uv run pytest` from clean checkout — verified (250 pass)
3. `uv run python -m factor_atlas run --mode fixture --cycles 2` produces paper logs — verified
4. All 250 tests still pass — verified
5. Ruff, format, mypy clean — verified
6. No credentials in any committed file — verified

## Concerns
- None. All acceptance criteria met.
