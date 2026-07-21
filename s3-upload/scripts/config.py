from __future__ import annotations

import os
import errno
import ipaddress
import re
import stat
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlsplit, urlunsplit

PROFILE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
FIELDS = {
    "S3_UPLOAD_ACCESS_KEY_ID": "access_key_id",
    "S3_UPLOAD_SECRET_ACCESS_KEY": "secret_access_key",
    "S3_UPLOAD_SESSION_TOKEN": "session_token",
    "S3_UPLOAD_BUCKET": "bucket",
    "S3_UPLOAD_ENDPOINT": "endpoint",
    "S3_UPLOAD_REGION": "region",
    "S3_UPLOAD_PROVIDER": "provider",
    "S3_UPLOAD_PUBLIC_BASE_URL": "public_base_url",
    "S3_UPLOAD_PREFIX": "prefix",
    "S3_UPLOAD_MAX_BYTES": "max_bytes",
    "S3_UPLOAD_PRESIGN_EXPIRES": "presign_expires",
    "S3_UPLOAD_ADDRESSING": "addressing",
    "S3_UPLOAD_FORCE_PATH_STYLE": "force_path_style",
    "S3_UPLOAD_PROFILE": "profile",
}

class ConfigError(ValueError):
    pass

@dataclass(frozen=True)
class Connection:
    access_key_id: str
    secret_access_key: str
    bucket: str
    endpoint: str
    region: str
    provider: str = "custom"
    addressing: str = "path"
    session_token: str = ""
    public_base_url: str = ""
    prefix: str = ""
    max_bytes: int = 104857600
    presign_expires: int = 3600


def parse_dotenv(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"invalid dotenv line {number}")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigError(f"invalid dotenv key on line {number}")
        if value[:1] in {"'", '"'}:
            quote_char = value[0]
            end = value.find(quote_char, 1)
            if end < 0 or value[end + 1:].strip() and not value[end + 1:].lstrip().startswith("#"):
                raise ConfigError(f"invalid quoted dotenv value on line {number}")
            value = value[1:end]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        result[key] = value
    return result


def _read_dotenv(path: Path) -> Dict[str, str]:
    if not path.is_file():
        return {}
    return parse_dotenv(path.read_text(encoding="utf-8"))


def _layered(environ: Dict[str, str], cwd: Path) -> Dict[str, str]:
    layers = [dict(environ), _read_dotenv(cwd / ".env.local"), _read_dotenv(cwd / ".env")]
    result: Dict[str, str] = {}
    for key in FIELDS:
        if key in {"S3_UPLOAD_ADDRESSING", "S3_UPLOAD_FORCE_PATH_STYLE"}:
            continue
        for layer in layers:
            if key in layer:
                result[key] = layer[key]
                break
    for layer in layers:
        if "S3_UPLOAD_ADDRESSING" in layer:
            result["S3_UPLOAD_ADDRESSING"] = layer["S3_UPLOAD_ADDRESSING"]
            break
        if layer.get("S3_UPLOAD_FORCE_PATH_STYLE", "").lower() in {"1", "true"}:
            result["S3_UPLOAD_ADDRESSING"] = "path"
            break
    return result


def validate_profile_name(name: str) -> str:
    if name in {".", ".."} or not PROFILE_RE.fullmatch(name):
        raise ConfigError("invalid profile name")
    return name


def load_profile(name: str, config_home: Path) -> Dict[str, str]:
    validate_profile_name(name)
    config_home = config_home.expanduser()
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    home_fd = profiles_fd = profile_fd = None
    try:
        home_fd = os.open(str(config_home), directory_flags)
        profiles_fd = os.open("profiles", directory_flags, dir_fd=home_fd)
        profile_fd = os.open(f"{name}.env", file_flags, dir_fd=profiles_fd)
        home_info, profiles_info, profile_info = os.fstat(home_fd), os.fstat(profiles_fd), os.fstat(profile_fd)
        if not stat.S_ISDIR(home_info.st_mode) or not stat.S_ISDIR(profiles_info.st_mode):
            raise ConfigError("credential profile path must contain directories")
        if stat.S_IMODE(home_info.st_mode) & 0o077 or stat.S_IMODE(profiles_info.st_mode) & 0o077:
            raise ConfigError("credential profile directories must be 0700")
        if not stat.S_ISREG(profile_info.st_mode):
            raise ConfigError("credential profile must be a regular file")
        mode = stat.S_IMODE(profile_info.st_mode)
        if mode & 0o077:
            raise ConfigError(f"credential profile permissions must be 0600, got {mode:04o}")
        chunks = []
        while True:
            chunk = os.read(profile_fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            if sum(map(len, chunks)) > 1048576:
                raise ConfigError("credential profile is too large")
        try:
            text = b"".join(chunks).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ConfigError("credential profile must be UTF-8") from exc
    except ConfigError:
        raise
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            raise ConfigError(f"credential profile not found: {name}") from exc
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise ConfigError("credential profile path contains a symlink or unsafe component") from exc
        raise ConfigError(f"credential profile unavailable or unsafe: {name}") from exc
    finally:
        for descriptor in (profile_fd, profiles_fd, home_fd):
            if descriptor is not None:
                os.close(descriptor)
    values = parse_dotenv(text)
    if "S3_UPLOAD_ADDRESSING" not in values and values.get("S3_UPLOAD_FORCE_PATH_STYLE", "").lower() in {"1", "true"}:
        values["S3_UPLOAD_ADDRESSING"] = "path"
    return {k: v for k, v in values.items() if k in FIELDS and k != "S3_UPLOAD_PROFILE"}


def normalize_endpoint(value: str) -> str:
    if "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError as exc:
        raise ConfigError("endpoint port must be an integer from 1 to 65535") from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname or port == 0:
        raise ConfigError("endpoint must be HTTP(S) with a host")
    if parts.username or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}:
        raise ConfigError("endpoint must not contain userinfo, path, query, or fragment")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def normalize_public_base(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ConfigError("public base URL must be HTTP(S) without userinfo, query, or fragment")
    return value.rstrip("/")


def _validate_virtual(endpoint: str, bucket: str) -> None:
    host = urlsplit(endpoint).hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ConfigError("virtual addressing requires a DNS endpoint")
    labels = host.rstrip(".").split(".")
    if host == "localhost" or len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        raise ConfigError("virtual addressing requires a DNS endpoint")
    bucket_labels = bucket.split(".")
    try:
        ipaddress.ip_address(bucket)
    except ValueError:
        bucket_is_ip = False
    else:
        bucket_is_ip = True
    if not 3 <= len(bucket) <= 63 or bucket_is_ip or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in bucket_labels):
        raise ConfigError("virtual addressing requires a DNS-compatible bucket")


