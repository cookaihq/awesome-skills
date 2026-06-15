"""xhs-downloader orchestrator (system python3).

Locates the XHS-Downloader clone + its venv, reads layered config/cookie, runs the
extraction driver, and on empty result (exit 3) or --login, opens the QR-login flow,
persists the cookie to ~/.config, and retries once.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _config  # noqa: E402
import _provision  # noqa: E402

HOME_CONFIG = Path.home() / ".config" / "xhs-downloader" / ".env"
SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS_DIR.parent


def _candidate_clone_paths() -> list:
    # Default discovery: walk up from the skill scripts dir looking for the known clone.
    here = SCRIPTS_DIR
    cands = []
    for up in [here] + list(here.parents):
        cands.append(up / "forked-repos" / "XHS-Downloader")
    return cands


def resolve_clone(use_local_key: bool, auto_setup: bool) -> Path:
    """Locate the XHS-Downloader clone, auto-provisioning into vendor/ on first use.

    Order: XHS_DOWNLOADER_PATH > dev clone (forked-repos) > managed vendor/ >
    (auto) clone into vendor/.
    """
    home = HOME_CONFIG if use_local_key else None
    explicit = _config.read_layered("XHS_DOWNLOADER_PATH", home_config=home)
    if explicit:
        p = Path(explicit).expanduser()
        if (p / "source").is_dir():
            return p
        sys.exit(f"[xhs-downloader] XHS_DOWNLOADER_PATH={explicit} 下找不到 source/ 目录")
    for c in _candidate_clone_paths():
        if (c / "source").is_dir():
            return c
    vendor = _provision.vendor_dir(SKILL_ROOT)
    if (vendor / "source").is_dir():
        return vendor
    if not auto_setup:
        sys.exit(
            "[xhs-downloader] 未找到 XHS-Downloader clone，且已用 --no-auto-setup 关闭自动下载。"
            f"请 git clone 到 {vendor}，或设置 XHS_DOWNLOADER_PATH 指向 clone 根。"
        )
    _provision.provision(vendor)
    if not (vendor / "source").is_dir():
        sys.exit(f"[xhs-downloader] 自动下载后仍未在 {vendor} 找到 source/ 目录")
    return vendor


def resolve_venv_python(clone: Path) -> Path:
    py = clone / ".venv" / "bin" / "python"
    if not py.exists():
        sys.exit(
            f"[xhs-downloader] 未找到 {py}。请在 {clone} 执行 `uv sync --no-dev` 创建 venv。"
        )
    return py


def read_cookie() -> str | None:
    # Cookie auto-reads ~/.config (deviation justified in spec: no billing side effect).
    return _config.read_layered("XHS_COOKIE", home_config=HOME_CONFIG)


def persist_cookie(cookie: str) -> None:
    HOME_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if HOME_CONFIG.is_file():
        lines = [
            ln for ln in HOME_CONFIG.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("XHS_COOKIE=")
        ]
    lines.append(f"XHS_COOKIE={cookie}")
    HOME_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        HOME_CONFIG.chmod(0o600)
    except OSError:
        pass


def run_extract(venv_py: Path, clone: Path, args, cookie: str | None) -> int:
    cmd = [
        str(venv_py), str(SCRIPTS_DIR / "run_extract.py"),
        "--repo-path", str(clone),
        "--url", args.url,
        "--output-dir", args.output_dir,
        "--timeout", str(args.timeout),
    ]
    if args.index:
        cmd += ["--index", args.index]
    if args.no_image:
        cmd.append("--no-image")
    if args.no_video:
        cmd.append("--no-video")
    if args.live:
        cmd.append("--live")
    if args.metadata_only:
        cmd.append("--metadata-only")
    if args.proxy:
        cmd += ["--proxy", args.proxy]
    if cookie:
        cmd += ["--cookie", cookie]
        print(f"[xhs-downloader] 使用 Cookie（{_config.mask(cookie)}）", file=sys.stderr)
    proc = subprocess.run(cmd)
    return proc.returncode


def maybe_update_check(clone: Path, enabled: bool) -> None:
    """Throttled, read-only update check. Prints a one-line notice if behind; never pulls."""
    if not enabled:
        return
    stamp = _provision.stamp_path(SKILL_ROOT)
    if not _provision.should_check(stamp, now=time.time()):
        return
    remote = _provision.fetch_remote_head(clone)
    _provision.write_stamp(stamp, now=time.time())
    if not remote:
        return  # offline / slow / not a git clone -> silently skip
    local = _provision.local_head(clone)
    if local and remote and local != remote:
        print(
            f"[xhs-downloader] 上游有更新（本地 {local[:7]} → 远端 {remote[:7]}）。"
            "如需更新，加 --update 重新运行。",
            file=sys.stderr,
        )


def do_login(venv_py: Path, clone: Path) -> str | None:
    if not _provision.ensure_playwright(clone):
        print("[xhs-downloader] playwright/chromium 未就绪，无法扫码登录。", file=sys.stderr)
        return None
    print("[xhs-downloader] 正在打开浏览器，请扫码登录……", file=sys.stderr)
    proc = subprocess.run(
        [str(venv_py), str(SCRIPTS_DIR / "login_cookie.py")],
        capture_output=True, text=True,
    )
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        return None
    cookie = proc.stdout.strip()
    return cookie or None


def main() -> int:
    p = argparse.ArgumentParser(description="下载小红书作品到本地")
    p.add_argument("--url", required=True, help="一个或多个链接，空格分隔")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--index", default="")
    p.add_argument("--no-image", action="store_true")
    p.add_argument("--no-video", action="store_true")
    p.add_argument("--live", action="store_true")
    p.add_argument("--metadata-only", action="store_true")
    p.add_argument("--proxy", default="")
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--login", action="store_true", help="先扫码登录再下载")
    p.add_argument("--use-local-key", action="store_true",
                   help="允许从 ~/.config 读取 XHS_DOWNLOADER_PATH")
    p.add_argument("--update", action="store_true",
                   help="运行前 git pull --ff-only 更新上游代码并重新 uv sync")
    p.add_argument("--no-update-check", action="store_true",
                   help="跳过上游更新检查")
    p.add_argument("--no-auto-setup", action="store_true",
                   help="找不到 clone 时不自动下载，仅报错")
    args = p.parse_args()

    if args.output_dir is None:
        args.output_dir = _config.read_layered("XHS_OUTPUT_DIR") or "./xhs-downloads"

    clone = resolve_clone(args.use_local_key, auto_setup=not args.no_auto_setup)

    if args.update:
        _provision.update_repo(clone)
    else:
        maybe_update_check(clone, enabled=not args.no_update_check)

    venv_py = resolve_venv_python(clone)
    cookie = read_cookie()

    if args.login and not cookie:
        cookie = do_login(venv_py, clone)
        if cookie:
            persist_cookie(cookie)

    code = run_extract(venv_py, clone, args, cookie)

    # Empty result without a cookie -> offer login + retry once.
    if code == 3 and not args.login:
        print("[xhs-downloader] 提取为空，尝试扫码登录后重试……", file=sys.stderr)
        new_cookie = do_login(venv_py, clone)
        if new_cookie:
            persist_cookie(new_cookie)
            code = run_extract(venv_py, clone, args, new_cookie)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
