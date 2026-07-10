"""Thin wrapper around the Gemini API for generation and LLM-as-judge calls."""

import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError

from config import settings
from exceptions import LLMResponseError

logger = logging.getLogger(__name__)

# Initialize the official Google GenAI SDK client
_client = genai.Client(api_key=settings.gemini_api_key)

# Transient statuses for retries
_TRANSIENT_STATUSES = {429, 500, 502, 503}


async def _create_completion(system: str, user: str, model: str, temperature: float) -> str | None:
    response = await _client.aio.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    return response.text


async def chat_json(
    system: str, user: str, model: str | None = None, temperature: float = 0.0
) -> dict[str, Any]:
    """Single chat completion constrained to a JSON object; parsed and returned.

    Gemini failures are mapped to LLMResponseError so the API layer returns a
    structured 502 instead of an opaque 500.
    """
    resolved_model = model or settings.judge_model
    try:
        try:
            content = await _create_completion(system, user, resolved_model, temperature)
        except APIError as exc:
            if exc.code not in _TRANSIENT_STATUSES:
                raise
            logger.warning(
                "gemini_transient_error_retrying",
                extra={"status": exc.code, "model": resolved_model},
            )
            await asyncio.sleep(1.0)
            content = await _create_completion(system, user, resolved_model, temperature)
    except APIError as exc:
        raise LLMResponseError(f"Gemini request failed: {exc}") from exc
    except Exception as exc:
        raise LLMResponseError(f"Unexpected error: {exc}") from exc

    if not content:
        raise LLMResponseError("Model returned an empty response")
    try:
        parsed: dict[str, Any] = json.loads(content)
        return parsed
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"Model returned invalid JSON: {content[:200]}") from exc
