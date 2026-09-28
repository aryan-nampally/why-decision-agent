"""LLM client: JSON-only completions validated against a Pydantic model.

The recommended open models occasionally return malformed JSON, so every call
is validated, retried once with the validation error, and otherwise raises
LLMError so callers can fall back safely.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import TypeVar

from openai import AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_RPM

T = TypeVar("T", bound=BaseModel)
_client: AsyncOpenAI | None = None
_model = LLM_MODEL
USAGE = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}  # process-wide counters (performance evaluation)


def use_model(name: str) -> None:
    """Switch the model for this process (the benchmark runs on a model with its own quota)."""
    global _model
    _model = name


def current_model() -> str:
    return _model


_pace_lock: asyncio.Lock | None = None
_last_call = 0.0


async def _pace() -> None:
    """Space requests to respect a provider's requests-per-minute limit (LLM_RPM)."""
    global _pace_lock, _last_call
    if not LLM_RPM:
        return
    if _pace_lock is None:
        _pace_lock = asyncio.Lock()
    async with _pace_lock:
        gap = 60.0 / LLM_RPM - (time.monotonic() - _last_call)
        if gap > 0:
            await asyncio.sleep(gap)
        _last_call = time.monotonic()


def _extra() -> dict:
    # gpt-oss models accept a reasoning effort; low keeps token use (and free-tier quota) down
    return {"reasoning_effort": "low"} if "gpt-oss" in _model else {}


class LLMError(RuntimeError):
    pass


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=60, max_retries=1)
    return _client


def _parse(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


async def complete_json(system: str, user: str, model: type[T], retries: int = 1) -> T:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_err = ""
    waits = 0
    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            await _pace()
            resp = await client().chat.completions.create(
                model=_model, messages=messages, temperature=0,
                response_format={"type": "json_object"}, extra_body=_extra(),
            )
            USAGE["calls"] += 1
            if resp.usage:
                USAGE["prompt_tokens"] += resp.usage.prompt_tokens or 0
                USAGE["completion_tokens"] += resp.usage.completion_tokens or 0
            content = resp.choices[0].message.content or ""
            return model.model_validate(_parse(content))
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = str(e)[:500]
            messages = messages[:2] + [
                {"role": "user", "content": f"Your previous reply was invalid: {last_err}\nReturn only valid JSON matching the requested schema."}
            ]
        except RateLimitError as e:
            msg = str(e)
            if "per day" in msg or waits >= 8:
                last_err = f"RateLimitError: {msg}"[:500]
                break  # daily quota exhausted (or persistent throttling): retrying cannot help
            m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", msg)
            delay = (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else 10.0
            waits += 1
            attempt -= 1  # a per-minute throttle is not a failed attempt
            await asyncio.sleep(min(delay + 0.5, 65))
        except Exception as e:  # network / provider errors
            last_err = f"{type(e).__name__}: {e}"[:500]
    raise LLMError(last_err)


async def complete_text(system: str, user: str) -> str:
    await _pace()
    resp = await client().chat.completions.create(
        model=_model, temperature=0, extra_body=_extra(),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return (resp.choices[0].message.content or "").strip()
