import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _config  # noqa: E402


def test_parse_env_basic(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "# comment\n"
        "XHS_COOKIE=abc123\n"
        'XHS_OUTPUT_DIR="./out"\n'
        "\n"
        "XHS_COOKIE=override\n",  # same key -> last wins
        encoding="utf-8",
    )
    parsed = _config.parse_env_file(f)
    assert parsed["XHS_COOKIE"] == "override"
    assert parsed["XHS_OUTPUT_DIR"] == "./out"


def test_parse_env_no_shell_expansion(tmp_path):
    f = tmp_path / ".env"
    f.write_text("XHS_COOKIE=${HOME}/x\n", encoding="utf-8")
    parsed = _config.parse_env_file(f)
    assert parsed["XHS_COOKIE"] == "${HOME}/x"  # literal, not expanded


def test_layered_env_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("XHS_COOKIE", "from_env")
    (tmp_path / ".env.local").write_text("XHS_COOKIE=from_local\n", encoding="utf-8")
    val = _config.read_layered("XHS_COOKIE", cwd=tmp_path, home_config=None)
    assert val == "from_env"  # process env beats files


def test_layered_local_beats_env_file(tmp_path):
    (tmp_path / ".env.local").write_text("XHS_COOKIE=from_local\n", encoding="utf-8")
    (tmp_path / ".env").write_text("XHS_COOKIE=from_envfile\n", encoding="utf-8")
    # ensure no real env var interferes
    env = {k: v for k, v in os.environ.items() if k != "XHS_COOKIE"}
    val = _config.read_layered("XHS_COOKIE", cwd=tmp_path, home_config=None, env=env)
    assert val == "from_local"


def test_home_config_gated(tmp_path):
    home_cfg = tmp_path / "hc.env"
    home_cfg.write_text("XHS_COOKIE=from_home\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "XHS_COOKIE"}
    # cwd has nothing; home_config only consulted when caller passes it
    assert _config.read_layered("XHS_COOKIE", cwd=tmp_path, home_config=None, env=env) is None
    assert (
        _config.read_layered("XHS_COOKIE", cwd=tmp_path, home_config=home_cfg, env=env)
        == "from_home"
    )


def test_mask_short_and_long():
    assert _config.mask("sk-1234567890abcd") == "sk-1****abcd"
    assert _config.mask("ab") == "****"  # too short to reveal
    assert _config.mask("") == ""
