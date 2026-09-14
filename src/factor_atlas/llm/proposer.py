"""LLM-backed proposer with safety validation."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from factor_atlas.config import FACTOR_VOCABULARY, INSTRUMENTS
from factor_atlas.contracts import FactorHypothesis, MarketSnapshot
from factor_atlas.factors import PARAM_SCHEMAS
from factor_atlas.llm.prompts import PROPOSE_SYSTEM, propose_user_prompt
from factor_atlas.llm.provider import LLMProvider, strip_code_fence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safety validation
# ---------------------------------------------------------------------------


def validate_llm_hypothesis(
    data: dict[str, object],
    snapshot: MarketSnapshot,
) -> FactorHypothesis | None:
    """Validate a single hypothesis dict from LLM output.

    Returns a FactorHypothesis if valid, None otherwise.
    Invalid entries are logged as warnings, never surfaced to the pipeline.
    """
    try:
        factor_name = data.get("factor_name")
        if not isinstance(factor_name, str) or factor_name not in FACTOR_VOCABULARY:
            logger.warning("LLM proposed unknown factor: %s", factor_name)
            return None

        params_raw = data.get("parameters")
        if not isinstance(params_raw, dict):
            logger.warning("LLM proposed non-dict parameters for %s", factor_name)
            return None

        # Validate parameters against schema
        schema = PARAM_SCHEMAS[factor_name]
        params: dict[str, float | int | str] = {}
        for pname, (lo, hi) in schema.items():
            val = params_raw.get(pname)
            if val is None or not isinstance(val, (int, float)):
                logger.warning(
                    "LLM proposed invalid param %s=%s for %s", pname, val, factor_name
                )
                return None
            if val < lo or val > hi:
                logger.warning(
                    "LLM proposed out-of-range param %s=%s for %s (range [%s, %s])",
                    pname,
                    val,
                    factor_name,
                    lo,
                    hi,
                )
                return None
            params[pname] = val

        # Validate instruments
        instruments_raw = data.get("instruments")
        if not isinstance(instruments_raw, list) or not instruments_raw:
            logger.warning("LLM proposed empty/invalid instruments for %s", factor_name)
            return None
        for inst in instruments_raw:
            if inst not in INSTRUMENTS:
                logger.warning("LLM proposed unknown instrument: %s", inst)
                return None

        direction = data.get("direction")
        if direction not in ("long", "short"):
            logger.warning("LLM proposed invalid direction: %s", direction)
            return None

        lookback = data.get("lookback")
        if not isinstance(lookback, int) or lookback < 1 or lookback > 500:
            logger.warning("LLM proposed invalid lookback: %s", lookback)
            return None

        entry_rule = data.get("entry_rule", "")
        exit_rule = data.get("exit_rule", "")
        rationale = data.get("rationale", "")
        if not isinstance(entry_rule, str) or not entry_rule.strip():
            return None
        if not isinstance(exit_rule, str) or not exit_rule.strip():
            return None
        if not isinstance(rationale, str) or not rationale.strip():
            return None

        return FactorHypothesis(
            hypothesis_id=str(uuid4()),
            factor_name=factor_name,
            parameters=params,
            lookback=lookback,
            instruments=instruments_raw,
            direction=direction,
            entry_rule=entry_rule,
            exit_rule=exit_rule,
            rationale=rationale,
            created_at=datetime.now(tz=UTC),
        )
    except Exception:
        logger.warning("Failed to validate LLM hypothesis", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# LLMProposer
# ---------------------------------------------------------------------------


class LLMProposer:
    """LLM-based hypothesis proposer, constrained to registered factors.

    Every hypothesis is validated against the factor registry.
    Invalid suggestions are dropped with a warning, not surfaced.
    """

    def __init__(self, provider: LLMProvider, max_hypotheses: int = 5) -> None:
        self._provider = provider
        self._max_hypotheses = max_hypotheses

    @property
    def model_name(self) -> str:
        """Model identifier for audit logging."""
        return self._provider.model_name

    def propose(self, snapshot: MarketSnapshot, budget: int) -> list[FactorHypothesis]:
        """Ask the LLM to suggest factor hypotheses.

        Every hypothesis is validated against the factor registry.
        Invalid suggestions are dropped with a warning, not surfaced.
        """
        effective_budget = min(budget, self._max_hypotheses)
        user_prompt = propose_user_prompt(snapshot, effective_budget)

        try:
            raw = self._provider.complete(PROPOSE_SYSTEM, user_prompt)
        except Exception:
            logger.warning("LLM provider failed during propose", exc_info=True)
            return []

        try:
            parsed = json.loads(strip_code_fence(raw))
        except (json.JSONDecodeError, TypeError):
            logger.warning("LLM returned malformed JSON for propose: %s", raw[:200])
            return []

        if not isinstance(parsed, dict):
            logger.warning("LLM returned non-dict top-level for propose")
            return []

        raw_hypotheses = parsed.get("hypotheses")
        if not isinstance(raw_hypotheses, list):
            logger.warning("LLM returned no 'hypotheses' list")
            return []

        results: list[FactorHypothesis] = []
        for item in raw_hypotheses[:effective_budget]:
            if not isinstance(item, dict):
                continue
            hyp = validate_llm_hypothesis(item, snapshot)
            if hyp is not None:
                results.append(hyp)

        return results


__all__ = [
    "LLMProposer",
    "validate_llm_hypothesis",
]
