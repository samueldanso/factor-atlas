"""LLM boundary layer: provider-neutral interfaces for FactorAtlas."""

from __future__ import annotations

from factor_atlas.llm.bedrock_provider import BedrockProvider
from factor_atlas.llm.decision import LLMDecisionProvider, validate_llm_decision
from factor_atlas.llm.prompts import (
    DECIDE_SYSTEM,
    PROPOSE_SYSTEM,
    decide_user_prompt,
    propose_user_prompt,
)
from factor_atlas.llm.proposer import LLMProposer, validate_llm_hypothesis
from factor_atlas.llm.provider import FixtureLLMProvider, LLMProvider, strip_code_fence

__all__ = [
    "DECIDE_SYSTEM",
    "PROPOSE_SYSTEM",
    "BedrockProvider",
    "FixtureLLMProvider",
    "LLMDecisionProvider",
    "LLMProposer",
    "LLMProvider",
    "decide_user_prompt",
    "propose_user_prompt",
    "strip_code_fence",
    "validate_llm_decision",
    "validate_llm_hypothesis",
]
