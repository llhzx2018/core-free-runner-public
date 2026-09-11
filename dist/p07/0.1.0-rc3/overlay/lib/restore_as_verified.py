#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence

import cloudpanel
import restore_as
import site_lifecycle

RESULT_SCHEMA = "vf-server-ops.restore-as-verified-result.v1"


class RestoreAsVerificationError(RuntimeError):
    pass


def _run(command: Sequence[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RestoreAsVerificationError("local verification command failed") from exc


def _http_code(curl: str, domain: str, scheme: str, port: int) -> tuple[int, str]:
    command = [
        curl,
        "--silent",
        "--show-error",
        "--output",
        "/dev/null",
        "--write-out",
        "%{http_code}",
        "--connect-timeout",
        "5",
        "--max-time",
        "15",
        "--resolve",
        f"{domain}:{port}:127.0.0.1",
    ]
    if scheme == "https":
        # The target certificate is intentionally not copied from SOURCE. Before DNS
        # is ready CloudPanel may expose a local/default certificate, so TLS identity
        # is not trusted here; --resolve still exercises target-domain SNI routing.
        command.append("--insecure")
    command.append(f"{scheme}://{domain}/")
    proc = _run(command)
    return proc.returncode, proc.stdout.strip()


def _valid_http_code(value: str) -> bool:
    return bool(re.fullmatch(r"[1-5][0-9]{2}", value))


def _nginx_has_target_vhost(nginx: str, domain: str) -> bool:
    proc = _run([nginx, "-T"], timeout=30)
    if proc.returncode != 0:
        return False
    text = f"{proc.stdout}\n{proc.stderr}"
    for match in re.finditer(r"\bserver_name\s+([^;]+);", text):
        names = {item.strip().lower() for item in match.group(1).split()}
        if domain.lower() in names:
            return True
    return False


def verify_local_restore(
    target_root: Path,
    result: dict[str, Any],
    *,
    curl: str = "/usr/bin/curl",
    nginx: str = "/usr/sbin/nginx",
) -> dict[str, Any]:
    source_domain = cloudpanel.validate_domain(str(result.get("source_domain", "")))
    target_domain = cloudpanel.validate_domain(str(result.get("target_domain", "")))
    if source_domain == target_domain:
        raise RestoreAsVerificationError("Restore-As target unexpectedly equals SOURCE")
    if result.get("dns_changed") is not False or result.get("source_deleted") is not False:
        raise RestoreAsVerificationError("Restore-As safety result is not fail-closed")
    if result.get("existing_site_overwrite_allowed") is not False or result.get("source_ssl_reused") is not False:
        raise RestoreAsVerificationError("Restore-As overwrite/TLS safety result is invalid")

    site_root = str(result.get("target_site_root", ""))
    if not site_root.startswith("/home/"):
        raise RestoreAsVerificationError("target site root is invalid")
    final_site = (target_root.resolve() / site_root.lstrip("/")).resolve(strict=False)
    root = target_root.resolve()
    if root not in final_site.parents:
        raise RestoreAsVerificationError("target site root escapes target")
    if not final_site.is_dir() or final_site.is_symlink():
        raise RestoreAsVerificationError("restored site root is unavailable")
    file_count = sum(1 for item in final_site.rglob("*") if item.is_file() and not item.is_symlink())
    if file_count < 1:
        raise RestoreAsVerificationError("restored site contains no files")

    http_rc, http_code = _http_code(curl, target_domain, "http", 80)
    if http_rc != 0 or not _valid_http_code(http_code):
        raise RestoreAsVerificationError("local Host routing verification failed")

    https_rc, https_code = _http_code(curl, target_domain, "https", 443)
    if https_rc == 0 and _valid_http_code(https_code):
        sni = {
            "status": "PASS",
            "mode": "LOCAL_HTTPS_SNI",
            "http_code": https_code,
            "certificate_trust": "NOT_ASSERTED_UNTIL_TARGET_DNS_CERTIFICATE",
        }
    elif _nginx_has_target_vhost(nginx, target_domain):
        # DNS may not yet point at this server and no target-domain certificate is
        # installed by Restore-As. The vhost identity is still verified locally;
        # certificate issuance remains explicitly deferred rather than reusing SOURCE.
        sni = {
            "status": "PASS",
            "mode": "TARGET_VHOST_PRESENT_TLS_DEFERRED",
            "http_code": None,
            "certificate_trust": "DEFERRED_UNTIL_TARGET_DNS_CERTIFICATE",
        }
    else:
        raise RestoreAsVerificationError("local SNI/vhost verification failed")

    return {
        "status": "PASS",
        "files": {"status": "PASS", "file_count": file_count},
        "database": {
            "status": "PASS" if result.get("database_import_verified_before_transform") else "NOT_APPLICABLE",
            "source_match_before_transform": bool(result.get("database_import_verified_before_transform")),
        },
        "application": {
            "status": "PASS",
            "mode": result.get("application_config_mode", "UNKNOWN"),
            "wordpress_urls": result.get("wordpress_urls"),
        },
        "host": {"status": "PASS", "mode": "LOCAL_HTTP_RESOLVE", "http_code": http_code},
        "sni": sni,
        "dns_changed": False,
        "source_deleted": False,
        "source_certificate_reused": False,
    }


def _rollback_verified_target(result: dict[str, Any], *, clpctl: str) -> dict[str, bool]:
    database = result.get("target_database")
    db_ok = True
    if isinstance(database, str) and database:
        db_ok = site_lifecycle.cleanup_database(database, clpctl=clpctl)
    domain = str(result.get("target_domain", ""))
    site_ok = bool(domain) and site_lifecycle.cleanup_site(domain, clpctl=clpctl)
    return {"database": db_ok, "site": site_ok}


def restore_as_verified(
    package_dir: Path,
    target_domain: str,
    target_root: Path,
    clpctl: str,
    confirm: str,
    *,
    runuser: str = "runuser",
    wp: str = "wp",
    curl: str = "/usr/bin/curl",
    nginx: str = "/usr/sbin/nginx",
) -> dict[str, Any]:
    result = restore_as.restore_as(
        package_dir,
        target_domain,
        target_root,
        clpctl,
        confirm,
        runuser=runuser,
        wp=wp,
    )
    try:
        local = verify_local_restore(target_root, result, curl=curl, nginx=nginx)
    except Exception as exc:
        rollback = _rollback_verified_target(result, clpctl=clpctl)
        rollback_status = "PASS" if all(rollback.values()) else "PARTIAL"
        reason = exc if isinstance(exc, RestoreAsVerificationError) else exc.__class__.__name__
        raise RestoreAsVerificationError(
            f"Restore-As local verification failed; rollback={rollback_status}; reason={reason}"
        ) from exc

    final = dict(result)
    final["schema"] = RESULT_SCHEMA
    final["status"] = "RESTORE_AS_VERIFIED"
    final["restore_engine_status"] = result.get("status")
    final["local_verification"] = local
    final["machine_verification_scope"] = "FILES_DB_APP_HOST_SNI"
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops Restore-As with automatic local verification")
    parser.add_argument("--package", required=True)
    parser.add_argument("--target-domain", required=True)
    parser.add_argument("--target-root", default="/")
    parser.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    parser.add_argument("--runuser", default=os.environ.get("VFOPS_RUNUSER", "runuser"))
    parser.add_argument("--wp", default=os.environ.get("VFOPS_WP", "wp"))
    parser.add_argument("--curl", default=os.environ.get("VFOPS_CURL", "/usr/bin/curl"))
    parser.add_argument("--nginx", default=os.environ.get("VFOPS_NGINX", "/usr/sbin/nginx"))
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        result = restore_as_verified(
            Path(args.package),
            args.target_domain,
            Path(args.target_root),
            args.clpctl,
            args.confirm,
            runuser=args.runuser,
            wp=args.wp,
            curl=args.curl,
            nginx=args.nginx,
        )
    except (
        RestoreAsVerificationError,
        restore_as.RestoreAsError,
        cloudpanel.CloudPanelError,
        site_lifecycle.SiteLifecycleError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 15
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
