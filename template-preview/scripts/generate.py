#!/usr/bin/env python3
"""template-preview: 把一组图片+文案渲染成「指定模板风格」的自包含展示页。

配置读取优先级（见仓库 CLAUDE.md 通用约定，本 skill 去掉 ~/.config 层）：
  1. 进程环境变量（本轮显式注入或已 export）
  2. $PWD/.env.local（自动读，不向上递归）
  3. $PWD/.env（自动读，不向上递归）
  4. 内置默认（模板级在 templates/<t>/defaults.env 与内置素材；skill 级写在本文件）
每个变量独立按此顺序取「首个非空来源」。
stdout 仅输出最终 index.html 路径；其余信息走 stderr。
"""
import argparse
import datetime
import html
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(HERE), "templates")

SKILL_DEFAULTS = {
    "TPL_OUTPUT_ROOT": "template-preview",
    "TPL_SUBDIR_PATTERN": "{date}-{time}-{label}",
}

# 各模板的人设变量前缀
TEMPLATE_VAR_PREFIX = {
    "xiaohongshu": "TPL_XHS_",
}

IMG_EXT = {".svg", ".jpg", ".jpeg", ".png", ".webp", ".gif"}


def log(msg):
    print(msg, file=sys.stderr)


def parse_env_file(path):
    """极简 .env 解析（与 preview-share 一致）：KEY=value / "value" / 'value'，
    # 注释，空行；同名取最后一次；不做 shell 展开 / 命令替换 / 续行。"""
    vals = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                    v = v[1:-1]
                vals[k] = v
    except FileNotFoundError:
        pass
    return vals


def resolve_config(varnames, builtin_defaults):
    """返回 (cfg, src)。每个变量独立按 env > $PWD/.env.local > $PWD/.env > builtin 取首个非空。"""
    layers = [
        ("env", {k: os.environ[k] for k in varnames if os.environ.get(k)}),
        ("$PWD/.env.local", parse_env_file(os.path.join(os.getcwd(), ".env.local"))),
        ("$PWD/.env", parse_env_file(os.path.join(os.getcwd(), ".env"))),
        ("builtin", builtin_defaults),
    ]
    cfg, src = {}, {}
    for var in varnames:
        for label, d in layers:
            if d.get(var):
                cfg[var] = d[var]
                src[var] = label
                break
    return cfg, src


def slugify_label(label):
    s = re.sub(r"[^-A-Za-z0-9._一-鿿]+", "-", (label or "").strip()).strip("-")
    return s or "preview"


def render_subdir(pattern, label, now):
    return pattern.format(
        date=now.strftime("%Y%m%d"),
        time=now.strftime("%H%M%S"),
        label=slugify_label(label),
    ).strip("/")


def build_output_dir(out_arg, output_root, subdir, pwd):
    if out_arg:
        return os.path.abspath(out_arg)
    root = output_root if os.path.isabs(output_root) else os.path.join(pwd, output_root)
    return os.path.join(root, subdir)


def ext_of(path, default=".jpg"):
    e = os.path.splitext(path)[1].lower()
    return e if e else default


def placeholder_likes(seed):
    """确定性占位点赞数：同输入同输出，落在 100..9099。"""
    return sum(ord(c) for c in str(seed)) % 9000 + 100


def resolve_cover(cover, pwd):
    return cover if os.path.isabs(cover) else os.path.join(pwd, cover)


def load_content(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_fillers(filler_dir):
    """读填充卡目录：图片文件 + 同目录 titles.json（[{file,title,likes}]）。"""
    meta = {}
    titles_path = os.path.join(filler_dir, "titles.json")
    if os.path.isfile(titles_path):
        with open(titles_path, encoding="utf-8") as f:
            for item in json.load(f):
                meta[item.get("file")] = item
    fillers = []
    if not os.path.isdir(filler_dir):
        return fillers
    for fn in sorted(os.listdir(filler_dir)):
        if fn == "titles.json":
            continue
        if os.path.splitext(fn)[1].lower() not in IMG_EXT:
            continue
        m = meta.get(fn, {})
        fillers.append({
            "cover_path": os.path.join(filler_dir, fn),
            "title": m.get("title", ""),
            "likes": m.get("likes"),
        })
    return fillers


def plan_render(content, persona, fillers, pwd, min_cards):
    """装配 (cards, copies)。
    cards: 模板用，含相对 cover/avatar、title、likes、author。
    copies: [(src_abs, dest_basename_under_assets)]，含头像。
    所有卡（含填充卡）作者头像/昵称统一用人设。"""
    avatar_rel = persona["avatar_rel"]
    copies = [(persona["avatar_path"], os.path.basename(avatar_rel))]
    cards = []

    for i, n in enumerate(content.get("notes", []), 1):
        src = resolve_cover(n["cover"], pwd)
        dest = f"note-{i:02d}{ext_of(src)}"
        copies.append((src, dest))
        likes = n.get("likes")
        title = n.get("title", "")
        if likes is None:
            likes = placeholder_likes(title)
        cards.append({"cover": f"assets/{dest}", "title": title, "likes": likes,
                      "author": persona["nickname"], "avatar": avatar_rel})

    for j, f in enumerate(fillers, 1):
        if len(cards) >= min_cards:
            break
        src = f["cover_path"]
        dest = f"filler-{j:02d}{ext_of(src, '.svg')}"
        copies.append((src, dest))
        likes = f.get("likes")
        if likes is None:
            likes = placeholder_likes(f.get("title", ""))
        cards.append({"cover": f"assets/{dest}", "title": f.get("title", ""), "likes": likes,
                      "author": persona["nickname"], "avatar": avatar_rel})

    return cards, copies


def format_count(n):
    """小红书风格计数：>=10000 显示「x.x万」（去掉 .0），否则原样。"""
    try:
        v = int(str(n).strip())
    except (ValueError, TypeError):
        return html.escape(str(n))
    if v < 10000:
        return str(v)
    s = f"{v / 10000:.1f}".rstrip("0").rstrip(".")
    return f"{s}万"


def render_card_html(card):
    return (
        '<div class="card">'
        f'<img class="cover" src="{card["cover"]}" alt="" loading="lazy">'
        '<div class="card-body">'
        f'<div class="card-title">{html.escape(card["title"])}</div>'
        '<div class="card-foot">'
        f'<span class="author"><img class="avatar-sm" src="{card["avatar"]}" alt="">'
        f'<span class="author-name">{html.escape(card["author"])}</span></span>'
        f'<span class="likes">♥ {format_count(card["likes"])}</span>'
        '</div></div></div>'
    )


_TOKEN_RE = re.compile(r"\{\{(NICKNAME|BIO|RED_ID|FOLLOWING|FOLLOWERS|LIKES|AVATAR)\}\}")


def render_html(template_str, persona, cards):
    cards_html = "\n".join(render_card_html(c) for c in cards)
    values = {
        "NICKNAME": html.escape(persona["nickname"]),
        "BIO": html.escape(persona["bio"]),
        "RED_ID": html.escape(persona["red_id"]),
        "FOLLOWING": format_count(persona["following"]),
        "FOLLOWERS": format_count(persona["followers"]),
        "LIKES": format_count(persona["likes"]),
        "AVATAR": persona["avatar_rel"],  # 相对路径，不转义
    }
    # 单遍替换：插入的值不会被再次扫描成 token（避免二次替换）
    out = _TOKEN_RE.sub(lambda m: values[m.group(1)], template_str)
    out = out.replace("<!--CARDS-->", cards_html)
    return out
