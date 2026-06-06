import dedup


def test_dedup_key_stable_and_order_independent_for_sources():
    a = dedup.dedup_key("gpt-5.5", "hi", None, ["/a.png", "/b.mp4"], 64, None, None, None)
    b = dedup.dedup_key("gpt-5.5", "hi", None, ["/b.mp4", "/a.png"], 64, None, None, None)
    assert a == b


def test_dedup_key_changes_with_any_param():
    base = dedup.dedup_key("gpt-5.5", "hi", None, ["/a.png"], 64, None, None, None)
    assert dedup.dedup_key("gpt-5.6", "hi", None, ["/a.png"], 64, None, None, None) != base
    assert dedup.dedup_key("gpt-5.5", "bye", None, ["/a.png"], 64, None, None, None) != base
    assert dedup.dedup_key("gpt-5.5", "hi", None, ["/a.png", "/c.mp3"], 64, None, None, None) != base
    assert dedup.dedup_key("gpt-5.5", "hi", None, ["/a.png"], 128, None, None, None) != base
    assert dedup.dedup_key("gpt-5.5", "hi", "sys", ["/a.png"], 64, None, None, None) != base


def test_dedup_key_uses_input_sources_not_post_upload_urls():
    k1 = dedup.dedup_key("gpt-5.5", "hi", None, ["/local/a.png"], 64, None, None, None)
    k2 = dedup.dedup_key("gpt-5.5", "hi", None, ["/local/a.png"], 64, None, None, None)
    assert k1 == k2
