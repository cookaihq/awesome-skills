from __future__ import annotations

from media import CONTENT_KEY_BY_KIND


def build_messages(prompt: "str | None", system: "str | None", media: list) -> list:
    """Build OpenAI-compatible messages[]. `media` is a list of (kind, url) where kind in
    {image,video,audio,file}. Content is always an array of typed blocks.
    An empty/None prompt yields no text block (intentional — avoids an empty text block).
    The caller (ask.py) must ensure at least one of prompt or media is provided, so content
    is never empty."""
    content = []
    if prompt:
        content.append({"type": "text", "text": prompt})
    for kind, url in media:
        key = CONTENT_KEY_BY_KIND[kind]
        content.append({"type": key, key: {"url": url}})
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": content})
    return msgs
