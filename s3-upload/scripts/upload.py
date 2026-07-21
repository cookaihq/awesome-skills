#!/usr/bin/env python3
from __future__ import annotations

import argparse
import mimetypes
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import ConfigError, mask_access_key, resolve_connection
from s3 import TransportError, http_request, presign_get, public_url, put_object

class FileError(ValueError): pass

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Upload one local file to an AWS SigV4-compatible S3 bucket")
    p.add_argument("--file", required=True); p.add_argument("--key"); p.add_argument("--prefix")
    p.add_argument("--content-type"); p.add_argument("--profile"); p.add_argument("--use-local-key", action="store_true")
    p.add_argument("--provider"); p.add_argument("--presign-expires", type=int); p.add_argument("--max-bytes", type=int)
    p.add_argument("--public-base-url"); p.add_argument("--dry-run", action="store_true")
    return p

def object_key(path: Path, key: Optional[str], prefix: str) -> str:
    value = key if key is not None else ((prefix.lstrip("/").rstrip("/") + "/") if prefix else "") + path.name
    if not value or value.startswith("/") or value.endswith("/") or ".." in value.split("/"):
        raise ConfigError("invalid object key")
    return value

def main(argv=None, *, environ=None, cwd=None, config_home=None, transport=http_request, now=None) -> int:
    args = parser().parse_args(argv); environ = dict(os.environ if environ is None else environ); cwd = cwd or os.getcwd()
    config_home = config_home or os.path.expanduser("~/.config/s3-upload")
    cli = {k: getattr(args, k) for k in ("profile", "provider", "prefix", "max_bytes", "public_base_url", "presign_expires")}
    try:
        conn = resolve_connection(environ=environ, cwd=cwd, use_local_key=args.use_local_key, config_home=config_home, cli=cli)
        path = Path(args.file)
        try:
            source = path.open("rb")
        except OSError as exc:
            raise FileError(f"cannot read local file: {exc}") from exc
        with source:
            try:
                info = os.fstat(source.fileno())
            except OSError as exc:
                raise FileError(f"cannot stat local file: {exc}") from exc
            if not stat.S_ISREG(info.st_mode):
                raise FileError("local file is not a regular file")
            size = info.st_size
            if size > conn.max_bytes: raise FileError(f"file exceeds soft size limit {conn.max_bytes}; v1 does not support multipart")
            key = object_key(path, args.key, conn.prefix)
            content_type = args.content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            kind = "public" if conn.public_base_url else "presigned"
            summary = f"bucket={conn.bucket} key={key} url_kind={kind} endpoint={conn.endpoint} size={size} content_type={content_type} access_key={mask_access_key(conn.access_key_id)}"
            if args.dry_run:
                print("[s3-upload] dry_run " + summary, file=sys.stderr); return 0
            try:
                body = source.read(conn.max_bytes + 1)
            except OSError as exc:
                raise FileError(f"cannot read local file: {exc}") from exc
            if len(body) > conn.max_bytes: raise FileError(f"file exceeds soft size limit {conn.max_bytes}; v1 does not support multipart")
        put_object(conn, key, body, content_type, transport=transport, now=now)
        try:
            url = public_url(conn.public_base_url, key) if conn.public_base_url else presign_get(conn, key, conn.presign_expires, now)
        except Exception as exc:
            print(f"[s3-upload] partial_success object_written=true bucket={conn.bucket} key={key} url_error={type(exc).__name__}", file=sys.stderr)
            return 1
        print(url)
        print("[s3-upload] ok " + summary, file=sys.stderr)
        if kind == "presigned":
            moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc) + timedelta(seconds=conn.presign_expires)
            print(f"[s3-upload] url_kind=presigned expires_in={conn.presign_expires} expires_at={moment.isoformat().replace('+00:00','Z')}", file=sys.stderr)
        return 0
    except ConfigError as exc:
        print(f"[s3-upload] config_error: {exc}", file=sys.stderr); return 2
    except FileError as exc:
        print(f"[s3-upload] file_error: {exc}", file=sys.stderr); return 3
    except TransportError as exc:
        print(f"[s3-upload] runtime_error: {exc}", file=sys.stderr); return 1
    except Exception as exc:
        # Do not include exception text: unexpected library/OS errors can embed
        # request headers or connection details. The type is enough to diagnose.
        print(f"[s3-upload] runtime_error: {type(exc).__name__}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
