"""LLM-backed decision provider with safety validation."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from factor_atlas.contracts import (
    FactorHypothesis,
    MarketSnapshot,
    TradeDecision,
    ValidationResult,
)
from factor_atlas.llm.prompts import DECIDE_SYSTEM, decide_user_prompt
from factor_atlas.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safety validation
# ---------------------------------------------------------------------------


def validate_llm_decision(
    data: dict[str, object],
    candidates: list[tuple[FactorHypothesis, ValidationResult]],
    snapshot: MarketSnapshot,
    cycle_id: str,
) -> TradeDecision | None:
    """Validate an LLM decision dict against the validated candidates.

    Returns a TradeDecision if valid, None otherwise.
    Rejects any selection that references a non-validated or out-of-range candidate.
    """
    try:
        selected_index = data.get("selected_index")

        # LLM may explicitly decline
        if selected_index is None:
            logger.info("LLM declined to select a candidate")
            return None

        if not isinstance(selected_index, int):
            logger.warning(
                "LLM returned non-integer selected_index: %s", selected_index
            )
            return None

        if selected_index < 0 or selected_index >= len(candidates):
            logger.warning(
                "LLM selected out-of-range index %d (have %d candidates)",
                selected_index,
                len(candidates),
            )
            return None

        hyp, val = candidates[selected_index]

        # Must be a validated (passed) candidate
        if not val.passed:
            logger.warning(
                "LLM selected non-validated candidate index %d (passed=False)",
                selected_index,
            )
            return None

        rationale = data.get("rationale", "")
        if not isinstance(rationale, str) or not rationale.strip():
            rationale = f"LLM selected candidate {selected_index}"

        side = "buy" if hyp.direction == "long" else "sell"

        return TradeDecision(
            decision_id=str(uuid4()),
            cycle_id=cycle_id,
            hypothesis_id=hyp.hypothesis_id,
            instrument=snapshot.instrument,
            side=side,
            quantity=Decimal(1),
            price=snapshot.close,
            rationale=rationale,
            timestamp=datetime.now(tz=UTC),
        )
    except Exception:
        logger.warning("Failed to validate LLM decision", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# LLMDecisionProvider
# ---------------------------------------------------------------------------


class LLMDecisionProvider:
    """LLM-based decision maker, constrained to validated candidates only.

    If the LLM selects a non-validated candidate, the decision is rejected.
    If the LLM suggests bypassing risk gates, the decision is rejected.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @property
    def model_name(self) -> str:
        """Model identifier for audit logging."""
        return self._provider.model_name

    def decide(
        self,
        snapshot: MarketSnapshot,
        candidates: list[tuple[FactorHypothesis, ValidationResult]],
        cycle_id: str,
    ) -> TradeDecision | None:
        """Ask the LLM to select from validated candidates.

        If the LLM selects a non-validated candidate, reject.
        If candidates is empty, return None without calling the LLM.
        """
        if not candidates:
            return None

        user_prompt = decide_user_prompt(snapshot, candidates, cycle_id)

        try:
            raw = self._provider.complete(DECIDE_SYSTEM, user_prompt)
        except Exception:
            logger.warning("LLM provider failed during decide", exc_info=True)
            return None

        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("LLM returned malformed JSON for decide: %s", raw[:200])
            return None

        if not isinstance(parsed, dict):
            logger.warning("LLM returned non-dict top-level for decide")
            return None

        return validate_llm_decision(parsed, candidates, snapshot, cycle_id)


__all__ = [
    "LLMDecisionProvider",
    "validate_llm_decision",
]
