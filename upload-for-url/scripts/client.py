from __future__ import annotations

import json as _json
import urllib.error
import urllib.request
from collections import namedtuple

DEFAULT_BOUNDARY = "----foxapiUploadBoundaryXyZ"

Resp = namedtuple("Resp", "status json text")


def encode_multipart(fields: dict, file_field: str, filename: str,
                     file_bytes: bytes, boundary: str = DEFAULT_BOUNDARY) -> tuple:
    """Build a multipart/form-data body. Returns (content_type, body_bytes)."""
    b = boundary.encode()
    crlf = b"\r\n"
    chunks = []
    for name, value in fields.items():
        chunks.append(b"--" + b + crlf)
        chunks.append(('Content-Disposition: form-data; name="%s"' % name).encode() + crlf)
        chunks.append(crlf)
        chunks.append(str(value).encode() + crlf)
    chunks.append(b"--" + b + crlf)
    chunks.append(
        ('Content-Disposition: form-data; name="%s"; filename="%s"' % (file_field, filename)).encode() + crlf
    )
    chunks.append(b"Content-Type: application/octet-stream" + crlf)
    chunks.append(crlf)
    chunks.append(file_bytes + crlf)
    chunks.append(b"--" + b + b"--" + crlf)
    return "multipart/form-data; boundary=" + boundary, b"".join(chunks)


def http_request(method: str, url: str, headers: dict,
                 body: "bytes | None" = None, timeout: int = 60) -> Resp:
    """Perform an HTTP request. Returns Resp(status, json, text) for any HTTP
    status (including 4xx/5xx). Raises urllib.error.URLError only on network
    failure (caller treats that as fatal, not a key-fallback trigger)."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code
    text = raw.decode("utf-8", "replace") if raw else ""
    try:
        parsed = _json.loads(text) if text else None
    except ValueError:
        parsed = None
    return Resp(status, parsed, text)
