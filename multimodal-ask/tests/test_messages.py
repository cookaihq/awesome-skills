import messages


def test_build_messages_text_only():
    msgs = messages.build_messages("count 1 to 3", None, [])
    assert msgs == [{"role": "user", "content": [{"type": "text", "text": "count 1 to 3"}]}]


def test_build_messages_with_system_and_mixed_media():
    media = [("image", "https://x/a.png"), ("video", "https://x/v.mp4"),
             ("audio", "https://x/u.mp3"), ("file", "https://x/d.pdf")]
    msgs = messages.build_messages("describe", "You are terse.", media)
    assert msgs[0] == {"role": "system", "content": "You are terse."}
    content = msgs[1]["content"]
    assert content[0] == {"type": "text", "text": "describe"}
    assert {"type": "image_url", "image_url": {"url": "https://x/a.png"}} in content
    assert {"type": "video_url", "video_url": {"url": "https://x/v.mp4"}} in content
    assert {"type": "audio_url", "audio_url": {"url": "https://x/u.mp3"}} in content
    assert {"type": "file_url", "file_url": {"url": "https://x/d.pdf"}} in content


def test_build_messages_media_without_prompt_has_no_empty_text_block():
    msgs = messages.build_messages(None, None, [("image", "https://x/a.png")])
    content = msgs[0]["content"]
    assert all(b["type"] != "text" for b in content)
    assert content == [{"type": "image_url", "image_url": {"url": "https://x/a.png"}}]
