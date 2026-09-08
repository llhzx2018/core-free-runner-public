#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

SCHEMA = "vf-server-ops.storage-config.v1"
RESULT_SCHEMA = "vf-server-ops.storage-setup.v1"
REMOTE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
DEFAULT_CONFIG = Path("/etc/vf-server-ops/storage.json")
DEFAULT_MACHINE_ID = Path("/etc/machine-id")
PROVENANCE_VERSION = 1
PROVENANCE_FRESH = "GUIDED_DEVICE_OAUTH_FRESH"


class SetupError(RuntimeError):
    pass


def run(rclone: str, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run([rclone, *args], text=True, capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError("rclone command unavailable or timed out") from exc


def normalize_remote(value: str) -> str:
    name = value.strip().rstrip(":")
    if not REMOTE_RE.fullmatch(name):
        raise SetupError(f"invalid rclone remote name: {value!r}")
    return name


def host_binding(machine_id_path: Path = DEFAULT_MACHINE_ID) -> str:
    try:
        machine_id = machine_id_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SetupError("local VPS machine identity unavailable") from exc
    if not machine_id:
        raise SetupError("local VPS machine identity is empty")
    return "sha256:" + hashlib.sha256(machine_id.encode("utf-8")).hexdigest()


def list_remotes(rclone: str) -> list[str]:
    proc = run(rclone, ["listremotes"])
    if proc.returncode != 0:
        raise SetupError("cannot list rclone remotes")
    result: list[str] = []
    for line in proc.stdout.splitlines():
        raw = line.strip()
        if not raw:
            continue
        name = normalize_remote(raw)
        if name not in result:
            result.append(name)
    return result


def redacted_config(rclone: str, remote: str) -> dict[str, str]:
    remote = normalize_remote(remote)
    proc = run(rclone, ["config", "redacted", remote])
    if proc.returncode != 0:
        raise SetupError(f"cannot safely inspect rclone remote: {remote}")
    values: dict[str, str] = {}
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("[") or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip()
    if not values.get("type"):
        raise SetupError(f"remote type unavailable from redacted config: {remote}")
    return values


def remote_type(rclone: str, remote: str) -> str:
    return redacted_config(rclone, remote).get("type", "").lower()


def crypt_underlying(rclone: str, crypt_remote: str) -> str:
    config = redacted_config(rclone, crypt_remote)
    if config.get("type", "").lower() != "crypt":
        raise SetupError(f"remote is not crypt: {crypt_remote}")
    underlying = config.get("remote", "")
    if not underlying or ":" not in underlying:
        raise SetupError(f"crypt underlying remote unavailable: {crypt_remote}")
    return normalize_remote(underlying.split(":", 1)[0])


def verify_google_pair(rclone: str, direct_remote: str, crypt_remote: str) -> dict[str, Any]:
    direct = normalize_remote(direct_remote)
    crypt = normalize_remote(crypt_remote)
    if remote_type(rclone, direct) != "drive":
        raise SetupError(f"Google source remote is not type=drive: {direct}")
    underlying = crypt_underlying(rclone, crypt)
    if underlying != direct:
        raise SetupError(f"Google crypt remote {crypt} does not point to {direct}")
    about = run(rclone, ["about", f"{direct}:", "--json"])
    if about.returncode != 0:
        raise SetupError(f"Google quota check failed: {direct}")
    try:
        quota = json.loads(about.stdout)
    except json.JSONDecodeError as exc:
        raise SetupError("Google quota response is invalid") from exc
    encode = run(rclone, ["backend", "encode", f"{crypt}:", "__vfops_probe__"])
    if encode.returncode != 0:
        raise SetupError(f"Google crypt verification failed: {crypt}")
    return {"direct": direct, "crypt": crypt, "quota": quota}


def verify_b2_crypt(rclone: str, crypt_remote: str) -> dict[str, str]:
    crypt = normalize_remote(crypt_remote)
    underlying = crypt_underlying(rclone, crypt)
    if remote_type(rclone, underlying) != "b2":
        raise SetupError(f"B2 crypt remote does not point to type=b2: {crypt}")
    encode = run(rclone, ["backend", "encode", f"{crypt}:", "__vfops_probe__"])
    if encode.returncode != 0:
        raise SetupError(f"B2 crypt verification failed: {crypt}")
    return {"direct": underlying, "crypt": crypt}


def provenance_payload(binding: str) -> dict[str, Any]:
    if not isinstance(binding, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", binding):
        raise SetupError("invalid local VPS provenance binding")
    return {"version": PROVENANCE_VERSION, "mode": PROVENANCE_FRESH, "host_binding": binding}


def build_config(google_direct: str, google_crypt: str, b2_crypt: str, binding: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "base_path": "VF-Server-Ops",
        "setup_provenance": provenance_payload(binding),
        "google_pool": [
            {
                "id": "google-a",
                "provider": "google",
                "role": "primary",
                "remote": google_crypt,
                "quota_remote": google_direct,
                "reserve_bytes": 5368709120,
                "priority": 10,
                "enabled": True,
            }
        ],
        "backblaze_b2": {
            "id": "b2-dr",
            "provider": "b2",
            "role": "disaster_recovery",
            "remote": b2_crypt,
            "reserve_bytes": 0,
            "priority": 100,
            "enabled": True,
        },
    }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    if os.geteuid() != 0:
        raise SetupError("storage setup write requires root")
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def configure(rclone: str, config_path: Path, google_direct: str, google_crypt: str, b2_crypt: str, machine_id_path: Path = DEFAULT_MACHINE_ID) -> dict[str, Any]:
    binding = host_binding(machine_id_path)
    google = verify_google_pair(rclone, google_direct, google_crypt)
    b2 = verify_b2_crypt(rclone, b2_crypt)
    payload = build_config(google["direct"], google["crypt"], b2["crypt"], binding)
    atomic_write(config_path, payload)
    return {
        "schema": RESULT_SCHEMA,
        "status": "PASS",
        "config": str(config_path),
        "google_direct": google["direct"],
        "google_crypt": google["crypt"],
        "b2_direct": b2["direct"],
        "b2_crypt": b2["crypt"],
        "setup_provenance": {"version": PROVENANCE_VERSION, "mode": PROVENANCE_FRESH, "local_host_bound": True},
        "secrets_written_to_p07_config": False,
        "mode": "0600",
    }


def inspect(rclone: str) -> dict[str, Any]:
    remotes = list_remotes(rclone)
    rows: list[dict[str, str]] = []
    for remote in remotes:
        try:
            config = redacted_config(rclone, remote)
            typ = config.get("type", "UNKNOWN")
            underlying = ""
            if typ.lower() == "crypt" and config.get("remote") and ":" in config["remote"]:
                underlying = normalize_remote(config["remote"].split(":", 1)[0])
            rows.append({"name": remote, "type": typ, "underlying": underlying})
        except SetupError:
            rows.append({"name": remote, "type": "UNKNOWN", "underlying": ""})
    return {"schema": RESULT_SCHEMA, "status": "PASS", "remotes": rows, "secret_values_emitted": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="P07 no-secret rclone storage setup")
    parser.add_argument("--rclone", default=os.environ.get("VFOPS_RCLONE", "rclone"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    cfg = sub.add_parser("configure")
    cfg.add_argument("--config", default=str(DEFAULT_CONFIG))
    cfg.add_argument("--google-direct", required=True)
    cfg.add_argument("--google-crypt", required=True)
    cfg.add_argument("--b2-crypt", required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect(args.rclone)
        else:
            result = configure(args.rclone, Path(args.config), args.google_direct, args.google_crypt, args.b2_crypt)
    except SetupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 13
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
