import models
from client import Resp

SAMPLE = [
    {"id": "gpt-5.5", "capabilities": ["text", "vision"]},
    {"id": "gemini-3.5-flash", "capabilities": ["text", "vision", "video", "audio", "file"]},
]


def test_fetch_models_returns_data_and_key():
    def transport(method, url, headers, body=None, timeout=60):
        assert method == "GET"
        assert url.endswith("/v1/configs/llm_generations_models")
        return Resp(200, {"object": "list", "data": SAMPLE}, "")

    data, used = models.fetch_models(["k1"], base_url="https://api.x", transport=transport)
    assert used == "k1"
    assert data[0]["id"] == "gpt-5.5"


def test_check_capabilities_model_missing():
    ok, reason, suggestions = models.check_capabilities(SAMPLE, "no-such-model", ["text"])
    assert ok is False
    assert "no-such-model" in reason
    assert "gpt-5.5" in suggestions and "gemini-3.5-flash" in suggestions


def test_check_capabilities_missing_capability_suggests_capable_models():
    ok, reason, suggestions = models.check_capabilities(SAMPLE, "gpt-5.5", ["video"])
    assert ok is False
    assert "video" in reason
    assert suggestions == ["gemini-3.5-flash"]


def test_check_capabilities_ok():
    ok, reason, suggestions = models.check_capabilities(SAMPLE, "gemini-3.5-flash", ["vision", "video"])
    assert ok is True
    assert reason == ""
