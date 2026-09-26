#!/usr/bin/env python3
"""P07 System Care resource profile engine.

Read-only by design. Detects current hardware/runtime and produces bounded
recommendations. It never writes PHP/MySQL/Swap/systemd configuration.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import resource_calibrations as calibrations  # noqa: E402

MODES = ("conservative", "balanced", "performance")
BASELINES: Dict[str, Dict[str, int]] = {
    "1G": {"ram_anchor": 1024, "buffer_pool": 128, "connections": 40, "tmp_table": 16, "table_open_cache": 500, "swap": 1024},
    "2G": {"ram_anchor": 2048, "buffer_pool": 256, "connections": 80, "tmp_table": 32, "table_open_cache": 1000, "swap": 2048},
    "4G": {"ram_anchor": 4096, "buffer_pool": 512, "connections": 120, "tmp_table": 48, "table_open_cache": 2000, "swap": 2048},
    "8G": {"ram_anchor": 8192, "buffer_pool": 1024, "connections": 200, "tmp_table": 64, "table_open_cache": 3000, "swap": 1024},
}
MODE_FACTORS: Dict[str, Dict[str, float]] = {
    "conservative": {"db": 0.80, "connections": 0.75, "php": 0.75, "table": 0.80, "tmp": 0.75},
    "balanced": {"db": 1.00, "connections": 1.00, "php": 1.00, "table": 1.00, "tmp": 1.00},
    "performance": {"db": 1.25, "connections": 1.25, "php": 1.25, "table": 1.20, "tmp": 1.25},
}
CLOUDPANEL_MIN_RAM_MIB = 2048


def _run(cmd: Sequence[str], timeout: float = 3.0) -> str:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return p.stdout if p.returncode == 0 else ""


def _meminfo() -> Dict[str, int]:
    out: Dict[str, int] = {}
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z_()]+):\s+(\d+)\s+kB$", line)
        if m:
            out[m.group(1)] = int(m.group(2)) // 1024
    return out


def _systemctl_active(unit: str) -> Optional[bool]:
    if not shutil.which("systemctl"):
        return None
    out = _run(["systemctl", "is-active", unit], timeout=2.0).strip()
    if not out:
        return None
    return out == "active"


def _pool_map() -> Tuple[Dict[int, Dict[str, str]], List[str], int]:
    mapping: Dict[int, Dict[str, str]] = {}
    active_versions: List[str] = []
    pool_count = 0
    root = Path("/etc/php")
    if not root.is_dir():
        return mapping, active_versions, pool_count

    for version_dir in sorted(root.iterdir(), key=lambda p: p.name):
        pool_dir = version_dir / "fpm" / "pool.d"
        if not pool_dir.is_dir():
            continue
        version = version_dir.name
        if _systemctl_active(f"php{version}-fpm") is True:
            active_versions.append(version)

        for path in sorted(pool_dir.glob("*.conf")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            pool_count += 1
            pool_m = re.search(r"(?m)^\[([^\]]+)\]", text)
            listen_m = re.search(r"(?m)^\s*listen\s*=\s*(?:127\.0\.0\.1:)?(\d+)\s*$", text)
            if not listen_m:
                continue
            port = int(listen_m.group(1))
            mapping[port] = {
                "version": version,
                "pool": pool_m.group(1).strip() if pool_m else path.stem,
                "file": str(path),
            }
    return mapping, active_versions, pool_count


def _nginx_fastcgi_ports() -> List[int]:
    root = Path("/etc/nginx")
    if not root.is_dir():
        return []
    ports = set()
    pattern = re.compile(r"fastcgi_pass\s+(?:127\.0\.0\.1:)?(\d+)\s*;")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in pattern.finditer(text):
            ports.add(int(m.group(1)))
    return sorted(ports)


def _php_workers() -> List[int]:
    text = _run(["ps", "-eo", "rss=,args="], timeout=3.0)
    rss: List[int] = []
    for line in text.splitlines():
        if "php-fpm: pool " not in line:
            continue
        m = re.match(r"\s*(\d+)\s+", line)
        if m:
            rss.append(max(1, math.ceil(int(m.group(1)) / 1024)))
    return rss


def _p75(values: Sequence[int]) -> Optional[int]:
    if not values:
        return None
    data = sorted(int(v) for v in values)
    return data[max(0, math.ceil(len(data) * 0.75) - 1)]


def _mysql_runtime() -> Tuple[bool, str, int]:
    text = _run(["ps", "-eo", "rss=,comm="], timeout=3.0)
    rss = 0
    present = False
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        if parts[1] in ("mysqld", "mariadbd"):
            present = True
            try:
                rss += max(1, math.ceil(int(parts[0]) / 1024))
            except ValueError:
                pass

    flavor = "none"
    if present:
        version = _run(["mysql", "--version"], timeout=2.0) or _run(["mysqld", "--version"], timeout=2.0)
        low = version.lower()
        if "mariadb" in low:
            flavor = "mariadb"
        elif "percona" in low:
            flavor = "percona"
        elif version:
            flavor = "mysql"
        else:
            flavor = "mysql-compatible"
    return present, flavor, rss


def detect_snapshot() -> Dict[str, Any]:
    mem = _meminfo()
    total = int(mem.get("MemTotal", 0))
    available = int(mem.get("MemAvailable", 0))
    swap = int(mem.get("SwapTotal", 0))
    cpu = max(1, os.cpu_count() or 1)
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = 0.0

    pool_map, active_versions, pool_count = _pool_map()
    fastcgi_ports = _nginx_fastcgi_ports()
    referenced_versions = sorted(
        {pool_map[p]["version"] for p in fastcgi_ports if p in pool_map},
        key=lambda x: tuple(int(part) if part.isdigit() else 999 for part in re.split(r"[._-]", x)),
    )
    referenced_pools = [pool_map[p] for p in fastcgi_ports if p in pool_map]
    worker_rss = _php_workers()
    mysql_present, mysql_flavor, mysql_rss = _mysql_runtime()

    return {
        "cpu_count": cpu,
        "memory_mib": total,
        "memory_available_mib": available,
        "swap_mib": swap,
        "load1": round(load1, 2),
        "load5": round(load5, 2),
        "load15": round(load15, 2),
        "cloudpanel_present": bool(shutil.which("clpctl") or Path("/home/clp").exists() or Path("/etc/cloudpanel").exists()),
        "nginx_present": bool(shutil.which("nginx") or Path("/etc/nginx").exists()),
        "php_active_versions": active_versions,
        "php_referenced_versions": referenced_versions,
        "php_unused_active_versions": sorted(set(active_versions) - set(referenced_versions)),
        "php_pool_count": pool_count,
        "php_referenced_pool_count": len(referenced_pools),
        "php_referenced_pools": referenced_pools,
        "php_worker_count": len(worker_rss),
        "php_worker_rss_mib_p75": _p75(worker_rss),
        "php_worker_rss_mib_max": max(worker_rss) if worker_rss else None,
        "mysql_present": mysql_present,
        "mysql_flavor": mysql_flavor,
        "mysql_rss_mib": mysql_rss,
    }


def hardware_band(memory_mib: int) -> str:
    if memory_mib < 1536:
        return "1G"
    if memory_mib < 3072:
        return "2G"
    if memory_mib < 6144:
        return "4G"
    if memory_mib < 12288:
        return "8G"
    return "Custom"


def _round_step(value: float, step: int) -> int:
    return int(round(value / step) * step)


def _custom_baseline(memory_mib: int, cpu_count: int) -> Dict[str, int]:
    return {
        "ram_anchor": memory_mib,
        "buffer_pool": max(1536, min(4096, _round_step(memory_mib * 0.22, 128))),
        "connections": min(300, 80 + 40 * max(1, cpu_count)),
        "tmp_table": 64,
        "table_open_cache": min(4000, 1000 + 500 * max(1, cpu_count)),
        "swap": 1024,
    }


def recommend(snapshot: Mapping[str, Any], mode: str = "balanced") -> Dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"invalid mode: {mode}")

    memory_mib = max(256, int(snapshot.get("memory_mib") or 0))
    cpu_count = max(1, int(snapshot.get("cpu_count") or 1))
    band = hardware_band(memory_mib)
    baseline = dict(BASELINES[band]) if band in BASELINES else _custom_baseline(memory_mib, cpu_count)
    factors = MODE_FACTORS[mode]

    buffer_pool = max(96, _round_step(baseline["buffer_pool"] * factors["db"], 32))
    connections = max(30, _round_step(baseline["connections"] * factors["connections"], 10))
    cpu_cap_balanced = {1: 80, 2: 160, 3: 220}.get(cpu_count, 320)
    connections = min(connections, max(30, _round_step(cpu_cap_balanced * factors["connections"], 10)))
    tmp_table = max(16, _round_step(baseline["tmp_table"] * factors["tmp"], 16))
    table_open_cache = max(400, _round_step(baseline["table_open_cache"] * factors["table"], 100))

    worker_rss = max(64, int(snapshot.get("php_worker_rss_mib_p75") or 96))
    os_reserve = max(320, int(round(memory_mib * 0.22)))
    residual = max(128, memory_mib - os_reserve - buffer_pool)
    php_budget = max(128, int(round(residual * 0.55 * factors["php"])))
    aggregate_children = max(1, php_budget // worker_rss)
    hot_pool = min(12, aggregate_children, max(1, math.ceil(cpu_count * 2 * factors["php"])))
    if cpu_count == 1 and mode in ("conservative", "balanced"):
        hot_pool = min(hot_pool, 2)
    elif cpu_count == 1:
        hot_pool = min(hot_pool, 3)
    low_traffic_pool = 1 if mode == "conservative" else min(2, hot_pool)

    recommended_swap = int(baseline["swap"])
    notes: List[str] = []
    load1 = float(snapshot.get("load1") or 0.0)
    if load1 / cpu_count >= 1.5:
        notes.append("CPU_PRESSURE")
    if int(snapshot.get("php_pool_count") or 0) >= 8 and memory_mib <= 2048:
        notes.append("MANY_PHP_POOLS_LOW_RAM")
    if int(snapshot.get("mysql_rss_mib") or 0) > memory_mib * 0.30:
        notes.append("MYSQL_RSS_HIGH")
    if int(snapshot.get("swap_mib") or 0) < recommended_swap // 2 and memory_mib <= 2048:
        notes.append("SWAP_BELOW_RECOMMENDED")
    if bool(snapshot.get("cloudpanel_present")) and band == "1G":
        notes.append("BELOW_CLOUDPANEL_MINIMUM_RAM")
    if cpu_count == 1:
        notes.append("SINGLE_CORE_CPU_CONTENTION_GUARD")

    active = list(snapshot.get("php_active_versions") or [])
    referenced = list(snapshot.get("php_referenced_versions") or [])
    unused = sorted(set(active) - set(referenced))
    profile_id = f"VF-RP-{band}-{cpu_count}C-{mode.upper()}"
    calibration = calibrations.get_calibration(profile_id)

    return {
        "schema": "vf-resource-profile.v2",
        "profile_id": profile_id,
        "hardware": {"band": band, "cpu_count": cpu_count, "memory_mib": memory_mib},
        "mode": mode,
        "mysql": {
            "innodb_buffer_pool_size_mib": buffer_pool,
            "max_connections": connections,
            "tmp_table_size_mib": tmp_table,
            "max_heap_table_size_mib": tmp_table,
            "table_open_cache": table_open_cache,
        },
        "php": {
            "worker_rss_reference_mib": worker_rss,
            "aggregate_children_budget": aggregate_children,
            "hot_pool_max_children": hot_pool,
            "low_traffic_pool_max_children": low_traffic_pool,
            "keep_versions": referenced,
            "unused_active_versions": unused,
        },
        "swap": {
            "current_mib": int(snapshot.get("swap_mib") or 0),
            "recommended_mib": recommended_swap,
            "action": "KEEP" if int(snapshot.get("swap_mib") or 0) >= recommended_swap // 2 else "REVIEW",
        },
        "calibration": calibration,
        "evidence": {
            "basis": "hardware_baseline_plus_runtime_measurement",
            "php_worker_rss_measured": snapshot.get("php_worker_rss_mib_p75") is not None,
            "production_calibration": calibration.get("legacy_reference"),
        },
        "notes": notes,
        "write_boundary": "READ_ONLY_RECOMMENDATION",
    }


NOTE_TEXT = {
    "CPU_PRESSURE": "当前 1 分钟负载相对 vCPU 偏高；不要仅靠增加 PHP Worker 解决。",
    "MANY_PHP_POOLS_LOW_RAM": "低内存服务器存在较多 PHP Pool；Apply 阶段应保持按 Pool 限制并优先停用未引用 PHP 版本。",
    "MYSQL_RSS_HIGH": "MySQL 当前 RSS 占总内存超过约 30%；建议优先核对数据库预算。",
    "SWAP_BELOW_RECOMMENDED": "低内存机器 Swap 低于建议保护量；这里只提示，不自动创建或清理 Swap。",
    "BELOW_CLOUDPANEL_MINIMUM_RAM": "已检测 CloudPanel，但内存低于 CloudPanel 当前官方最低 2GB 要求；不应把 1GB Profile 当作受支持的 CloudPanel Production 配置。",
    "SINGLE_CORE_CPU_CONTENTION_GUARD": "单核机器以 CPU 争用为主要并发约束，热点 PHP Pool 不建议无限随内存放大。",
}


def _fmt_mib(value: int) -> str:
    if value >= 1024 and value % 1024 == 0:
        return f"{value // 1024} GB"
    return f"{value} MB"


def render_preview(snapshot: Mapping[str, Any], rec: Mapping[str, Any]) -> str:
    hw = rec["hardware"]
    mysql = rec["mysql"]
    php = rec["php"]
    swap = rec["swap"]
    lines = [
        "P07 · 资源优化 / 配置推荐",
        "",
        f"识别配置    {hw['cpu_count']} vCPU / {_fmt_mib(hw['memory_mib'])} RAM / {_fmt_mib(int(snapshot.get('swap_mib') or 0))} Swap",
        f"Profile     {rec['profile_id']}",
        f"Calibration {rec['calibration']['state']}",
        f"模式        {rec['mode']}",
        f"当前负载    {snapshot.get('load1', 0)} / {snapshot.get('load5', 0)} / {snapshot.get('load15', 0)}",
        "",
        "PHP",
        f"  站点引用版本       {', '.join(php['keep_versions']) if php['keep_versions'] else '未识别'}",
        f"  当前未引用且 Active {', '.join(php['unused_active_versions']) if php['unused_active_versions'] else '无/未识别'}",
        f"  Worker RSS 参考     {php['worker_rss_reference_mib']} MB",
        f"  热点 Pool 上限      {php['hot_pool_max_children']}",
        f"  低流量 Pool 上限    {php['low_traffic_pool_max_children']}",
        f"  PHP 总子进程预算    {php['aggregate_children_budget']}",
        "",
        "MySQL / MariaDB / Percona",
        f"  Buffer Pool         {mysql['innodb_buffer_pool_size_mib']} MB",
        f"  Max Connections     {mysql['max_connections']}",
        f"  Tmp Table           {mysql['tmp_table_size_mib']} MB",
        f"  Max Heap            {mysql['max_heap_table_size_mib']} MB",
        f"  Table Open Cache    {mysql['table_open_cache']}",
        "",
        f"Swap 建议             {_fmt_mib(swap['recommended_mib'])} ({swap['action']})",
    ]
    if rec["notes"]:
        lines += ["", "注意"]
        for note in rec["notes"]:
            lines.append(f"  - {NOTE_TEXT.get(note, note)}")
    lines += ["", "边界：本页只生成建议，不修改 PHP / MySQL / Swap / systemd，不重启服务。"]
    return "\n".join(lines)


def matrix(mode: str = "balanced") -> List[Dict[str, Any]]:
    rows = []
    for memory_mib in (1024, 2048, 4096, 8192):
        for cpu_count in (1, 2, 4):
            snap = {
                "cpu_count": cpu_count,
                "memory_mib": memory_mib,
                "swap_mib": 0,
                "load1": 0.0,
                "php_pool_count": 1,
                "php_worker_rss_mib_p75": 96,
                "mysql_rss_mib": 0,
                "php_active_versions": [],
                "php_referenced_versions": [],
            }
            rows.append(recommend(snap, mode))
    return rows


def render_matrix(mode: str = "balanced") -> str:
    rows = matrix(mode)
    out = [
        f"P07 Resource Profile Matrix · {mode}",
        "",
        "RAM   CPU   MySQL Buffer   Connections   Tmp   TableCache   Hot PHP   Swap    Calibration",
        "----  ----  -------------  ------------  ----  -----------  --------  ------  -------------------",
    ]
    for r in rows:
        h = r["hardware"]; m = r["mysql"]; p = r["php"]; s = r["swap"]
        out.append(
            f"{hardware_band(h['memory_mib']):<4}  {h['cpu_count']:<4}  "
            f"{m['innodb_buffer_pool_size_mib']:>7} MB      "
            f"{m['max_connections']:>5}         "
            f"{m['tmp_table_size_mib']:>3}M      "
            f"{m['table_open_cache']:>5}        "
            f"{p['hot_pool_max_children']:>3}       "
            f"{s['recommended_mib']:>4}M  "
            f"{r['calibration']['state']}"
        )
    out += ["", "说明：矩阵是硬件基线；真实 Preview 会用当前 PHP Worker RSS、Pool 数、Load、MySQL RSS 再修正/提示。"]
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="P07 read-only resource profile engine")
    parser.add_argument("action", nargs="?", choices=("preview", "json", "matrix"), default="preview")
    parser.add_argument("--mode", choices=MODES, default="balanced")
    args = parser.parse_args(argv)

    if args.action == "matrix":
        print(render_matrix(args.mode))
        return 0

    snapshot = detect_snapshot()
    recommendation = recommend(snapshot, args.mode)
    if args.action == "json":
        print(json.dumps({"snapshot": snapshot, "recommendation": recommendation}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_preview(snapshot, recommendation))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
