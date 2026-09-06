#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

import package as package_engine
import restore as restore_plan
import restore_new

PLAN_SCHEMA = "vf-server-ops.runtime-activation-plan.v1"
RESULT_SCHEMA = "vf-server-ops.runtime-activation-result.v1"
SAFE_SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
NODE_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+){0,2})$")


class RuntimeActivationError(RuntimeError):
    pass


def load_manifest(package_dir: Path) -> dict[str, Any]:
    fresh = package_engine.verify_package(package_dir)
    if fresh.get("status") != "PASS":
        raise RuntimeActivationError("backup package failed fresh verification")
    try:
        payload = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeActivationError("backup manifest is invalid") from exc
    if payload.get("schema") != package_engine.PACKAGE_SCHEMA:
        raise RuntimeActivationError("unsupported backup package schema")
    return payload


def inventory_site(package_dir: Path) -> dict[str, Any]:
    path = package_dir / "metadata" / "inventory-site.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeActivationError("inventory-site recovery metadata is missing or invalid") from exc
    if not isinstance(payload, dict):
        raise RuntimeActivationError("inventory-site recovery metadata is invalid")
    return payload


def cron_package_file(package_dir: Path, source_path: str) -> Path:
    name = package_engine.safe_name(source_path.strip("/").replace("/", "__"))
    return package_dir / "metadata" / "cron" / name


def build_plan(package_dir: Path, target_root: Path) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    target_root = target_root.resolve()
    manifest = load_manifest(package_dir)
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    domain = str(site.get("domain", ""))
    user = str(site.get("site_user", ""))
    site_root = restore_plan.safe_absolute_site_path(str(site.get("site_root", "")))
    target_site = restore_plan.target_path(target_root, site_root)
    if not target_site.is_dir():
        raise RuntimeActivationError("restored target site does not exist")

    inv = inventory_site(package_dir)
    cron = inv.get("cron", {}) if isinstance(inv.get("cron"), dict) else {}
    source_paths = cron.get("source_paths", []) if isinstance(cron.get("source_paths"), list) else []
    user_crontabs: list[dict[str, str]] = []
    manual_cron: list[dict[str, str]] = []
    for source in source_paths:
        if not isinstance(source, str):
            continue
        package_file = cron_package_file(package_dir, source)
        if not package_file.is_file():
            manual_cron.append({"source": source, "reason": "PACKAGE_FILE_MISSING"})
            continue
        if source in {f"/var/spool/cron/crontabs/{user}", f"/var/spool/cron/{user}"}:
            user_crontabs.append({"source": source, "file": str(package_file.relative_to(package_dir))})
        elif source.startswith("/etc/cron.d/"):
            manual_cron.append({"source": source, "reason": "SYSTEM_CRON_REQUIRES_MANUAL_RECONCILIATION"})
        else:
            manual_cron.append({"source": source, "reason": "UNSUPPORTED_CRON_SOURCE"})

    if len(user_crontabs) > 1:
        raise RuntimeActivationError("multiple user crontab sources are ambiguous")

    pm2_file = package_dir / "metadata" / "pm2" / "dump.pm2"
    pm2_ready = pm2_file.is_file()
    return {
        "schema": PLAN_SCHEMA,
        "status": "READY_WITH_MANUAL_GATES" if manual_cron else "READY",
        "backup_id": manifest.get("backup_id"),
        "domain": domain,
        "site_user": user,
        "target_site_root": site_root,
        "user_crontab": user_crontabs[0] if user_crontabs else None,
        "pm2": {"ready": pm2_ready, "file": "metadata/pm2/dump.pm2" if pm2_ready else None},
        "manual_cron": manual_cron,
        "vhost_reference_only": any(str(item).startswith("metadata/vhost/") for item in manifest.get("contents", {}).get("metadata", {}).get("copied", [])),
        "writes_performed": False,
        "dns_changed": False,
        "secrets_emitted": False,
    }


