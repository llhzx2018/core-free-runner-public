#!/usr/bin/env bash
set -Eeuo pipefail

# Public versions stay short and semantic. Internal build identities remain hidden
# and are used only for exact validation / engineering traceability.
VERSION="V0.1.0"
BUILD_ID="0.1.0-preview10"

VF_NODE_PUBLIC="V0.1.0"
VF_NODE_EXPECTED="0.1.0-rc9"
VF_NODE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/vf-node.sh"

VPS_AUDIT_PUBLIC="V2.0.0"
VPS_AUDIT_EXPECTED="2.0.0-rc4-zh"
VPS_AUDIT_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/1197372f0b32b7cc9a8b35736c30563cb36633c9/experiments/p07-vps-audit-v20-rc4.sh"
VPS_AUDIT_SHA256="54325e92bdf78a90c74b5fed73be9d0633b402659fdfa2848dc751ff23efaecd"

VF_SERVER_OPS_PUBLIC="V0.1.0"
VF_SERVER_OPS_EXPECTED="VF Server Ops 0.1.0 RC2"
VF_SERVER_OPS_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07.sh"

SYSTEM_CARE_PUBLIC="V0.1.0"
SYSTEM_CARE_EXPECTED="0.1.0-rc3"
SYSTEM_CARE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-system-care.sh"

C_RESET=''; C_BOLD=''; C_CYAN=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_GRAY=''
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_GRAY=$'\033[90m'
fi

say() { printf '%b\n' "$*"; }
pause_menu() { [[ -t 0 ]] || return 0; printf '\n按 Enter 返回主菜单...'; read -r _ || true; }

show_header() {
  clear 2>/dev/null || true
  say "${C_CYAN}┌──────────────────────────────────────────────────────────────┐${C_RESET}"
  say "${C_CYAN}│${C_RESET}  ${C_BOLD}P07 · VF Server Ops${C_RESET}   ${C_GRAY}${VERSION}${C_RESET}                                  ${C_CYAN}│${C_RESET}"
  say "${C_CYAN}└──────────────────────────────────────────────────────────────┘${C_RESET}"
  say
}

show_menu() {
  show_header
  say "  ${C_GREEN}1.${C_RESET} 网络节点 / V2Ray              ${C_GRAY}${VF_NODE_PUBLIC}${C_RESET}      ${C_GREEN}可用${C_RESET}"
  say "  ${C_GREEN}2.${C_RESET} VPS 一键验机                  ${C_GRAY}${VPS_AUDIT_PUBLIC}${C_RESET}      ${C_GREEN}可用${C_RESET}"
  say "  ${C_CYAN}3.${C_RESET} CloudPanel 备份 / 恢复 / 迁移  ${C_GRAY}${VF_SERVER_OPS_PUBLIC}${C_RESET}      ${C_YELLOW}测试中${C_RESET}"
  say "  ${C_CYAN}4.${C_RESET} 系统维护 / 安全                ${C_GRAY}${SYSTEM_CARE_PUBLIC}${C_RESET}      ${C_YELLOW}测试中${C_RESET}"
  say "  ${C_GRAY}0.${C_RESET} 退出"
  say
}

local_node_version() {
  command -v vf-node >/dev/null 2>&1 || return 1
  NO_COLOR=1 vf-node --version 2>/dev/null | awk '{print $NF}' || true
}

run_network_node() {
  if [[ "$(local_node_version || true)" == "$VF_NODE_EXPECTED" ]]; then
    vf-node
    return $?
  fi

  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }
  local tmp rc
  tmp="$(mktemp -t p07-vf-node.XXXXXX)"
  chmod 700 "$tmp"
  curl -fsSL "$VF_NODE_INSTALLER" -o "$tmp" || { rm -f "$tmp"; say "${C_RED}✗ 网络节点入口下载失败。${C_RESET}" >&2; return 4; }
  set +e
  bash "$tmp"
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
  else
    return 127
  fi
}

render_vps_audit_output() {
  sed -u \
    -e "s/P07 VPS 一键验机 2\.0/P07 VPS 一键验机 ${VPS_AUDIT_PUBLIC}/g" \
    -e "s/2\.0\.0-rc3-zh/${VPS_AUDIT_PUBLIC}/g" \
    -e "s/2\.0\.0-rc4-zh/${VPS_AUDIT_PUBLIC}/g"
}

