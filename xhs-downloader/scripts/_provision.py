"""First-use provisioning + update checks for the vendored XHS-Downloader clone.

Pure decision helpers (`should_check`, `write_stamp`) are unit-tested; the git/uv
operations are thin subprocess wrappers verified against the real upstream.

Layout: the managed clone lives at `<skill_root>/vendor/XHS-Downloader`. Heavy
deps (playwright + chromium) are installed lazily, only when the login flow needs
them — a plain download never pays that cost.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

UPSTREAM = "https://github.com/JoeanAmier/XHS-Downloader.git"
BRANCH = "master"
CHECK_INTERVAL = 24 * 3600  # seconds between update checks


def vendor_dir(skill_root: Path) -> Path:
    return skill_root / "vendor" / "XHS-Downloader"


def is_managed_clone(clone: Path, skill_root: Path) -> bool:
    """True only for the skill's own vendor/ clone.

    Auto-update may run `git reset --hard` to roll back a bad upstream version,
    which would destroy uncommitted work in a developer's forked-repos clone or
    a user-specified XHS_DOWNLOADER_PATH clone. So that destructive path is gated
    to the one clone the skill fully owns.
    """
    try:
        return clone.resolve() == vendor_dir(skill_root).resolve()
    except OSError:
        return False


def stamp_path(skill_root: Path) -> Path:
    return skill_root / "vendor" / ".last_update_check"


# ---- pure decision helpers (unit-tested) ----

def should_check(stamp: Path, now: float, interval: float = CHECK_INTERVAL) -> bool:
    if not stamp.is_file():
        return True
    try:
        last = float(stamp.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return True
    return (now - last) >= interval


def write_stamp(stamp: Path, now: float) -> None:
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(str(int(now)), encoding="utf-8")


# ---- environment checks ----

def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"[xhs-downloader] 缺少必需命令 `{name}`，请先安装后重试。")
    return path


# ---- provisioning ----

def clone_repo(dest: Path) -> None:
    require_tool("git")
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[xhs-downloader] 首次使用：克隆 XHS-Downloader 到 {dest} …", file=sys.stderr)
    subprocess.run(
        ["git", "clone", "--depth", "1", "-b", BRANCH, UPSTREAM, str(dest)],
        check=True,
    )


def sync_deps(clone: Path) -> None:
    require_tool("uv")
    print("[xhs-downloader] 安装依赖（uv sync --no-dev）…", file=sys.stderr)
    subprocess.run(["uv", "sync", "--no-dev"], cwd=str(clone), check=True)


def provision(dest: Path) -> Path:
    """Clone + sync deps. Heavy browser deps are installed lazily elsewhere."""
    clone_repo(dest)
    sync_deps(dest)
    return dest


def ensure_playwright(clone: Path) -> bool:
    """Make sure playwright + chromium are available in the clone's venv.

    Called only on the login path. Idempotent and fast when already present.
    Returns True on success.
    """
    venv_py = clone / ".venv" / "bin" / "python"
    probe = subprocess.run(
        [str(venv_py), "-c", "import playwright"], capture_output=True
    )
    if probe.returncode != 0:
        if not shutil.which("uv"):
            print("[xhs-downloader] 缺少 uv，无法安装 playwright。", file=sys.stderr)
            return False
        print("[xhs-downloader] 安装 playwright 到 venv …", file=sys.stderr)
        subprocess.run(
            ["uv", "pip", "install", "playwright"],
            cwd=str(clone),
            env={**_env(), "VIRTUAL_ENV": str(clone / ".venv")},
            check=True,
        )
    # `playwright install chromium` is idempotent: fast no-op if already cached.
    print("[xhs-downloader] 确认 chromium 浏览器已就绪 …", file=sys.stderr)
    r = subprocess.run(
        [str(venv_py), "-m", "playwright", "install", "chromium"]
    )
    return r.returncode == 0


# ---- update check ----

def local_head(clone: Path) -> Optional[str]:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(clone), capture_output=True, text=True
    )
    return r.stdout.strip() or None


def fetch_remote_head(clone: Path, timeout: float = 5.0) -> Optional[str]:
    """Short-timeout fetch + remote head. Returns None if offline/slow/not-a-git-repo."""
    try:
        subprocess.run(
            ["git", "fetch", "--quiet", "origin", BRANCH],
            cwd=str(clone),
            timeout=timeout,
            check=True,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        return None
    r = subprocess.run(
        ["git", "rev-parse", f"origin/{BRANCH}"],
        cwd=str(clone),
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() or None


def update_repo(clone: Path) -> bool:
    """Fast-forward pull + re-sync deps. ff-only never clobbers local work."""
    r = subprocess.run(
        ["git", "pull", "--ff-only", "origin", BRANCH], cwd=str(clone)
    )
    if r.returncode != 0:
        print("[xhs-downloader] git pull --ff-only 失败（本地可能有改动），跳过更新。", file=sys.stderr)
        return False
    sync_deps(clone)
    return True


def smoke_check(clone: Path, venv_py: Path, scripts_dir: Path) -> bool:
    """Offline contract check inside the venv. True = wrapper still compatible."""
    r = subprocess.run(
        [str(venv_py), str(scripts_dir / "smoke_check.py"), "--repo-path", str(clone)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 and r.stderr:
        sys.stderr.write(r.stderr)
    return r.returncode == 0


def _hard_reset(clone: Path, commit: str) -> None:
    subprocess.run(
        ["git", "reset", "--hard", commit],
        cwd=str(clone),
        capture_output=True,
    )


def auto_update_with_rollback(clone: Path, venv_py: Path, scripts_dir: Path) -> None:
    """Pull the upstream forward, verify the wrapper still works, roll back if not.

    Destructive (`git reset --hard` on rollback) — callers MUST gate this to the
    managed vendor clone via `is_managed_clone`. Fully defensive: any failure
    here is contained so a normal download is never aborted by an update attempt.
    """
    prev = local_head(clone)
    if not prev:
        return  # not a resolvable git clone; leave it alone
    try:
        if not update_repo(clone):
            return  # nothing pulled (e.g. local changes) -> no rollback needed
        new = local_head(clone)
        if new == prev:
            return  # already up to date
        if smoke_check(clone, venv_py, scripts_dir):
            print(
                f"[xhs-downloader] 上游已更新（{prev[:7]} → {new[:7]}），自检通过。",
                file=sys.stderr,
            )
            return
        print(
            f"[xhs-downloader] 上游新版自检失败，回滚到 {prev[:7]}，本次仍用旧版下载。",
            file=sys.stderr,
        )
        _hard_reset(clone, prev)
        sync_deps(clone)
    except Exception as e:  # noqa: BLE001 - update must never break the download
        print(
            f"[xhs-downloader] 自动更新出错（{e}），回滚到 {prev[:7]} 继续。",
            file=sys.stderr,
        )
        _hard_reset(clone, prev)


def _env() -> dict:
    import os
    return dict(os.environ)
