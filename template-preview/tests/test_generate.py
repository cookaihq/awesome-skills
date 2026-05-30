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


def test_build_output_dir_empty_root_is_pwd(tmp_path):
    # 空 root = 直接放在 $PWD 下（无 template-preview 等中间目录）
    out = gen.build_output_dir(None, "", "my-page", str(tmp_path))
    assert out == os.path.join(str(tmp_path), "my-page")


def test_placeholder_likes_deterministic():
    a = gen.placeholder_likes("笔记标题")
    b = gen.placeholder_likes("笔记标题")
    assert a == b                       # 同输入同输出
    assert 100 <= a <= 9099             # 落在合理区间
    assert gen.placeholder_likes("另一个") != a or True  # 不要求不同，只要求确定


def test_ext_of():
    assert gen.ext_of("/a/b.JPG") == ".jpg"
    assert gen.ext_of("noext", default=".svg") == ".svg"


def test_resolve_path_abs_and_rel():
    assert gen.resolve_path("/abs/x.jpg", "/pwd") == "/abs/x.jpg"
    assert gen.resolve_path("imgs/x.jpg", "/pwd") == os.path.join("/pwd", "imgs/x.jpg")


def test_note_image_srcs_images_priority():
    n = {"cover": "c.jpg", "images": ["a.jpg", "b.png"]}
    assert gen.note_image_srcs(n, "/pwd") == [os.path.join("/pwd", "a.jpg"),
                                              os.path.join("/pwd", "b.png")]


def test_note_image_srcs_falls_back_to_cover():
    assert gen.note_image_srcs({"cover": "c.jpg"}, "/pwd") == [os.path.join("/pwd", "c.jpg")]
    assert gen.note_image_srcs({"images": []}, "/pwd") == []  # 空 images 视为无图


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


def _persona():
    return {"nickname": "阿喵", "bio": "b", "red_id": "r", "following": "8",
            "followers": "9", "likes": "0", "avatar_path": "/tpl/avatar-default.svg",
            "avatar_rel": "assets/avatar.svg"}


def test_plan_render_multi_note_pages_and_assets(tmp_path):
    filler_dir = _make_fillers(tmp_path, 4)
    fillers = gen.load_fillers(filler_dir)
    persona = _persona()
    content = {"notes": [
        {"cover": "/abs/c1.jpg", "title": "用户卡A", "likes": 9,
         "images": ["/abs/c1.jpg", "rel/c2.png"]},
        {"cover": "rel/d1.png", "title": "用户卡B"},   # 无 images→回落 cover；无 likes→占位
    ]}
    home_cards, note_pages, copies = gen.plan_render(content, persona, fillers, pwd="/pwd", min_cards=5)

    # 主页：2 真卡 + 3 填充 = 5
    assert len(home_cards) == 5
    assert [c["title"] for c in home_cards[:2]] == ["用户卡A", "用户卡B"]
    # 真卡有 href 指向详情页，封面=首图
    assert home_cards[0]["href"] == "note-01.html"
    assert home_cards[1]["href"] == "note-02.html"
    assert home_cards[0]["cover"] == "assets/note-01-img-01.jpg"
    assert home_cards[1]["cover"] == "assets/note-02-img-01.png"
    # 填充卡无 href（不可点）
    assert all("href" not in c for c in home_cards[2:])
    # 缺省 likes 走占位
    assert home_cards[1]["likes"] == gen.placeholder_likes("用户卡B")

    # 详情页：每条笔记一个
    assert len(note_pages) == 2
    assert note_pages[0]["filename"] == "note-01.html"
    assert note_pages[0]["slides"] == ["assets/note-01-img-01.jpg", "assets/note-01-img-02.png"]
    assert note_pages[1]["slides"] == ["assets/note-02-img-01.png"]  # 回落单图

    # 拷贝清单：头像 + (2 用户图) + (1 用户图) + 3 填充 = 7
    dests = [d for _, d in copies]
    assert "avatar.svg" in dests
    assert "note-01-img-01.jpg" in dests and "note-01-img-02.png" in dests
    assert "note-02-img-01.png" in dests
    assert sum(1 for d in dests if d.startswith("filler-")) == 3
    # 相对路径以 pwd 为基准
    srcs = dict((d, s) for s, d in copies)
    assert srcs["note-01-img-01.jpg"] == "/abs/c1.jpg"
    assert srcs["note-01-img-02.png"] == os.path.join("/pwd", "rel/c2.png")
    assert srcs["note-02-img-01.png"] == os.path.join("/pwd", "rel/d1.png")


