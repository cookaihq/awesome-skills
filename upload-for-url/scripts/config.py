from __future__ import annotations


def parse_dotenv(text: str) -> dict:
    """Minimal, non-shell .env parser. Supports KEY=value / KEY="value" /
    KEY='value', whitespace around =, leading-# comment lines, blank lines.
    Last occurrence wins. No ${X} / $(...) / line-continuation expansion."""
    out: dict = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        out[key] = val
    return out


def read_key_from_dotenv(path: str) -> "str | None":
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    return parse_dotenv(text).get("X_API_KEY")
