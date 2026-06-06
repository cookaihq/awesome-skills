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


def test_resolve_api_keys_precedence_env_then_dotenvlocal_then_dotenv(tmp_path):
    (tmp_path / ".env.local").write_text("X_API_KEY=sk-local\n", encoding="utf-8")
    (tmp_path / ".env").write_text("X_API_KEY=sk-dotenv\n", encoding="utf-8")
    keys = config.resolve_api_keys(
        environ={"X_API_KEY": "sk-env"},
        cwd=str(tmp_path),
        use_local_key=False,
        config_dir="/unused",
    )
    assert keys == ["sk-env", "sk-local", "sk-dotenv"]


def test_resolve_api_keys_dedup_preserves_order(tmp_path):
    (tmp_path / ".env.local").write_text("X_API_KEY=sk-env\n", encoding="utf-8")
    keys = config.resolve_api_keys(
        environ={"X_API_KEY": "sk-env"},
        cwd=str(tmp_path),
        use_local_key=False,
        config_dir="/unused",
    )
    assert keys == ["sk-env"]  # duplicate value collapsed


def test_resolve_api_keys_config_dir_only_with_flag(tmp_path):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / ".env").write_text("X_API_KEY=sk-persist\n", encoding="utf-8")
    without = config.resolve_api_keys({}, str(tmp_path), use_local_key=False, config_dir=str(cfg))
    assert without == []
    with_flag = config.resolve_api_keys({}, str(tmp_path), use_local_key=True, config_dir=str(cfg))
    assert with_flag == ["sk-persist"]


def test_mask_key():
    assert config.mask_key("sk-1234567890abcd") == "sk-1****abcd"
    assert config.mask_key("short") == "****"
    assert config.mask_key("") == "(empty)"
