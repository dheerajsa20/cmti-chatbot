"""The only module that talks to OpenAI. Uses the Chat Completions API of the official openai SDK."""
import time

import openai
from openai import OpenAI

from app.config import settings


class ChatError(Exception):
    """An error with a message that is safe to show to the user, and an HTTP status for the API."""

    def __init__(self, status: int, user_message: str):
        super().__init__(user_message)
        self.status = status
        self.user_message = user_message


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if not settings.openai_api_key:
        raise ChatError(503, "The assistant is not configured yet. Please contact CMTI at cmtioffice@cmti.co.in.")
    if _client is None:
        # max_retries=1 keeps most replies under the 5-second target while surviving one network blip.
        _client = OpenAI(api_key=settings.openai_api_key, timeout=settings.request_timeout_s, max_retries=1)
    return _client


def complete(messages: list[dict]) -> tuple[str, int, int]:
    """Returns (reply_text, latency_ms, total_tokens). Raises ChatError with a friendly message on failure."""
    client = _get_client()
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_output_tokens,
        )
    except openai.RateLimitError:
        raise ChatError(429, "I'm receiving too many requests right now. Please wait a few seconds and try again.")
    except openai.APITimeoutError:
        raise ChatError(504, "The reply took too long. Please try again in a moment.")
    except openai.APIConnectionError:
        raise ChatError(503, "I couldn't reach the AI service. Please check your connection and try again.")
    except openai.AuthenticationError:
        raise ChatError(503, "The assistant is temporarily unavailable. Please contact CMTI at cmtioffice@cmti.co.in.")
    except openai.BadRequestError:
        raise ChatError(400, "I couldn't process that message. Please rephrase it and try again.")
    except openai.APIStatusError:
        raise ChatError(502, "The AI service had a problem. Please try again shortly.")
    latency_ms = round((time.perf_counter() - started) * 1000)
    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        raise ChatError(502, "I didn't get a reply. Please try asking again.")
    tokens = response.usage.total_tokens if response.usage else 0
    return reply, latency_ms, tokens
