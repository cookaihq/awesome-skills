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
    assert "文件过大" in ei.value.message
