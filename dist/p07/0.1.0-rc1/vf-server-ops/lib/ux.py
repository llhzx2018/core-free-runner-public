#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


class UxSummaryError(RuntimeError):
    pass


def _mapping(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise UxSummaryError("result payload must be an object")
    return payload


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, default: str = "UNKNOWN") -> str:
    if value is None:
        return default
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return default


def _yes_no(value: Any) -> str:
    return "是" if value is True else "否" if value is False else "未知"


def _bytes(value: Any) -> str:
    if not isinstance(value, int) or value < 0:
        return "UNKNOWN"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def render_storage_status(payload: dict[str, Any]) -> list[str]:
    accounts = [item for item in _items(payload.get("accounts")) if isinstance(item, dict)]
    enabled = [item for item in accounts if item.get("enabled") is True]
    healthy = [item for item in enabled if item.get("health") == "OK" and item.get("encrypted_remote") is True]
    google_ready = [item for item in healthy if item.get("provider") == "google"]
    b2_ready = [item for item in healthy if item.get("provider") == "b2" and item.get("role") == "disaster_recovery"]
    lines = [
        f"远程存储账号：{len(accounts)} 个 · 已启用：{len(enabled)} 个 · 加密可用：{len(healthy)} 个",
        f"Google 主备份池：{'READY' if google_ready else 'NOT_READY'}（{len(google_ready)} 个可用）",
        f"B2 灾备目标：{'READY' if b2_ready else 'NOT_READY'}（{len(b2_ready)} 个可用）",
    ]
    if not accounts:
        lines.append("未发现已配置账号。")
        return lines
    for item in accounts:
        account_id = _text(item.get("id"))
        provider = _text(item.get("provider"))
        health = _text(item.get("health"))
        encrypted = _yes_no(item.get("encrypted_remote"))
        quota_status = _text(item.get("quota_status"))
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        free = _bytes(quota.get("free")) if quota else "N_A"
        lines.append(
            f"- {account_id} · {provider} · 健康={health} · 加密远程={encrypted} · 配额={quota_status} · 可用={free}"
        )
    lines.append("说明：B2 灾备目标 READY 只表示加密远程可达；真正可恢复性仍以完整 DR 恢复演练为准。")
    return lines


def render_storage_list(payload: dict[str, Any]) -> list[str]:
    backups = [item for item in _items(payload.get("backups")) if isinstance(item, dict)]
    errors = [item for item in _items(payload.get("errors")) if isinstance(item, dict)]
    lines = [f"可恢复远程备份：{len(backups)} 个（只显示 COMPLETE）"]
    for item in backups:
        lines.append(
            f"- {_text(item.get('backup_id'))} · {_text(item.get('provider'))} · {_text(item.get('account_id'))}"
        )
    if errors:
        lines.append(f"部分账号读取异常：{len(errors)} 个")
        for item in errors:
            lines.append(f"- {_text(item.get('account_id'))} · {_text(item.get('error'))}")
    return lines


def render_storage_push(payload: dict[str, Any]) -> list[str]:
    return [
        "远程备份上传：PASS",
        f"Backup ID：{_text(payload.get('backup_id'))}",
        f"目标：{_text(payload.get('provider'))} / {_text(payload.get('account_id'))}",
        f"大小：{_bytes(payload.get('package_bytes'))}",
        f"加密远程验证：{_yes_no(payload.get('encrypted_remote_verified'))}",
        f"Cryptcheck：{_text(payload.get('cryptcheck'))}",
        f"本地备份已删除：{_yes_no(payload.get('local_package_deleted'))}",
    ]


def render_storage_fetch(payload: dict[str, Any]) -> list[str]:
    return [
        "远程备份取回：PASS",
        f"Backup ID：{_text(payload.get('backup_id'))}",
        f"来源：{_text(payload.get('provider'))} / {_text(payload.get('source_account_id'))}",
        f"本地位置：{_text(payload.get('local_path'))}",
        f"下载后重新验证：{_text(payload.get('fresh_local_verification'))}",
        f"远程备份已删除：{_yes_no(payload.get('remote_deleted'))}",
    ]


def render_restore_plan(payload: dict[str, Any]) -> list[str]:
    blockers = [_text(item) for item in _items(payload.get("blockers"))]
    gates = [_text(item) for item in _items(payload.get("gates"))]
    warnings = [_text(item) for item in _items(payload.get("warnings"))]
    lines = [
        "恢复计划检查完成（零写入）",
        f"状态：{_text(payload.get('status'))}",
        f"站点：{_text(payload.get('domain'))}",
        f"Backup ID：{_text(payload.get('backup_id'))}",
        f"目标站点已存在：{_yes_no(payload.get('target_site_exists'))}",
        f"阻塞项：{len(blockers)} · 待确认 Gate：{len(gates)} · 警告：{len(warnings)}",
    ]
    lines.extend(f"BLOCKER · {item}" for item in blockers)
    lines.extend(f"GATE · {item}" for item in gates)
    lines.extend(f"WARNING · {item}" for item in warnings)
    return lines


