# Task T6 Brief: LLM Behind Safe Interfaces

## Spec Section
Technical spec → LLM layer boundaries; tasks/plan.md T6

## Scope
Add provider-neutral proposer and decision interfaces. Implement fixture provider first and optional configured LLM adapter second. All LLM output is schema-validated, limited to registered factors and validated candidates, and never controls gate outcomes or raw order placement.

## Dependencies
- T3: Proposer and DecisionProvider protocols
- T5: complete audit chain

## What the LLM MAY do:
- Propose bounded hypotheses from the registered factor vocabulary
- Select registered factor routines by name
- Summarize validation results
- Select ONLY from validated candidates
- Provide a structured rationale

## What the LLM MAY NOT do:
- Invent arbitrary executable code
- Invent factors outside the registry
- Invent metrics or market data
- Override risk gates
- Place raw orders
- Trade live
- Convert failed validation into a recommendation

## Architecture

### LLM Provider Interface (already exists as Proposer + DecisionProvider protocols)

The key is to add an LLM implementation behind these existing protocols.

### LLMProposer
```python
class LLMProposer:
    """LLM-based hypothesis proposer, constrained to registered factors."""

    def __init__(self, provider: LLMProvider, max_hypotheses: int = 5): ...

    def propose(self, snapshot: MarketSnapshot, budget: int) -> list[FactorHypothesis]:
        """
        Ask the LLM to suggest factor hypotheses.
        Every hypothesis is validated against the factor registry.
        Invalid suggestions are dropped with a warning, not surfaced.
        """
```

### LLMDecisionProvider
```python
class LLMDecisionProvider:
    """LLM-based decision maker, constrained to validated candidates only."""

    def __init__(self, provider: LLMProvider): ...

    def decide(
        self,
        snapshot: MarketSnapshot,
        candidates: list[tuple[FactorHypothesis, ValidationResult]],
        cycle_id: str,
    ) -> TradeDecision | None:
        """
        Ask the LLM to select from validated candidates.
        If the LLM selects a non-validated candidate, reject.
        If the LLM suggests bypassing risk gates, reject.
        """
```

### LLMProvider (abstract base)
```python
class LLMProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt and get a text response."""
        ...
    
    @property
    def model_name(self) -> str:
        """Return the model identifier for audit logging."""
        ...
```

### Implementations:
1. **FixtureLLMProvider**: Returns pre-defined responses (for testing). Already deterministic.
2. **OpenAIProvider** (optional): Uses httpx to call OpenAI-compatible APIs. Requires OPENAI_API_KEY env var. Must gracefully degrade if credentials missing.

### Prompt construction:
- System prompt describes the factor vocabulary, valid instruments, and constraints
- User prompt includes the market snapshot data and asks for structured JSON output
- Response is parsed as JSON and validated against schemas
- Invalid JSON or out-of-schema responses are rejected (not retried in MVP)

### Safety boundary enforcement:
```python
def validate_llm_hypothesis(
    hypothesis_data: dict, snapshot: MarketSnapshot
) -> FactorHypothesis | None:
    """Validate LLM output against factor registry. Returns None if invalid."""


def validate_llm_decision(
    decision_data: dict, candidates: list[...]
) -> TradeDecision | None:
    """Validate LLM decision against validated candidates. Returns None if invalid."""
```

## Files to create/modify
- `src/factor_atlas/llm/__init__.py` — exports
- `src/factor_atlas/llm/provider.py` — LLMProvider protocol, FixtureLLMProvider
- `src/factor_atlas/llm/proposer.py` — LLMProposer with safety validation
- `src/factor_atlas/llm/decision.py` — LLMDecisionProvider with safety validation
- `src/factor_atlas/llm/prompts.py` — prompt templates
- `tests/test_llm_boundary.py` — safety boundary tests

## Tests required
1. **Valid LLM proposal**: fixture provider returns valid factor hypotheses
2. **Invalid factor name rejection**: LLM suggests unknown factor → dropped
3. **Invalid parameters rejection**: LLM suggests out-of-range params → dropped
4. **Invalid instrument rejection**: LLM suggests unknown instrument → dropped
5. **Valid LLM decision**: fixture provider selects from validated candidates
6. **Non-validated candidate rejection**: LLM tries to select a non-validated candidate → rejected
7. **Malformed JSON rejection**: provider returns garbage → handled gracefully
8. **No-credential fixture run**: entire cycle works without any API key
9. **Model name appears in audit trail**: the LLM provider name is traceable

## Acceptance Criteria
1. LLM output is schema-validated
2. Limited to registered factors and validated candidates
3. Never controls gate outcomes or raw order placement
4. Malformed output is handled gracefully (no crash)
5. Credential-free fixture run completes full cycle
6. All prior tests still pass (190)
7. `uv run ruff check .` clean
8. `uv run ruff format --check .` clean
9. `uv run mypy src/ tests/` clean

## Credential mode
Unused for tests — FixtureLLMProvider only. OpenAI adapter is optional, tested with mocks.

## Verification commands
```bash
uv run pytest tests/test_llm_boundary.py -v
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
```
