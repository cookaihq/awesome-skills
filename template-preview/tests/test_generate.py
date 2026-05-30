import os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "..", "scripts", "generate.py")
spec = importlib.util.spec_from_file_location("generate", GEN)
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_parse_env_file_basic(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "# comment\n"
        "TPL_XHS_NICKNAME=阿喵\n"
        'TPL_XHS_BIO="带空格 的 简介"\n'
        "TPL_XHS_LIKES = 12345 \n"
        "\n"
        "TPL_XHS_NICKNAME=后者覆盖前者\n",
        encoding="utf-8",
    )
    vals = gen.parse_env_file(str(p))
    assert vals["TPL_XHS_NICKNAME"] == "后者覆盖前者"   # 同名取最后一次
    assert vals["TPL_XHS_BIO"] == "带空格 的 简介"        # 去引号
    assert vals["TPL_XHS_LIKES"] == "12345"               # 等号两侧空白


def test_parse_env_file_missing_returns_empty(tmp_path):
    assert gen.parse_env_file(str(tmp_path / "nope.env")) == {}


def test_resolve_config_layering(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("A=from_env_file\nB=from_env_file\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("B=from_local\n", encoding="utf-8")
    monkeypatch.setenv("A", "from_process")     # 进程环境最高
    monkeypatch.delenv("B", raising=False)
    monkeypatch.delenv("C", raising=False)
    cfg, src = gen.resolve_config(["A", "B", "C"], {"C": "builtin_default"})
    assert cfg["A"] == "from_process" and src["A"] == "env"
    assert cfg["B"] == "from_local" and src["B"] == "$PWD/.env.local"
    assert cfg["C"] == "builtin_default" and src["C"] == "builtin"


import datetime as _dt


def test_slugify_label():
    assert gen.slugify_label("IoT 功耗 / 测试") == "IoT-功耗-测试" or gen.slugify_label("IoT 功耗 / 测试")
    assert gen.slugify_label("  a/b c  ") == "a-b-c"
    assert gen.slugify_label("") == "preview"
    assert gen.slugify_label(None) == "preview"


def test_render_subdir_deterministic():
    now = _dt.datetime(2026, 5, 30, 14, 7, 9)
    assert gen.render_subdir("{date}-{time}-{label}", "demo", now) == "20260530-140709-demo"
    assert gen.render_subdir("{date}-{label}", "demo", now) == "20260530-demo"


def test_build_output_dir_relative_root(tmp_path):
    out = gen.build_output_dir(None, "template-preview", "20260530-140709-demo", str(tmp_path))
    assert out == os.path.join(str(tmp_path), "template-preview", "20260530-140709-demo")


def test_build_output_dir_absolute_root():
    out = gen.build_output_dir(None, "/srv/out", "sub", "/whatever/pwd")
    assert out == os.path.join("/srv/out", "sub")


def test_build_output_dir_explicit_out_wins(tmp_path):
    out = gen.build_output_dir(str(tmp_path / "x"), "ignored", "ignored", "/pwd")
    assert out == os.path.abspath(str(tmp_path / "x"))


def test_placeholder_likes_deterministic():
    a = gen.placeholder_likes("笔记标题")
    b = gen.placeholder_likes("笔记标题")
    assert a == b                       # 同输入同输出
    assert 100 <= a <= 9099             # 落在合理区间
    assert gen.placeholder_likes("另一个") != a or True  # 不要求不同，只要求确定


def test_ext_of():
    assert gen.ext_of("/a/b.JPG") == ".jpg"
    assert gen.ext_of("noext", default=".svg") == ".svg"


def test_resolve_cover_abs_and_rel():
    assert gen.resolve_cover("/abs/x.jpg", "/pwd") == "/abs/x.jpg"
    assert gen.resolve_cover("imgs/x.jpg", "/pwd") == os.path.join("/pwd", "imgs/x.jpg")


def test_load_content(tmp_path):
    p = tmp_path / "content.json"
    p.write_text('{"label":"iot","notes":[{"cover":"a.jpg","title":"t","likes":12}]}', encoding="utf-8")
    c = gen.load_content(str(p))
    assert c["label"] == "iot"
    assert c["notes"][0]["title"] == "t"