run_vps_audit() {
  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }

  local tmp actual_sha version rc cmd
  tmp="$(mktemp -t p07-vps-audit.XXXXXX)"
  chmod 700 "$tmp"

  say "${C_CYAN}正在启动 VPS 一键验机 ${VPS_AUDIT_PUBLIC}…${C_RESET}"

  if ! curl -fsSL "$VPS_AUDIT_URL" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ VPS 验机模块下载失败。${C_RESET}" >&2
    return 4
  fi

  actual_sha="$(sha256_file "$tmp" 2>/dev/null || true)"
  if [[ -z "$actual_sha" ]]; then
    rm -f "$tmp"
    say "${C_RED}✗ 当前系统缺少 SHA256 校验工具，已停止执行。${C_RESET}" >&2
    return 5
  fi
  if [[ "$actual_sha" != "$VPS_AUDIT_SHA256" ]]; then
    rm -f "$tmp"
    say "${C_RED}✗ VPS 验机模块完整性校验失败，已停止执行。${C_RESET}" >&2
    return 6
  fi

  version="$(NO_COLOR=1 bash "$tmp" --version 2>/dev/null | awk '{print $NF}' || true)"
  if [[ "$version" != "$VPS_AUDIT_EXPECTED" ]]; then
    rm -f "$tmp"
    say "${C_RED}✗ VPS 验机模块版本不匹配，已停止执行。${C_RESET}" >&2
    return 7
  fi

  set +e
  if [[ -t 1 ]] && command -v script >/dev/null 2>&1; then
    printf -v cmd 'bash %q' "$tmp"
    script -qec "$cmd" /dev/null | render_vps_audit_output
    rc=${PIPESTATUS[0]}
  else
    bash "$tmp" | render_vps_audit_output
    rc=${PIPESTATUS[0]}
  fi
  set -e
  rm -f "$tmp"
  return "$rc"
}

local_server_ops_version() {
  command -v vfops >/dev/null 2>&1 || return 1
  NO_COLOR=1 vfops --version 2>/dev/null || true
}

run_server_ops() {
  if [[ "$(local_server_ops_version || true)" == "$VF_SERVER_OPS_EXPECTED" ]]; then
    vfops
    return $?
  fi

  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }

  local tmp rc
  tmp="$(mktemp -t p07-server-ops.XXXXXX)"
  chmod 700 "$tmp"
  if ! curl -fsSL "$VF_SERVER_OPS_INSTALLER" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ CloudPanel 运维模块入口下载失败。${C_RESET}" >&2
    return 4
  fi
  if ! bash -n "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ CloudPanel 运维模块入口校验失败。${C_RESET}" >&2
    return 5
  fi

  set +e
  P07_TOOLBOX_PARENT=1 bash "$tmp"
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

local_system_care_version() {
  command -v vf-system-care >/dev/null 2>&1 || return 1
  NO_COLOR=1 vf-system-care --version 2>/dev/null | awk '{print $NF}' || true
}

run_system_care() {
  if [[ "$(local_system_care_version || true)" == "$SYSTEM_CARE_EXPECTED" ]]; then
    vf-system-care menu
    return $?
  fi

  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }

  local tmp rc
  tmp="$(mktemp -t p07-system-care.XXXXXX)"
  chmod 700 "$tmp"
  if ! curl -fsSL "$SYSTEM_CARE_INSTALLER" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 系统维护模块入口下载失败。${C_RESET}" >&2
    return 4
  fi
  if ! bash -n "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 系统维护模块入口校验失败。${C_RESET}" >&2
    return 5
  fi

  set +e
  bash "$tmp" menu
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

main_menu() {
  local choice rc
  while true; do
    show_menu
    printf '请选择 [0-4]：'
    read -r choice || return 0
    case "$choice" in
      1)
        set +e
        run_network_node
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || { say "${C_YELLOW}⚠ 网络节点模块返回退出码 ${rc}。${C_RESET}"; pause_menu; }
        ;;
      2)
        set +e
        run_vps_audit
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || say "${C_YELLOW}⚠ VPS 一键验机模块返回退出码 ${rc}。${C_RESET}"
        pause_menu
        ;;
      3)
        set +e
        run_server_ops
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || { say "${C_YELLOW}⚠ CloudPanel 运维模块返回退出码 ${rc}。${C_RESET}"; pause_menu; }
        ;;
      4)
        set +e
        run_system_care
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || { say "${C_YELLOW}⚠ 系统维护模块返回退出码 ${rc}。${C_RESET}"; pause_menu; }
        ;;
      0) return 0 ;;
      *) say "${C_YELLOW}⚠ 无效选择，请输入 0-4。${C_RESET}" ;;
    esac
  done
}

case "${1:-}" in
  --version|-V) printf 'P07 Toolbox %s\n' "$VERSION" ;;
  --help|-h)
    cat <<EOF
P07 · VF Server Ops ${VERSION}

Usage:
  p07-toolbox

1. 网络节点 / V2Ray              ${VF_NODE_PUBLIC}
2. VPS 一键验机                  ${VPS_AUDIT_PUBLIC}
3. CloudPanel 备份 / 恢复 / 迁移  ${VF_SERVER_OPS_PUBLIC}（测试中）
4. 系统维护 / 安全                ${SYSTEM_CARE_PUBLIC}（测试中）

说明：用户界面仅显示 Vx.x.x 公共版本；RC / preview / zh 等构建标识只用于内部工程追溯。
EOF
    ;;
  "")
    if [[ -t 0 && -t 1 ]]; then main_menu; else printf 'ERROR: P07 Toolbox menu requires an interactive terminal.\n' >&2; exit 2; fi
    ;;
  *) printf 'ERROR: unknown argument: %s\n' "$1" >&2; exit 2 ;;
esac
