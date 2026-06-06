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


def size_warning(path: str, threshold_bytes: int) -> "str | None":
    """If a local media file exceeds the advisory threshold, return a textual warning;
    else None. The threshold is an EMPIRICAL heuristic, NOT the API's hard limit (which
    is unknown and enforced reactively via 413 / model_rule_violation)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size > threshold_bytes:
        mb = size / (1024.0 * 1024.0)
        return ("文件 %s 约 %.1f MB，超过 ~%d MB 经验阈值，上游可能拒绝或任务失败，"
                "建议压缩 / 截取后再传（注：经验提醒，非 API 硬限制）"
                % (os.path.basename(path), mb, threshold_bytes // (1024 * 1024)))
    return None
