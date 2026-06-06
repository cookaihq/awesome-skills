import client


def test_encode_multipart_structure():
    ctype, body = client.encode_multipart(
        fields={"auto_cleanup": "true"},
        file_field="file",
        filename="clip.mp4",
        file_bytes=b"\x00\x01BINARY",
        boundary="BOUND123",
    )
    assert ctype == "multipart/form-data; boundary=BOUND123"
    assert b'name="auto_cleanup"' in body
    assert b"true" in body
    assert b'name="file"; filename="clip.mp4"' in body
    assert b"\x00\x01BINARY" in body
    assert body.endswith(b"--BOUND123--\r\n")
    assert body.startswith(b"--BOUND123\r\n")
