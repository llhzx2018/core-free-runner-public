#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import cloudpanel
import package as package_engine
import restore as restore_plan
import restore_apply
import restore_new
import site_lifecycle
import verify as verify_engine

RESULT_SCHEMA = "vf-server-ops.restore-as-result.v1"
CONTROLLED_MARKER = restore_new.CONTROLLED_MARKER
CONTROLLED_MARKER_VALUE = restore_new.CONTROLLED_MARKER_VALUE
ENV_NAMES = (".env", ".env.local", ".env.production", ".env.prod")
DB_NAME_KEYS = {"DB_DATABASE", "DB_NAME", "MYSQL_DATABASE", "DATABASE_NAME"}
DB_USER_KEYS = {"DB_USERNAME", "DB_USER", "MYSQL_USER", "DATABASE_USER"}
DB_PASS_KEYS = {"DB_PASSWORD", "DB_PASS", "MYSQL_PASSWORD", "DATABASE_PASSWORD"}
DB_URL_KEYS = {"DATABASE_URL", "MYSQL_URL", "MARIADB_URL"}
SITE_URL_KEYS = {"APP_URL", "SITE_URL", "URL"}


class RestoreAsError(RuntimeError):
    pass


def load_manifest(package_dir: Path) -> dict[str, Any]:
    try:
        payload = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestoreAsError("backup manifest is invalid") from exc
    if payload.get("schema") != package_engine.PACKAGE_SCHEMA:
        raise RestoreAsError("unsupported backup package schema")
    return payload


def expected_confirm(manifest: dict[str, Any], target_domain: str) -> str:
    source_domain = str((manifest.get("site") or {}).get("domain", ""))
    backup_id = str(manifest.get("backup_id", ""))
    target_domain = cloudpanel.validate_domain(target_domain)
    if not source_domain or not backup_id:
        raise RestoreAsError("backup identity is incomplete")
    return f"RESTORE_AS:{source_domain}:{target_domain}:{backup_id}"


def require_target(target_root: Path, manifest: dict[str, Any], target_domain: str, confirm: str) -> Path:
    root = target_root.resolve()
    if not root.is_dir():
        raise RestoreAsError("target root must already exist")
    if confirm != expected_confirm(manifest, target_domain):
        raise RestoreAsError("explicit Restore-As confirmation is invalid")
    if root == Path("/"):
        if not Path("/home/clp/htdocs/app/data/db.sq3").is_file():
            raise RestoreAsError("/ is not a detected CloudPanel target")
    else:
        marker = root / CONTROLLED_MARKER
        try:
            value = marker.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RestoreAsError("controlled CloudPanel target marker is missing") from exc
        if value != CONTROLLED_MARKER_VALUE:
            raise RestoreAsError("controlled CloudPanel target marker is invalid")
    return root


def _private_payload(package_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    info = manifest.get("contents", {}).get("metadata", {}).get("cloudpanel_private_metadata", {})
    relative = info.get("file") if isinstance(info, dict) else None
    if not isinstance(relative, str):
        return {}
    try:
        path = restore_plan.safe_package_path(package_dir, relative)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, restore_plan.RestorePlanError):
        return {}
    return payload if isinstance(payload, dict) else {}


def source_vhost_template(package_dir: Path, manifest: dict[str, Any]) -> str:
    payload = _private_payload(package_dir, manifest)
    rows = payload.get("tables", {}).get("site", []) if isinstance(payload.get("tables"), dict) else []
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        value = rows[0].get("vhost_template")
        if isinstance(value, str) and value and "\x00" not in value and "\n" not in value and "\r" not in value:
            return value
    return "Generic"


