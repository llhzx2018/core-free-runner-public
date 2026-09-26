#!/usr/bin/env python3
"""P07 Resource Safe Apply RC15.

Auto-apply eligibility is controlled by the calibration registry.
Only independently Production-verified profiles may pass the write gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import resource_profile as rp  # noqa: E402
import resource_calibrations as calibrations  # noqa: E402

MYSQL_CONFIG = Path("/etc/mysql/mysql.conf.d/mysqld.cnf")
BACKUP_ROOT = Path("/var/lib/vf-system-care/resource-backups")
APPLY_TOKEN = "APPLY_RESOURCE_PROFILE"
ROLLBACK_TOKEN = "ROLLBACK_RESOURCE_PROFILE"

MYSQL_KEYS = (
    "innodb_buffer_pool_size",
    "max_connections",
    "tmp_table_size",
    "max_heap_table_size",
    "table_open_cache",
)


class ApplyBlocked(RuntimeError):
    pass


class ApplyFailed(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


def _run(
    cmd: Sequence[str],
    *,
    env: Optional[Mapping[str, str]] = None,
    timeout: float = 15.0,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        env=dict(env) if env is not None else None,
        check=False,
    )
    if check and p.returncode != 0:
        raise ApplyFailed(f"command failed: {cmd[0]} rc={p.returncode}")
    return p


def _parse_size_mib(value: str) -> int:
    value = value.strip()
    m = re.fullmatch(r"(\d+)([KkMmGg]?)", value)
    if not m:
        raise ValueError(value)
    n = int(m.group(1))
    u = m.group(2).upper()
    if u == "K":
        return max(1, (n + 1023) // 1024)
    if u == "M" or not u:
        return n
    if u == "G":
        return n * 1024
    raise ValueError(value)


def _mysql_config_values(path: Path) -> Dict[str, Tuple[str, int]]:
    text = _read(path)
    out: Dict[str, Tuple[str, int]] = {}
    for key in MYSQL_KEYS:
        matches = list(
            re.finditer(
                rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=[ \t]*([^#;\r\n]+)[ \t]*(?:[#;].*)?$",
                text,
            )
        )
        if len(matches) != 1:
            raise ApplyBlocked(f"MYSQL_CONFIG_KEY_COUNT:{key}:{len(matches)}")
        raw = matches[0].group(1).strip()
        if key in ("innodb_buffer_pool_size", "tmp_table_size", "max_heap_table_size"):
            numeric = _parse_size_mib(raw)
        else:
            if not re.fullmatch(r"\d+", raw):
                raise ApplyBlocked(f"MYSQL_CONFIG_UNPARSEABLE:{key}")
            numeric = int(raw)
        out[key] = (raw, numeric)
    return out


def _replace_single(text: str, key: str, value: str) -> str:
    pattern = re.compile(
        rf"(?m)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*)([^#;\r\n]+)([ \t]*(?:[#;].*)?)$"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ApplyBlocked(f"CONFIG_KEY_COUNT:{key}:{len(matches)}")
    return pattern.sub(rf"\g<1>{value}\g<3>", text, count=1)


def _php_current_max_children(path: Path) -> int:
    text = _read(path)
    matches = re.findall(r"(?m)^[ \t]*pm\.max_children[ \t]*=[ \t]*(\d+)[ \t]*$", text)
    if len(matches) != 1:
        raise ApplyBlocked(f"PHP_MAX_CHILDREN_COUNT:{path}:{len(matches)}")
    return int(matches[0])


def _rooted(path: Path, root: Path) -> Path:
    if root == Path("/"):
        return path
    return root / path.relative_to("/")


def build_plan(
    snapshot: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    *,
    root: Path = Path("/"),
) -> Dict[str, Any]:
    reasons: List[str] = []
    profile_id = str(recommendation.get("profile_id") or "")
    calibration = calibrations.get_calibration(profile_id)
    if calibration.get("state") != calibrations.PRODUCTION_VERIFIED or not calibration.get("auto_apply"):
        reasons.append(f"PROFILE_CALIBRATION_STATE:{calibration.get('state')}")
    if recommendation.get("mode") != "balanced":
        reasons.append("MODE_NOT_BALANCED")
    if not bool(snapshot.get("cloudpanel_present")):
        reasons.append("CLOUDPANEL_NOT_DETECTED")
    if not bool(snapshot.get("mysql_present")):
        reasons.append("MYSQL_NOT_DETECTED")
    flavor = str(snapshot.get("mysql_flavor") or "")
    if flavor not in ("mysql", "percona", "mysql-compatible"):
        reasons.append("MYSQL_FLAVOR_NOT_SUPPORTED")

    mysql_path = _rooted(MYSQL_CONFIG, root)
    if not mysql_path.is_file():
        reasons.append("MYSQL_CONFIG_NOT_FOUND")

    mysql_changes: List[Dict[str, Any]] = []
    if mysql_path.is_file():
        try:
            current = _mysql_config_values(mysql_path)
            target = recommendation["mysql"]
            ceilings = {
                "innodb_buffer_pool_size": (int(target["innodb_buffer_pool_size_mib"]), "mib"),
                "max_connections": (int(target["max_connections"]), "int"),
                "tmp_table_size": (int(target["tmp_table_size_mib"]), "mib"),
                "max_heap_table_size": (int(target["max_heap_table_size_mib"]), "mib"),
                "table_open_cache": (int(target["table_open_cache"]), "int"),
            }
            for key, (ceiling, kind) in ceilings.items():
                raw, cur = current[key]
                effective = min(cur, ceiling)
                new_raw = f"{effective}M" if kind == "mib" else str(effective)
                mysql_changes.append(
                    {
                        "key": key,
                        "current_raw": raw,
                        "current_numeric": cur,
                        "ceiling": ceiling,
                        "effective_numeric": effective,
                        "new_raw": new_raw,
                        "change": effective < cur,
                    }
                )
        except (ApplyBlocked, ValueError) as e:
            reasons.append(str(e))

    php_changes: List[Dict[str, Any]] = []
    php_ceiling = int(recommendation.get("php", {}).get("hot_pool_max_children") or 0)
    for pool in snapshot.get("php_referenced_pools") or []:
        raw_path = Path(str(pool.get("file") or ""))
        if not raw_path.is_absolute():
            continue
        path = _rooted(raw_path, root)
        if not path.is_file():
            reasons.append(f"PHP_POOL_NOT_FOUND:{raw_path}")
            continue
        try:
            cur = _php_current_max_children(path)
        except ApplyBlocked as e:
            reasons.append(str(e))
            continue
        effective = min(cur, php_ceiling)
        php_changes.append(
            {
                "version": str(pool.get("version") or ""),
                "pool": str(pool.get("pool") or path.stem),
                "path": str(raw_path),
                "current": cur,
                "ceiling": php_ceiling,
                "effective": effective,
                "change": effective < cur,
            }
        )

    eligible = not reasons
    return {
        "schema": "vf-resource-apply-plan.v1",
        "profile_id": recommendation.get("profile_id"),
        "mode": recommendation.get("mode"),
        "calibration_state": calibration.get("state"),
        "calibration_evidence": calibration.get("evidence"),
        "eligible": eligible,
        "apply_state": "ELIGIBLE" if eligible else "PREVIEW_ONLY_BLOCKED",
        "block_reasons": reasons,
        "cap_only": True,
        "mysql_config": str(MYSQL_CONFIG),
        "mysql_changes": mysql_changes,
        "php_changes": php_changes,
        "unused_php_services": [
            f"php{v}-fpm" for v in recommendation.get("php", {}).get("unused_active_versions") or []
        ],
        "swap": {
            "current_mib": recommendation.get("swap", {}).get("current_mib"),
            "recommended_mib": recommendation.get("swap", {}).get("recommended_mib"),
            "automatic_action": "NONE",
        },
        "automatic_service_disable": False,
        "automatic_mysql_restart": False,
        "write_boundary": "PRODUCTION_HIGH_RISK_EXPLICIT_CONFIRMATION",
    }


def render_plan(plan: Mapping[str, Any]) -> str:
    lines = [
        "P07 · Resource Safe Plan",
        "",
        f"Profile      {plan.get('profile_id')}",
        f"Calibration  {plan.get('calibration_state')}",
        f"Apply State  {plan.get('apply_state')}",
        "Policy       CAP-ONLY（只降低超额上限，不自动提高资源）",
    ]
    if plan.get("block_reasons"):
        lines += ["", "阻断原因"]
        lines += [f"  - {x}" for x in plan["block_reasons"]]
    lines += ["", "MySQL"]
    for item in plan.get("mysql_changes") or []:
        marker = "CHANGE" if item["change"] else "KEEP"
        lines.append(
            f"  {marker:<6} {item['key']}: {item['current_raw']} -> {item['new_raw']} "
            f"(ceiling={item['ceiling']})"
        )
    lines += ["", "PHP"]
    for item in plan.get("php_changes") or []:
        marker = "CHANGE" if item["change"] else "KEEP"
        lines.append(
            f"  {marker:<6} PHP {item['version']} / {item['pool']}: "
            f"{item['current']} -> {item['effective']}"
        )
    unused = plan.get("unused_php_services") or []
    if unused:
        lines += ["", "未引用 PHP 服务（仅建议，不自动停）", "  " + ", ".join(unused)]
    lines += [
        "",
        "Swap：仅建议，不自动创建 / 清理 / swapoff。",
        "MySQL：不自动 restart。",
    ]
    return "\n".join(lines)


def _atomic_write(path: Path, text: str) -> None:
    st = path.stat()
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.vf-", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IMODE(st.st_mode))
        try:
            os.chown(tmp, st.st_uid, st.st_gid)
        except PermissionError:
            pass
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _apply_plan_files(plan: Mapping[str, Any], *, root: Path, backup_dir: Path) -> Dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(backup_dir, 0o700)
    records: List[Dict[str, Any]] = []

    mysql_live = _rooted(Path(plan["mysql_config"]), root)
    mysql_backup = backup_dir / "mysql" / mysql_live.name
    mysql_backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mysql_live, mysql_backup)
    records.append(
        {
            "live": str(mysql_live),
            "backup": str(mysql_backup),
            "before_sha256": _sha256(mysql_backup),
            "after_sha256": None,
        }
    )

    php_targets: List[Tuple[Mapping[str, Any], Path, Path]] = []
    for item in plan.get("php_changes") or []:
        if not item["change"]:
            continue
        live = _rooted(Path(item["path"]), root)
        rel = Path(item["path"]).relative_to("/")
        backup = backup_dir / "php" / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(live, backup)
        records.append(
            {
                "live": str(live),
                "backup": str(backup),
                "before_sha256": _sha256(backup),
                "after_sha256": None,
            }
        )
        php_targets.append((item, live, backup))

    try:
        mysql_text = _read(mysql_live)
        for item in plan.get("mysql_changes") or []:
            if item["change"]:
                mysql_text = _replace_single(mysql_text, item["key"], item["new_raw"])
        _atomic_write(mysql_live, mysql_text)

        for item, live, _backup in php_targets:
            text = _read(live)
            text = re.sub(
                r"(?m)^([ \t]*pm\.max_children[ \t]*=[ \t]*)\d+[ \t]*$",
                rf"\g<1>{int(item['effective'])}",
                text,
                count=1,
            )
            _atomic_write(live, text)

        for record in records:
            record["after_sha256"] = _sha256(Path(record["live"]))
        return {"files": records}
    except Exception:
        _restore_files({"files": records})
        raise


def _restore_files(state: Mapping[str, Any]) -> None:
    for item in state.get("files") or []:
        live = Path(item["live"])
        backup = Path(item["backup"])
        if not backup.is_file():
            raise ApplyFailed(f"backup missing: {backup}")
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, live)


def _parse_clp_credentials(text: str) -> Tuple[str, str, str, int]:
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text)
    wanted = {
        "host": "host",
        "user name": "user",
        "username": "user",
        "password": "password",
        "port": "port",
    }
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if "|" in line:
            cells = [x.strip() for x in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[0].lower() in wanted:
                out[wanted[cells[0].lower()]] = "|".join(cells[1:]).strip()
                continue
        m = re.match(r"^(Host|User Name|Username|Password|Port)\s*:\s*(.*)$", line, re.I)
        if m:
            out[wanted[m.group(1).lower()]] = m.group(2).strip()
    password = out.get("password", "")
    if not password:
        raise ApplyBlocked("MYSQL_MASTER_CREDENTIAL_PARSE_FAILED")
    return out.get("user", "root"), password, out.get("host", "127.0.0.1"), int(out.get("port", "3306"))


def _mysql_client() -> Tuple[List[str], Dict[str, str]]:
    if not shutil.which("clpctl") or not shutil.which("mysql"):
        raise ApplyBlocked("MYSQL_LOCAL_ADMIN_TOOLING_MISSING")
    creds = _run(["clpctl", "db:show:master-credentials"], timeout=8.0)
    user, password, host, port = _parse_clp_credentials(creds.stdout)
    env = os.environ.copy()
    env["MYSQL_PWD"] = password
    cmd = [
        "mysql", "--protocol=TCP", "--connect-timeout=5", "--batch", "--skip-column-names",
        "-h", host, "-P", str(port), "-u", user,
    ]
    _run(cmd + ["-e", "SELECT 1"], env=env, timeout=8.0)
    return cmd, env


def _mysql_runtime_state(cmd: Sequence[str], env: Mapping[str, str]) -> Dict[str, Any]:
    sql = """
