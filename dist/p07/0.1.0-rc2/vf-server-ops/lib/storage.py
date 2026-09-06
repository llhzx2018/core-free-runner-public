#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Any

import package as package_engine

SCHEMA = "vf-server-ops.storage.v1"
RESULT_SCHEMA = "vf-server-ops.storage-result.v1"
LIST_SCHEMA = "vf-server-ops.storage-list.v1"
FETCH_SCHEMA = "vf-server-ops.storage-fetch.v1"
CONFIG_SCHEMA = "vf-server-ops.storage-config.v1"
REMOTE_MARKER_SCHEMA = "vf-server-ops.remote-completion.v1"
REMOTE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(f"invalid storage config: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CONFIG_SCHEMA:
        raise StorageError(f"unsupported storage config schema: {payload.get('schema') if isinstance(payload, dict) else 'INVALID'}")
    return payload


def validate_relative_remote_path(value: str) -> str:
    if not value or value.startswith("/") or ":" in value or "\\" in value:
        raise StorageError("remote base_path must be a relative rclone path")
    path = PurePosixPath(value)
    if any(part in ("", ".", "..") for part in path.parts):
        raise StorageError("remote base_path contains unsafe path segment")
    return path.as_posix().rstrip("/")


def validate_remote_name(value: str) -> str:
    if not REMOTE_RE.fullmatch(value or ""):
        raise StorageError(f"invalid rclone remote name: {value!r}")
    return value


def validate_backup_id(value: str) -> str:
    if not value or not REMOTE_RE.fullmatch(value) or value in (".", ".."):
        raise StorageError(f"invalid backup id: {value!r}")
    return value


def run_rclone(rclone: str, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [rclone, *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StorageError("rclone operation timed out") from exc
    except OSError as exc:
        raise StorageError("rclone executable is unavailable") from exc


def require_crypt_remote(rclone: str, remote: str) -> None:
    remote = validate_remote_name(remote)
    proc = run_rclone(rclone, ["backend", "encode", f"{remote}:", "__vfops_probe__"], timeout=20)
    if proc.returncode != 0:
        raise StorageError(f"remote {remote} is not a verified rclone crypt remote")


def quota_about(rclone: str, remote: str) -> dict[str, int | None]:
    remote = validate_remote_name(remote)
    proc = run_rclone(rclone, ["about", f"{remote}:", "--json"], timeout=30)
    if proc.returncode != 0:
        raise StorageError(f"quota unavailable for remote {remote}")
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise StorageError(f"invalid quota response for remote {remote}") from exc
    if not isinstance(raw, dict):
        raise StorageError(f"invalid quota response for remote {remote}")
    result: dict[str, int | None] = {}
    for key in ("total", "used", "free", "trashed", "other"):
        value = raw.get(key)
        result[key] = int(value) if isinstance(value, (int, float)) and value >= 0 else None
    return result


def directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file() and not item.is_symlink():
            total += item.stat().st_size
    return total


def read_package_manifest(package_dir: Path) -> dict[str, Any]:
    manifest_path = package_dir / "manifest.json"
    verify_path = package_dir / "verification.json"
    checksums = package_dir / "checksums.sha256"
    if not package_dir.is_dir() or not manifest_path.is_file() or not verify_path.is_file() or not checksums.is_file():
        raise StorageError("package is incomplete: manifest/verification/checksums required")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        verification = json.loads(verify_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorageError("package manifest or verification JSON is invalid") from exc
    if manifest.get("schema") != "vf-server-ops.backup-package.v1":
        raise StorageError("unsupported backup package schema")
    if verification.get("schema") != "vf-server-ops.backup-verification.v1" or verification.get("status") != "PASS":
        raise StorageError("package has no PASS verification evidence")
    fresh_verification = package_engine.verify_package(package_dir)
    if fresh_verification.get("status") != "PASS":
        raise StorageError("local package failed fresh verification before remote operation")
    if manifest.get("security", {}).get("remote_storage_requires_encryption") is not True:
        raise StorageError("package does not declare encrypted remote requirement")
    backup_id = manifest.get("backup_id")
    if not isinstance(backup_id, str):
        raise StorageError("invalid backup_id")
    validate_backup_id(backup_id)
    return manifest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_private_permissions(root: Path) -> None:
    os.chmod(root, 0o700)
    for path in root.rglob("*"):
        try:
            if path.is_dir():
                os.chmod(path, 0o700)
            elif path.is_file():
                os.chmod(path, 0o600)
        except OSError as exc:
            raise StorageError(f"cannot normalize private permissions: {path}") from exc


def normalize_account(raw: dict[str, Any], provider: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise StorageError(f"invalid {provider} account config")
    account_id = str(raw.get("id", ""))
    remote = validate_remote_name(str(raw.get("remote", "")))
    quota_remote = validate_remote_name(str(raw.get("quota_remote", ""))) if raw.get("quota_remote") else None
    reserve = raw.get("reserve_bytes", 0)
    priority = raw.get("priority", 100)
    if not isinstance(reserve, int) or reserve < 0:
        raise StorageError(f"invalid reserve_bytes for {account_id}")
    if not isinstance(priority, int):
        raise StorageError(f"invalid priority for {account_id}")
    if not account_id or "/" in account_id or ".." in account_id:
        raise StorageError("invalid storage account id")
    if provider == "google" and quota_remote is None:
        raise StorageError(f"Google pool account requires quota_remote: {account_id}")
    return {
        "id": account_id,
        "provider": provider,
        "role": str(raw.get("role", "primary" if provider == "google" else "disaster_recovery")),
        "remote": remote,
        "quota_remote": quota_remote,
        "reserve_bytes": reserve,
        "priority": priority,
        "enabled": raw.get("enabled", True) is True,
    }


def accounts_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    google_pool = config.get("google_pool", [])
    if not isinstance(google_pool, list):
        raise StorageError("google_pool must be a list")
    accounts: list[dict[str, Any]] = [normalize_account(raw, "google") for raw in google_pool]
    b2 = config.get("backblaze_b2")
    if isinstance(b2, dict):
        accounts.append(normalize_account(b2, "b2"))
    ids = [item["id"] for item in accounts]
    if len(ids) != len(set(ids)):
        raise StorageError("duplicate storage account id")
    return accounts


def account_status(rclone: str, account: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": account["id"],
        "provider": account["provider"],
        "role": account["role"],
        "enabled": account["enabled"],
        "encrypted_remote": False,
        "quota": None,
        "quota_status": "N_A" if account["provider"] == "b2" and not account["quota_remote"] else "UNKNOWN",
        "health": "DISABLED" if not account["enabled"] else "UNKNOWN",
    }
    if not account["enabled"]:
        return result
    try:
        require_crypt_remote(rclone, account["remote"])
        result["encrypted_remote"] = True
        if account["quota_remote"]:
            result["quota"] = quota_about(rclone, account["quota_remote"])
            result["quota_status"] = "OK"
        result["health"] = "OK"
    except StorageError:
        result["health"] = "UNAVAILABLE"
    return result


def choose_google(rclone: str, accounts: list[dict[str, Any]], package_bytes: int) -> tuple[dict[str, Any], dict[str, Any]]:
    eligible: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    for account in accounts:
        if account["provider"] != "google" or not account["enabled"]:
            continue
        require_crypt_remote(rclone, account["remote"])
        quota = quota_about(rclone, account["quota_remote"])
        free = quota.get("free")
        if free is None:
            continue
        free_after = free - package_bytes
        if free_after < account["reserve_bytes"]:
            continue
        eligible.append((account["priority"], -free_after, account, quota))
    if not eligible:
        raise StorageError("no Google Drive pool account has enough verified free space")
    eligible.sort(key=lambda item: (item[0], item[1], item[2]["id"]))
    _, _, account, quota = eligible[0]
    return account, quota


def select_target(rclone: str, accounts: list[dict[str, Any]], target: str, package_bytes: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if target in ("auto", "google"):
        return choose_google(rclone, accounts, package_bytes)

    candidates = [a for a in accounts if a["enabled"] and (a["id"] == target or (target == "b2" and a["provider"] == "b2"))]
    if len(candidates) != 1:
        raise StorageError(f"storage target not found or ambiguous: {target}")
    account = candidates[0]
    require_crypt_remote(rclone, account["remote"])
    quota = quota_about(rclone, account["quota_remote"]) if account["quota_remote"] else None
    if quota and quota.get("free") is not None and quota["free"] - package_bytes < account["reserve_bytes"]:
        raise StorageError(f"storage target lacks required free-space reserve: {account['id']}")
    return account, quota


def candidate_accounts(accounts: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    enabled = [account for account in accounts if account["enabled"]]
    if source == "auto":
        return sorted(enabled, key=lambda a: (0 if a["provider"] == "google" else 1, a["priority"], a["id"]))
    if source in ("google", "b2"):
        matches = [account for account in enabled if account["provider"] == source]
    else:
        matches = [account for account in enabled if account["id"] == source]
    if not matches:
        raise StorageError(f"storage source not found: {source}")
    return sorted(matches, key=lambda a: (a["priority"], a["id"]))


def remote_destination(account: dict[str, Any], base_path: str, backup_id: str) -> str:
    return f"{account['remote']}:{base_path}/{backup_id}"


def upload_package(rclone: str, package_dir: Path, destination: str, marker: Path) -> None:
    common = ["--immutable", "--retries", "3", "--low-level-retries", "5", "--contimeout", "20s", "--timeout", "5m"]
    copy_proc = run_rclone(rclone, ["copy", str(package_dir), destination, *common], timeout=3600)
    if copy_proc.returncode != 0:
        raise StorageError("remote package transfer failed")

    check_proc = run_rclone(rclone, ["cryptcheck", str(package_dir), destination, "--one-way"], timeout=3600)
    if check_proc.returncode != 0:
        raise StorageError("remote encrypted integrity check failed")

    marker_proc = run_rclone(rclone, ["copyto", str(marker), f"{destination}/_VFOPS_COMPLETE.json", "--immutable", "--retries", "3"], timeout=300)
    if marker_proc.returncode != 0:
        raise StorageError("remote completion marker upload failed")


def push(config_path: Path, package_dir: Path, target: str, rclone: str) -> dict[str, Any]:
    config = load_json(config_path)
    base_path = validate_relative_remote_path(str(config.get("base_path", "VF-Server-Ops")))
    accounts = accounts_from_config(config)
    if not accounts:
        raise StorageError("no storage accounts configured")

    package_dir = package_dir.resolve()
    manifest = read_package_manifest(package_dir)
    package_bytes = directory_size(package_dir)
    if package_bytes <= 0:
        raise StorageError("backup package is empty")

    account, quota = select_target(rclone, accounts, target, package_bytes)
    backup_id = manifest["backup_id"]
    destination = remote_destination(account, base_path, backup_id)

    marker_payload = {
        "schema": REMOTE_MARKER_SCHEMA,
        "status": "COMPLETE",
        "backup_id": backup_id,
        "package_manifest_sha256": sha256_file(package_dir / "manifest.json"),
    }
    fd, marker_name = tempfile.mkstemp(prefix="vfops-complete-", suffix=".json")
    marker = Path(marker_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(marker_payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        upload_package(rclone, package_dir, destination, marker)
    finally:
        marker.unlink(missing_ok=True)

    return {
        "schema": RESULT_SCHEMA,
        "status": "PASS",
        "backup_id": backup_id,
        "package_bytes": package_bytes,
        "account_id": account["id"],
        "provider": account["provider"],
        "role": account["role"],
        "remote": account["remote"],
        "destination": f"{base_path}/{backup_id}",
        "encrypted_remote_verified": True,
        "cryptcheck": "PASS",
        "completion_marker": "_VFOPS_COMPLETE.json",
        "quota_free_before": quota.get("free") if quota else None,
        "quota_status": "OK" if quota else "N_A",
        "reserve_bytes": account["reserve_bytes"],
        "single_account_package": True,
        "local_package_deleted": False,
    }


def read_remote_marker(rclone: str, account: dict[str, Any], base_path: str, backup_id: str) -> dict[str, Any] | None:
    backup_id = validate_backup_id(backup_id)
    destination = remote_destination(account, base_path, backup_id)
    proc = run_rclone(rclone, ["cat", f"{destination}/_VFOPS_COMPLETE.json"], timeout=60)
    if proc.returncode != 0:
        return None
    try:
        marker = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(marker, dict):
        return None
    if marker.get("schema") != REMOTE_MARKER_SCHEMA or marker.get("status") != "COMPLETE" or marker.get("backup_id") != backup_id:
        return None
    digest = marker.get("package_manifest_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    return marker


def list_account_backups(rclone: str, account: dict[str, Any], base_path: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        require_crypt_remote(rclone, account["remote"])
    except StorageError as exc:
        return [], str(exc)
    proc = run_rclone(rclone, ["lsf", f"{account['remote']}:{base_path}", "--dirs-only", "--format", "p"], timeout=120)
    if proc.returncode != 0:
        return [], "REMOTE_LIST_FAILED"
    results: list[dict[str, Any]] = []
    for raw in proc.stdout.splitlines():
        backup_id = raw.strip().rstrip("/")
        try:
            validate_backup_id(backup_id)
        except StorageError:
            continue
        marker = read_remote_marker(rclone, account, base_path, backup_id)
        if marker is None:
            continue
        results.append({
            "backup_id": backup_id,
            "account_id": account["id"],
            "provider": account["provider"],
            "role": account["role"],
            "status": "COMPLETE",
            "package_manifest_sha256": marker["package_manifest_sha256"],
        })
    return results, None


def list_remote_backups(config_path: Path, source: str, rclone: str) -> dict[str, Any]:
    config = load_json(config_path)
    base_path = validate_relative_remote_path(str(config.get("base_path", "VF-Server-Ops")))
    accounts = candidate_accounts(accounts_from_config(config), source)
    backups: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for account in accounts:
        found, error = list_account_backups(rclone, account, base_path)
        backups.extend(found)
        if error:
            errors.append({"account_id": account["id"], "provider": account["provider"], "error": error})
    backups.sort(key=lambda item: (item["backup_id"], item["provider"], item["account_id"]), reverse=True)
    return {
        "schema": LIST_SCHEMA,
        "source": source,
        "complete_only": True,
        "backups": backups,
        "errors": errors,
    }


def find_remote_backup(rclone: str, accounts: list[dict[str, Any]], base_path: str, backup_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for account in accounts:
        require_crypt_remote(rclone, account["remote"])
        marker = read_remote_marker(rclone, account, base_path, backup_id)
        if marker is not None:
            return account, marker
    raise StorageError(f"no COMPLETE remote backup found: {backup_id}")


def fetch_remote_backup(config_path: Path, backup_id: str, target_dir: Path, source: str, rclone: str) -> dict[str, Any]:
    backup_id = validate_backup_id(backup_id)
    config = load_json(config_path)
    base_path = validate_relative_remote_path(str(config.get("base_path", "VF-Server-Ops")))
    accounts = candidate_accounts(accounts_from_config(config), source)
    account, marker = find_remote_backup(rclone, accounts, base_path, backup_id)

    target_dir = target_dir.resolve()
    if not target_dir.is_dir():
        raise StorageError("fetch target directory must already exist")
    final_dir = target_dir / backup_id
    if final_dir.exists():
        raise StorageError(f"local fetched backup already exists: {final_dir}")

    staging = Path(tempfile.mkdtemp(prefix=f".{backup_id}.fetch-", dir=target_dir))
    os.chmod(staging, 0o700)
    destination = remote_destination(account, base_path, backup_id)
    try:
        proc = run_rclone(
            rclone,
            ["copy", destination, str(staging), "--exclude", "_VFOPS_COMPLETE.json", "--retries", "3", "--low-level-retries", "5", "--contimeout", "20s", "--timeout", "5m"],
            timeout=3600,
        )
        if proc.returncode != 0:
            raise StorageError("remote backup fetch failed")
        normalize_private_permissions(staging)
        manifest = read_package_manifest(staging)
        if manifest.get("backup_id") != backup_id:
            raise StorageError("fetched package backup_id does not match requested id")
        manifest_sha = sha256_file(staging / "manifest.json")
        if manifest_sha != marker["package_manifest_sha256"]:
            raise StorageError("fetched package does not match remote completion marker")
        os.replace(staging, final_dir)
        normalize_private_permissions(final_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return {
        "schema": FETCH_SCHEMA,
        "status": "PASS",
        "backup_id": backup_id,
        "source_account_id": account["id"],
        "provider": account["provider"],
        "role": account["role"],
        "encrypted_remote_verified": True,
        "completion_marker_verified": True,
        "fresh_local_verification": "PASS",
        "local_path": str(final_dir),
        "local_mode": "0700/0600",
        "remote_deleted": False,
    }


def status(config_path: Path, rclone: str) -> dict[str, Any]:
    config = load_json(config_path)
    accounts = accounts_from_config(config)
    return {
        "schema": SCHEMA,
        "base_path": validate_relative_remote_path(str(config.get("base_path", "VF-Server-Ops"))),
        "accounts": [account_status(rclone, account) for account in accounts],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops encrypted remote storage adapter")
    parser.add_argument("--config", required=True, help="storage metadata config; contains no credentials")
    parser.add_argument("--rclone", default=os.environ.get("VFOPS_RCLONE", "rclone"), help="rclone executable")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="check configured storage remotes and quota")

    list_parser = sub.add_parser("list", help="list only COMPLETE remote backups")
    list_parser.add_argument("--source", default="auto", help="auto/google/b2 or configured account id")

    push_parser = sub.add_parser("push", help="upload a verified package to an encrypted remote")
    push_parser.add_argument("--package", required=True, help="verified local backup package directory")
    push_parser.add_argument("--target", default="auto", help="auto/google/b2 or configured account id")

    fetch_parser = sub.add_parser("fetch", help="fetch and reverify a COMPLETE encrypted remote backup")
    fetch_parser.add_argument("--backup-id", required=True, help="backup id returned by storage list")
    fetch_parser.add_argument("--target-dir", required=True, help="existing private local directory for fetched backup")
    fetch_parser.add_argument("--source", default="auto", help="auto/google/b2 or configured account id")
    args = parser.parse_args()

    try:
        if args.command == "status":
            result = status(Path(args.config), args.rclone)
        elif args.command == "list":
            result = list_remote_backups(Path(args.config), args.source, args.rclone)
        elif args.command == "push":
            result = push(Path(args.config), Path(args.package), args.target, args.rclone)
        else:
            result = fetch_remote_backup(Path(args.config), args.backup_id, Path(args.target_dir), args.source, args.rclone)
    except StorageError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 5
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
