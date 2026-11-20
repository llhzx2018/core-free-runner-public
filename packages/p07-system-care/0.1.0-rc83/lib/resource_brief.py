#!/usr/bin/env python3
"""Compact owner-facing view of the canonical P07 resource application plan.

Both the first screen and the confirmation screen use resource_apply.build_plan,
not the older CloudPanel 2048 MiB presentation heuristic. This file never
changes configuration or bypasses the production apply guard.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Mapping

import resource_profile as profile
import resource_apply as engine


def _style(value: str, tone: str) -> str:
    return profile.color(value, tone)


def _changes(plan: Mapping[str, Any]) -> tuple[int, int]:
    mysql = sum(bool(v.get("change")) for v in plan.get("mysql_changes", []))
    php = sum(bool(v.get("change")) for v in plan.get("php_changes", []))
    return mysql, php


def compact_view(snapshot: Mapping[str, Any], plan: Mapping[str, Any], mode: str) -> str:
    eligible = bool(plan.get("eligible"))
    mysql, php = _changes(plan)
    unchanged = eligible and mysql == 0 and php == 0
    cpu = int(snapshot.get("cpu_count") or 0)
    memory = int(snapshot.get("memory_mib") or 0)
    swap = int(snapshot.get("swap_mib") or 0)
    result = []
    if mode == "overview":
        result.append(f"服务器      {cpu} 核  ·  内存 {memory} MB  ·  虚拟内存 {swap} MB")
        result.append("运行环境    CloudPanel {0}  ·  数据库 {1}".format(
            "已检测" if snapshot.get("cloudpanel_present") else "未检测",
            "已检测" if snapshot.get("mysql_present") else "未检测"))
        result.append("适用性      " + _style(
            "当前配置符合建议，无需修改" if unchanged else ("符合初步条件，执行时还需复核" if eligible else "只允许查看，不可自动调整"),
            "green" if eligible else "yellow"))
    else:
        result.append("调整方案    " + _style(
            "没有需要应用的变更" if unchanged else ("通过初步校验" if eligible else "当前不可应用"),
            "green" if eligible else "yellow"))
    if eligible and not unchanged:
        result.append(f"涉及调整    PHP {php} 项  ·  数据库 {mysql} 项")
        result.append(_style("安全边界    仅降低超额上限；不修改 Swap、不自动重启数据库", "gray"))
    elif not eligible:
        reasons = []
        for code in plan.get("block_reasons", []):
            reason = engine.block_reason_text(str(code))
            if reason not in reasons:
                reasons.append(reason)
        result.append("原因        " + ("；".join(reasons[:2]) or "安全条件未满足"))
        result.append(_style("本次只读查看，不修改任何服务器配置。", "gray"))
    return "\n".join(result)


def compact_result(result: Mapping[str, Any]) -> str:
    state = str(result.get("state") or "")
    if state not in {"APPLIED_VERIFIED", "EMPTY_SERVER_CONFIG_APPLIED_VERIFIED",
                     "EMPTY_SERVER_CONFIG_VERIFIED_KEEP", "UNCHANGED_VERIFIED"}:
        raise ValueError("无法确认实际应用结果")
    backup = str(result.get("backup_dir") or "")
    label = "配置已核对，无需修改" if state in {"EMPTY_SERVER_CONFIG_VERIFIED_KEEP", "UNCHANGED_VERIFIED"} else "配置已应用且验证通过"
    lines = [_style("完成        " + label, "green")]
    if backup:
        lines.append("恢复副本    已安全保存（通过高级配置记录查阅）")
    lines.append(_style("没有自动重启 MySQL，也没有修改 Swap。", "gray"))
    return "\n".join(lines)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode == "result":
        try:
            data = json.load(sys.stdin)
            print(compact_result(data))
        except (ValueError, json.JSONDecodeError):
            print("应用结果无法核实，请通过工具检查实际状态。", file=sys.stderr)
            return 2
        return 0
    if mode not in ("overview", "plan"):
        print("用法：resource_brief.py overview|plan|result", file=sys.stderr)
        return 2
    try:
        snap = profile.detect_snapshot()
        rec = profile.recommend(snap, "balanced")
        plan = engine.build_plan(snap, rec)
    except (OSError, ValueError, KeyError, engine.ApplyBlocked) as error:
        print(f"只读检查没有完成：{type(error).__name__}", file=sys.stderr)
        return 2
    print(compact_view(snap, plan, mode), flush=True)
    # 4 means eligible but no changes; UI only offers Enter to leave.
    if plan.get("eligible") and not any(_changes(plan)):
        return 4
    return 0 if plan.get("eligible") else 3


if __name__ == "__main__":
    raise SystemExit(main())
