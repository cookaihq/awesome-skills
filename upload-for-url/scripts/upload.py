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


from client import call_with_key_fallback, http_request

ERROR_HINTS = {
    400: "请求格式错误",
    401: "鉴权失败（key 无效 / 缺失 / 权限不足）",
    403: "存储空间不足（如使用了 --no-auto-cleanup）",
    413: "文件过大，请压缩或更换更小的文件",
    429: "请求频率超限，请稍后再试（不自动重试）",
    500: "服务器内部错误",
}


class UploadError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def run_upload(full_url, headers, body, keys, transport=None) -> tuple:
    # Resolve the default transport at call time (not as a default-arg value) so
    # monkeypatch.setattr(upload, "http_request", fake) is picked up by main()'s calls.
    if transport is None:
        transport = http_request

    def attempt(key):
        h = dict(headers)
        h["Authorization"] = "Bearer " + key
        return transport("POST", full_url, h, body)

    return call_with_key_fallback(keys, attempt)


def interpret_upload(resp) -> dict:
    if resp.status == 200 and resp.json and resp.json.get("url"):
        return resp.json
    hint = ERROR_HINTS.get(resp.status, "未预期的响应")
    server_msg = ""
    if resp.json and isinstance(resp.json.get("error"), dict):
        server_msg = resp.json["error"].get("message", "")
    message = "[HTTP %s] %s" % (resp.status, hint)
    if server_msg:
        message += " | 上游: " + server_msg
    raise UploadError(resp.status, message)
