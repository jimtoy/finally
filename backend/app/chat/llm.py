"""LiteLLM -> OpenRouter client for the chat assistant (PLAN.md sec 9).

Every failure mode the provider can produce — transport error, timeout, empty or
non-conforming content — surfaces as a single `LlmError` so the service layer has
one thing to catch.
"""

from __future__ import annotations

import os

from pydantic import ValidationError

from .schemas import LlmChatOutput

MODEL = "openrouter/openai/gpt-oss-120b"
REQUEST_TIMEOUT_SECONDS = 60.0

_TRUTHY = {"1", "true", "yes", "on"}


class LlmError(Exception):
    """The provider call failed or returned something we cannot use."""


def is_mock_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() in _TRUTHY


def get_api_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "").strip()


async def complete(messages: list[dict]) -> LlmChatOutput:
    """One structured-output completion. Raises `LlmError` on any failure."""
    import litellm  # imported lazily: it is slow to import and unused in mock mode

    try:
        response = await litellm.acompletion(
            model=MODEL,
            messages=messages,
            api_key=get_api_key(),
            response_format=LlmChatOutput,
            temperature=0.2,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise LlmError(f"LLM provider call failed: {exc}") from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise LlmError(f"Unexpected LLM response shape: {exc}") from exc

    if not content:
        raise LlmError("LLM returned an empty response.")

    try:
        return LlmChatOutput.model_validate_json(content)
    except ValidationError as exc:
        raise LlmError(f"LLM response did not match the required schema: {exc}") from exc
