from __future__ import annotations

import hashlib
import json


def dedup_key(model, prompt, system, sources: list, max_tokens, temperature, top_p, stop) -> str:
    """Stable hash identifying a request for same-round duplicate-submit guarding.
    Keyed on the USER INPUT media sources (local paths / original URLs / YouTube links),
    NOT post-upload aihubmax URLs — the same file yields a new upload URL each time, so
    using the uploaded URL would defeat dedup. Sources are sorted (order-independent)."""
    payload = {
        "model": model,
        "prompt": prompt or "",
        "system": system or "",
        "sources": sorted(sources or []),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stop": stop,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
