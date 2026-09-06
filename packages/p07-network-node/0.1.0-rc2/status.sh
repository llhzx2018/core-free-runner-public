#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

quiet=0
[[ "${1:-}" == "--quiet" ]] && quiet=1

load_state
cli="$(v2ray_cli || true)"
managed=0
[[ -r "$VF_NODE_STATE_FILE" ]] && managed=1
active=0
service_active && active=1
listener=0
if [[ -n "${PORT:-}" ]] && valid_port "$PORT" && port_in_use_udp "$PORT"; then
  listener=1
fi

if ((quiet)); then
  if ((managed && active && listener)); then
    exit 0
  fi
  exit 1
fi

section "VF Node · 节点状态"
printf '%-18s %s\n' "模块版本" "$VF_NODE_VERSION"

if ((managed)); then
  printf '%-18s %b\n' "管理状态" "${C_GREEN}P07 已接管${C_RESET}"
  printf '%-18s %s\n' "Profile" "${PROFILE:-UNKNOWN}"
  printf '%-18s %s\n' "V2Ray Core" "${CORE_VERSION:-UNKNOWN}"
  printf '%-18s %s\n' "Core Asset" "${CORE_ASSET:-UNKNOWN}"
  printf '%-18s %s\n' "UDP 端口" "${PORT:-UNKNOWN}"
  printf '%-18s %s\n' "上游提交" "${SOURCE_COMMIT:-UNKNOWN}"
  printf '%-18s %s\n' "安装时间" "${INSTALLED_AT:-UNKNOWN}"
else
  if [[ -n "$cli" ]]; then
    printf '%-18s %b\n' "管理状态" "${C_YELLOW}检测到外部 V2Ray，未由 P07 接管${C_RESET}"
  else
    printf '%-18s %b\n' "管理状态" "${C_GRAY}未安装${C_RESET}"
  fi
fi

if [[ -n "$cli" ]]; then
  printf '%-18s %s\n' "管理命令" "$cli"
else
  printf '%-18s %b\n' "管理命令" "${C_RED}未找到${C_RESET}"
fi

if ((active)); then
  printf '%-18s %b\n' "服务" "${C_GREEN}✓ active${C_RESET}"
else
  printf '%-18s %b\n' "服务" "${C_RED}✗ inactive / unknown${C_RESET}"
fi

if [[ -n "${PORT:-}" ]]; then
  if ((listener)); then
    printf '%-18s %b\n' "UDP 监听" "${C_GREEN}✓ ${PORT}/UDP${C_RESET}"
  else
    printf '%-18s %b\n' "UDP 监听" "${C_RED}✗ 未检测到 ${PORT}/UDP${C_RESET}"
  fi
fi

say
if ((managed && active && listener)); then
  ok "节点基础健康检查 PASS"
  exit 0
fi
if [[ -n "$cli" ]] && ((managed == 0)); then
  warn "发现已有 V2Ray，但当前不是 P07 管理安装。不会自动修改。"
  exit 10
fi
fail "节点基础健康检查未通过"
exit 1
