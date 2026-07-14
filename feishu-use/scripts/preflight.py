#!/usr/bin/env python3
"""Read-only lark-cli readiness, version, identity, account, and scope checks."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence


SCHEMA_VERSION = 1
READY_USER_STATUSES = {"ready", "needs_refresh"}
READY_BOT_STATUSES = {"ready"}
EXIT_CODES = {
    "ready": 0,
    "invalid_input": 19,
    "cli_missing": 20,
    "cli_broken": 21,
    "update_available": 22,
    "update_check_failed": 23,
    "config_required": 24,
    "login_required": 25,
    "account_mismatch": 26,
    "account_confirmation_required": 27,
    "scope_required": 28,
    "auth_check_failed": 29,
    "scope_check_failed": 30,
    "identity_unavailable": 31,
    "profile_required": 32,
}

CommandResult = Dict[str, Any]
Executor = Callable[[Sequence[str], float], CommandResult]
CliLocator = Callable[[str], Optional[str]]


def execute_command(argv: Sequence[str], timeout: float) -> CommandResult:
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "command timed out",
        }
    except OSError as exc:
        return {"returncode": 127, "stdout": "", "stderr": str(exc)}

    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_json_result(result: CommandResult) -> Optional[Any]:
    for stream in (result.get("stdout", ""), result.get("stderr", "")):
        text = str(stream).strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


def parse_version(text: str) -> Optional[str]:
    match = re.search(
        r"(?:\bversion\s+|\bv)(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def mask_open_id(open_id: str) -> str:
    if len(open_id) <= 10:
        return open_id
    return f"{open_id[:7]}...{open_id[-4:]}"


def finish(
    report: Dict[str, Any], stage: str, next_action: str, *, ok: bool = False
) -> Dict[str, Any]:
    report["ok"] = ok
    report["stage"] = stage
    report["next_action"] = next_action
    return report


def profile_command(cli_path: str, profile: Optional[str], *args: str) -> List[str]:
    command = [cli_path]
    if profile:
        command.extend(["--profile", profile])
    command.extend(args)
    return command


def is_not_configured(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("reason") == "not_configured":
        return True
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    return error.get("type") == "configuration" or error.get("subtype") in {
        "not_configured",
        "config_missing",
    }


def is_missing_profile(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    message = str(error.get("message") or "").lower()
    return error.get("subtype") == "not_configured" and (
        "profile" in message and "not found" in message
    )


def extract_users(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("users"), list):
        return [item for item in payload["users"] if isinstance(item, dict)]
    return []


def dedupe_scopes(scopes: Sequence[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for group in scopes:
        for scope in group.replace(",", " ").split():
            if scope and scope not in seen:
                seen.add(scope)
                result.append(scope)
    return result


def is_externally_managed_identity(identity_payload: Dict[str, Any]) -> bool:
    message = str(identity_payload.get("message") or "").lower()
    hint = str(identity_payload.get("hint") or "").lower()
    return (
        "provided by " in message
        or "credential source" in message
        or "credential provider" in hint
    )


def run_preflight(
    *,
    identity: str,
    expected_open_id: Optional[str] = None,
    expected_name: Optional[str] = None,
    profile: Optional[str] = None,
    scopes: Optional[Sequence[str]] = None,
    allow_outdated: bool = False,
    allow_unknown_version: bool = False,
    accept_name_match: bool = False,
    cli_name: str = "lark-cli",
    timeout: float = 20.0,
    executor: Executor = execute_command,
    cli_locator: CliLocator = shutil.which,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "stage": "starting",
        "next_action": "inspect",
        "cli": {"installed": False},
        "auth": {"identity": identity},
    }

    if identity not in {"user", "bot"}:
        return finish(report, "invalid_input", "choose_identity")
    if identity == "bot" and (expected_open_id or expected_name or scopes):
        return finish(report, "invalid_input", "remove_user_only_options")

    cli_path = cli_locator(cli_name)
    if not cli_path:
        return finish(report, "cli_missing", "ask_install")

    report["cli"] = {"installed": True, "path": cli_path}
    version_result = executor([cli_path, "--version"], timeout)
    version_output = "\n".join(
        str(version_result.get(stream, "")) for stream in ("stdout", "stderr")
    )
    current_version = parse_version(version_output)
    if version_result.get("returncode") != 0 or not current_version:
        report["cli"]["version_check_exit_code"] = version_result.get("returncode")
        return finish(report, "cli_broken", "ask_reinstall")
    report["cli"]["current_version"] = current_version

    update_result = executor([cli_path, "update", "--check", "--json"], timeout)
    update_payload = parse_json_result(update_result)
    valid_update_payload = (
        isinstance(update_payload, dict)
        and update_payload.get("ok") is not False
        and (
            bool(update_payload.get("action"))
            or bool(update_payload.get("current_version"))
            or bool(update_payload.get("latest_version"))
            or bool(update_payload.get("current"))
            or bool(update_payload.get("latest"))
        )
    )
    if update_result.get("returncode") != 0 or not valid_update_payload:
        report["cli"]["update"] = {
            "status": "unknown",
            "check_exit_code": update_result.get("returncode"),
        }
        if not allow_unknown_version:
            return finish(
                report, "update_check_failed", "ask_continue_without_version_check"
            )
    else:
        update_current = str(
            update_payload.get("current_version")
            or update_payload.get("current")
            or current_version
        )
        latest_version = update_payload.get("latest_version") or update_payload.get(
            "latest"
        )
        action = str(update_payload.get("action", ""))
        update_available = action == "update_available" or (
            latest_version is not None and update_current != str(latest_version)
        )
        report["cli"]["update"] = {
            "status": "update_available" if update_available else "up_to_date",
            "current_version": update_current,
            "latest_version": str(latest_version or update_current),
            "update_command": "lark-cli update --json",
        }
        if update_available and not allow_outdated:
            return finish(report, "update_available", "ask_update_choice")

    if profile:
        report["auth"]["profile"] = profile
    auth_command = profile_command(cli_path, profile, "auth", "status", "--json")
    auth_result = executor(auth_command, timeout)
    auth_payload = parse_json_result(auth_result)
    if is_missing_profile(auth_payload):
        return finish(report, "profile_required", "choose_existing_profile")
    if is_not_configured(auth_payload):
        return finish(report, "config_required", "ask_configure")
    if auth_result.get("returncode") != 0 or not isinstance(auth_payload, dict):
        report["auth"]["check_exit_code"] = auth_result.get("returncode")
        return finish(report, "auth_check_failed", "inspect_auth_error")

    report["auth"]["app_id"] = auth_payload.get("appId")
    report["auth"]["brand"] = auth_payload.get("brand")
    identities = auth_payload.get("identities")
    selected = identities.get(identity) if isinstance(identities, dict) else None
    if not isinstance(selected, dict):
        return finish(report, "auth_check_failed", "inspect_auth_error")

    status = str(selected.get("status", "unknown"))
    available = bool(selected.get("available"))
    externally_managed = is_externally_managed_identity(selected)
    report["auth"]["status"] = status
    report["auth"]["available"] = available
    report["auth"]["managed_externally"] = externally_managed

    ready_statuses = READY_USER_STATUSES if identity == "user" else READY_BOT_STATUSES
    if not available or status not in ready_statuses:
        if externally_managed:
            return finish(
                report,
                "identity_unavailable",
                "repair_external_credential_provider",
            )
        if status == "not_configured":
            return finish(
                report,
                "identity_unavailable",
                "inspect_identity_policy_or_credentials",
            )
        if identity == "user" and status == "missing":
            return finish(report, "login_required", "start_device_login")
        return finish(report, "auth_check_failed", "inspect_auth_error")

    if identity == "bot":
        return finish(report, "ready", "run_lark_cli", ok=True)

    actual_open_id = str(selected.get("openId") or "")
    actual_name = str(selected.get("userName") or "")
    if not actual_open_id or not actual_name:
        list_command = profile_command(cli_path, profile, "auth", "list", "--json")
        list_result = executor(list_command, timeout)
        users = extract_users(parse_json_result(list_result))
        usable_users = [
            user
            for user in users
            if user.get("tokenStatus") in READY_USER_STATUSES
            or user.get("tokenStatus") == "valid"
        ]
        if len(usable_users) == 1:
            actual_open_id = str(usable_users[0].get("userOpenId") or "")
            actual_name = str(usable_users[0].get("userName") or "")

    if not actual_open_id:
        return finish(report, "login_required", "start_device_login")

    report["auth"]["user_name"] = actual_name or None
    report["auth"]["user_open_id_masked"] = mask_open_id(actual_open_id)

    if expected_open_id:
        if actual_open_id != expected_open_id:
            report["auth"]["account_match"] = "mismatch"
            return finish(report, "account_mismatch", "ask_replace_account")
        report["auth"]["account_match"] = "strong"
        if expected_name and actual_name and expected_name != actual_name:
            report["auth"]["account_name_warning"] = "open_id_matched_name_changed"
    elif expected_name:
        if actual_name != expected_name:
            report["auth"]["account_match"] = "mismatch"
            return finish(report, "account_mismatch", "ask_replace_account")
        report["auth"]["account_match"] = "weak"
        if not accept_name_match:
            return finish(
                report,
                "account_confirmation_required",
                "ask_confirm_name_match",
            )
    else:
        report["auth"]["account_match"] = "not_requested"

    required_scopes = dedupe_scopes(scopes or [])
    if required_scopes:
        report["auth"]["required_scopes"] = required_scopes
        if externally_managed:
            report["auth"]["scope_check"] = "delegated_to_external_provider"
            return finish(report, "ready", "run_lark_cli", ok=True)
        scope_value = " ".join(required_scopes)
        scope_command = profile_command(
            cli_path, profile, "auth", "check", "--scope", scope_value, "--json"
        )
        scope_result = executor(scope_command, timeout)
        scope_payload = parse_json_result(scope_result)
        if not isinstance(scope_payload, dict):
            report["auth"]["scope_check_exit_code"] = scope_result.get("returncode")
            return finish(report, "scope_check_failed", "inspect_scope_error")
        scope_error = scope_payload.get("error")
        if isinstance(scope_error, str) and scope_error in {
            "not_logged_in",
            "no_token",
        }:
            return finish(report, "login_required", "start_device_login")
        if "missing" not in scope_payload:
            report["auth"]["scope_check_exit_code"] = scope_result.get("returncode")
            return finish(report, "scope_check_failed", "inspect_scope_error")
        missing = scope_payload.get("missing") or []
        if not isinstance(missing, list):
            return finish(report, "scope_check_failed", "inspect_scope_error")
        report["auth"]["missing_scopes"] = missing
        if missing:
            return finish(report, "scope_required", "authorize_missing_scopes")

    return finish(report, "ready", "run_lark_cli", ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only preflight checks before using lark-cli"
    )
    parser.add_argument("--identity", choices=("user", "bot"), required=True)
    parser.add_argument("--expected-open-id")
    parser.add_argument("--expected-name")
    parser.add_argument("--profile")
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="required user scope; repeat or pass a space/comma-separated group",
    )
    parser.add_argument(
        "--allow-outdated",
        action="store_true",
        help="continue only after the user explicitly chose to skip an available update",
    )
    parser.add_argument(
        "--allow-unknown-version",
        action="store_true",
        help="continue only after the user accepted an unavailable update check",
    )
    parser.add_argument(
        "--accept-name-match",
        action="store_true",
        help="continue only after the user confirmed a display-name-only match",
    )
    parser.add_argument("--cli", default="lark-cli", help="lark-cli executable name")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_preflight(
        identity=args.identity,
        expected_open_id=args.expected_open_id,
        expected_name=args.expected_name,
        profile=args.profile,
        scopes=args.scope,
        allow_outdated=args.allow_outdated,
        allow_unknown_version=args.allow_unknown_version,
        accept_name_match=args.accept_name_match,
        cli_name=args.cli,
        timeout=args.timeout,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return EXIT_CODES.get(str(report.get("stage")), 1)


if __name__ == "__main__":
    sys.exit(main())
