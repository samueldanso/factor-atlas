# FactorAtlas Execution Checklist

## Planning gate

- [ ] Human approves `docs/specs/technical-spec.md`
- [ ] Human approves `tasks/plan.md`
- [ ] Confirm exact rToken instruments and data availability

## Build sequence

- [ ] T1 — typed contracts and fixture event stream
- [ ] T2 — factor registry and deterministic validation
- [ ] T3 — autonomous discovery-and-decision cycle
- [ ] Checkpoint A — review autonomous loop
- [ ] T4 — risk gates and automatic paper broker
- [ ] T5 — audit and deterministic replay
- [ ] Checkpoint B — review simulator evidence
- [ ] T6 — safe LLM proposer/decision boundary
- [ ] T7 — optional read-only/Demo adapter
- [ ] T8 — runnable demo and submission evidence

## Verification gate

- [ ] `uv sync`
- [ ] `uv run pytest`
- [ ] `uv run ruff check .`
- [ ] Type check passes
- [ ] Accepted autonomous cycle recorded
- [ ] Rejected autonomous cycle recorded
- [ ] No live trading or withdrawal path
