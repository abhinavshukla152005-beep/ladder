"""Model wiring: Amazon Bedrock in production, a scripted model for offline runs."""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterable, Callable
from typing import Any

from strands.models.bedrock import BedrockModel
from strands.models.model import Model

DEFAULT_MODEL_ID = os.environ.get("LADDER_MODEL_ID", "us.amazon.nova-lite-v1:0")


def bedrock_model(model_id: str = DEFAULT_MODEL_ID, temperature: float = 0.2) -> BedrockModel:
    """Bedrock model using the ambient AWS credentials (sandbox, instance role, or profile)."""
    return BedrockModel(
        model_id=model_id,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        temperature=temperature,
        max_tokens=2048,
        streaming=True,
    )


def json_block(text: str) -> Any:
    """Pull the first JSON object or array out of a model reply, fences and all."""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON found in model output: {text[:200]!r}")


class ScriptedModel(Model):
    """Deterministic stand-in for Bedrock.

    Every stage of the pipeline asks its model for JSON, so a test can supply a
    provider that reads the system prompt and returns a fixed answer. The graph,
    the tools and the metrics stay exactly the same as in production.
    """

    def __init__(self, provider: Callable[[list[dict], str], str], latency_ms: int = 0) -> None:
        self._provider = provider
        self._latency_ms = latency_ms
        self._config = {"model_id": "scripted", "temperature": 0.0}
        self.calls: list[dict] = []

    def get_config(self) -> dict:
        return self._config

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    @property
    def context_window_limit(self) -> int:
        return 200_000

    async def stream(
        self,
        messages: list[dict],
        tool_specs: list[dict] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict]:
        text = self._provider(messages, system_prompt or "")
        self.calls.append({"system_prompt": system_prompt or "", "messages": messages, "reply": text})

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}, "contentBlockIndex": 0}}
        for i in range(0, len(text), 24):
            yield {
                "contentBlockDelta": {"delta": {"text": text[i : i + 24]}, "contentBlockIndex": 0},
            }
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": sum(len(m.get("content", [])) for m in messages),
                    "outputTokens": len(text.split()),
                    "totalTokens": len(text.split()),
                },
                "metrics": {"latencyMs": self._latency_ms},
            }
        }

    async def structured_output(
        self,
        output_model: type[Any],
        prompt: list[dict],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[dict]:
        text = self._provider(prompt, system_prompt or "")
        payload = json_block(text)
        yield {"output": output_model(**payload)}