def run_command(args: list[str], timeout: int = 120, env: dict[str, str] | None = None, cwd: Path | str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, text=True, capture_output=True, check=False, timeout=timeout, env=env, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeActivationError(f"runtime command unavailable: {args[0]}") from exc


def pm2_dump_node_versions(pm2_source: Path) -> list[str]:
    try:
        payload = json.loads(pm2_source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    versions: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        value = item.get("node_version")
        if not isinstance(value, str):
            continue
        match = NODE_VERSION_RE.fullmatch(value.strip())
        if match:
            versions.add(match.group(1))
    return sorted(versions)


def resolve_site_user_nvm_pm2(user: str, pm2_source: Path, home_root: Path = Path("/home")) -> tuple[str, str]:
    if not user or "/" in user or user in {".", ".."}:
        raise RuntimeActivationError("site user is invalid for NVM PM2 resolution")
    nvm_node_root = home_root / user / ".nvm" / "versions" / "node"
    installed = sorted(
        path
        for path in nvm_node_root.glob("*/bin/pm2")
        if path.is_file() and os.access(path, os.X_OK)
    ) if nvm_node_root.is_dir() else []
    source_versions = set(pm2_dump_node_versions(pm2_source))
    if source_versions:
        matching = [path for path in installed if path.parent.parent.name.lstrip("v") in source_versions]
        if len(matching) == 1:
            chosen = matching[0]
        elif not matching:
            raise RuntimeActivationError("matching site-user NVM PM2 version is unavailable on target")
        else:
            raise RuntimeActivationError("multiple matching site-user NVM PM2 binaries are ambiguous")
    else:
        if len(installed) == 1:
            chosen = installed[0]
        elif not installed:
            raise RuntimeActivationError("site-user NVM PM2 is unavailable on target")
        else:
            raise RuntimeActivationError("multiple site-user NVM PM2 binaries are ambiguous")
    return str(chosen), f"{chosen.parent}:{SAFE_SYSTEM_PATH}"


def current_crontab(crontab: str, user: str) -> tuple[bool, str]:
    proc = run_command([crontab, "-u", user, "-l"], timeout=30)
    if proc.returncode == 0:
        return True, proc.stdout
    if proc.returncode == 1 and not proc.stdout.strip():
        return False, ""
    raise RuntimeActivationError("cannot inspect target user crontab safely")


def meaningful_cron(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def run_private_crontab_file(crontab: str, user: str, content: str, temp_root: Path, name: str) -> subprocess.CompletedProcess[str]:
    temp_root.mkdir(parents=True, exist_ok=True)
    os.chmod(temp_root, 0o700)
    work = Path(tempfile.mkdtemp(prefix="vfops-cron-", dir=temp_root))
    os.chmod(work, 0o700)
    staged = work / name
    try:
        staged.write_text(content, encoding="utf-8")
        os.chmod(staged, 0o600)
        return run_command([crontab, "-u", user, str(staged)], timeout=30)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def install_crontab(crontab: str, user: str, source: Path, temp_root: Path) -> None:
    try:
        content = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeActivationError("user crontab source cannot be read") from exc
    proc = run_private_crontab_file(crontab, user, content, temp_root, "crontab.install")
    if proc.returncode != 0:
        raise RuntimeActivationError("user crontab installation failed")


def restore_previous_crontab(crontab: str, user: str, existed: bool, content: str, temp_root: Path) -> None:
    if existed:
        proc = run_private_crontab_file(crontab, user, content, temp_root, "crontab.rollback")
    else:
        proc = run_command([crontab, "-u", user, "-r"], timeout=30)
    if proc.returncode != 0:
        raise RuntimeActivationError("user crontab rollback failed")


def best_effort_pm2_shutdown(runuser: str, user: str, runtime_env: list[str], pm2_command: str, cwd: Path | str) -> bool:
    ok = True
    for command in (["delete", "all"], ["kill"]):
        try:
            proc = run_command([runuser, "-u", user, "--", "/usr/bin/env", *runtime_env, pm2_command, *command], timeout=60, cwd=cwd)
        except RuntimeActivationError:
            ok = False
        else:
            if proc.returncode != 0:
                ok = False
    return ok


def require_activation_target(target_root: Path, manifest: dict, confirm: str) -> Path:
    root = target_root.resolve()
    site = manifest.get("site", {}) if isinstance(manifest.get("site"), dict) else {}
    domain = str(site.get("domain", ""))
    backup_id = str(manifest.get("backup_id", ""))
    required = f"ACTIVATE_RUNTIME:{domain}:{backup_id}"
    if confirm != required:
        raise RuntimeActivationError(f"explicit confirmation required: {required}")
    if root == Path("/"):
        if not Path("/home/clp/htdocs/app/data/db.sq3").is_file():
            raise RuntimeActivationError("/ is not a detected CloudPanel target")
    else:
        marker = root / restore_new.CONTROLLED_MARKER
        try:
            value = marker.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeActivationError("controlled CloudPanel target marker is missing") from exc
        if value != restore_new.CONTROLLED_MARKER_VALUE:
            raise RuntimeActivationError("controlled CloudPanel target marker is invalid")
    return root


def apply_runtime(package_dir: Path, target_root: Path, confirm: str, crontab: str, runuser: str, pm2: str, chown: str) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    manifest = load_manifest(package_dir)
    target_root = require_activation_target(target_root, manifest, confirm)
    plan = build_plan(package_dir, target_root)
    if plan["manual_cron"]:
        raise RuntimeActivationError("runtime activation has unresolved system/unsupported Cron sources")

    user = plan["site_user"]
    if not user:
        raise RuntimeActivationError("site user is missing")
    previous_exists, previous_cron = current_crontab(crontab, user)
    if meaningful_cron(previous_cron):
        raise RuntimeActivationError("target user already has a non-empty crontab; refusing replacement")

    pm2_source = package_dir / "metadata" / "pm2" / "dump.pm2"
    target_pm2_home = restore_plan.target_path(target_root, f"/home/{user}/.pm2")
    target_pm2_dump = target_pm2_home / "dump.pm2"
    pm2_home_existed = target_pm2_home.exists()
    pm2_existed = target_pm2_dump.is_file()
    if pm2_existed and pm2_source.is_file() and package_engine.sha256_file(target_pm2_dump) != package_engine.sha256_file(pm2_source):
        raise RuntimeActivationError("target PM2 dump already exists with different content")

    cron_temp_root = target_root / "var/lib/vf-server-ops/runtime-tmp"
    temp_dir = cron_temp_root / str(manifest.get("backup_id"))
    if temp_dir.exists():
        raise RuntimeActivationError("runtime activation temp directory already exists")
    temp_dir.mkdir(parents=True, mode=0o700)

    cron_changed = False
    pm2_copied = False
    pm2_resurrect_attempted = False
    pm2_rollback_command: str | None = None
    pm2_rollback_env: list[str] = []
    pm2_execution_mode = "NOT_REQUIRED"
    steps: list[str] = []
    try:
        cron_info = plan.get("user_crontab")
        if isinstance(cron_info, dict):
            source = restore_plan.safe_package_path(package_dir, str(cron_info["file"]))
            install_crontab(crontab, user, source, cron_temp_root)
            cron_changed = True
            steps.append("user_crontab_installed")
        else:
            steps.append("user_crontab_not_required")

        if plan.get("pm2", {}).get("ready"):
            target_pm2_home.mkdir(parents=True, exist_ok=True)
            if not pm2_existed:
                shutil.copy2(pm2_source, target_pm2_dump)
                os.chmod(target_pm2_dump, 0o600)
                pm2_copied = True
            chown_proc = run_command([chown, f"{user}:{user}", str(target_pm2_home), str(target_pm2_dump)], timeout=30)
            if chown_proc.returncode != 0:
                raise RuntimeActivationError("PM2 ownership reconciliation failed")
            pm2_home_env = "/home/{}/.pm2".format(user) if target_root == Path("/") else str(target_pm2_home)
            pm2_command = pm2
            pm2_path_env: str | None = None
            if target_root == Path("/") and pm2 == "pm2":
                pm2_command, pm2_path_env = resolve_site_user_nvm_pm2(user, pm2_source)
                pm2_execution_mode = "SITE_USER_NVM_AUTO_RESOLVED"
            else:
                pm2_execution_mode = "EXPLICIT_OR_SANDBOX_PM2"
            runtime_env = [f"HOME=/home/{user}" if target_root == Path("/") else f"HOME={target_pm2_home.parent}", f"PM2_HOME={pm2_home_env}"]
            if pm2_path_env:
                runtime_env.append(f"PATH={pm2_path_env}")
            pm2_working_dir = target_pm2_home.parent
            if not pm2_working_dir.is_dir():
                raise RuntimeActivationError("site-user PM2 working directory is unavailable on target")
            pm2_rollback_command = pm2_command
            pm2_rollback_env = list(runtime_env)
            pm2_resurrect_attempted = True
            proc = run_command([runuser, "-u", user, "--", "/usr/bin/env", *runtime_env, pm2_command, "resurrect"], timeout=120, cwd=pm2_working_dir)
            if proc.returncode != 0:
                raise RuntimeActivationError("PM2 resurrect failed")
            steps.append("pm2_resurrected")
        else:
            steps.append("pm2_not_required")

        return {
            "schema": RESULT_SCHEMA,
            "status": "RUNTIME_ACTIVATED",
            "backup_id": manifest.get("backup_id"),
            "domain": manifest.get("site", {}).get("domain"),
            "site_user": user,
            "cron_installed": cron_changed,
            "pm2_started": bool(plan.get("pm2", {}).get("ready")),
            "pm2_execution_mode": pm2_execution_mode,
            "manual_cron_remaining": [],
            "vhost_reference_only": plan.get("vhost_reference_only"),
            "dns_changed": False,
            "owner_confirmation_verified": True,
            "steps": steps,
            "secrets_emitted": False,
        }
    except Exception as exc:
        cleanup_partial = False
        if cron_changed:
            try:
                restore_previous_crontab(crontab, user, previous_exists, previous_cron, cron_temp_root)
            except (OSError, RuntimeActivationError):
                cleanup_partial = True
        if pm2_resurrect_attempted and not pm2_home_existed and pm2_rollback_command:
            if not best_effort_pm2_shutdown(runuser, user, pm2_rollback_env, pm2_rollback_command, target_pm2_home.parent):
                cleanup_partial = True
        if pm2_copied and target_pm2_dump.exists():
            try:
                target_pm2_dump.unlink()
            except OSError:
                cleanup_partial = True
        if not pm2_home_existed and target_pm2_home.exists():
            try:
                shutil.rmtree(target_pm2_home)
            except OSError:
                cleanup_partial = True
        if isinstance(exc, RuntimeActivationError):
            if cleanup_partial:
                raise RuntimeActivationError(f"{exc}; cleanup=PARTIAL") from exc
            raise
        suffix = "; cleanup=PARTIAL" if cleanup_partial else ""
        raise RuntimeActivationError(f"runtime activation failed{suffix}") from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops guarded runtime activation")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--package", required=True)
    plan.add_argument("--target-root", default="/")
    apply = sub.add_parser("apply-new-site")
    apply.add_argument("--package", required=True)
    apply.add_argument("--target-root", default="/")
    apply.add_argument("--confirm", required=True)
    apply.add_argument("--crontab", default=os.environ.get("VFOPS_CRONTAB", "crontab"))
    apply.add_argument("--runuser", default=os.environ.get("VFOPS_RUNUSER", "runuser"))
    apply.add_argument("--pm2", default=os.environ.get("VFOPS_PM2", "pm2"))
    apply.add_argument("--chown", default=os.environ.get("VFOPS_CHOWN", "chown"))
    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = build_plan(Path(args.package), Path(args.target_root))
        else:
            result = apply_runtime(Path(args.package), Path(args.target_root), args.confirm, args.crontab, args.runuser, args.pm2, args.chown)
    except (RuntimeActivationError, restore_plan.RestorePlanError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 13
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
