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
