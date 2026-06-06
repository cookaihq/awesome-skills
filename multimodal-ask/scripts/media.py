from __future__ import annotations

import os
import re
from urllib.parse import urlparse

_YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}

CONTENT_KEY_BY_KIND = {
    "image": "image_url", "video": "video_url", "audio": "audio_url", "file": "file_url",
}
CAPABILITY_BY_KIND = {
    "image": "vision", "video": "video", "audio": "audio", "file": "file",
}


def classify_source(s: str) -> str:
    """Return 'youtube' | 'url' | 'local' for a media reference."""
    low = s.strip().lower()
    if low.startswith("http://") or low.startswith("https://"):
        host = urlparse(s.strip()).netloc.lower()
        if host in _YOUTUBE_HOSTS:
            return "youtube"
        return "url"
    return "local"


def normalize_youtube(url: str) -> str:
    """Rewrite YouTube Shorts URLs to the watch?v= form (Shorts URLs are rejected upstream)."""
    m = re.search(r"youtube\.com/shorts/([A-Za-z0-9_-]+)", url)
    if m:
        return "https://www.youtube.com/watch?v=" + m.group(1)
    return url