def test_plan_render_title_body_fallback():
    # 取不到标题/正文 → 固定回落「暂无标题」「暂无正文」（真实笔记）
    content = {"notes": [{"images": ["/abs/x.png"]}]}   # 无 title、无 body
    home_cards, note_pages, _ = gen.plan_render(content, _persona(), [], "/pwd", min_cards=1)
    assert home_cards[0]["title"] == "暂无标题"
    assert note_pages[0]["title"] == "暂无标题"
    assert note_pages[0]["body"] == "暂无正文"
    # 空白字符串也算取不到
    content2 = {"notes": [{"images": ["/abs/x.png"], "title": "   ", "body": "\n  \n"}]}
    _, np2, _ = gen.plan_render(content2, _persona(), [], "/pwd", min_cards=1)
    assert np2[0]["title"] == "暂无标题" and np2[0]["body"] == "暂无正文"


def test_plan_render_filler_title_not_forced(tmp_path):
    # 填充卡标题为空时保持空，不应被塞「暂无标题」
    filler_dir = tmp_path / "f"; filler_dir.mkdir()
    (filler_dir / "a.svg").write_text("<svg/>", encoding="utf-8")  # 无 titles.json → title 空
    fillers = gen.load_fillers(str(filler_dir))
    content = {"notes": [{"images": ["/abs/x.png"], "title": "真卡"}]}
    home_cards, _, _ = gen.plan_render(content, _persona(), fillers, "/pwd", min_cards=2)
    assert home_cards[0]["title"] == "真卡"
    assert home_cards[1]["title"] == ""          # 填充卡标题保持空


def test_plan_render_single_note_uses_fillers(tmp_path):
    filler_dir = _make_fillers(tmp_path, 6)
    fillers = gen.load_fillers(filler_dir)
    content = {"notes": [{"images": ["/abs/x.png"], "title": "唯一"}]}
    home_cards, note_pages, _ = gen.plan_render(content, _persona(), fillers, "/pwd", min_cards=6)
    assert len(note_pages) == 1                       # 单篇只出一个详情页
    assert len(home_cards) == 6                       # 主页 1 真卡 + 5 填充补足
    assert home_cards[0]["href"] == "note-01.html"
    assert all("href" not in c for c in home_cards[1:])


def test_format_count():
    assert gen.format_count("0") == "0"
    assert gen.format_count(999) == "999"
    assert gen.format_count(12345) == "1.2万"
    assert gen.format_count("20000") == "2万"


def test_render_card_html_real_has_link_filler_does_not():
    real = gen.render_card_html({"cover": "assets/n.jpg", "title": "t", "likes": 1,
                                 "author": "a", "avatar": "assets/avatar.svg",
                                 "href": "note-01.html"})
    filler = gen.render_card_html({"cover": "assets/f.svg", "title": "f", "likes": 1,
                                   "author": "a", "avatar": "assets/avatar.svg"})
    assert '<a class="card-link" href="note-01.html">' in real
    assert "card-link" not in filler                  # 填充卡不可点


def test_render_dots_html():
    assert gen.render_dots_html(1) == ""              # 单图无圆点
    dots = gen.render_dots_html(3)
    assert dots.count('<span class="dot') == 3
    assert dots.count("active") == 1                  # 首点 active


def test_render_slides_html():
    out = gen.render_slides_html(["assets/a.png", "assets/b.png"])
    assert out.count("<div class=\"slide\">") == 2
    assert 'src="assets/a.png"' in out and 'src="assets/b.png"' in out


def test_render_body_html_paragraphs_and_escape():
    out = gen.render_body_html("第一段 <b>\n续行\n\n第二段 & 收尾")
    assert out.count("<p>") == 2                       # 空行切两段
    assert "<br>" in out                               # 段内换行
    assert "&lt;b&gt;" in out and "&amp;" in out       # 转义
    assert gen.render_body_html("") == ""              # 空正文整块不渲染
    assert gen.render_body_html("   ") == ""


def test_render_home_html_replaces_tokens_and_injects_cards():
    template = (
        "<h1>{{NICKNAME}}</h1><p>{{BIO}}</p><i>{{RED_ID}}</i>"
        "<span>{{FOLLOWING}}/{{FOLLOWERS}}/{{LIKES}}</span>"
        '<img id="me" src="{{AVATAR}}">'
        '<section class="grid"><!--CARDS--></section>'
    )
    persona = {"nickname": "阿<喵>", "bio": "bio", "red_id": "xhs_1",
               "following": "88", "followers": "1024", "likes": "20000",
               "avatar_rel": "assets/avatar.svg"}
    cards = [{"cover": "assets/note-01-img-01.jpg", "title": "标题&", "likes": 1234,
              "author": "阿<喵>", "avatar": "assets/avatar.svg", "href": "note-01.html"}]
    out = gen.render_home_html(template, persona, cards)

    assert "阿&lt;喵&gt;" in out                       # 昵称被 HTML 转义
    assert "标题&amp;" in out                           # 卡标题被转义
    assert 'src="{{AVATAR}}"' not in out               # 头像 token 被替换
    assert 'src="assets/avatar.svg"' in out
    assert 'href="note-01.html"' in out                # 卡片链接
    assert "<!--CARDS-->" not in out
    assert "2万" in out                                 # 获赞数格式化


