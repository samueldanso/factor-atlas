"""LLM provider protocol and fixture implementation."""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from factor_atlas.config import FACTOR_VOCABULARY, INSTRUMENTS
from factor_atlas.factors import PARAM_SCHEMAS

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Provider-neutral interface to a language model."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt pair and get a text response."""
        ...

    @property
    def model_name(self) -> str:
        """Return the model identifier for audit logging."""
        ...


# ---------------------------------------------------------------------------
# FixtureLLMProvider
# ---------------------------------------------------------------------------


class FixtureLLMProvider:
    """Deterministic LLM provider that returns pre-built JSON responses.

    Credential-free. Generates valid responses from the factor registry
    so the full pipeline can be tested without an API key.
    """

    @property
    def model_name(self) -> str:
        return "fixture-llm-v1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return deterministic JSON based on prompt content."""
        if "propose" in system_prompt.lower() or "hypothes" in system_prompt.lower():
            return self._propose_response(user_prompt)
        if "decide" in system_prompt.lower() or "select" in system_prompt.lower():
            return self._decide_response(user_prompt)
        return json.dumps({"error": "unrecognized prompt"})

    # -- helpers ----------------------------------------------------------

    def _propose_response(self, user_prompt: str) -> str:
        """Build a valid proposal JSON from registered factors."""
        instrument = self._extract_instrument(user_prompt)
        factors = sorted(FACTOR_VOCABULARY)[:3]
        hypotheses: list[dict[str, object]] = []
        for factor_name in factors:
            schema = PARAM_SCHEMAS[factor_name]
            params: dict[str, float] = {}
            for pname, (lo, hi) in schema.items():
                params[pname] = round((lo + hi) / 2, 4)
            hypotheses.append(
                {
                    "factor_name": factor_name,
                    "parameters": params,
                    "lookback": 30,
                    "instruments": [instrument],
                    "direction": "long",
                    "entry_rule": "signal > 0",
                    "exit_rule": "signal reverses or stop loss",
                    "rationale": f"Fixture LLM hypothesis for {factor_name}",
                }
            )
        return json.dumps({"hypotheses": hypotheses})

    def _decide_response(self, user_prompt: str) -> str:
        """Pick the first candidate (index 0)."""
        return json.dumps(
            {
                "selected_index": 0,
                "rationale": "Fixture LLM: selecting highest-ranked candidate",
            }
        )

    @staticmethod
    def _extract_instrument(prompt: str) -> str:
        """Find the first known instrument in prompt text."""
        for inst in sorted(INSTRUMENTS):
            if inst in prompt:
                return inst
        return min(INSTRUMENTS)


def strip_code_fence(text: str) -> str:
    """Strip markdown code fences from LLM output before JSON parsing."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop opening fence (```json or ```)
        start = 1
        # Drop closing fence
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()
    return text


__all__ = [
    "FixtureLLMProvider",
    "LLMProvider",
    "strip_code_fence",
]
