"""Shared config helpers for the xhs-downloader skill.

Layered, non-shell .env reading (repo CLAUDE.md convention) and credential
masking. Pure functions only — no side effects, fully unit-testable.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def parse_env_file(path: Path) -> dict:
    """Minimal, non-shell .env parser.

    Supports `KEY=value`, `KEY="value"`, `KEY='value'`, whitespace around `=`,
    `#` full-line comments, blank lines. Same key -> last wins. No `${X}`/`$(...)`
    expansion, no line continuation. Values are literal strings.
    """
    result: dict = {}
    if not path or not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            result[key] = val
    return result


def read_layered(
    name: str,
    cwd: Optional[Path] = None,
    home_config: Optional[Path] = None,
    env: Optional[dict] = None,
) -> Optional[str]:
    """First-found-wins across: process env -> cwd/.env.local -> cwd/.env -> home_config.

    `home_config` is only consulted when the caller passes it (caller enforces the
    --use-local-key gate). Files are NOT searched recursively upward.
    """
    env = os.environ if env is None else env
    if env.get(name):
        return env[name]
    cwd = Path.cwd() if cwd is None else cwd
    for fname in (".env.local", ".env"):
        val = parse_env_file(cwd / fname).get(name)
        if val:
            return val
    if home_config is not None:
        val = parse_env_file(home_config).get(name)
        if val:
            return val
    return None


def mask(secret: str) -> str:
    """Mask a credential as head4****tail4; reveal nothing if too short."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}****{secret[-4:]}"