def mask_access_key(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


def resolve_connection(*, environ: Dict[str, str], cwd: str, use_local_key: bool,
                       config_home: str, cli: Optional[Dict[str, object]] = None) -> Connection:
    cli = cli or {}
    high = _layered(environ, Path(cwd))
    profile = str(cli.get("profile") or high.get("S3_UPLOAD_PROFILE") or "")
    if not profile and use_local_key:
        default = Path(config_home) / "profiles" / "default.env"
        if default.exists():
            profile = "default"
    if profile and not use_local_key:
        raise ConfigError("profile requires --use-local-key")
    merged = load_profile(profile, Path(config_home)) if profile else {}
    merged.update({k: v for k, v in high.items() if k != "S3_UPLOAD_PROFILE"})

    cli_map = {
        "provider": "S3_UPLOAD_PROVIDER", "prefix": "S3_UPLOAD_PREFIX",
        "max_bytes": "S3_UPLOAD_MAX_BYTES", "public_base_url": "S3_UPLOAD_PUBLIC_BASE_URL",
        "presign_expires": "S3_UPLOAD_PRESIGN_EXPIRES",
    }
    for arg, env_key in cli_map.items():
        if cli.get(arg) is not None:
            if cli[arg] == "":
                raise ConfigError(f"--{arg.replace('_', '-')} cannot be empty")
            merged[env_key] = str(cli[arg])
    provider = merged.get("S3_UPLOAD_PROVIDER", "custom")
    if provider not in {"custom", "aws-s3", "cloudflare-r2"}:
        raise ConfigError(f"unknown provider: {provider}")
    region = merged.get("S3_UPLOAD_REGION") or ("auto" if provider == "cloudflare-r2" else "us-east-1")
    endpoint = merged.get("S3_UPLOAD_ENDPOINT", "")
    addressing = merged.get("S3_UPLOAD_ADDRESSING") or ("virtual" if provider == "aws-s3" else "path")
    if provider == "aws-s3" and not endpoint:
        endpoint = "https://s3.amazonaws.com" if region == "us-east-1" else f"https://s3.{region}.amazonaws.com"
    if not endpoint:
        raise ConfigError(f"endpoint is required for provider {provider}")
    endpoint = normalize_endpoint(endpoint)
    if addressing not in {"path", "virtual"}:
        raise ConfigError("addressing must be path or virtual")
    required = ["S3_UPLOAD_ACCESS_KEY_ID", "S3_UPLOAD_SECRET_ACCESS_KEY", "S3_UPLOAD_BUCKET"]
    missing = [x for x in required if not merged.get(x)]
    if missing:
        raise ConfigError("incomplete connection: missing " + ", ".join(missing))
    max_bytes = _bounded_int(merged.get("S3_UPLOAD_MAX_BYTES", "104857600"), 1, 536870912, "max bytes")
    expires = _bounded_int(merged.get("S3_UPLOAD_PRESIGN_EXPIRES", "3600"), 1, 604800, "presign expires")
    bucket = merged["S3_UPLOAD_BUCKET"]
    if addressing == "virtual":
        _validate_virtual(endpoint, bucket)
    return Connection(
        access_key_id=merged["S3_UPLOAD_ACCESS_KEY_ID"], secret_access_key=merged["S3_UPLOAD_SECRET_ACCESS_KEY"],
        session_token=merged.get("S3_UPLOAD_SESSION_TOKEN", ""), bucket=bucket, endpoint=endpoint,
        region=region, provider=provider, addressing=addressing,
        public_base_url=normalize_public_base(merged["S3_UPLOAD_PUBLIC_BASE_URL"]) if merged.get("S3_UPLOAD_PUBLIC_BASE_URL") else "",
        prefix=merged.get("S3_UPLOAD_PREFIX", ""),
        max_bytes=max_bytes, presign_expires=expires,
    )


def _bounded_int(value: object, low: int, high: int, label: str) -> int:
    try:
        number = int(str(value))
    except ValueError as exc:
        raise ConfigError(f"{label} must be an integer") from exc
    if not low <= number <= high:
        raise ConfigError(f"{label} must be between {low} and {high}")
    return number