def render_restore_result(payload: dict[str, Any]) -> list[str]:
    runtime_required = payload.get("runtime_activation_required") is True
    lines = [
        "全新站点恢复：PASS",
        f"状态：{_text(payload.get('status'))}",
        f"站点：{_text(payload.get('domain'))}",
        f"Backup ID：{_text(payload.get('backup_id'))}",
        f"Restore Verify：{_text(payload.get('restore_verify_status'))}",
        f"还需要 Runtime Activation：{'是' if runtime_required else '否'}",
        f"站点所有权已按目标 CloudPanel 校正：{_yes_no(payload.get('site_ownership_reconciled'))}",
        f"DNS 已修改：{_yes_no(payload.get('dns_changed'))}",
        "注意：恢复 PASS 不等于已完成 DNS 切换。",
    ]
    if runtime_required:
        lines.append("下一步：先执行“运行环境检查（零写入）”，确认 Cron/PM2 条件后再激活 Runtime。")
    return lines


def render_verify_restore(payload: dict[str, Any]) -> list[str]:
    failed = [_text(item) for item in _items(payload.get("failed_components"))]
    lines = [
        f"恢复结果验证：{_text(payload.get('status'))}",
        f"备份 Fresh Verify：{_text(payload.get('package_fresh_verification'))}",
        f"失败组件：{len(failed)}",
    ]
    lines.extend(f"FAIL · {item}" for item in failed)
    return lines


def render_migration_result(payload: dict[str, Any]) -> list[str]:
    ready = payload.get("technical_cutover_ready") is True
    lines = [
        "服务器迁移：技术验证 PASS" if ready else "服务器迁移：技术验证未通过",
        f"站点：{_text(payload.get('domain'))}",
        f"Backup ID：{_text(payload.get('backup_id'))}",
        f"目标恢复：{_text(payload.get('restore_status'))}",
        f"Runtime：{_text(payload.get('runtime_status'))}",
        f"跨服务器一致性：{_text(payload.get('cross_server_status'))}",
        f"HTTP/HTTPS：{_text(payload.get('http_https_status'))}",
        f"私有传输暂存已清理：{'是' if payload.get('remote_private_staging_cleanup') == 'PASS' else '未知'}",
        f"技术切换条件：{'已通过' if ready else '未通过'}",
        f"DNS 已修改：{_yes_no(payload.get('dns_changed'))}",
        f"旧服务器删除请求：{_yes_no(payload.get('old_server_delete_requested'))}",
    ]
    if ready:
        lines.append("下一步：等待 OWNER Cutover 决策；本工具不会自动修改 DNS 或删除旧服务器。")
    return lines


def render_runtime_plan(payload: dict[str, Any]) -> list[str]:
    manual = [item for item in _items(payload.get("manual_cron")) if isinstance(item, dict)]
    user_cron = isinstance(payload.get("user_crontab"), dict)
    pm2 = payload.get("pm2") if isinstance(payload.get("pm2"), dict) else {}
    pm2_required = pm2.get("ready") is True
    lines = [
        "运行环境检查完成（零写入）",
        f"状态：{_text(payload.get('status'))}",
        f"站点：{_text(payload.get('domain'))}",
        f"Backup ID：{_text(payload.get('backup_id'))}",
        f"将恢复用户 Cron：{'是' if user_cron else '否'}",
        f"将恢复 PM2：{'是' if pm2_required else '否'}",
        f"Manual Cron Gate：{len(manual)} 个",
        f"自动激活条件：{'READY' if not manual else 'BLOCKED_BY_MANUAL_GATE'}",
    ]
    for item in manual:
        reason = _text(item.get("reason"))
        lines.append(f"MANUAL_GATE · {reason}")
    if pm2_required:
        lines.append("PM2 前置条件：目标 Site User 必须存在可匹配的 NVM/Node/PM2；激活时会再次 fail-closed 检查。")
    if user_cron:
        lines.append("Cron 前置条件：目标 Site User 已有非空 crontab 时会拒绝覆盖。")
    return lines


def render_runtime_result(payload: dict[str, Any]) -> list[str]:
    manual = _items(payload.get("manual_cron_remaining"))
    return [
        "运行环境激活：PASS",
        f"状态：{_text(payload.get('status'))}",
        f"站点：{_text(payload.get('domain'))}",
        f"Backup ID：{_text(payload.get('backup_id'))}",
        f"用户 Cron 已安装：{_yes_no(payload.get('cron_installed'))}",
        f"PM2 已启动：{_yes_no(payload.get('pm2_started'))}",
        f"PM2 执行模式：{_text(payload.get('pm2_execution_mode'))}",
        f"剩余 Manual Cron Gate：{len(manual)} 个",
        f"DNS 已修改：{_yes_no(payload.get('dns_changed'))}",
    ]


RENDERERS = {
    "storage-status": render_storage_status,
    "storage-list": render_storage_list,
    "storage-push": render_storage_push,
    "storage-fetch": render_storage_fetch,
    "restore-plan": render_restore_plan,
    "restore-result": render_restore_result,
    "verify-restore": render_verify_restore,
    "migration-result": render_migration_result,
    "runtime-plan": render_runtime_plan,
    "runtime-result": render_runtime_result,
}


def render(mode: str, payload: Any) -> str:
    renderer = RENDERERS.get(mode)
    if renderer is None:
        raise UxSummaryError(f"unsupported summary mode: {mode}")
    lines = renderer(_mapping(payload))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="VF Server Ops safe human result summary")
    parser.add_argument("mode", choices=sorted(RENDERERS))
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        sys.stdout.write(render(args.mode, payload))
    except (json.JSONDecodeError, UxSummaryError) as exc:
        print(f"ERROR: result summary failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
