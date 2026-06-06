from __future__ import annotations

from client import call_with_key_fallback, http_request


def fetch_models(keys: list, *, base_url: str, transport=None) -> tuple:
    """GET the token's available llm-custom models. Returns (data_list, used_key).
    This config query does not consume credits."""
    if transport is None:
        transport = http_request
    url = base_url + "/v1/configs/llm_generations_models"

    def attempt(key):
        return transport("GET", url, {"Authorization": "Bearer " + key}, None)

    resp, used = call_with_key_fallback(keys, attempt)
    data = resp.json.get("data", []) if isinstance(resp.json, dict) else []
    return data, used


def check_capabilities(models: list, model_id: str, needed_caps: list) -> tuple:
    """Return (ok, reason, suggestions). Advisory only — the API is the final authority.
    capabilities is the union across visible channels."""
    found = next((m for m in models if m.get("id") == model_id), None)
    if found is None:
        return False, "模型 '%s' 不在当前 token 可用清单" % model_id, [m.get("id") for m in models]
    caps = set(found.get("capabilities") or [])
    missing = [c for c in needed_caps if c not in caps]
    if missing:
        suggestions = [m.get("id") for m in models if set(needed_caps) <= set(m.get("capabilities") or [])]
        return False, "模型 '%s' 不支持所需能力 %s" % (model_id, missing), suggestions
    return True, "", []
