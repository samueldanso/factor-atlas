### Task 5: Remove silent LLM fallback and add manifest fields

**Files:**
- Modify: `src/factor_atlas/runner.py` (lines 716-728 — LLM provider selection)
- Modify: `src/factor_atlas/runner.py` (`_build_manifest` — add llm_provider, llm_model, llm_mode, account, environment fields)
- Add tests to: `tests/test_runner.py`

**Interfaces:**
- Consumes: `BedrockProvider`, `FixtureLLMProvider` from `factor_atlas.llm`
- Produces: updated `_build_manifest()` that includes `llm_provider`, `llm_model`, `llm_mode`, `account`, `environment` fields. Demo mode raises `RuntimeError` if BedrockProvider fails (no fallback).

- [ ] **Step 1: Write test for demo mode raising on LLM failure**

```python
# Add to tests/test_runner.py
class TestDemoLLMFailure:
    def test_demo_mode_raises_when_bedrock_fails(self, tmp_path: Path) -> None:
        """Demo mode must not silently fall back to fixture LLM."""
        from unittest.mock import patch

        from factor_atlas.__main__ import main

        with patch(
            "factor_atlas.runner.BedrockProvider",
            side_effect=RuntimeError("Bedrock unavailable"),
        ):
            rc = main(
                ["run", "--mode", "demo", "--cycles", "1", "--output", str(tmp_path)]
            )
        assert rc == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runner.py::TestDemoLLMFailure -v`
Expected: FAIL (currently falls back to fixture provider and returns 0)

- [ ] **Step 3: Remove silent fallback in runner.py**

Replace lines 716-728 in `src/factor_atlas/runner.py`:

```python
    if mode == "demo":
        llm_provider = BedrockProvider()
        print(f"  LLM: {llm_provider.model_name} (AWS Bedrock)")
        llm_info = {
            "llm_provider": "aws-bedrock",
            "llm_model": llm_provider.model_name,
            "llm_mode": "live",
        }
    else:
        llm_provider = FixtureLLMProvider()  # type: ignore[assignment]
        llm_info = {
            "llm_provider": "fixture",
            "llm_model": "fixture",
            "llm_mode": "fixture",
        }
```

Update `_build_manifest` to accept and include `llm_info: dict[str, str]`:

```python
def _build_manifest(
    run_id: str,
    mode: str,
    start_time: datetime,
    end_time: datetime,
    results: list[CycleResult],
    config_hash: str,
    commit: str,
    closed_trades: list[ClosedTrade] | None = None,
    llm_info: dict[str, str] | None = None,
) -> dict[str, Any]:
    # ... existing code ...
    manifest["llm_provider"] = (llm_info or {}).get("llm_provider", "unknown")
    manifest["llm_model"] = (llm_info or {}).get("llm_model", "unknown")
    manifest["llm_mode"] = (llm_info or {}).get("llm_mode", "unknown")
    return manifest
```

Pass `llm_info` from `run_paper_session` to `_build_manifest`.

- [ ] **Step 4: Write test for manifest LLM fields**

```python
# Add to tests/test_runner.py TestRunPaperSession
def test_manifest_contains_llm_fields(self, fixture_run_dir: Path) -> None:
    manifest = json.loads((fixture_run_dir / "manifest.json").read_text())
    assert manifest["llm_provider"] == "fixture"
    assert manifest["llm_model"] == "fixture"
    assert manifest["llm_mode"] == "fixture"
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/factor_atlas/runner.py tests/test_runner.py
git commit -m "fix(runner): remove silent LLM fallback, add manifest LLM fields"
```

---
