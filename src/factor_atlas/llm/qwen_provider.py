"""Qwen LLM provider via Bitget's OpenAI-compatible endpoint."""

from __future__ import annotations

import json
import os

import httpx


class QwenProvider:
    """LLM provider backed by Qwen 3.8 Max via Bitget hackathon endpoint.

    Uses the OpenAI-compatible chat completions API at
    ``https://hackathon.bitgetops.com/v1``.

    Reads ``BITGET_QWEN_API_KEY`` from environment.
    """

    DEFAULT_MODEL = "qwen3.8-max"
    BASE_URL = "https://hackathon.bitgetops.com/v1"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self._model = model
        self._api_key = os.environ.get("BITGET_QWEN_API_KEY", "")
        if not self._api_key:
            msg = "BITGET_QWEN_API_KEY not set in environment"
            raise RuntimeError(msg)

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion request and return the text response."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.7,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        response = httpx.post(
            f"{self.BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                return content
        return json.dumps(data)


__all__ = ["QwenProvider"]