SELECT CONCAT_WS('|',
@@GLOBAL.innodb_buffer_pool_size,
@@GLOBAL.max_connections,
@@GLOBAL.tmp_table_size,
@@GLOBAL.max_heap_table_size,
@@GLOBAL.table_open_cache,
@@version,
@@version_comment
);
SELECT VARIABLE_VALUE
FROM performance_schema.global_status
WHERE VARIABLE_NAME='Max_used_connections';
"""
    out = _run(list(cmd) + ["-e", sql], env=env, timeout=10.0).stdout.strip().splitlines()
    if len(out) < 2:
        raise ApplyFailed("MYSQL_RUNTIME_QUERY_INCOMPLETE")
    parts = out[0].split("|")
    if len(parts) < 7:
        raise ApplyFailed("MYSQL_RUNTIME_QUERY_PARSE_FAILED")
    comment = "|".join(parts[6:])
    return {
        "innodb_buffer_pool_size": int(parts[0]),
        "max_connections": int(parts[1]),
        "tmp_table_size": int(parts[2]),
        "max_heap_table_size": int(parts[3]),
        "table_open_cache": int(parts[4]),
        "version": parts[5],
        "version_comment": comment,
        "max_used_connections": int(out[-1]),
    }


def _runtime_numeric_for_plan(key: str, value: int) -> int:
    if key in ("innodb_buffer_pool_size", "tmp_table_size", "max_heap_table_size"):
        return max(1, int(value) // (1024 * 1024))
    return int(value)


def _cap_plan_to_runtime(plan: Dict[str, Any], runtime_before: Mapping[str, Any]) -> None:
    """Make CAP-ONLY apply to live MySQL values as well as persistent config."""
    for item in plan.get("mysql_changes") or []:
        key = str(item["key"])
        runtime_numeric = _runtime_numeric_for_plan(key, int(runtime_before[key]))
        effective = min(int(item["effective_numeric"]), runtime_numeric)
        item["runtime_current_numeric"] = runtime_numeric
        item["effective_numeric"] = effective
        item["new_raw"] = (
            f"{effective}M"
            if key in ("innodb_buffer_pool_size", "tmp_table_size", "max_heap_table_size")
            else str(effective)
        )
        item["change"] = effective < int(item["current_numeric"])


def _runtime_targets(plan: Mapping[str, Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in plan.get("mysql_changes") or []:
        n = int(item["effective_numeric"])
        if item["key"] in ("innodb_buffer_pool_size", "tmp_table_size", "max_heap_table_size"):
            n *= 1024 * 1024
        out[item["key"]] = n
    return out


def _set_mysql_globals(cmd: Sequence[str], env: Mapping[str, str], values: Mapping[str, int]) -> None:
    sql = "\n".join(f"SET GLOBAL {key}={int(values[key])};" for key in MYSQL_KEYS if key in values)
    _run(list(cmd) + ["-e", sql], env=env, timeout=15.0)


def _validate_mysql() -> None:
    if not shutil.which("mysqld"):
        raise ApplyBlocked("MYSQLD_BINARY_MISSING")
    _run(["mysqld", "--validate-config"], timeout=15.0)


def _validate_php(versions: Iterable[str]) -> None:
    for version in sorted(set(v for v in versions if v)):
        binary = shutil.which(f"php-fpm{version}")
        if not binary:
            raise ApplyBlocked(f"PHP_FPM_BINARY_MISSING:{version}")
        _run([binary, "-t"], timeout=10.0)


def _reload_php(versions: Iterable[str]) -> None:
    for version in sorted(set(v for v in versions if v)):
        _run(["systemctl", "reload", f"php{version}-fpm"], timeout=15.0)


def _verify_services(versions: Iterable[str]) -> None:
    for unit in ["mysql", "nginx"] + [f"php{v}-fpm" for v in sorted(set(versions))]:
        p = _run(["systemctl", "is-active", unit], timeout=5.0, check=False)
        if p.stdout.strip() != "active":
            raise ApplyFailed(f"SERVICE_NOT_ACTIVE:{unit}")
    _run(["nginx", "-t"], timeout=10.0)


def _origin_smoke(pools: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    if not shutil.which("curl"):
        return results
    for pool in pools:
        name = str(pool.get("pool") or "")
        if "." not in name or " " in name:
            continue
        p = _run(
            [
                "curl", "-ksS", "--resolve", f"{name}:443:127.0.0.1",
                "--connect-timeout", "3", "--max-time", "12",
                "-o", "/dev/null", "-w", "%{http_code}", f"https://{name}/",
            ],
            timeout=15.0,
            check=False,
        )
        code = p.stdout.strip()
        ok = code.isdigit() and 200 <= int(code) < 500
        results.append({"domain": name, "code": code or "000", "ok": ok})
        if not ok:
            raise ApplyFailed(f"ORIGIN_SMOKE_FAILED:{name}:{code or '000'}")
    return results


def _write_state(path: Path, state: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _write_initial_state_or_restore(
    state_path: Path,
    state: Mapping[str, Any],
    file_state: Mapping[str, Any],
) -> None:
    """Close the crash window between config mutation and durable rollback state."""
    try:
        _write_state(state_path, state)
    except Exception:
        _restore_files(file_state)
        raise


def production_apply(mode: str, confirm: str) -> Dict[str, Any]:
    if os.geteuid() != 0:
        raise ApplyBlocked("ROOT_REQUIRED")
    if not sys.stdin.isatty():
        raise ApplyBlocked("INTERACTIVE_TTY_REQUIRED")
    if confirm != APPLY_TOKEN:
        raise ApplyBlocked("CONFIRMATION_TOKEN_REQUIRED")

    snapshot = rp.detect_snapshot()
    rec = rp.recommend(snapshot, mode)
    plan = build_plan(snapshot, rec)
    if not plan["eligible"]:
        raise ApplyBlocked("PLAN_NOT_ELIGIBLE:" + ",".join(plan["block_reasons"]))

    cmd, env = _mysql_client()
    runtime_before = _mysql_runtime_state(cmd, env)
    _cap_plan_to_runtime(plan, runtime_before)
    version_comment = (runtime_before["version"] + " " + runtime_before["version_comment"]).lower()
    major_match = re.match(r"(\d+)", runtime_before["version"])
    major = int(major_match.group(1)) if major_match else 0
    if major < 8 or ("mariadb" in version_comment):
        raise ApplyBlocked("MYSQL_RUNTIME_NOT_CALIBRATED")
    runtime_targets = _runtime_targets(plan)
    target_conn = runtime_targets.get("max_connections", runtime_before["max_connections"])
    if runtime_before["max_used_connections"] >= max(10, target_conn - 10):
        raise ApplyBlocked("MAX_USED_CONNECTIONS_TOO_CLOSE_TO_TARGET")

    ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup_dir = BACKUP_ROOT / f"{ts}-{rec['profile_id']}"
    file_state = _apply_plan_files(plan, root=Path("/"), backup_dir=backup_dir)
    changed_versions = [x["version"] for x in plan["php_changes"] if x["change"]]
    state: Dict[str, Any] = {
        "schema": "vf-resource-apply-state.v1",
        "status": "BACKED_UP",
        "created_utc": ts,
        "profile_id": rec["profile_id"],
        "mode": mode,
        "plan": plan,
        "mysql_runtime_before": runtime_before,
        "files": file_state["files"],
        "changed_php_versions": changed_versions,
        "origin_smoke": [],
    }
    state_path = backup_dir / "state.json"
    _write_initial_state_or_restore(state_path, state, file_state)

    try:
        _validate_mysql()
        _validate_php(changed_versions)
        state["status"] = "CONFIG_VALIDATED"
        _write_state(state_path, state)

        _set_mysql_globals(cmd, env, runtime_targets)
        _reload_php(changed_versions)
        state["status"] = "RUNTIME_APPLIED"
        _write_state(state_path, state)

        _verify_services(changed_versions)
        after = _mysql_runtime_state(cmd, env)
        for key, expected in runtime_targets.items():
            if int(after[key]) != int(expected):
                raise ApplyFailed(f"MYSQL_RUNTIME_MISMATCH:{key}")
        state["mysql_runtime_after"] = after
        state["origin_smoke"] = _origin_smoke(snapshot.get("php_referenced_pools") or [])
        state["status"] = "APPLIED_VERIFIED"
        _write_state(state_path, state)
        return {"state": "APPLIED_VERIFIED", "backup_dir": str(backup_dir), "profile_id": rec["profile_id"]}
    except Exception:
        try:
            _restore_files(state)
            _validate_mysql()
            _validate_php(changed_versions)
            old = {k: int(runtime_before[k]) for k in MYSQL_KEYS}
            _set_mysql_globals(cmd, env, old)
            _reload_php(changed_versions)
            _verify_services(changed_versions)
            state["status"] = "APPLY_ROLLED_BACK"
            _write_state(state_path, state)
        finally:
            env.pop("MYSQL_PWD", None)
        raise
    finally:
        env.pop("MYSQL_PWD", None)


def rollback(state_dir: Path, confirm: str, *, require_tty: bool = True) -> Dict[str, Any]:
    if os.geteuid() != 0:
        raise ApplyBlocked("ROOT_REQUIRED")
    if require_tty and not sys.stdin.isatty():
        raise ApplyBlocked("INTERACTIVE_TTY_REQUIRED")
    if confirm != ROLLBACK_TOKEN:
        raise ApplyBlocked("ROLLBACK_CONFIRMATION_TOKEN_REQUIRED")
    state_path = state_dir / "state.json"
    if not state_path.is_file():
        raise ApplyBlocked("STATE_FILE_MISSING")
    state = json.loads(_read(state_path))
    if state.get("status") == "ROLLED_BACK":
        return {"state": "ROLLED_BACK", "backup_dir": str(state_dir), "idempotent": True}

    cmd, env = _mysql_client()
    try:
        _restore_files(state)
        _validate_mysql()
        versions = state.get("changed_php_versions") or []
        _validate_php(versions)
        before = state.get("mysql_runtime_before") or {}
        old = {k: int(before[k]) for k in MYSQL_KEYS if k in before}
        if len(old) != len(MYSQL_KEYS):
            raise ApplyFailed("ROLLBACK_MYSQL_STATE_INCOMPLETE")
        _set_mysql_globals(cmd, env, old)
        _reload_php(versions)
        _verify_services(versions)
        state["status"] = "ROLLED_BACK"
        state["rolled_back_utc"] = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        _write_state(state_path, state)
        return {"state": "ROLLED_BACK", "backup_dir": str(state_dir), "idempotent": False}
    finally:
        env.pop("MYSQL_PWD", None)


def synthetic_apply(plan: Mapping[str, Any], root: Path, backup_dir: Path) -> Dict[str, Any]:
    if not plan.get("eligible"):
        raise ApplyBlocked("PLAN_NOT_ELIGIBLE")
    return _apply_plan_files(plan, root=root, backup_dir=backup_dir)


def synthetic_rollback(state: Mapping[str, Any]) -> None:
    _restore_files(state)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="P07 Resource Safe Apply RC14")
    sub = parser.add_subparsers(dest="action", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--mode", choices=rp.MODES, default="balanced")
    p_plan.add_argument("--json", action="store_true")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--mode", choices=rp.MODES, default="balanced")
    p_apply.add_argument("--confirm", default="")

    p_rb = sub.add_parser("rollback")
    p_rb.add_argument("--state-dir", required=True)
    p_rb.add_argument("--confirm", default="")

    args = parser.parse_args(argv)
    try:
        if args.action == "plan":
            snap = rp.detect_snapshot()
            rec = rp.recommend(snap, args.mode)
            plan = build_plan(snap, rec)
            print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) if args.json else render_plan(plan))
            return 0
        if args.action == "apply":
            result = production_apply(args.mode, args.confirm)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.action == "rollback":
            result = rollback(Path(args.state_dir), args.confirm)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    except ApplyBlocked as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        return 77
    except ApplyFailed as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 78
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
