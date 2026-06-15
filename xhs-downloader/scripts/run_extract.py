"""XHS extraction driver. MUST run inside the XHS-Downloader .venv.

stdout: one-line JSON array (one object per work).
stderr: human summary.
exit codes: 0 ok | 3 empty result (likely needs cookie) | 1 error | 2 arg error.

This is a pure execution layer: no layered config, no masking. The orchestrator
(xhs_dl.py) owns those concerns and passes everything explicitly.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# --repo-path puts the clone on sys.path so `import source` works.


def _media_files(root: Path) -> list:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".mp4", ".mov", ".m4v", ".live"}
    if not root.exists():
        return []
    return sorted(
        str(p) for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts
    )


async def _run(args) -> int:
    from source import XHS  # imported here so --help works without the venv

    work_path = str(Path(args.output_dir).expanduser().resolve())
    folder_name = "Download"
    download_root = Path(work_path) / folder_name

    index = None
    if args.index:
        index = [int(x) for x in args.index.split(",") if x.strip()]

    async with XHS(
        work_path=work_path,
        folder_name=folder_name,
        cookie=args.cookie or "",
        proxy=args.proxy or None,
        timeout=args.timeout,
        image_download=not args.no_image,
        video_download=not args.no_video,
        live_download=args.live,
        folder_mode=True,
        author_archive=False,
        download_record=False,
        record_data=False,
    ) as xhs:
        before = set(_media_files(download_root))
        results = await xhs.extract(
            args.url,
            download=not args.metadata_only,
            index=index,
        )

    works = [r for r in results if isinstance(r, dict) and r]
    if not works:
        print("[]", flush=True)
        print("提取结果为空（可能需要 Cookie 或链接无效）", file=sys.stderr)
        return 3

    after = set(_media_files(download_root))
    new_files = sorted(after - before)

    out = []
    for w in works:
        out.append({
            "作品标题": w.get("作品标题", ""),
            "作品类型": w.get("作品类型", ""),
            "作者昵称": w.get("作者昵称", ""),
            "作品链接": w.get("作品链接", ""),
            "下载地址": w.get("下载地址", ""),
            "动图地址": w.get("动图地址", ""),
            "saved_dir": str(download_root),
        })
    print(json.dumps(out, ensure_ascii=False), flush=True)
    print(
        f"✓ {len(out)} 个作品，新增文件 {len(new_files)} 个，保存到 {download_root}",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="XHS extraction driver (run inside XHS .venv)")
    p.add_argument("--repo-path", required=True, help="XHS-Downloader clone root")
    p.add_argument("--url", required=True, help="one or more links, space-separated")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--index", default="")
    p.add_argument("--cookie", default="")
    p.add_argument("--proxy", default="")
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--no-image", action="store_true")
    p.add_argument("--no-video", action="store_true")
    p.add_argument("--live", action="store_true")
    p.add_argument("--metadata-only", action="store_true")
    args = p.parse_args()

    sys.path.insert(0, str(Path(args.repo_path).expanduser().resolve()))
    try:
        return asyncio.run(_run(args))
    except Exception as e:  # noqa: BLE001 - report upstream failure verbatim
        print(f"提取过程出错: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
