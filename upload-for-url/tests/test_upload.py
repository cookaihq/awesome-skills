import json

import upload

BASE = "https://api.foxapi.cc"


def test_build_request_stream_multipart():
    url, headers, body = upload.build_request(
        "stream", base_url=BASE, file_bytes=b"DATA", filename="a.png", auto_cleanup=True
    )
    assert url == BASE + "/v1/files/upload/stream"
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'filename="a.png"' in body
    assert b"DATA" in body
    assert b'name="auto_cleanup"' in body


def test_build_request_base64_json():
    url, headers, body = upload.build_request(
        "base64", base_url=BASE, file_data="Zm9v", file_name="x.bin", auto_cleanup=False
    )
    assert url == BASE + "/v1/files/upload/base64"
    assert headers["Content-Type"] == "application/json"
    payload = json.loads(body)
    assert payload == {"file_data": "Zm9v", "auto_cleanup": False, "file_name": "x.bin"}


def test_build_request_url_json_omits_optional_filename():
    url, headers, body = upload.build_request(
        "url", base_url=BASE, url="https://src/v.mp4", auto_cleanup=True
    )
    assert url == BASE + "/v1/files/upload/url"
    payload = json.loads(body)
    assert payload == {"url": "https://src/v.mp4", "auto_cleanup": True}


import pytest

from client import Resp


def test_run_upload_uses_fallback_transport():
    seen = []

    def transport(method, url, headers, body=None, timeout=60):
        seen.append(headers["Authorization"])
        return Resp(401, None, "") if "bad" in headers["Authorization"] else Resp(200, {"url": "u"}, "")

    resp, used = upload.run_upload("https://api/x", {"Content-Type": "application/json"},
                                   b"{}", ["bad", "good"], transport=transport)
    assert resp.status == 200
    assert used == "good"
    assert seen == ["Bearer bad", "Bearer good"]


def test_interpret_upload_success_returns_json():
    out = upload.interpret_upload(Resp(200, {"url": "https://x/y", "id": "f1", "size": 9}, ""))
    assert out["url"] == "https://x/y"


def test_interpret_upload_413_raises_file_too_large():
    with pytest.raises(upload.UploadError) as ei:
        upload.interpret_upload(Resp(413, {"error": {"message": "文件过大", "type": "file_too_large_error"}}, ""))
    assert ei.value.status == 413
    assert "文件过大" in ei.value.message


def test_interpret_upload_200_without_url_is_error():
    with pytest.raises(upload.UploadError):
        upload.interpret_upload(Resp(200, {"unexpected": True}, ""))
