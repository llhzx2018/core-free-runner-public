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
healthy=0
if ((managed && active && listener)); then
  healthy=1
fi

if ((quiet)); then
  ((healthy)) && exit 0
  exit 1
fi

section "网络代理节点状态"
say
if ((managed)); then
  if ((healthy)); then say "结论       ${C_GREEN}运行正常 ✓${C_RESET}"; else say "结论       ${C_RED}节点异常 · 可自动修复${C_RESET}"; fi
  say "方案       VMess + mKCP + dtls"
  say "服务       $([[ "$active" -eq 1 ]] && printf '运行中' || printf '未运行')"
  if [[ -n "${PORT:-}" ]]; then say "UDP 端口   ${PORT} · $([[ "$listener" -eq 1 ]] && printf '监听中' || printf '未监听')"; fi
else
  if [[ -n "$cli" ]]; then say "结论       ${C_YELLOW}检测到已有 V2Ray · 当前不由工具管理${C_RESET}"; else say "结论       ${C_GRAY}未安装${C_RESET}"; fi
fi
say
say "${C_GRAY}──────────────────────────────────────────────────────────────${C_RESET}"
say
if ((healthy)); then
  ok "节点基础健康检查通过"
  exit 0
fi
if ((managed)); then
  fail "节点已由 P07 管理，但当前没有通过健康检查。可从菜单选择安装 / 修复节点自动尝试修复。"
  exit 1
fi
if [[ -n "$cli" ]]; then
  warn "发现已有 V2Ray，但当前不是 P07 管理安装。不会自动修改。"
  exit 10
fi
fail "节点基础健康检查未通过"
exit 1
