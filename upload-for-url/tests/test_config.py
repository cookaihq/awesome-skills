import os

import config


def test_parse_dotenv_basic_and_quotes_and_comments():
    text = (
        "# comment line\n"
        "\n"
        "X_API_KEY=sk-plain\n"
        'OTHER="quoted value"\n'
        "SPACED =  trimmed \n"
    )
    out = config.parse_dotenv(text)
    assert out["X_API_KEY"] == "sk-plain"
    assert out["OTHER"] == "quoted value"
    assert out["SPACED"] == "trimmed"
    assert "# comment line" not in out


def test_parse_dotenv_last_wins_and_no_shell_expansion():
    text = "X_API_KEY=first\nX_API_KEY=second\nLIT=${OTHER}\n"
    out = config.parse_dotenv(text)
    assert out["X_API_KEY"] == "second"
    assert out["LIT"] == "${OTHER}"  # literal, no expansion


def test_read_key_from_dotenv_missing_file_returns_none():
    assert config.read_key_from_dotenv("/nonexistent/path/.env") is None


def test_read_key_from_dotenv_reads_x_api_key(tmp_path):
    p = tmp_path / ".env"
    p.write_text("X_API_KEY='sk-fromfile'\n", encoding="utf-8")
    assert config.read_key_from_dotenv(str(p)) == "sk-fromfile"
