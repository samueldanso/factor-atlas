"""Prompt templates for LLM-based proposer and decision provider."""

from __future__ import annotations

from factor_atlas.config import FACTOR_VOCABULARY, INSTRUMENTS
from factor_atlas.contracts import FactorHypothesis, MarketSnapshot, ValidationResult
from factor_atlas.factors import PARAM_SCHEMAS

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_FACTOR_DESCRIPTIONS: str = "\n".join(
    f"  - {name}: params {dict(PARAM_SCHEMAS[name])}"
    for name in sorted(FACTOR_VOCABULARY)
)

_INSTRUMENT_LIST: str = ", ".join(sorted(INSTRUMENTS))

PROPOSE_SYSTEM: str = f"""\
You are a quantitative factor research assistant for the FactorAtlas agent.
You MUST propose factor hypotheses using ONLY the registered factors below.
You MUST NOT invent new factors, generate code, or reference factors not in this list.

Registered factors:
{_FACTOR_DESCRIPTIONS}

Valid instruments: {_INSTRUMENT_LIST}

Respond with a JSON object containing a single key "hypotheses" whose value is
a list of objects.  Each object MUST have these keys:
  factor_name, parameters, lookback, instruments, direction, entry_rule,
  exit_rule, rationale

direction must be "long" or "short".
instruments must be a list of valid instrument strings.
parameters must have numeric values within the schema ranges above.

Return ONLY raw JSON — no markdown, no code fences, no explanation.
"""

DECIDE_SYSTEM: str = """\
You are a trade-selection assistant for the FactorAtlas agent.
You MUST select ONLY from the validated candidates presented to you.
You MUST NOT invent new trades, override risk gates, or recommend
candidates that failed validation.

Respond with a JSON object:
  {"selected_index": <int>, "rationale": "<string>"}

selected_index is the 0-based index into the candidates list.
If none of the candidates are acceptable, respond:
  {"selected_index": null, "rationale": "<reason>"}

Return ONLY raw JSON — no markdown, no code fences, no explanation.
"""


# ---------------------------------------------------------------------------
# User prompts
# ---------------------------------------------------------------------------


def propose_user_prompt(snapshot: MarketSnapshot, budget: int) -> str:
    """Build the user prompt for hypothesis proposal."""
    return (
        f"Market snapshot for {snapshot.instrument}:\n"
        f"  timestamp: {snapshot.timestamp.isoformat()}\n"
        f"  open={snapshot.open}, high={snapshot.high}, "
        f"low={snapshot.low}, close={snapshot.close}, volume={snapshot.volume}\n\n"
        f"Propose up to {budget} factor hypotheses as JSON."
    )


def decide_user_prompt(
    snapshot: MarketSnapshot,
    candidates: list[tuple[FactorHypothesis, ValidationResult]],
    cycle_id: str,
) -> str:
    """Build the user prompt for trade selection."""
    lines = [
        f"Cycle: {cycle_id}",
        f"Instrument: {snapshot.instrument}",
        f"Price: {snapshot.close}",
        "",
        "Validated candidates:",
    ]
    for idx, (hyp, val) in enumerate(candidates):
        lines.append(
            f"  [{idx}] factor={hyp.factor_name}, "
            f"direction={hyp.direction}, "
            f"sharpe={val.metrics.sharpe_ratio.value:.4f}, "
            f"max_dd={val.metrics.max_drawdown.value:.4f}, "
            f"passed={val.passed}"
        )
    lines.append("")
    lines.append("Select the best candidate by index, or null if none.")
    return "\n".join(lines)


__all__ = [
    "DECIDE_SYSTEM",
    "PROPOSE_SYSTEM",
    "decide_user_prompt",
    "propose_user_prompt",
]
