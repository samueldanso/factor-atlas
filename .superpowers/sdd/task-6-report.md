# Task T6 Report: LLM Behind Safe Interfaces

## Status: COMPLETE

## Commits
- `0a11ddb` feat(llm): add provider-neutral LLM boundary with safety validation

## Files Created
- `src/factor_atlas/llm/__init__.py` — package exports
- `src/factor_atlas/llm/provider.py` — LLMProvider protocol + FixtureLLMProvider
- `src/factor_atlas/llm/proposer.py` — LLMProposer with `validate_llm_hypothesis`
- `src/factor_atlas/llm/decision.py` — LLMDecisionProvider with `validate_llm_decision`
- `src/factor_atlas/llm/prompts.py` — PROPOSE_SYSTEM, DECIDE_SYSTEM, user-prompt builders
- `tests/test_llm_boundary.py` — 23 safety boundary tests

## Test Summary
- **23 new tests**, all passing
- **213 total** (190 prior + 23 new), all passing
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean
- `uv run mypy src/ tests/` — clean, no issues

## Acceptance Criteria Verification
| # | Criterion | Status |
|---|-----------|--------|
| 1 | LLM output is schema-validated | PASS — JSON parsed and validated against Pydantic schemas |
| 2 | Limited to registered factors and validated candidates | PASS — unknown factors, bad params, bad instruments all rejected |
| 3 | Never controls gate outcomes or raw order placement | PASS — LLM only proposes/selects; gates and broker remain external |
| 4 | Malformed output handled gracefully | PASS — garbage JSON, explosions, bad types all return empty/None |
| 5 | Credential-free fixture run | PASS — full propose→decide cycle with FixtureLLMProvider |
| 6 | All prior tests still pass | PASS — 190 existing tests unaffected |
| 7 | ruff check clean | PASS |
| 8 | ruff format clean | PASS |
| 9 | mypy clean | PASS |

## Architecture Decisions
- `LLMProvider` is a `typing.Protocol` (runtime_checkable), matching the existing Proposer/DecisionProvider pattern
- `LLMProposer` satisfies the `Proposer` protocol; `LLMDecisionProvider` satisfies `DecisionProvider`
- Validation is a separate function (`validate_llm_hypothesis`, `validate_llm_decision`) for direct unit testing
- Prompt templates are deterministic strings built from config constants, ensuring vocabulary drift is impossible
- FixtureLLMProvider parses prompt keywords to decide propose vs decide response, returns valid JSON from the registry

## Concerns
- None. No existing code modified. All new code is additive. Optional OpenAI adapter deferred per brief.
