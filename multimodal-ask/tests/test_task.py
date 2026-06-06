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


import pytest

from client import Resp


def test_submit_llm_success_returns_id_and_key():
    def transport(method, url, headers, body=None, timeout=60):
        assert method == "POST" and url.endswith("/v1/llm/generations")
        return Resp(200, {"id": "task-llm-1", "status": "pending"}, "")

    out, used = task.submit_llm({"model": "gpt-5.5", "messages": []}, ["k1"],
                                base_url="https://api.x", transport=transport)
    assert out["id"] == "task-llm-1"
    assert used == "k1"


def test_submit_llm_422_raises_llmerror_with_code():
    def transport(method, url, headers, body=None, timeout=60):
        return Resp(422, {"error": {"code": "model_not_support_capability",
                                    "message": "不支持 text+video"}}, "")

    with pytest.raises(task.LLMError) as ei:
        task.submit_llm({"model": "gpt-5.5", "messages": []}, ["k1"],
                        base_url="https://api.x", transport=transport)
    assert ei.value.status == 422
    assert "model_not_support_capability" in ei.value.message
    assert "不支持 text+video" in ei.value.message


def test_poll_task_polls_until_completed():
    calls = {"n": 0}

    def transport(method, url, headers, body=None, timeout=60):
        assert method == "GET" and "sync_upstream=true" in url
        calls["n"] += 1
        if calls["n"] < 3:
            return Resp(200, {"status": "processing", "progress": 50}, "")
        return Resp(200, {"status": "completed", "results": [{"choices": [
            {"message": {"role": "assistant", "content": "done"}}]}]}, "")

    final = task.poll_task("task-llm-1", "k1", base_url="https://api.x",
                           transport=transport, interval=1, timeout=60, sleep=lambda s: None)
    assert final["status"] == "completed"
    assert calls["n"] == 3


def test_poll_task_timeout_raises():
    def transport(method, url, headers, body=None, timeout=60):
        return Resp(200, {"status": "processing"}, "")

    with pytest.raises(task.PollTimeout):
        task.poll_task("task-llm-1", "k1", base_url="https://api.x",
                       transport=transport, interval=1, timeout=2, sleep=lambda s: None)


def test_extract_text_completed():
    j = {"status": "completed", "results": [{"choices": [
        {"message": {"role": "assistant", "content": "hello"}}]}]}
    assert task.extract_text(j) == "hello"


def test_extract_text_empty_content_for_reasoning_model_ok():
    j = {"status": "completed", "results": [{"choices": [{"message": {"content": ""}}]}]}
    assert task.extract_text(j) == ""


def test_extract_text_failed_raises():
    j = {"status": "failed", "error": {"code": "task_failed", "message": "content policy"}}
    with pytest.raises(task.TaskFailed) as ei:
        task.extract_text(j)
    assert "content policy" in str(ei.value)
