import task


def test_family_of():
    assert task.family_of("claude-opus-4-7") == "claude"
    assert task.family_of("gpt-5.5") == "gpt"
    assert task.family_of("gemini-3.5-flash") == "gemini"
    assert task.family_of("kimi-k2.6") is None


def test_apply_max_tokens_defaults_claude_when_missing():
    assert task.apply_max_tokens("claude-opus-4-7", None) == 1024
    assert task.apply_max_tokens("claude-opus-4-7", 64) == 64
    assert task.apply_max_tokens("gemini-3.5-flash", None) is None
    assert task.apply_max_tokens("gpt-5.5", None) is None


def test_build_submit_body_minimal_text():
    body = task.build_submit_body("gpt-5.5", [{"role": "user", "content": [{"type": "text", "text": "hi"}]}])
    assert body["model"] == "gpt-5.5"
    assert body["stream"] is False
    assert "max_tokens" not in body
    assert "reasoning" not in body


def test_build_submit_body_claude_adds_default_max_tokens_and_optionals():
    body = task.build_submit_body("claude-opus-4-7", [{"role": "user", "content": "hi"}],
                                  temperature=0.5, top_p=0.9, stop=["X"], reasoning=True)
    assert body["max_tokens"] == 1024
    assert body["temperature"] == 0.5
    assert body["top_p"] == 0.9
    assert body["stop"] == ["X"]
    assert body["reasoning"] is True
