#!/usr/bin/env bash
set -euo pipefail
usage() { echo "usage: set_profile.sh NAME --stdin [--force]" >&2; exit 2; }
[[ $# -ge 2 ]] || usage
name=$1; shift
stdin=false; force=false
while [[ $# -gt 0 ]]; do case "$1" in --stdin) stdin=true;; --force) force=true;; *) usage;; esac; shift; done
$stdin || usage
[[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ && "$name" != "." && "$name" != ".." ]] || { echo "invalid profile name" >&2; exit 2; }
base="${S3_UPLOAD_CONFIG_HOME:-$HOME/.config/s3-upload}"
script_dir=$(cd "$(dirname "$0")" && pwd -P)
[[ ! -L "$base" ]] || { echo "config home must not be a symlink" >&2; exit 2; }
mkdir -p "$base"; chmod 700 "$base"
base_real=$(cd "$base" && pwd -P)
dir="$base/profiles"
[[ ! -L "$dir" ]] || { echo "profiles directory must not be a symlink" >&2; exit 2; }
mkdir -p "$dir"; chmod 700 "$dir"
dir_real=$(cd "$dir" && pwd -P)
[[ "$dir_real" == "$base_real/profiles" ]] || { echo "profiles directory escapes config home" >&2; exit 2; }
target="$dir/$name.env"
[[ ! -L "$target" ]] || { echo "profile target must not be a symlink" >&2; exit 2; }
[[ ! -e "$target" || "$force" == true ]] || { echo "profile exists; use --force" >&2; exit 1; }
tmp=$(mktemp "$dir/.${name}.XXXXXX"); trap 'rm -f "$tmp"' EXIT
chmod 600 "$tmp"; cat > "$tmp"
python3 - "$tmp" "$script_dir" <<'PY'
import pathlib, sys
sys.path.insert(0, sys.argv[2])
from config import ConfigError, FIELDS, parse_dotenv
p=pathlib.Path(sys.argv[1]); text=p.read_text()
required={'S3_UPLOAD_ACCESS_KEY_ID','S3_UPLOAD_SECRET_ACCESS_KEY','S3_UPLOAD_BUCKET'}
try:
    values=parse_dotenv(text)
except ConfigError as exc:
    raise SystemExit(str(exc))
unknown=set(values)-set(FIELDS)
if unknown: raise SystemExit('unsupported fields: '+', '.join(sorted(unknown)))
missing={key for key in required if not values.get(key)}
if missing: raise SystemExit('missing or empty required fields: '+', '.join(sorted(missing)))
PY
mv -f "$tmp" "$target"; chmod 600 "$target"; trap - EXIT
echo "profile saved: $name" >&2
