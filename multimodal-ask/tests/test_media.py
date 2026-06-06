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
