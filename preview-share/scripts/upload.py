#!/usr/bin/env python3
"""preview-share: 把本地文件（及其关联资源）通过 FTP 上传到预览服务器，返回预览 URL。

核心行为：给一个入口文件（通常是 HTML），自动扫描它引用的本地资源
（src/href/<link>/<script>/url(...)/srcset 等），递归收集，保留相对目录结构
整体上传到唯一子目录下，使得在线打开的页面里所有相对引用都能正确解析。

配置读取优先级（见仓库 CLAUDE.md「Skills 配置读取优先级」通用约定）：
  1. 进程环境变量（本轮显式注入或已 export）
  2. $PWD/.env.local      （自动读，不向上递归）
  3. $PWD/.env            （自动读，不向上递归）
  4. ~/.config/preview-share/.env  （仅 --use-local-key 时读）
每个变量独立按此顺序取「首个非空来源」。
"""
import argparse
import datetime
import ftplib
import os
import re
import sys
import urllib.parse

VARS = ("PREVIEW_SHARE_FTP", "PREVIEW_SHARE_BASEURL")

# 文本类入口会被递归扫描依赖；其它一律按二进制原样上传
SCANNABLE_EXT = {".html", ".htm", ".css", ".svg"}

# 跳过的非本地引用前缀
SKIP_PREFIXES = ("http://", "https://", "//", "data:", "mailto:",
                 "tel:", "javascript:", "#", "blob:")

# HTML/CSS 中提取引用的正则
RE_ATTR = re.compile(r"""(?:src|href|poster|data-src|background)\s*=\s*["']([^"']+)["']""", re.I)
RE_SRCSET = re.compile(r"""srcset\s*=\s*["']([^"']+)["']""", re.I)
RE_CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.I)


def log(msg):
    print(msg, file=sys.stderr)


def mask_ftp(url):
    """ftp://user:pass@host -> ftp://user:***@host，日志安全。"""
    try:
        u = urllib.parse.urlparse(url)
        host = u.hostname or ""
        port = f":{u.port}" if u.port else ""
        user = f"{u.username}:***@" if u.username else ""
        return f"{u.scheme}://{user}{host}{port}{u.path}"
    except Exception:
        return "ftp://***"


# ---------- 配置读取（分层优先级） ----------

def parse_env_file(path):
    """极简 .env 解析：KEY=value / KEY="value" / KEY='value'，# 注释，空行。
    不做 shell 展开 / 命令替换 / 续行。同名取最后一次。"""
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


def resolve_config(use_local_key):
    """返回 (config dict, sources dict)。每个变量独立取首个非空来源。"""
    layers = []  # (label, dict)
    layers.append(("env", {k: os.environ[k] for k in VARS if os.environ.get(k)}))
    layers.append(("$PWD/.env.local", parse_env_file(os.path.join(os.getcwd(), ".env.local"))))
    layers.append(("$PWD/.env", parse_env_file(os.path.join(os.getcwd(), ".env"))))
    if use_local_key:
        home_env = os.path.expanduser("~/.config/preview-share/.env")
        layers.append(("~/.config/preview-share/.env", parse_env_file(home_env)))

    cfg, src = {}, {}
    for var in VARS:
        for label, d in layers:
            if d.get(var):
                cfg[var] = d[var]
                src[var] = label
                break
    return cfg, src


# ---------- 依赖扫描 ----------

def clean_ref(ref):
    """归一化一个引用：去 query/fragment；非本地返回 None。"""
    ref = ref.strip()
    if not ref:
        return None
    low = ref.lower()
    if any(low.startswith(p) for p in SKIP_PREFIXES):
        return None
    ref = ref.split("#", 1)[0].split("?", 1)[0]
    if not ref or ref.startswith("/"):  # 绝对文件系统路径不处理
        return None
    return ref


def extract_refs(text):
    refs = set()
    for m in RE_ATTR.finditer(text):
        r = clean_ref(m.group(1))
        if r:
            refs.add(r)
    for m in RE_SRCSET.finditer(text):
        for cand in m.group(1).split(","):
            r = clean_ref(cand.strip().split()[0]) if cand.strip() else None
            if r:
                refs.add(r)
    for m in RE_CSS_URL.finditer(text):
        r = clean_ref(m.group(1))
        if r:
            refs.add(r)
    return refs