def _php_single_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def rewrite_wordpress_config(path: Path, database: str, username: str, password: str) -> None:
    try:
        original = path.read_text(encoding="utf-8")
        mode = path.stat().st_mode & 0o777
    except OSError as exc:
        raise RestoreAsError("WordPress wp-config.php cannot be read") from exc

    replacements = {
        "DB_NAME": database,
        "DB_USER": username,
        "DB_PASSWORD": password,
    }
    text = original
    for key, value in replacements.items():
        pattern = re.compile(
            rf"define\s*\(\s*(['\"]){re.escape(key)}\1\s*,\s*(['\"])(.*?)\2\s*\)\s*;",
            re.DOTALL,
        )
        replacement = f"define('{key}', '{_php_single_quote(value)}');"
        text, count = pattern.subn(lambda _m, r=replacement: r, text, count=1)
        if count != 1:
            raise RestoreAsError(f"WordPress {key} mapping is unavailable")

    fd, temp_name = tempfile.mkstemp(prefix=".vfops-wp-config-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _split_env_line(line: str) -> tuple[str, str, str] | None:
    match = re.match(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*?)(\r?\n?)$", line)
    if not match:
        return None
    prefix = f"{match.group(1)}{match.group(2)}{match.group(3)}"
    return match.group(2), prefix, f"{match.group(4)}{match.group(5)}"


def _env_quote_like(old: str, value: str) -> str:
    newline = "\n" if old.endswith("\n") else ""
    body = old[:-1] if newline else old
    stripped = body.strip()
    if stripped.startswith("'") and stripped.endswith("'"):
        return "'" + value.replace("'", "\\'") + "'" + newline
    if stripped.startswith('"') and stripped.endswith('"'):
        return '"' + value.replace('"', '\\"') + '"' + newline
    return value + newline


def _rewrite_database_url(old_value: str, database: str, username: str, password: str) -> str:
    quote_char = ""
    stripped = old_value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        quote_char = stripped[0]
        stripped = stripped[1:-1]
    parts = urlsplit(stripped)
    if parts.scheme not in {"mysql", "mariadb"} or not parts.hostname:
        raise RestoreAsError("database URL cannot be safely remapped")
    host = parts.hostname
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{host}"
    rebuilt = urlunsplit((parts.scheme, netloc, f"/{quote(database, safe='')}", parts.query, parts.fragment))
    return f"{quote_char}{rebuilt}{quote_char}" if quote_char else rebuilt


def rewrite_dotenv(path: Path, database: str, username: str, password: str, source_domain: str, target_domain: str) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        mode = path.stat().st_mode & 0o777
    except OSError:
        return False
    changed = False
    mapped_db = mapped_user = mapped_pass = False
    out: list[str] = []
    for line in lines:
        parsed = _split_env_line(line)
        if parsed is None:
            out.append(line)
            continue
        key, prefix, old_value = parsed
        new_value: str | None = None
        if key in DB_NAME_KEYS:
            new_value = _env_quote_like(old_value, database)
            mapped_db = True
        elif key in DB_USER_KEYS:
            new_value = _env_quote_like(old_value, username)
            mapped_user = True
        elif key in DB_PASS_KEYS:
            new_value = _env_quote_like(old_value, password)
            mapped_pass = True
        elif key in DB_URL_KEYS:
            new_value = _env_quote_like(old_value, _rewrite_database_url(old_value, database, username, password).strip("'\""))
            mapped_db = mapped_user = mapped_pass = True
        elif key in SITE_URL_KEYS and source_domain in old_value:
            new_value = old_value.replace(source_domain, target_domain)
        if new_value is None:
            out.append(line)
            continue
        out.append(prefix + new_value)
        changed = True
    if not changed or not (mapped_db and mapped_user and mapped_pass):
        return False
    fd, temp_name = tempfile.mkstemp(prefix=".vfops-env-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines(out)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return True


def locate_wordpress_config(site: Path) -> Path | None:
    candidates = [site / "wp-config.php", site / "public" / "wp-config.php"]
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def rewrite_application_database_config(
    staged_site: Path,
    source_domain: str,
    target_domain: str,
    database: str,
    username: str,
    password: str,
) -> tuple[str, Path | None]:
    wp_config = locate_wordpress_config(staged_site)
    if wp_config is not None:
        rewrite_wordpress_config(wp_config, database, username, password)
        return "WORDPRESS_WP_CONFIG", wp_config

    for name in ENV_NAMES:
        for candidate in (staged_site / name, staged_site / "public" / name):
            if candidate.is_file() and not candidate.is_symlink():
                if rewrite_dotenv(candidate, database, username, password, source_domain, target_domain):
                    return "DOTENV", candidate
    raise RestoreAsError("application database configuration cannot be safely remapped")


def verify_imported_database(package_dir: Path, source_database: str, target_database: str, clpctl: str) -> None:
    entries = (load_manifest(package_dir).get("contents", {}) or {}).get("mysql", [])
    source_ref = None
    for item in entries if isinstance(entries, list) else []:
        if isinstance(item, dict) and str(item.get("database", "")) == source_database:
            source_ref = str(item.get("file", ""))
            break
    if not source_ref:
        raise RestoreAsError("source database dump is unavailable")
    source = restore_plan.safe_package_path(package_dir, source_ref)
    with tempfile.TemporaryDirectory(prefix="vfops-restore-as-db-") as td:
        exported = Path(td) / "target.sql.gz"
        try:
            cloudpanel.export_database(target_database, exported, clpctl=clpctl)
            before, before_count = verify_engine.sql_fingerprint(source)
            after, after_count = verify_engine.sql_fingerprint(exported)
        except (cloudpanel.CloudPanelError, verify_engine.RestoreVerifyError, ValueError) as exc:
            raise RestoreAsError("target database verification failed") from exc
    if before != after or before_count != after_count:
        raise RestoreAsError("target database fingerprint does not match backup")


def _run_wp(site_user: str, wp_root: Path, args: list[str], *, runuser: str = "runuser", wp: str = "wp") -> str:
    command = [runuser, "-u", site_user, "--", wp, f"--path={wp_root}", *args]
    try:
        proc = subprocess.run(command, text=True, capture_output=True, check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RestoreAsError("WP-CLI execution failed") from exc
    if proc.returncode != 0:
        raise RestoreAsError("WP-CLI operation failed")
    return proc.stdout.strip()


def reconcile_wordpress_domain(
    site_user: str,
    wp_root: Path,
    source_domain: str,
    target_domain: str,
    *,
    runuser: str = "runuser",
    wp: str = "wp",
) -> dict[str, str]:
    home = _run_wp(site_user, wp_root, ["option", "get", "home"], runuser=runuser, wp=wp)
    siteurl = _run_wp(site_user, wp_root, ["option", "get", "siteurl"], runuser=runuser, wp=wp)
    old_values = []
    for value in (home, siteurl):
        if value and source_domain in value and value not in old_values:
            old_values.append(value.rstrip("/"))
    if not old_values:
        raise RestoreAsError("WordPress source URL cannot be verified before replacement")
    for old in old_values:
        parts = urlsplit(old)
        if not parts.scheme or not parts.netloc:
            raise RestoreAsError("WordPress source URL is invalid")
        target = urlunsplit((parts.scheme, target_domain, parts.path, "", "")).rstrip("/")
        _run_wp(
            site_user,
            wp_root,
            ["search-replace", old, target, "--all-tables-with-prefix", "--skip-columns=guid", "--precise"],
            runuser=runuser,
            wp=wp,
        )
    new_home = _run_wp(site_user, wp_root, ["option", "get", "home"], runuser=runuser, wp=wp)
    new_siteurl = _run_wp(site_user, wp_root, ["option", "get", "siteurl"], runuser=runuser, wp=wp)
    if target_domain not in new_home or target_domain not in new_siteurl:
        raise RestoreAsError("WordPress target URL verification failed")
    return {"home": new_home, "siteurl": new_siteurl}


def restore_as(
    package_dir: Path,
    target_domain: str,
    target_root: Path,
    clpctl: str,
    confirm: str,
    *,
    runuser: str = "runuser",
    wp: str = "wp",
) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    target_domain = cloudpanel.validate_domain(target_domain)
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise RestoreAsError("backup package failed fresh verification")
    manifest = load_manifest(package_dir)
    source_site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    source_domain = cloudpanel.validate_domain(str(source_site.get("domain", "")))
    target_root = require_target(target_root, manifest, target_domain, confirm)
    try:
        site_lifecycle.ensure_domain_available(target_root, target_domain)
    except site_lifecycle.SiteLifecycleError as exc:
        raise RestoreAsError(str(exc)) from exc

    backup_id = str(manifest.get("backup_id", ""))
    identity = site_lifecycle.derive_target_identity(target_domain, backup_id)
    final_site = restore_plan.target_path(target_root, identity.site_root)
    parent = final_site.parent
    archive_rel = str(manifest.get("contents", {}).get("files_archive", ""))
    archive = restore_plan.safe_package_path(package_dir, archive_rel)
    archive_check = restore_plan.inspect_archive(archive)
    if archive_check.get("blockers"):
        raise RestoreAsError("site archive failed extraction safety checks")

    mysql_entries = manifest.get("contents", {}).get("mysql", [])
    if not isinstance(mysql_entries, list):
        raise RestoreAsError("MySQL manifest is invalid")
    if len(mysql_entries) > 1:
        raise RestoreAsError("Restore-As currently refuses ambiguous multi-database applications")

    created_site = False
    created_databases: list[str] = []
    staging: Path | None = None
    bootstrap_dir: Path | None = None
    committed = False
    failure_stage = "TARGET_PREFLIGHT"
    app_kind = "NO_DATABASE"
    config_rel: str | None = None
    target_database: str | None = None
    target_db_user: str | None = None
    target_db_password: str | None = None
    wp_root: Path | None = None
    wordpress_urls: dict[str, str] | None = None

    try:
        failure_stage = "CLOUDPANEL_SITE_CREATE"
        site_lifecycle.create_site(
            source_site,
            identity,
            clpctl=clpctl,
            vhost_template=source_vhost_template(package_dir, manifest),
        )
        created_site = True
        if not final_site.is_dir():
            raise RestoreAsError("CloudPanel site creation did not create expected target root")

        failure_stage = "SITE_FILES_STAGE"
        staging = Path(tempfile.mkdtemp(prefix=f".vfops-restore-as-{backup_id}-", dir=parent))
        os.chmod(staging, 0o700)
        staged_site = staging / "site"
        restore_apply.extract_site_archive(archive, staged_site)

        source_site_root = restore_plan.safe_absolute_site_path(str(source_site.get("site_root", "")))
        files_check = verify_engine.verify_files(package_dir, manifest, staged_site, source_site_root)
        sqlite_check = verify_engine.verify_sqlite(package_dir, manifest, staged_site, source_site_root)
        if files_check.get("status") != "PASS" or sqlite_check.get("status") != "PASS":
            raise RestoreAsError("restored files failed pre-transform verification")

        failure_stage = "MYSQL_CREATE_IMPORT_VERIFY"
        if mysql_entries:
            source_database = str(mysql_entries[0].get("database", ""))
            dump = restore_plan.safe_package_path(package_dir, str(mysql_entries[0].get("file", "")))
            target_database, target_db_user, target_db_password = site_lifecycle.derive_database_identity(
                target_domain, backup_id, 1
            )
            cloudpanel.add_database(
                target_domain,
                target_database,
                target_db_user,
                target_db_password,
                clpctl=clpctl,
            )
            created_databases.append(target_database)
            cloudpanel.import_database(target_database, dump, clpctl=clpctl)
            verify_imported_database(package_dir, source_database, target_database, clpctl)

            failure_stage = "APPLICATION_CONFIG_REMAP"
            app_kind, config_path = rewrite_application_database_config(
                staged_site,
                source_domain,
                target_domain,
                target_database,
                target_db_user,
                target_db_password,
            )
            config_rel = config_path.relative_to(staged_site).as_posix() if config_path else None
            if app_kind == "WORDPRESS_WP_CONFIG" and config_path is not None:
                wp_root = final_site / config_path.parent.relative_to(staged_site)

        failure_stage = "SITE_OWNERSHIP_RECONCILIATION"
        restore_new.reconcile_site_ownership(staged_site, final_site)

        failure_stage = "SITE_ATOMIC_COMMIT"
        bootstrap_dir = parent / f".vfops-bootstrap-as-{backup_id}"
        if bootstrap_dir.exists():
            raise RestoreAsError("bootstrap recovery point already exists")
        os.replace(final_site, bootstrap_dir)
        try:
            os.replace(staged_site, final_site)
        except Exception:
            os.replace(bootstrap_dir, final_site)
            bootstrap_dir = None
            raise
        committed = True

        if app_kind == "WORDPRESS_WP_CONFIG" and wp_root is not None:
            failure_stage = "WORDPRESS_DOMAIN_REMAP"
            wordpress_urls = reconcile_wordpress_domain(
                identity.site_user,
                wp_root,
                source_domain,
                target_domain,
                runuser=runuser,
                wp=wp,
            )

        failure_stage = "POST_RESTORE_PERMISSIONS"
        try:
            cloudpanel.reset_permissions(final_site, clpctl=clpctl)
        except cloudpanel.CloudPanelError as exc:
            raise RestoreAsError("CloudPanel permission reconciliation failed") from exc

        if bootstrap_dir and bootstrap_dir.exists():
            shutil.rmtree(bootstrap_dir)
            bootstrap_dir = None

        return {
            "schema": RESULT_SCHEMA,
            "status": "RESTORE_AS_VERIFIED",
            "backup_id": backup_id,
            "source_domain": source_domain,
            "target_domain": target_domain,
            "target_site_user": identity.site_user,
            "target_site_root": identity.site_root,
            "application_config_mode": app_kind,
            "application_config_file": config_rel,
            "target_database": target_database,
            "target_database_user": target_db_user,
            "database_import_verified_before_transform": bool(mysql_entries),
            "wordpress_urls": wordpress_urls,
            "source_ssl_reused": source_domain == target_domain,
            "ssl_status": "SOURCE_DOMAIN_CERTIFICATE_NOT_REUSED; DNS_REQUIRED_FOR_NEW_CERTIFICATE"
            if source_domain != target_domain
            else "SOURCE_DOMAIN_RESTORE_AS; CERTIFICATE_RECONCILIATION_DEFERRED",
            "runtime_metadata_status": "DEFERRED_FOR_IDENTITY_REMAP",
            "dns_changed": False,
            "source_deleted": False,
            "existing_site_overwrite_allowed": False,
            "secrets_emitted": False,
        }
    except Exception as exc:
        if committed and final_site.exists():
            shutil.rmtree(final_site, ignore_errors=True)
        if bootstrap_dir and bootstrap_dir.exists() and not final_site.exists():
            try:
                os.replace(bootstrap_dir, final_site)
                bootstrap_dir = None
            except OSError:
                pass
        for database in reversed(created_databases):
            site_lifecycle.cleanup_database(database, clpctl=clpctl)
        if created_site:
            site_lifecycle.cleanup_site(target_domain, clpctl=clpctl)
        reason = exc if isinstance(exc, RestoreAsError) else exc.__class__.__name__
        raise RestoreAsError(f"Restore-As failed; stage={failure_stage}; reason={reason}") from exc
    finally:
        if staging and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops restore a verified backup as a new CloudPanel site")
    parser.add_argument("--package", required=True)
    parser.add_argument("--target-domain", required=True)
    parser.add_argument("--target-root", default="/")
    parser.add_argument("--clpctl", default=os.environ.get("VFOPS_CLPCTL", "clpctl"))
    parser.add_argument("--runuser", default=os.environ.get("VFOPS_RUNUSER", "runuser"))
    parser.add_argument("--wp", default=os.environ.get("VFOPS_WP", "wp"))
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    try:
        result = restore_as(
            Path(args.package),
            args.target_domain,
            Path(args.target_root),
            args.clpctl,
            args.confirm,
            runuser=args.runuser,
            wp=args.wp,
        )
    except (RestoreAsError, cloudpanel.CloudPanelError, site_lifecycle.SiteLifecycleError, ValueError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 14
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
