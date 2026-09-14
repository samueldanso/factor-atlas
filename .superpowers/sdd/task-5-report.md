# Task T5 Report: Remove Silent LLM Fallback, Add Manifest LLM Fields

## Status: COMPLETE

## Commit
`ddb8d6a` — `fix(runner): remove silent LLM fallback, add manifest LLM fields`

## Files Modified
- `src/factor_atlas/runner.py` — removed try/except fallback in demo LLM init, added `llm_info` dict, updated `_build_manifest` signature and body to include `llm_provider`, `llm_model`, `llm_mode` fields
- `tests/test_runner.py` — added `TestDemoLLMFailure` (1 test) and `TestManifestLLMFields` (1 test)

## Test Summary
- **22 tests pass** (20 existing + 2 new) in `tests/test_runner.py`
- `uv run ruff check .` — clean
- `uv run ruff format --check .` — clean

## Acceptance Criteria Verified
1. Demo mode raises loudly (rc=1) when `BedrockProvider` init fails — `TestDemoLLMFailure::test_demo_mode_raises_when_bedrock_fails` passes
2. Fixture mode manifest contains `llm_provider: "fixture"`, `llm_model: "fixture"`, `llm_mode: "fixture"` — `TestManifestLLMFields::test_manifest_contains_llm_fields` passes
3. All 20 prior tests still pass
4. No `# type: ignore` added (existing one on FixtureLLMProvider assignment retained, unchanged)
5. Ruff check clean
6. Ruff format clean

## Changes Summary
- **Removed**: try/except block catching `ImportError, RuntimeError, OSError` around `BedrockProvider()` init in demo mode
- **Added**: `llm_info` dict in both branches (`aws-bedrock`/`live` for demo, `fixture`/`fixture` for fixture)
- **Updated**: `_build_manifest` accepts optional `llm_info: dict[str, str] | None` and writes three new manifest fields
- **Updated**: `_build_manifest` call site passes `llm_info=llm_info`

## Concerns
- None. Demo mode will now propagate `RuntimeError` from `BedrockProvider.__init__` through `run_paper_session` to `main()`, which catches it and returns rc=1 — the existing error-handling path in `__main__.py` handles this correctly.
