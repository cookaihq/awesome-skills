from __future__ import annotations

import json
import time

from client import call_with_key_fallback, http_request


def family_of(model: str) -> "str | None":
    m = (model or "").lower()
    if m.startswith("claude"):
        return "claude"
    if m.startswith("gpt"):
        return "gpt"
    if m.startswith("gemini"):
        return "gemini"
    return None


def apply_max_tokens(model: str, max_tokens) -> "int | None":
    """Family rule: claude-* requires max_tokens (default 1024 when missing);
    gpt-*/gemini-*/others optional (omit when missing). User-given values pass through."""
    if max_tokens is not None:
        return max_tokens
    if family_of(model) == "claude":
        return 1024
    return None


def build_submit_body(model, messages, *, max_tokens=None, temperature=None,
                      top_p=None, stop=None, reasoning=False) -> dict:
    body = {"model": model, "messages": messages, "stream": False}
    mt = apply_max_tokens(model, max_tokens)
    if mt is not None:
        body["max_tokens"] = mt
    if temperature is not None:
        body["temperature"] = temperature
    if top_p is not None:
        body["top_p"] = top_p
    if stop is not None:
        body["stop"] = stop
    if reasoning:
        # opt-in passthrough; llm-custom schema doesn't list it but additionalProperties:true.
        body["reasoning"] = True
    return body
