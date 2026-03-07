"""Thin async wrapper around Google Gemini API (vision + text)."""

from __future__ import annotations

import logging
import time

from google import genai
from google.genai import errors as genai_errors, types

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


class LLMError(Exception):
    """Raised when the LLM API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(api_version="v1beta"),
        )
    return _client


async def call_vision(
    image_bytes: bytes,
    media_type: str,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> tuple[str, int]:
    """Send an image to Gemini vision model and return (text_response, latency_ms)."""
    client = _get_client()
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=media_type)

    t0 = time.perf_counter()
    try:
        response = await client.aio.models.generate_content(
            model=model or settings.GEMINI_MODEL,
            contents=[user_prompt, image_part],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                max_output_tokens=4096,
            ),
        )
    except genai_errors.ClientError as exc:
        logger.error("Gemini API error: %s", exc)
        raise LLMError(str(exc), status_code=exc.code) from exc

    latency_ms = int((time.perf_counter() - t0) * 1000)
    text = response.text or ""
    logger.info("Gemini vision call completed in %dms (%d chars)", latency_ms, len(text))
    return text, latency_ms


async def call_text(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> str:
    """Plain text completion (used for JSON repair and OCR parsing)."""
    client = _get_client()

    try:
        response = await client.aio.models.generate_content(
            model=model or settings.GEMINI_MODEL,
            contents=[user_prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                max_output_tokens=4096,
            ),
        )
    except genai_errors.ClientError as exc:
        logger.error("Gemini API error: %s", exc)
        raise LLMError(str(exc), status_code=exc.code) from exc

    return response.text or ""
