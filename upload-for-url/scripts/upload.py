from __future__ import annotations

import json

from client import encode_multipart


def build_request(mode, *, base_url, file_bytes=None, filename=None, file_data=None,
                  url=None, file_name=None, auto_cleanup=True) -> tuple:
    """Return (full_url, headers_without_auth, body_bytes) for one upload mode."""
    if mode == "stream":
        fields = {"auto_cleanup": "true" if auto_cleanup else "false"}
        if file_name:
            fields["file_name"] = file_name
        ctype, body = encode_multipart(fields, "file", filename, file_bytes)
        return base_url + "/v1/files/upload/stream", {"Content-Type": ctype}, body
    if mode == "base64":
        payload = {"file_data": file_data, "auto_cleanup": auto_cleanup}
        if file_name:
            payload["file_name"] = file_name
        return (base_url + "/v1/files/upload/base64",
                {"Content-Type": "application/json"}, json.dumps(payload).encode())
    if mode == "url":
        payload = {"url": url, "auto_cleanup": auto_cleanup}
        if file_name:
            payload["file_name"] = file_name
        return (base_url + "/v1/files/upload/url",
                {"Content-Type": "application/json"}, json.dumps(payload).encode())
    raise ValueError("unknown upload mode: %r" % mode)