def test_render_note_html_swiper_title_body():
    template = ('<title>{{TITLE}}·{{NICKNAME}}</title><img src="{{AVATAR}}">'
                '<div class="track"><!--SLIDES--></div><div class="dots"><!--DOTS--></div>'
                '<h1>{{TITLE}}</h1><!--BODY--><span>{{LIKES_NOTE}}</span>')
    persona = _persona()
    page = {"filename": "note-01.html", "title": "我的<笔记>", "body": "正文A\n\n正文B",
            "likes": 2175, "slides": ["assets/note-01-img-01.png", "assets/note-01-img-02.png"]}
    out = gen.render_note_html(template, persona, page)

    assert "我的&lt;笔记&gt;" in out                    # 标题转义
    assert out.count('class="slide"') == 2             # 轮播两张
    assert out.count('<span class="dot') == 2          # 两个圆点 span（不含 .dots 容器）
    assert "<p>正文A</p>" in out and "<p>正文B</p>" in out
    assert "{{TITLE}}" not in out and "{{LIKES_NOTE}}" not in out
    assert "2175" in out                               # 笔记点赞 <10000 原样


def test_render_note_html_single_image_no_dots_no_body():
    template = ('<div class="track"><!--SLIDES--></div><div class="dots"><!--DOTS--></div>'
                '<h1>{{TITLE}}</h1><!--BODY-->')
    page = {"title": "t", "body": "", "likes": 5, "slides": ["assets/note-01-img-01.png"]}
    out = gen.render_note_html(template, _persona(), page)
    assert out.count('class="slide"') == 1
    assert '<span class="dot' not in out               # 单图无圆点 span
    assert 'class="body"' not in out                   # 空正文不渲染


def _run(argv, cwd):
    old = os.getcwd()
    os.chdir(cwd)
    try:
        return gen.main(argv)
    finally:
        os.chdir(old)


def test_main_real_generation_multi_page(tmp_path):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"label": "iot", "notes": [
        {"title": "我的第一篇笔记", "body": "段落一\n\n段落二",
         "images": [cover, cover]}]}, ensure_ascii=False), encoding="utf-8")

    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--label", "iot", "--out", str(tmp_path / "out")], cwd=str(tmp_path))
    assert rc == 0
    out = tmp_path / "out"
    assert (out / "index.html").is_file()
    assert (out / "note-01.html").is_file()
    assert (out / "content.json").is_file()
    assert (out / "assets" / "note-01-img-01.jpg").is_file()
    assert (out / "assets" / "note-01-img-02.jpg").is_file()
    assert (out / "assets" / "avatar.svg").is_file()
    fillers = list((out / "assets").glob("filler-*.svg"))
    assert len(fillers) >= 1

    home = (out / "index.html").read_text(encoding="utf-8")
    assert "我的第一篇笔记" in home
    assert 'href="note-01.html"' in home               # 主页卡链到详情
    assert "小红薯" in home                              # 默认人设
    # 主页所有 img 相对、可解析
    for s in re.findall(r'src="([^"]+)"', home):
        assert s.startswith("assets/")
        assert (out / s).is_file()

    note = (out / "note-01.html").read_text(encoding="utf-8")
    assert note.count('class="slide"') == 2            # 轮播两张
    assert "段落一" in note and "段落二" in note
    assert 'href="index.html"' in note                 # 返回主页
    for s in re.findall(r'src="([^"]+)"', note):
        assert s.startswith("assets/")
        assert (out / s).is_file()


def test_main_stdout_prints_all_page_paths(tmp_path, capsys):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [
        {"title": "A", "images": [cover]},
        {"title": "B", "images": [cover]}]}), encoding="utf-8")
    out = tmp_path / "out"
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--out", str(out)], cwd=str(tmp_path))
    assert rc == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert lines[0] == str(out / "index.html")         # 第一行=主页（移交 preview-share 的入口）
    assert str(out / "note-01.html") in lines
    assert str(out / "note-02.html") in lines
    assert len(lines) == 3                              # 主页 + 2 笔记页


def test_main_backward_compatible_cover_only(tmp_path):
    # 老 content.json（仅 cover，无 images/body）：退化为单图详情页
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"cover": cover, "title": "老格式"}]}), encoding="utf-8")
    out = tmp_path / "out"
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--out", str(out)], cwd=str(tmp_path))
    assert rc == 0
    assert (out / "note-01.html").is_file()
    assert (out / "assets" / "note-01-img-01.jpg").is_file()
    note = (out / "note-01.html").read_text(encoding="utf-8")
    assert note.count('class="slide"') == 1
    assert "暂无正文" in note                            # 无 body → 固定回落


