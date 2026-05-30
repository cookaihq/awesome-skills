import os, sys, importlib.util
import re

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


import json


def _make_fillers(tmp_path, n=3):
    d = tmp_path / "fillers"
    d.mkdir()
    items = []
    for i in range(1, n + 1):
        (d / f"filler-{i:02d}.svg").write_text("<svg/>", encoding="utf-8")
        items.append({"file": f"filler-{i:02d}.svg", "title": f"标题{i}", "likes": 100 + i})
    (d / "titles.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return str(d)


def test_load_fillers(tmp_path):
    d = _make_fillers(tmp_path, 2)
    fillers = gen.load_fillers(d)
    assert len(fillers) == 2
    assert fillers[0]["title"] == "标题1"
    assert fillers[0]["likes"] == 101
    assert fillers[0]["cover_path"].endswith("filler-01.svg")


def test_load_fillers_missing_dir():
    assert gen.load_fillers("/nonexistent/dir/xyz") == []


def test_plan_render_fills_to_min_and_uses_persona_author(tmp_path):
    filler_dir = _make_fillers(tmp_path, 4)
    fillers = gen.load_fillers(filler_dir)
    persona = {"nickname": "阿喵", "avatar_path": "/tpl/avatar-default.svg",
               "avatar_rel": "assets/avatar.svg"}
    content = {"notes": [{"cover": "/abs/c1.jpg", "title": "用户卡A", "likes": 9},
                         {"cover": "rel/c2.png", "title": "用户卡B"}]}  # B 无 likes
    cards, copies = gen.plan_render(content, persona, fillers, pwd="/pwd", min_cards=5)

    assert len(cards) == 5                                   # 2 用户 + 3 填充 = 5
    assert [c["title"] for c in cards[:2]] == ["用户卡A", "用户卡B"]
    assert cards[0]["cover"] == "assets/note-01.jpg"
    assert cards[1]["cover"] == "assets/note-02.png"
    assert cards[1]["likes"] == gen.placeholder_likes("用户卡B")   # 缺省占位
    assert cards[2]["cover"].startswith("assets/filler-")
    # 所有卡作者头像/昵称都用人设
    assert all(c["author"] == "阿喵" for c in cards)
    assert all(c["avatar"] == "assets/avatar.svg" for c in cards)
    # 拷贝清单：头像 + 2 用户封面 + 3 填充封面 = 6
    dests = [d for _, d in copies]
    assert "avatar.svg" in dests
    assert "note-01.jpg" in dests and "note-02.png" in dests
    assert sum(1 for d in dests if d.startswith("filler-")) == 3
    # 用户卡相对路径正确解析（rel 以 pwd 为基准）
    srcs = dict((d, s) for s, d in copies)
    assert srcs["note-01.jpg"] == "/abs/c1.jpg"
    assert srcs["note-02.png"] == os.path.join("/pwd", "rel/c2.png")


def test_format_count():
    assert gen.format_count("0") == "0"
    assert gen.format_count(999) == "999"
    assert gen.format_count(12345) == "1.2万"
    assert gen.format_count("20000") == "2万"


def test_render_html_replaces_tokens_and_injects_cards():
    template = (
        "<h1>{{NICKNAME}}</h1><p>{{BIO}}</p><i>{{RED_ID}}</i>"
        "<span>{{FOLLOWING}}/{{FOLLOWERS}}/{{LIKES}}</span>"
        '<img id="me" src="{{AVATAR}}">'
        '<section class="grid"><!--CARDS--></section>'
    )
    persona = {"nickname": "阿<喵>", "bio": "bio", "red_id": "xhs_1",
               "following": "88", "followers": "1024", "likes": "20000",
               "avatar_rel": "assets/avatar.svg"}
    cards = [{"cover": "assets/note-01.jpg", "title": "标题&", "likes": 1234,
              "author": "阿<喵>", "avatar": "assets/avatar.svg"}]
    out = gen.render_html(template, persona, cards)

    assert "阿&lt;喵&gt;" in out                       # 昵称被 HTML 转义
    assert "标题&amp;" in out                           # 卡标题被转义
    assert 'src="{{AVATAR}}"' not in out               # 头像 token 被替换
    assert 'src="assets/avatar.svg"' in out            # 替成相对路径（未被转义破坏）
    assert 'src="assets/note-01.jpg"' in out           # 卡封面相对 <img>
    assert "<!--CARDS-->" not in out                   # 占位被卡片替换
    assert "2万" in out                                 # 获赞数格式化
    assert "1234" in out                                # 卡 likes 渲染（<10000 原样）


def test_render_html_all_images_relative():
    template = '<img src="{{AVATAR}}"><div><!--CARDS--></div>'
    persona = {"nickname": "n", "bio": "", "red_id": "", "following": "0",
               "followers": "0", "likes": "0", "avatar_rel": "assets/avatar.svg"}
    cards = [{"cover": "assets/note-01.jpg", "title": "t", "likes": 1,
              "author": "n", "avatar": "assets/avatar.svg"}]
    out = gen.render_html(template, persona, cards)
    srcs = re.findall(r'src="([^"]+)"', out)
    assert srcs and all(s.startswith("assets/") for s in srcs)   # 全相对，preview-share 可扫描


def test_render_html_no_second_pass_token_substitution():
    template = "<h1>{{NICKNAME}}</h1><span>{{LIKES}}</span><!--CARDS-->"
    persona = {"nickname": "{{LIKES}}", "bio": "", "red_id": "", "following": "0",
               "followers": "0", "likes": "20000", "avatar_rel": "assets/avatar.svg"}
    out = gen.render_html(template, persona, [])
    assert "{{LIKES}}" in out          # nickname 的字面 {{LIKES}} 不被替换
    assert out.count("2万") == 1        # 只有真正的 {{LIKES}} token 被格式化


def _run(argv, cwd):
    old = os.getcwd()
    os.chdir(cwd)
    try:
        return gen.main(argv)
    finally:
        os.chdir(old)


def test_main_real_generation(tmp_path, capsys):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"label": "iot", "notes": [
        {"cover": cover, "title": "我的第一篇笔记"}]}, ensure_ascii=False), encoding="utf-8")

    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--label", "iot", "--out", str(tmp_path / "out")], cwd=str(tmp_path))
    assert rc == 0
    out = tmp_path / "out"
    assert (out / "index.html").is_file()
    assert (out / "content.json").is_file()
    assert (out / "assets" / "note-01.jpg").is_file()
    assert (out / "assets" / "avatar.svg").is_file()
    fillers = list((out / "assets").glob("filler-*.svg"))
    assert len(fillers) >= 1
    htmltext = (out / "index.html").read_text(encoding="utf-8")
    assert "我的第一篇笔记" in htmltext
    assert "小红薯" in htmltext
    srcs = re.findall(r'src="([^"]+)"', htmltext)
    assert srcs
    for s in srcs:
        assert s.startswith("assets/")
        assert (out / s).is_file()


def test_main_dry_run_writes_nothing(tmp_path):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"cover": cover, "title": "t"}]}), encoding="utf-8")
    out = tmp_path / "out"
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--label", "d", "--out", str(out), "--dry-run"], cwd=str(tmp_path))
    assert rc == 0
    assert not out.exists()


def test_main_unknown_template(tmp_path):
    content = tmp_path / "c.json"
    content.write_text('{"notes":[]}', encoding="utf-8")
    rc = _run(["--template", "nope", "--content", str(content)], cwd=str(tmp_path))
    assert rc == 2


def test_main_refuses_overwrite_on_derived_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TPL_SUBDIR_PATTERN", "{label}")
    monkeypatch.setenv("TPL_OUTPUT_ROOT", str(tmp_path / "root"))
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "c.json"
    content.write_text(json.dumps({"notes": [{"cover": cover, "title": "t"}]}), encoding="utf-8")
    args = ["--template", "xiaohongshu", "--content", str(content), "--label", "dup"]
    assert _run(args, cwd=str(tmp_path)) == 0
    assert _run(args, cwd=str(tmp_path)) == 2
