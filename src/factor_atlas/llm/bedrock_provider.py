"""AWS Bedrock LLM provider using Claude via boto3."""

from __future__ import annotations

import json
import os


class BedrockProvider:
    """LLM provider backed by AWS Bedrock (Claude Sonnet 4.6).

    Reads AWS_REGION and AWS_PROFILE from environment.
    Falls back to us-east-1 region if AWS_REGION is not set.
    """

    DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID) -> None:
        import boto3

        self._model_id = model_id
        session_kwargs: dict[str, str] = {}
        profile = os.environ.get("AWS_PROFILE")
        if profile:
            session_kwargs["profile_name"] = profile

        region = os.environ.get("AWS_REGION", "us-east-1")
        session = boto3.Session(**session_kwargs)
        self._client = session.client("bedrock-runtime", region_name=region)

    @property
    def model_name(self) -> str:
        return self._model_id

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Invoke Claude on Bedrock and return the text response."""
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
        )
        response = self._client.invoke_model(modelId=self._model_id, body=body)
        result: dict[str, object] = json.loads(response["body"].read())
        content = result.get("content", [])
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                text = first.get("text", "")
                if isinstance(text, str):
                    return text
        return json.dumps(result)


__all__ = ["BedrockProvider"]
