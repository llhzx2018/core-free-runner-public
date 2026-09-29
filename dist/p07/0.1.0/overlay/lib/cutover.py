#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any

import package as package_engine
import verify as restore_verify

INVENTORY_SCHEMA = "vf-server-ops.inventory.v1"
CROSS_SCHEMA = "vf-server-ops.cross-server-verification.v1"
CUTOVER_SCHEMA = "vf-server-ops.cutover-readiness.v1"
UNKNOWN = "UNKNOWN"
DOMAIN_RE = re.compile(r"^[A-Za-z0-9.*_-]+(?:\.[A-Za-z0-9_-]+)+$")
DEFAULT_CURL_RETRY_ATTEMPTS = 8
DEFAULT_CURL_RETRY_DELAY_SECONDS = 2.0


class CutoverError(RuntimeError):
    pass


def load_inventory(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CutoverError(f"invalid inventory manifest: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != INVENTORY_SCHEMA:
        raise CutoverError(f"unsupported inventory manifest: {path}")
    return payload


def find_site(manifest: dict[str, Any], domain: str) -> dict[str, Any]:
    sites = manifest.get("sites", [])
    if not isinstance(sites, list):
        raise CutoverError("inventory sites are invalid")
    for site in sites:
        if isinstance(site, dict) and (site.get("domain") == domain or domain in site.get("domains", [])):
            return site
    raise CutoverError(f"site not found in inventory: {domain}")


def is_unknown(value: Any) -> bool:
    return value is None or value == UNKNOWN


def normalize_runtime_type(value: Any) -> Any:
    if is_unknown(value):
        return UNKNOWN
    return str(value).strip().lower().replace("-", "_")


def normalize_site_path(value: Any, domain: str) -> Any:
    if is_unknown(value):
        return UNKNOWN
    text = str(value)
    marker = f"/htdocs/{domain}"
    index = text.find(marker)
    if index >= 0:
        suffix = text[index + len(marker):]
        return suffix or "/"
    return text


def normalize_sqlite_paths(value: Any, domain: str) -> Any:
    if is_unknown(value):
        return UNKNOWN
    if not isinstance(value, list):
        return UNKNOWN
    return sorted(normalize_site_path(item, domain) for item in value)


def normalize_pm2(value: Any, domain: str) -> Any:
    if is_unknown(value):
        return UNKNOWN
    if not isinstance(value, list):
        return UNKNOWN
    rows = []
    for item in value:
        if not isinstance(item, dict):
            return UNKNOWN
        rows.append((
            str(item.get("name", UNKNOWN)),
            normalize_site_path(item.get("script", UNKNOWN), domain),
            normalize_site_path(item.get("cwd", UNKNOWN), domain),
        ))
    return sorted(rows)


def comparison(name: str, source: Any, target: Any) -> dict[str, Any]:
    if is_unknown(source) or is_unknown(target):
        return {"field": name, "status": "UNKNOWN", "source": "UNKNOWN" if is_unknown(source) else source, "target": "UNKNOWN" if is_unknown(target) else target}
    return {"field": name, "status": "PASS" if source == target else "FAIL", "source": source, "target": target}


def compare_site(source: dict[str, Any], target: dict[str, Any], domain: str) -> dict[str, Any]:
    source_runtime = source.get("runtime", {}) if isinstance(source.get("runtime"), dict) else {}
    target_runtime = target.get("runtime", {}) if isinstance(target.get("runtime"), dict) else {}
    runtime_type_source = normalize_runtime_type(source_runtime.get("type"))
    runtime_type_target = normalize_runtime_type(target_runtime.get("type"))

    checks: list[dict[str, Any]] = [
        comparison("domains", sorted(source.get("domains", [])) if isinstance(source.get("domains"), list) else UNKNOWN, sorted(target.get("domains", [])) if isinstance(target.get("domains"), list) else UNKNOWN),
        comparison("document_root", normalize_site_path(source.get("document_root"), domain), normalize_site_path(target.get("document_root"), domain)),
        comparison("runtime.type", runtime_type_source, runtime_type_target),
        comparison("mysql_databases", sorted(source.get("mysql_databases", [])) if isinstance(source.get("mysql_databases"), list) else UNKNOWN, sorted(target.get("mysql_databases", [])) if isinstance(target.get("mysql_databases"), list) else UNKNOWN),
        comparison("sqlite_paths", normalize_sqlite_paths(source.get("sqlite_paths"), domain), normalize_sqlite_paths(target.get("sqlite_paths"), domain)),
        comparison("cron.entry_count", source.get("cron", {}).get("entry_count") if isinstance(source.get("cron"), dict) else UNKNOWN, target.get("cron", {}).get("entry_count") if isinstance(target.get("cron"), dict) else UNKNOWN),
        comparison("pm2.processes", normalize_pm2(source.get("pm2", {}).get("processes") if isinstance(source.get("pm2"), dict) else UNKNOWN, domain), normalize_pm2(target.get("pm2", {}).get("processes") if isinstance(target.get("pm2"), dict) else UNKNOWN, domain)),
        comparison("ssl.configured", source.get("ssl", {}).get("configured") if isinstance(source.get("ssl"), dict) else UNKNOWN, target.get("ssl", {}).get("configured") if isinstance(target.get("ssl"), dict) else UNKNOWN),
    ]

    if runtime_type_source in {"php"} or runtime_type_target in {"php"}:
        checks.append(comparison("runtime.version", source_runtime.get("version"), target_runtime.get("version")))
    if runtime_type_source in {"nodejs", "node_js", "reverse_proxy", "reverseproxy", "python"} or runtime_type_target in {"nodejs", "node_js", "reverse_proxy", "reverseproxy", "python"}:
        checks.append(comparison("runtime.version", source_runtime.get("version"), target_runtime.get("version")))
        checks.append(comparison("runtime.app_port", source_runtime.get("app_port"), target_runtime.get("app_port")))

    failures = [item["field"] for item in checks if item["status"] == "FAIL"]
    unknowns = [item["field"] for item in checks if item["status"] == "UNKNOWN"]
    status = "FAIL" if failures else ("UNKNOWN" if unknowns else "PASS")
    return {"status": status, "domain": domain, "checks": checks, "failures": failures, "unknowns": unknowns}


def cross_verify(source_inventory: Path, target_inventory: Path, domain: str) -> dict[str, Any]:
    source_manifest = load_inventory(source_inventory)
    target_manifest = load_inventory(target_inventory)
    source_site = find_site(source_manifest, domain)
    target_site = find_site(target_manifest, domain)
    site = compare_site(source_site, target_site, domain)
    source_server = source_manifest.get("source_server", {}).get("hostname_hash", UNKNOWN)
    target_server = target_manifest.get("source_server", {}).get("hostname_hash", UNKNOWN)
    return {
        "schema": CROSS_SCHEMA,
        "status": site["status"],
        "domain": domain,
        "site": site,
        "source_server_identity": source_server,
        "target_server_identity": target_server,
        "server_identity_changed": None if UNKNOWN in (source_server, target_server) else source_server != target_server,
        "server_identity_is_not_a_business_asset_match_requirement": True,
        "secrets_emitted": False,
    }


def validate_domain(domain: str) -> str:
    if not DOMAIN_RE.fullmatch(domain) or domain.startswith("*."):
        raise CutoverError(f"domain is not directly probeable: {domain}")
    return domain.lower()


def probe_retry_settings() -> tuple[int, float]:
    try:
        attempts = int(os.environ.get("VFOPS_CUTOVER_RETRY_ATTEMPTS", str(DEFAULT_CURL_RETRY_ATTEMPTS)))
    except ValueError:
        attempts = DEFAULT_CURL_RETRY_ATTEMPTS
    try:
        delay = float(os.environ.get("VFOPS_CUTOVER_RETRY_DELAY", str(DEFAULT_CURL_RETRY_DELAY_SECONDS)))
    except ValueError:
        delay = DEFAULT_CURL_RETRY_DELAY_SECONDS
    return max(1, min(attempts, 20)), max(0.0, min(delay, 10.0))


def curl_probe(curl: str, domain: str, target_ip: str, scheme: str, path: str) -> dict[str, Any]:
    domain = validate_domain(domain)
    try:
        address = ipaddress.ip_address(target_ip)
    except ValueError as exc:
        raise CutoverError("target IP is invalid") from exc
    if not path.startswith("/") or "\n" in path or "\r" in path:
        raise CutoverError("probe path must be an absolute URL path")
    port = 443 if scheme == "https" else 80
    resolve_ip = f"[{address}]" if address.version == 6 else str(address)
    url = f"{scheme}://{domain}{path}"
    attempts, delay = probe_retry_settings()
    last: dict[str, Any] = {"scheme": scheme, "status": "FAIL", "http_code": None, "curl_exit": None, "attempts": 0}
    for attempt in range(1, attempts + 1):
        try:
            proc = subprocess.run(
                [
                    curl,
                    "--silent", "--show-error", "--output", "/dev/null",
                    "--write-out", "%{http_code}",
                    "--connect-timeout", "10", "--max-time", "30",
                    "--resolve", f"{domain}:{port}:{resolve_ip}",
                    url,
                ],
                text=True,
                capture_output=True,
                check=False,
                timeout=40,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last = {"scheme": scheme, "status": "FAIL", "http_code": None, "error": exc.__class__.__name__, "attempts": attempt}
        else:
            code_text = proc.stdout.strip()[-3:]
            code = int(code_text) if code_text.isdigit() else None
            passed = proc.returncode == 0 and code is not None and 200 <= code < 400
            last = {"scheme": scheme, "status": "PASS" if passed else "FAIL", "http_code": code, "curl_exit": proc.returncode, "attempts": attempt}
            if passed:
                return last
        if attempt < attempts and delay > 0:
            time.sleep(delay)
    return last


def http_https_probe(domains: list[str], target_ip: str, curl: str, path: str = "/") -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    skipped: list[str] = []
    for raw in sorted(set(domains)):
        if raw.startswith("*."):
            skipped.append(raw)
            continue
        domain = validate_domain(raw)
        https = curl_probe(curl, domain, target_ip, "https", path)
        http = curl_probe(curl, domain, target_ip, "http", path)
        results.append({"domain": domain, "https": https, "http": http, "status": "PASS" if https["status"] == "PASS" and http["status"] == "PASS" else "FAIL"})
    failures = [item["domain"] for item in results if item["status"] != "PASS"]
    status = "FAIL" if failures or not results else "PASS"
    return {"status": status, "target_ip": target_ip, "path": path, "results": results, "skipped_wildcards": skipped, "failures": failures, "dns_changed": False, "method": "CURL_RESOLVE_HOST_AND_SNI_WITH_TRANSIENT_RETRY"}


def load_package_domain(package_dir: Path) -> tuple[dict[str, Any], str, list[str]]:
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise CutoverError("backup package failed fresh verification")
    try:
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CutoverError("backup manifest is invalid") from exc
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    domain = str(site.get("domain", ""))
    domains = site.get("domains", [domain]) if isinstance(site.get("domains"), list) else [domain]
    if not domain:
        raise CutoverError("backup package has no domain")
    return manifest, domain, [str(item) for item in domains if isinstance(item, str) and item]


def cutover_readiness(package_dir: Path, source_inventory: Path, target_inventory: Path, target_root: Path, target_ip: str, clpctl: str, curl: str, path: str) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    _, domain, domains = load_package_domain(package_dir)
    try:
        restore = restore_verify.verify_restore(package_dir, target_root.resolve(), clpctl)
    except restore_verify.RestoreVerifyError as exc:
        raise CutoverError(f"restore verification could not run: {exc}") from exc
    cross = cross_verify(source_inventory, target_inventory, domain)
    probe = http_https_probe(domains, target_ip, curl, path)
    blockers: list[str] = []
    if restore.get("status") != "RESTORE_VERIFIED":
        blockers.append("RESTORE_NOT_VERIFIED")
    if cross.get("status") != "PASS":
        blockers.append("CROSS_SERVER_VERIFY_NOT_PASS")
    if probe.get("status") != "PASS":
        blockers.append("HTTP_HTTPS_TARGET_PROBE_NOT_PASS")
    ready = not blockers
    return {
        "schema": CUTOVER_SCHEMA,
        "status": "TECHNICAL_CUTOVER_READY" if ready else "NOT_READY",
        "domain": domain,
        "restore_status": restore.get("status"),
        "cross_server_status": cross.get("status"),
        "http_https_status": probe.get("status"),
        "blockers": blockers,
        "cross_server": cross,
        "http_https_probe": probe,
        "owner_cutover_gate_required": True,
        "automatic_dns_change": False,
        "dns_changed": False,
        "old_server_delete_allowed": False,
        "secrets_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops cross-server and cutover verification")
    sub = parser.add_subparsers(dest="command", required=True)

    cross = sub.add_parser("cross", help="compare source and target inventory for one site")
    cross.add_argument("--source-inventory", required=True)
    cross.add_argument("--target-inventory", required=True)
    cross.add_argument("--domain", required=True)

    cutover = sub.add_parser("cutover", help="compute technical cutover readiness without changing DNS")
    cutover.add_argument("--package", required=True)
    cutover.add_argument("--source-inventory", required=True)
    cutover.add_argument("--target-inventory", required=True)
    cutover.add_argument("--target-root", required=True)
    cutover.add_argument("--target-ip", required=True)
    cutover.add_argument("--path", default="/")
    cutover.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    cutover.add_argument("--curl", default=os.environ.get("VFOPS_CURL", "curl"))
    args = parser.parse_args()

    try:
        if args.command == "cross":
            result = cross_verify(Path(args.source_inventory), Path(args.target_inventory), args.domain)
            success = result["status"] == "PASS"
        else:
            result = cutover_readiness(Path(args.package), Path(args.source_inventory), Path(args.target_inventory), Path(args.target_root), args.target_ip, args.clpctl, args.curl, args.path)
            success = result["status"] == "TECHNICAL_CUTOVER_READY"
    except (CutoverError, restore_verify.RestoreVerifyError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 10
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if success else 10


if __name__ == "__main__":
    raise SystemExit(main())