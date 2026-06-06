#!/usr/bin/env bash
# Store X_API_KEY into ~/.config/upload-for-url/.env (read only with --use-local-key).
set -euo pipefail
CONFIG_DIR="${HOME}/.config/upload-for-url"
mkdir -p "$CONFIG_DIR"
if [[ "${1:-}" == "--stdin" ]]; then
  read -r KEY
else
  read -r -p "Enter X_API_KEY (sk-...): " KEY
fi
if [[ -z "${KEY:-}" ]]; then
  echo "no key provided" >&2
  exit 1
fi
printf 'X_API_KEY=%s\n' "$KEY" > "$CONFIG_DIR/.env"
chmod 600 "$CONFIG_DIR/.env"
masked="${KEY:0:4}****${KEY: -4}"
echo "saved to $CONFIG_DIR/.env (key=$masked)"
