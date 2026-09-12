# Task T3 Brief: Autonomous Discovery-and-Decision Cycle

## Spec Section
Technical spec → Autonomous cycle contract; tasks/plan.md T3

## Scope
Add the autonomous cycle runner that: observes an event, proposes multiple bounded hypotheses, iterates evaluation/backtesting within a search budget, and asks a decision provider to select only from validated candidates.

## Dependencies
- T1: contracts (MarketSnapshot, FactorHypothesis, TradeDecision, ValidationResult)
- T2: factor registry (`compute_factor`, `FACTOR_REGISTRY`) and validation engine (`validate_factor`)

## Architecture

### Proposer Interface (Protocol)
```python
class Proposer(Protocol):
    def propose(self, snapshot: MarketSnapshot, budget: int) -> list[FactorHypothesis]:
        """Generate up to `budget` hypotheses for a given snapshot."""
        ...
```

Two implementations:
1. **FixtureProposer**: returns pre-built fixture hypotheses (credential-free, deterministic)
2. (Later T6: LLMProposer behind the same interface)

### DecisionProvider Interface (Protocol)
```python
class DecisionProvider(Protocol):
    def decide(
        self,
        snapshot: MarketSnapshot,
        candidates: list[tuple[FactorHypothesis, ValidationResult]],
        cycle_id: str,
    ) -> TradeDecision | None:
        """Select one validated candidate and return a TradeDecision, or None if no trade."""
        ...
```

Two implementations:
1. **FixtureDecisionProvider**: deterministically selects the best Sharpe candidate (credential-free)
2. (Later T6: LLMDecisionProvider behind the same interface)

### CycleRunner
The core orchestrator that runs one autonomous cycle:

```python
@dataclass
class CycleResult:
    cycle_id: str
    snapshot: MarketSnapshot
    hypotheses: list[FactorHypothesis]
    evaluations: list[tuple[FactorHypothesis, ValidationResult]]
    validated: list[tuple[FactorHypothesis, ValidationResult]]
    decision: TradeDecision | None
    status: Literal["accepted", "no_candidate", "no_hypothesis"]
```

Steps:
1. **Observe**: receive a MarketSnapshot
2. **Propose**: call proposer.propose(snapshot, budget) → list of hypotheses
3. **Evaluate**: for each hypothesis, run validate_factor with OHLCV data → collect ValidationResults
4. **Filter**: keep only those with passed=True
5. **Decide**: if validated candidates exist, call decision_provider.decide() → TradeDecision or None
6. Return CycleResult with all intermediate state

### MultiCycleRunner
Runs multiple cycles from a list of snapshots:

```python
def run_cycles(
    snapshots: list[MarketSnapshot],
    ohlcv_data: dict[str, pd.DataFrame],  # instrument -> OHLCV
    proposer: Proposer,
    decision_provider: DecisionProvider,
    search_budget: int = 5,
) -> list[CycleResult]:
```

Must proceed **without human approval** between cycles. Each cycle is independent.

## Files to create
- `src/factor_atlas/proposer.py` — Proposer protocol + FixtureProposer
- `src/factor_atlas/decision.py` — DecisionProvider protocol + FixtureDecisionProvider
- `src/factor_atlas/orchestrator.py` — CycleRunner + MultiCycleRunner + CycleResult
- `tests/test_orchestrator.py` — cycle tests

## Important implementation details
- `from __future__ import annotations` in all files
- FixtureProposer generates hypotheses from the registered factor vocabulary for the snapshot's instrument
- FixtureDecisionProvider picks the candidate with the highest Sharpe ratio
- If no hypotheses proposed, CycleResult.status = "no_hypothesis"
- If no candidates pass validation, CycleResult.status = "no_candidate"  
- If a decision is made, CycleResult.status = "accepted"
- The runner MUST NOT pause for human approval between cycles
- Use uuid4 for cycle_id generation (deterministic uuids via uuid5 in fixture mode)
- All Protocols should use `typing.Protocol` with `runtime_checkable`
- Import OHLCV fixture data from `factor_atlas.fixtures.events` for testing

## Acceptance Criteria
1. The runner proceeds without human approval pause
2. No passing candidate produces no order (status="no_candidate")
3. The decision contains instrument, side, quantity, and rationale
4. Multi-cycle fixture run completes autonomously
5. Candidate allowlist test: decision_provider cannot select non-validated candidates
6. Accepted and no-candidate cycles both demonstrated
7. `uv run pytest tests/test_orchestrator.py -v` passes
8. All prior tests still pass (`uv run pytest tests/ -v`)
9. `uv run ruff check .` clean
10. `uv run ruff format --check .` clean
11. `uv run mypy src/ tests/` clean

## Credential mode
Unused — pure fixtures, no network, no API.

## Verification commands
```bash
uv run pytest tests/test_orchestrator.py -v
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
uv run mypy src/ tests/
```
