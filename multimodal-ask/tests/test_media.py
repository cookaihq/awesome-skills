import media


def test_classify_source():
    assert media.classify_source("/tmp/a.png") == "local"
    assert media.classify_source("./rel/clip.mp4") == "local"
    assert media.classify_source("https://example.com/a.jpg") == "url"
    assert media.classify_source("http://example.com/a.jpg") == "url"
    assert media.classify_source("https://www.youtube.com/watch?v=abc123") == "youtube"
    assert media.classify_source("https://youtu.be/abc123") == "youtube"
    assert media.classify_source("https://youtube.com/shorts/XY_z-12") == "youtube"


def test_normalize_youtube_rewrites_shorts():
    assert media.normalize_youtube("https://www.youtube.com/shorts/XY_z-12") == \
        "https://www.youtube.com/watch?v=XY_z-12"
    watch = "https://www.youtube.com/watch?v=abc123"
    assert media.normalize_youtube(watch) == watch
    short = "https://youtu.be/abc123"
    assert media.normalize_youtube(short) == short


def test_size_warning_under_threshold_returns_none(tmp_path):
    f = tmp_path / "small.bin"
    f.write_bytes(b"x" * 100)
    assert media.size_warning(str(f), 20 * 1024 * 1024) is None


def test_size_warning_over_threshold_returns_message(tmp_path):
    f = tmp_path / "big.mp4"
    f.write_bytes(b"x" * (3 * 1024 * 1024))
    msg = media.size_warning(str(f), 2 * 1024 * 1024)  # 2 MB threshold
    assert msg is not None
    assert "big.mp4" in msg
    assert "经验阈值" in msg and "非 API 硬限制" in msg


def test_size_warning_missing_file_returns_none():
    assert media.size_warning("/nonexistent/x", 1) is None


def test_capability_and_content_maps():
    assert media.CAPABILITY_BY_KIND["image"] == "vision"
    assert media.CONTENT_KEY_BY_KIND["video"] == "video_url"
