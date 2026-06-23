"""Offline integration-contract smoke check for the upstream XHS class.

Run inside the XHS-Downloader .venv after an auto-update. It does NOT touch the
network, a cookie, or download anything — it only introspects `source.XHS` to
confirm the wrapper's call contract still holds ("使用方式不变"). If upstream
renamed/removed a constructor kwarg we pass by name (its `**kwargs` would
otherwise swallow the change silently) or changed `extract`'s signature, this
reports it and the caller rolls the update back.

exit 0: contract intact. exit 1: contract broken (problems printed to stderr).
exit 2: could not import `source.XHS` at all.
"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

# Constructor kwargs run_extract.py passes XHS by name. Each must remain a named
# parameter upstream — relying on **kwargs to absorb a rename would silently
# break behavior (e.g. images stop downloading), so we require the names.
REQUIRED_INIT_PARAMS = [
    "work_path",
    "folder_name",
    "cookie",
    "proxy",
    "timeout",
    "image_download",
    "video_download",
    "live_download",
    "folder_mode",
    "author_archive",
    "download_record",
    "record_data",
]

# Arguments run_extract.py passes to `await xhs.extract(...)`.
REQUIRED_EXTRACT_PARAMS = ["url", "download", "index"]


def _can_bind(sig: inspect.Signature, name: str) -> bool:
    """True if `name` is an explicit parameter or absorbed by **kwargs."""
    params = sig.parameters
    if name in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def check_contract(xhs_cls) -> list:
    """Return a list of human-readable problem strings; empty means contract OK."""
    problems = []

    # async context manager
    for dunder in ("__aenter__", "__aexit__"):
        fn = getattr(xhs_cls, dunder, None)
        if fn is None:
            problems.append(f"XHS 缺少 {dunder}（不再是 async context manager）")
        elif not inspect.iscoroutinefunction(fn):
            problems.append(f"XHS.{dunder} 不是协程")

    # __init__ keeps every kwarg we pass by name
    init = getattr(xhs_cls, "__init__", None)
    if init is None:
        problems.append("XHS 缺少 __init__")
    else:
        sig = inspect.signature(init)
        params = sig.parameters
        for name in REQUIRED_INIT_PARAMS:
            # Demand an explicit named param: **kwargs absorbing it would hide a rename.
            if name not in params:
                problems.append(f"XHS.__init__ 不再接受具名参数 `{name}`")

    # extract is a coroutine accepting (url, download, index)
    extract = getattr(xhs_cls, "extract", None)
    if extract is None:
        problems.append("XHS 缺少 extract 方法")
    else:
        if not inspect.iscoroutinefunction(extract):
            problems.append("XHS.extract 不是协程（async def）")
        sig = inspect.signature(extract)
        for name in REQUIRED_EXTRACT_PARAMS:
            if not _can_bind(sig, name):
                problems.append(f"XHS.extract 不再接受参数 `{name}`")

    return problems


def main() -> int:
    p = argparse.ArgumentParser(description="XHS integration-contract smoke check")
    p.add_argument("--repo-path", required=True, help="XHS-Downloader clone root")
    args = p.parse_args()

    sys.path.insert(0, str(Path(args.repo_path).expanduser().resolve()))
    try:
        from source import XHS
    except Exception as e:  # noqa: BLE001 - any import failure means the contract is broken
        print(f"[xhs-downloader] 自检失败：无法导入 source.XHS（{e}）", file=sys.stderr)
        return 2

    problems = check_contract(XHS)
    if problems:
        print("[xhs-downloader] 上游契约自检失败：", file=sys.stderr)
        for prob in problems:
            print(f"  - {prob}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