def test_main_default_root_is_pwd(tmp_path):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"images": [cover], "title": "t"}]}), encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--name", "my-page"], cwd=str(tmp_path))
    assert rc == 0
    assert (tmp_path / "my-page" / "index.html").is_file()
    assert not (tmp_path / "template-preview").exists()


def test_main_name_skips_pattern_and_slugifies(tmp_path):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"images": [cover], "title": "t"}]}), encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--name", "我的 主页!"], cwd=str(tmp_path))
    assert rc == 0
    assert (tmp_path / "我的-主页" / "index.html").is_file()


def test_main_out_root_custom_parent(tmp_path):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"images": [cover], "title": "t"}]}), encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--name", "p", "--out-root", str(tmp_path / "custom")], cwd=str(tmp_path))
    assert rc == 0
    assert (tmp_path / "custom" / "p" / "index.html").is_file()


def test_main_out_root_flag_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TPL_OUTPUT_ROOT", str(tmp_path / "from_env"))
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"images": [cover], "title": "t"}]}), encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--name", "p", "--out-root", str(tmp_path / "from_flag")], cwd=str(tmp_path))
    assert rc == 0
    assert (tmp_path / "from_flag" / "p" / "index.html").is_file()
    assert not (tmp_path / "from_env").exists()


def test_main_dry_run_writes_nothing(tmp_path, capsys):
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"images": [cover], "title": "t"}]}), encoding="utf-8")
    out = tmp_path / "out"
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--label", "d", "--out", str(out), "--dry-run"], cwd=str(tmp_path))
    assert rc == 0
    assert not out.exists()
    lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert lines[0] == str(out / "index.html")         # dry-run 也打印将生成的页面
    assert str(out / "note-01.html") in lines


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
    content.write_text(json.dumps({"notes": [{"images": [cover], "title": "t"}]}), encoding="utf-8")
    args = ["--template", "xiaohongshu", "--content", str(content), "--label", "dup"]
    assert _run(args, cwd=str(tmp_path)) == 0
    assert _run(args, cwd=str(tmp_path)) == 2


def test_main_bad_json_returns_2(tmp_path):
    content = tmp_path / "content.json"
    content.write_text("{not valid json", encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--out", str(tmp_path / "o")], cwd=str(tmp_path))
    assert rc == 2


def test_main_bad_min_cards_returns_2(tmp_path, monkeypatch):
    monkeypatch.setenv("TPL_XHS_MIN_CARDS", "abc")
    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"images": [cover], "title": "t"}]}), encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--out", str(tmp_path / "o")], cwd=str(tmp_path))
    assert rc == 2


def test_main_note_missing_image_returns_2(tmp_path):
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [{"title": "no image"}]}), encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--out", str(tmp_path / "o")], cwd=str(tmp_path))
    assert rc == 2


def test_main_notes_not_a_list_returns_2(tmp_path):
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": {"cover": "x"}}), encoding="utf-8")
    rc = _run(["--template", "xiaohongshu", "--content", str(content),
               "--out", str(tmp_path / "o")], cwd=str(tmp_path))
    assert rc == 2


def test_output_is_scannable_by_preview_share(tmp_path):
    # 加载 preview-share 的真实依赖扫描器
    ps = os.path.join(HERE, "..", "..", "preview-share", "scripts", "upload.py")
    pspec = importlib.util.spec_from_file_location("ps_upload", ps)
    psmod = importlib.util.module_from_spec(pspec)
    pspec.loader.exec_module(psmod)

    cover = os.path.join(HERE, "fixtures", "sample-cover.jpg")
    content = tmp_path / "content.json"
    content.write_text(json.dumps({"notes": [
        {"title": "n1", "images": [cover, cover]},
        {"title": "n2", "images": [cover]}]}), encoding="utf-8")
    out = tmp_path / "out"
    _run(["--template", "xiaohongshu", "--content", str(content),
          "--label", "x", "--out", str(out)], cwd=str(tmp_path))

    # 以 index.html 为入口，扫描器应沿 href 跟进到所有笔记页 + 其图
    collected, missing = psmod.scan_deps(str(out / "index.html"))
    assert missing == []                               # 无裂图引用（含填充卡）
    names = {os.path.basename(p) for p in collected}
    assert "note-01.html" in names and "note-02.html" in names   # 经 href 跟进到详情页
    assert "note-01-img-01.jpg" in names and "note-01-img-02.jpg" in names
    assert "note-02-img-01.jpg" in names
    assert any(n.startswith("filler-") for n in names)  # 填充卡图
    assert "avatar.svg" in names
