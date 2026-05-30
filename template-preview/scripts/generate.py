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
