import pytest

import upload_helper
from client import Resp


def test_upload_local_file_success(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"VIDEO")
    seen = {}

    def transport(method, url, headers, body=None, timeout=60):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")
        return Resp(200, {"url": "https://files/clip.mp4", "id": "f1", "size": 5}, "")

    out = upload_helper.upload_local_file(str(f), ["k1"], base_url="https://api.x", transport=transport)
    assert out == "https://files/clip.mp4"
    assert seen["url"] == "https://api.x/v1/files/upload/stream"
    assert seen["auth"] == "Bearer k1"


def test_upload_local_file_error_raises(tmp_path):
    f = tmp_path / "big.mp4"
    f.write_bytes(b"x")

    def transport(method, url, headers, body=None, timeout=60):
        return Resp(413, {"error": {"message": "文件过大"}}, "")

    with pytest.raises(upload_helper.UploadHelperError) as ei:
        upload_helper.upload_local_file(str(f), ["k1"], base_url="https://api.x", transport=transport)
    assert ei.value.status == 413
    assert "请压缩" in ei.value.message   # hint from _HINTS[413], not just the upstream echo
    assert "上游" in ei.value.message     # upstream message section present


def test_upload_local_file_200_without_url_raises(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"x")

    def transport(method, url, headers, body=None, timeout=60):
        return Resp(200, {"id": "f1"}, "")  # 200 but no url field

    with pytest.raises(upload_helper.UploadHelperError) as ei:
        upload_helper.upload_local_file(str(f), ["k1"], base_url="https://api.x", transport=transport)
    assert ei.value.status == 200
    assert "缺少 url" in ei.value.message


def test_upload_local_file_urlerror_propagates(tmp_path):
    import urllib.error
    f = tmp_path / "x.bin"
    f.write_bytes(b"x")

    def transport(method, url, headers, body=None, timeout=60):
        raise urllib.error.URLError("boom")

    with pytest.raises(urllib.error.URLError):
        upload_helper.upload_local_file(str(f), ["k1"], base_url="https://api.x", transport=transport)