def scan_deps(entry):
    """从 entry 出发递归收集本地依赖文件，返回去重后的绝对路径集合（含 entry）。"""
    entry = os.path.realpath(entry)
    collected = {entry}
    queue = [entry]
    missing = []
    while queue:
        cur = queue.pop()
        if os.path.splitext(cur)[1].lower() not in SCANNABLE_EXT:
            continue
        try:
            with open(cur, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        base = os.path.dirname(cur)
        for ref in extract_refs(text):
            target = os.path.realpath(os.path.join(base, ref))
            if target in collected:
                continue
            if os.path.isfile(target):
                collected.add(target)
                queue.append(target)
            else:
                missing.append((cur, ref))
    return collected, missing


# ---------- FTP 上传 ----------

def ensure_remote_dir(ftp, path):
    """逐级 MKD，已存在则忽略。"""
    parts = [p for p in path.split("/") if p]
    cur = "" if not path.startswith("/") else ""
    built = "/" if path.startswith("/") else ""
    for p in parts:
        built = built.rstrip("/") + "/" + p
        try:
            ftp.mkd(built)
        except ftplib.error_perm as e:
            # 550 通常是「已存在」，其它权限错误才需要关注
            if not str(e).startswith("550"):
                raise


def main():
    ap = argparse.ArgumentParser(description="FTP 上传文件及其关联资源，返回预览 URL")
    ap.add_argument("entry", help="入口文件（其 URL 会被返回；通常是 preview.html）")
    ap.add_argument("--include", action="append", default=[],
                    help="额外强制包含的文件或目录（相对/绝对皆可），可重复")
    ap.add_argument("--label", help="子目录标签，最终子目录 = {时间戳}-{标签}")
    ap.add_argument("--subdir", help="直接指定远程子目录名（覆盖 时间戳-标签）")
    ap.add_argument("--no-scan", action="store_true",
                    help="不扫描依赖，只上传 entry 与 --include 指定项")
    ap.add_argument("--use-local-key", action="store_true",
                    help="允许读取 ~/.config/preview-share/.env")
    ap.add_argument("--timeout", type=int, default=300,
                    help="FTP 连接/传输超时秒数（默认 300，大文件可调大）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只解析并打印文件清单与预览 URL，不真正上传")
    args = ap.parse_args()

    if not os.path.isfile(args.entry):
        log(f"[error] 入口文件不存在: {args.entry}")
        return 2

    cfg, src = resolve_config(args.use_local_key)
    missing_cfg = [v for v in VARS if not cfg.get(v)]
    if missing_cfg:
        log(f"[error] 缺少配置: {', '.join(missing_cfg)}")
        log("  按优先级设置：进程环境变量 > $PWD/.env.local > $PWD/.env > ~/.config/preview-share/.env(--use-local-key)")
        return 2
    log(f"[config] PREVIEW_SHARE_FTP <- {src['PREVIEW_SHARE_FTP']}  ({mask_ftp(cfg['PREVIEW_SHARE_FTP'])})")
    log(f"[config] PREVIEW_SHARE_BASEURL <- {src['PREVIEW_SHARE_BASEURL']}  ({cfg['PREVIEW_SHARE_BASEURL']})")

    u = urllib.parse.urlparse(cfg["PREVIEW_SHARE_FTP"])
    if u.scheme != "ftp":
        log(f"[error] PREVIEW_SHARE_FTP scheme 必须是 ftp，实际: {u.scheme}（如需 sftp/ftps 请扩展脚本）")
        return 2
    remote_base = u.path.rstrip("/") or ""
    baseurl = cfg["PREVIEW_SHARE_BASEURL"].rstrip("/")

    # 收集文件
    files = set()
    missing_refs = []
    if args.no_scan:
        files.add(os.path.realpath(args.entry))
    else:
        files, missing_refs = scan_deps(args.entry)
    for inc in args.include:
        p = os.path.realpath(inc)
        if os.path.isdir(p):
            for root, _, fns in os.walk(p):
                for fn in fns:
                    files.add(os.path.join(root, fn))
        elif os.path.isfile(p):
            files.add(p)
        else:
            log(f"[warn] --include 未找到: {inc}")

    files = sorted(files)
    root = os.path.dirname(os.path.realpath(args.entry)) if len(files) == 1 \
        else os.path.commonpath(files)
    if os.path.isfile(root):
        root = os.path.dirname(root)

    # 子目录命名
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.subdir:
        subdir = args.subdir
    elif args.label:
        subdir = f"{ts}-{args.label}"
    else:
        subdir = ts
    subdir = subdir.strip("/")

    entry_rel = os.path.relpath(os.path.realpath(args.entry), root).replace(os.sep, "/")
    preview_url = f"{baseurl}/{subdir}/{entry_rel}"

    # 打印清单
    log(f"\n[plan] 本地根目录: {root}")
    log(f"[plan] 远程子目录: {remote_base}/{subdir}/")
    log(f"[plan] 待上传 {len(files)} 个文件:")
    plan = []
    for f in files:
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        remote = f"{remote_base}/{subdir}/{rel}"
        plan.append((f, remote, rel))
        size = os.path.getsize(f)
        mark = "  <== 入口" if rel == entry_rel else ""
        log(f"   {rel}  ({size:,}B) -> {remote}{mark}")
    if missing_refs:
        log(f"\n[warn] 以下引用在本地未找到（不会上传，线上可能裂图）:")
        for parent, ref in missing_refs:
            log(f"   {os.path.relpath(parent, root)} -> {ref}")

    log(f"\n[preview] {preview_url}")

    if args.dry_run:
        log("\n[dry-run] 未上传。")
        print(preview_url)
        return 0

    # 上传
    log(f"\n[ftp] 连接 {u.hostname}:{u.port or 21} 用户 {u.username} …")
    try:
        ftp = ftplib.FTP()
        ftp.connect(u.hostname, u.port or 21, timeout=args.timeout)
        ftp.login(u.username or "", urllib.parse.unquote(u.password or ""))
        ftp.set_pasv(True)
    except ftplib.error_perm as e:
        log(f"[error] FTP 登录失败（认证/权限）: {e}")
        return 3
    except OSError as e:
        log(f"[error] FTP 连接失败: {e}")
        return 3

    made_dirs = set()
    try:
        for local, remote, rel in plan:
            rdir = os.path.dirname(remote)
            if rdir not in made_dirs:
                ensure_remote_dir(ftp, rdir)
                made_dirs.add(rdir)
            with open(local, "rb") as fh:
                ftp.storbinary(f"STOR {remote}", fh)
            log(f"   ✓ {rel}")
    except ftplib.all_errors as e:
        log(f"[error] 上传中断: {e}")
        try:
            ftp.quit()
        except Exception:
            pass
        return 3
    try:
        ftp.quit()
    except Exception:
        pass

    log(f"\n[done] 已上传 {len(plan)} 个文件。")
    print(preview_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
