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


_LLM_HINTS = {
    "no_available_model": "模型未配置或不可用",
    "model_not_support_capability": "该模型不支持本次内容类型组合",
    "model_rule_violation": "违反模型规则（如视频过大 / 多视频等）",
    "invalid_param": "参数非法（含 max_tokens 家族约束）",
}


class LLMError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class PollTimeout(Exception):
    pass


class TaskFailed(Exception):
    pass


def _llm_error_message(resp) -> str:
    code = ""
    server = ""
    if isinstance(resp.json, dict) and isinstance(resp.json.get("error"), dict):
        err = resp.json["error"]
        code = err.get("code") or err.get("type") or ""
        server = err.get("message") or ""
    hint = _LLM_HINTS.get(code, "")
    parts = ["[HTTP %s]" % resp.status]
    if code:
        parts.append(code)
    if hint:
        parts.append(hint)
    if server:
        parts.append("| 上游: " + server)
    return " ".join(parts)


def submit_llm(body: dict, keys: list, *, base_url: str, transport=None) -> tuple:
    """POST the llm-custom task. Returns (submit_json, used_key). Raises LLMError on non-200."""
    if transport is None:
        transport = http_request
    url = base_url + "/v1/llm/generations"
    payload = json.dumps(body).encode()

    def attempt(key):
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key}
        return transport("POST", url, headers, payload)

    resp, used = call_with_key_fallback(keys, attempt)
    if resp.status == 200 and isinstance(resp.json, dict) and resp.json.get("id"):
        return resp.json, used
    raise LLMError(resp.status, _llm_error_message(resp))


def poll_task(task_id: str, key: str, *, base_url: str, transport=None,
              interval: int = 5, timeout: int = 300, sleep=None) -> dict:
    """Poll GET /v1/tasks/{id}?sync_upstream=true until status is completed/failed.
    Returns the terminal task json. Raises PollTimeout if it never reaches terminal."""
    if transport is None:
        transport = http_request
    if sleep is None:
        sleep = time.sleep
    url = base_url + "/v1/tasks/" + task_id + "?sync_upstream=true"
    headers = {"Authorization": "Bearer " + key}
    max_polls = max(1, timeout // interval)
    for i in range(max_polls + 1):
        resp = transport("GET", url, headers, None)
        if isinstance(resp.json, dict) and resp.json.get("status") in ("completed", "failed"):
            return resp.json
        if i < max_polls:
            sleep(interval)
    raise PollTimeout("任务 %s 轮询超时（可能仍在运行），可凭 task_id 稍后手动查询" % task_id)


def extract_text(task_json: dict) -> str:
    """Return the assistant text from a terminal task. Raises TaskFailed on failure or
    malformed result. Note: thinking models may legitimately return empty content."""
    if task_json.get("status") == "failed":
        err = task_json.get("error") or {}
        raise TaskFailed("任务失败: [%s] %s"
                         % (err.get("code") or err.get("type") or "?", err.get("message") or ""))
    results = task_json.get("results") or []
    if not results or not isinstance(results[0], dict):
        raise TaskFailed("任务已终态但无 results")
    choices = results[0].get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise TaskFailed("结果无 choices")
    message = choices[0].get("message") or {}
    return message.get("content") or ""
