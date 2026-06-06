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


def test_main_success_prints_url_and_72h_notice(monkeypatch, tmp_path, capsys):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"VIDEOBYTES")
    monkeypatch.setenv("X_API_KEY", "sk-abcd1234efgh")

    def fake_transport(method, url, headers, body=None, timeout=60):
        assert url.endswith("/v1/files/upload/stream")
        return Resp(200, {"url": "https://files/x.mp4", "id": "f9", "size": 10}, "")

    monkeypatch.setattr(upload, "http_request", fake_transport)
    code = upload.main(["--file", str(f)])
    out = capsys.readouterr()
    assert code == 0
    assert out.out.strip() == "https://files/x.mp4"          # stdout = pure URL
    assert "72" in out.err                                    # 72h notice on stderr
    assert "sk-abcd1234efgh" not in out.err                   # key never printed raw
    assert "sk-a****efgh" in out.err                          # masked


def test_main_no_key_returns_2(monkeypatch, tmp_path, capsys):
    f = tmp_path / "a.bin"
    f.write_bytes(b"x")
    monkeypatch.delenv("X_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env / .env.local here
    code = upload.main(["--file", str(f)])
    assert code == 2


def test_main_413_returns_1(monkeypatch, tmp_path, capsys):
    f = tmp_path / "big.mp4"
    f.write_bytes(b"x")
    monkeypatch.setenv("X_API_KEY", "sk-abcd1234efgh")
    monkeypatch.setattr(upload, "http_request",
                        lambda *a, **k: Resp(413, {"error": {"message": "文件过大"}}, ""))
    code = upload.main(["--file", str(f)])
    assert code == 1
    assert "文件过大" in capsys.readouterr().err
