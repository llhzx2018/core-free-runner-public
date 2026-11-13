#!/usr/bin/env bash
set -Eeuo pipefail

# P07 V0.1.0 final public distribution readback marker.
# 公共版本保持简短稳定；内部构建身份仅用于精确校验和工程追溯。
VERSION="V0.1.0"
BUILD_ID="0.1.0-preview16"

VF_NODE_PUBLIC="V0.1.0"
VF_NODE_EXPECTED="0.1.0-rc13"
VF_NODE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/vf-node.sh"

VPS_AUDIT_PUBLIC="V2.1.0"
VPS_AUDIT_EXPECTED="V2.1.0"
VPS_AUDIT_BUILD_EXPECTED="2.1.0-rc7-field"
VPS_AUDIT_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/0a851b9fe1819c7970ed5bb8e3633f2fc8e73166/experiments/p07-vps-audit-v21.sh"
VPS_AUDIT_SHA256="d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d"

VF_SERVER_OPS_PUBLIC="V0.1.0"
VF_SERVER_OPS_EXPECTED="VF Server Ops 0.1.0"
VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release115"
VF_SERVER_OPS_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07.sh"

SYSTEM_CARE_PUBLIC="V0.1.0"
SYSTEM_CARE_EXPECTED="0.1.0-rc82"
SYSTEM_CARE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-system-care.sh"

# P07-M05 新服务器初始化 has its OWN runtime/build and no M03/M04 installer calls.
# The isolated M05 artifact is not publicly distributed yet: do not invent a
# download URL or silently fall back to the legacy M03+M04 installers.
M05_BUILD_EXPECTED="0.1.0-m05-candidate1"
M05_RUNTIME="/opt/vfops-modules/m05/current/bin/vfops-init-entry"

C_RESET=''; C_BOLD=''; C_CYAN=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_GRAY=''
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_GRAY=$'\033[90m'
fi

say() { printf '%b\n' "$*"; }
pause_menu() { [[ -t 0 ]] || return 0; printf '\n按 Enter 返回主菜单...'; read -r _ || true; }
screen_clear() { if [[ -t 0 || -t 1 ]]; then printf '\033[2J\033[H'; fi; }

show_header() {
  screen_clear
  say "${C_CYAN}┌──────────────────────────────────────────────────────────────┐${C_RESET}"
  say "${C_CYAN}│${C_RESET}  ${C_BOLD}服务器工具箱${C_RESET}   ${C_GRAY}${VERSION}${C_RESET}                                       ${C_CYAN}│${C_RESET}"
  say "${C_CYAN}└──────────────────────────────────────────────────────────────┘${C_RESET}"
  say
}

show_menu() {
  show_header
  say "${C_GREEN}功能：5 项${C_RESET}"
  say
  say "  ${C_GREEN}1.${C_RESET} 网络代理节点        ${C_GRAY}V2Ray代理${C_RESET}"
  say "  ${C_GREEN}2.${C_RESET} 服务器性能检测      ${C_GRAY}VPS验机${C_RESET}"
  say "  ${C_GREEN}3.${C_RESET} 网站与数据          ${C_GRAY}网站/数据库/备份${C_RESET}"
  say "  ${C_GREEN}4.${C_RESET} 服务器维护与安全    ${C_GRAY}更新/清理/安全${C_RESET}"
  say "  ${C_GREEN}5.${C_RESET} 新服务器初始化      ${C_GRAY}更新/面板/优化${C_RESET}"
  say "  ${C_GRAY}0.${C_RESET} 退出"
  say
  say "${C_GRAY}版本信息进入对应功能后查看；主菜单只保留常用操作。${C_RESET}"
}

local_node_version() {
  command -v vf-node >/dev/null 2>&1 || return 1
  NO_COLOR=1 vf-node --version 2>/dev/null | awk '{print $NF}' || true
}

run_network_node() {
  screen_clear
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

run_vps_audit() {
  screen_clear
  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }

  local tmp actual_sha version build_id rc cmd
  tmp="$(mktemp -t p07-vps-audit.XXXXXX)"
  chmod 700 "$tmp"

  say "${C_CYAN}正在启动服务器性能检测 ${VPS_AUDIT_PUBLIC}…${C_RESET}"

  if ! curl -fsSL "$VPS_AUDIT_URL" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 服务器性能检测模块下载失败。${C_RESET}" >&2
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
    say "${C_RED}✗ 服务器性能检测模块完整性校验失败，已停止执行。${C_RESET}" >&2
    return 6
  fi

  version="$(NO_COLOR=1 bash "$tmp" --version 2>/dev/null | awk '{print $NF}' || true)"
  if [[ "$version" != "$VPS_AUDIT_EXPECTED" ]]; then
    rm -f "$tmp"
    say "${C_RED}✗ 服务器性能检测模块版本不匹配，已停止执行。${C_RESET}" >&2
    return 7
  fi

  build_id="$(NO_COLOR=1 bash "$tmp" --build-id 2>/dev/null || true)"
  if [[ "$build_id" != "$VPS_AUDIT_BUILD_EXPECTED" ]]; then
    rm -f "$tmp"
    say "${C_RED}✗ 服务器性能检测模块构建身份不匹配，已停止执行。${C_RESET}" >&2
    return 8
  fi

  set +e
  bash "$tmp"
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

local_server_ops_version() {
  command -v vfops >/dev/null 2>&1 || return 1
  NO_COLOR=1 vfops --version 2>/dev/null || true
}

local_server_ops_build() {
  command -v vfops >/dev/null 2>&1 || return 1
  local entry root value
  entry="$(readlink -f "$(command -v vfops)" 2>/dev/null || true)"
  case "$entry" in
    */bin/vfops-user) root="${entry%/bin/vfops-user}" ;;
    */bin/vfops) root="${entry%/bin/vfops}" ;;
    *) return 1 ;;
  esac
  [[ -f "$root/BUILD_ID" ]] || return 1
  IFS= read -r value < "$root/BUILD_ID" || return 1
  printf '%s' "$value"
}

ensure_server_ops_current() {
  if [[ "$(local_server_ops_version || true)" == "$VF_SERVER_OPS_EXPECTED" && \
        "$(local_server_ops_build || true)" == "$VF_SERVER_OPS_BUILD_EXPECTED" ]]; then
    return 0
  fi

  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }
  local tmp rc
  tmp="$(mktemp -t p07-server-ops.XXXXXX)"
  chmod 700 "$tmp"
  if ! curl -fsSL "$VF_SERVER_OPS_INSTALLER" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 网站与数据模块入口下载失败。${C_RESET}" >&2
    return 4
  fi
  if ! bash -n "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 网站与数据模块入口校验失败。${C_RESET}" >&2
    return 5
  fi

  set +e
  P07_TOOLBOX_PARENT=1 P07_NO_EXEC=1 bash "$tmp"
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

server_ops_root() {
  local entry
  entry="$(readlink -f "$(command -v vfops)" 2>/dev/null || true)"
  case "$entry" in
    */bin/vfops-user) printf '%s' "${entry%/bin/vfops-user}" ;;
    */bin/vfops) printf '%s' "${entry%/bin/vfops}" ;;
    *) return 1 ;;
  esac
}

# Same public Toolbox URL; release115 remains stable, release124 is an explicit safe-diagnostic trial.
# The release124 OWNER trial installs in a separate root-only slot. Never auto-migrate.
P07_OWNER124_SHA256="fd39e3dabb9a3ad32e39622206edd01f942f30ba4f40cdc86e9ea0d7aab8aa8d"
P07_OWNER124_URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/assets/727279744"
P07_OWNER124_BOOTSTRAP="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/1a2ecbd84210bcc81c1722c9a781e368cae916e7/installers/p07-owner-test124.sh"
P07_OWNER124_BOOTSTRAP_BLOB="258f64f8b6e2700b9bad514749e2b26bdae32239"

run_server_ops_owner124_trial() {
  if [[ "$(id -u)" != 0 ]]; then
    say "✗ 请在新服务器以 root 运行试用版。"
    return 13
  fi
  if command -v vfops-rc124 >/dev/null 2>&1 && \
     [[ "$(NO_COLOR=1 vfops-rc124 --build-id 2>/dev/null || true)" == "0.1.0-release124" ]]; then
    say "已安装 release124 试用版，直接进入。"
    vfops-rc124
    return $?
  fi
  if [[ "$(local_server_ops_build || true)" != "0.1.0-release115" ]] || \
     [[ ! -f /opt/vf-server-ops/BUILD_ID ]] || \
     [[ "$(cat /opt/vf-server-ops/BUILD_ID)" != "0.1.0-release115" ]]; then
    say "正式版 release115 未核实；请先选正式版，不自动覆盖现有安装。"
    return 13
  fi
  local cmd tmp rc
  for cmd in curl python3 sha256sum; do
    command -v "$cmd" >/dev/null 2>&1 || {
      say "✗ 缺少试用安装依赖：$cmd。未修改现有版本。"
      return 13
    }
  done
  tmp="$(mktemp -t p07-owner124-entry.XXXXXXXX)" || return 13
  chmod 700 "$tmp"
  if ! curl -fsSL --proto '=https' --proto-redir '=https' \
       --connect-timeout 15 --max-time 90 "$P07_OWNER124_BOOTSTRAP" -o "$tmp"; then
    rm -f -- "$tmp"
    say "✗ 试用版入口下载失败，正式版保持不变。"
    return 13
  fi
  if ! python3 -B - "$tmp" "$P07_OWNER124_BOOTSTRAP_BLOB" <<'PY'
import hashlib,sys
data=open(sys.argv[1],"rb").read()
value=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
if value!=sys.argv[2]:
    raise SystemExit(13)
PY
  then
    rm -f -- "$tmp"
    say "✗ 试用入口完整性校验失败，已停止。"
    return 13
  fi
  say "安装 release124 独立试用版；保留 release115，不自动迁移或修改 DNS。"
  P07_TRIAL_URL="$P07_OWNER124_URL" P07_TRIAL_SHA256="$P07_OWNER124_SHA256" \
    bash "$tmp"
  rc=$?
  rm -f -- "$tmp"
  if [[ "$rc" != 0 ]]; then
    say "✗ 试用安装未完成；正式版未被替换。"
    return "$rc"
  fi
  [[ "$(NO_COLOR=1 vfops-rc124 --build-id 2>/dev/null || true)" == "0.1.0-release124" ]] || return 13
  vfops-rc124
}

# Nonformal release143 owner-trial: deliberately published installable runtime.
# Exact candidate is bound to one source SHA and SHA-256. This does NOT
# promote vfops stable or authorize the original 18-site data migration.
P07_OWNER143_SHA256="018a29a407a30fe5e667cd42cb1b7e47f99b29df01003d9a7aeb7e4cc7ba1850"
P07_OWNER143_SOURCE_SHA="6a6f6e56b8c8195eb9f254cef019d5d395afa83c"
P07_OWNER143_URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/assets/736140731"

owner143_trial_installed() {
  local entry value
  [[ -f /opt/vf-server-ops-rc143/BUILD_ID &&
     ! -L /opt/vf-server-ops-rc143 &&
     -f /opt/vf-server-ops-rc143/.owner-trial-source &&
     ! -L /opt/vf-server-ops-rc143/.owner-trial-source ]] || return 1
  IFS= read -r value < /opt/vf-server-ops-rc143/.owner-trial-source || return 1
  [[ "$value" == "$P07_OWNER143_SOURCE_SHA" &&
     "$(cat /opt/vf-server-ops-rc143/BUILD_ID)" == "0.1.0-release143" ]] || return 1
  entry="$(readlink -f /usr/local/bin/vfops-rc143 2>/dev/null || true)"
  case "$entry" in
    /opt/vf-server-ops-rc143/bin/vfops|/opt/vf-server-ops-rc143/bin/vfops-user) ;;
    *) return 1 ;;
  esac
  [[ -x /usr/local/bin/vfops-rc143 ]] || return 1
  [[ "$(NO_COLOR=1 /usr/local/bin/vfops-rc143 --build-id 2>/dev/null || true)" == "0.1.0-release143" ]]
}

run_server_ops_owner143_trial() {
  if [[ "$(id -u)" != 0 ]]; then
    say "✗ 请在新服务器使用 root 运行 release143 试用版。"
    return 13
  fi
  if owner143_trial_installed; then
    say "已安装并核对 release143 当前试用版，直接进入。"
    /usr/local/bin/vfops-rc143
    return $?
  fi
  local cmd tmp inspect stable_before='' stable_after='' stable_link='' rc entry marker tmpmarker
  for cmd in curl sha256sum python3 bash readlink mktemp; do
    command -v "$cmd" >/dev/null 2>&1 || {
      say "✗ 缺少下载或校验所需系统命令：$cmd。未修改服务器。"
      return 13
    }
  done
  if [[ -f /opt/vf-server-ops/BUILD_ID ]]; then
    stable_before="$(sha256sum /opt/vf-server-ops/BUILD_ID | awk '{print $1}')"
  fi
  if [[ -e /usr/local/bin/vfops || -L /usr/local/bin/vfops ]]; then
    stable_link="$(readlink -f /usr/local/bin/vfops 2>/dev/null || true)"
  fi
  tmp="$(mktemp -t p07-owner143-entry.XXXXXXXX)" || return 13
  chmod 700 "$tmp"
  say "正在核验 release143 非正式试用候选；正式版和原迁移任务不会自动改动。"
  if ! curl -fsSL --proto '=https' --proto-redir '=https' \
        --connect-timeout 15 --max-time 180 --retry 2 \
        -H 'Accept: application/octet-stream' \
        "$P07_OWNER143_URL" -o "$tmp"; then
    rm -f -- "$tmp"
    say "✗ 最新试用包无法通过统一入口下载；没有使用旧版代替。"
    return 13
  fi
  if ! printf '%s  %s\n' "$P07_OWNER143_SHA256" "$tmp" |
      sha256sum -c --status; then
    rm -f -- "$tmp"
    say "✗ release143 包 SHA-256 不匹配；没有安装。"
    return 13
  fi
  if ! bash -n "$tmp"; then
    rm -f -- "$tmp"
    say "✗ release143 包 Shell 语法验证失败；没有安装。"
    return 13
  fi
  if ! inspect="$(bash "$tmp" --inspect)"; then
    rm -f -- "$tmp"
    say "✗ release143 包内部身份校验失败；没有安装。"
    return 13
  fi
  if ! printf '%s\n' "$inspect" | grep -Fxq "P07_TRIAL_SOURCE_SHA=$P07_OWNER143_SOURCE_SHA" ||
     ! printf '%s\n' "$inspect" | grep -Fxq 'P07_TRIAL_BUILD=0.1.0-release143' ||
     ! printf '%s\n' "$inspect" | grep -Fxq 'P07_TRIAL_PACKAGE_INTEGRITY=PASS' ||
     ! printf '%s\n' "$inspect" | grep -Fxq 'P07_TRIAL_VPS_WRITES=NONE'; then
    rm -f -- "$tmp"
    say "✗ 试用包版本、来源或只读检查不一致；没有安装。"
    return 13
  fi
  say "试用范围：安装与只读查看；不自动重导原四库、不停旧站、不切 DNS。"
  # The onefile installer independently asks for typed INSTALL in an
  # interactive terminal. Clear environment overrides before launching.
  set +e
  (
    unset P07_OWNER_TRIAL_TEST P07_ALLOW_NONROOT P07_INSTALL_DIR
    unset P07_PREVIOUS_DIR P07_BIN_LINK P07_PUBLIC_ROOT P07_NO_EXEC
    bash "$tmp" --install
  )
  rc=$?
  set -e
  rm -f -- "$tmp"
  if [[ "$rc" != 0 ]]; then
    say "✗ 非正式试用安装未完成；不会运行旧版本冒充成功。"
    return "$rc"
  fi
  if [[ ! -d /opt/vf-server-ops-rc143 ||
        -L /opt/vf-server-ops-rc143 ||
        ! -f /opt/vf-server-ops-rc143/BUILD_ID ||
        "$(cat /opt/vf-server-ops-rc143/BUILD_ID)" != "0.1.0-release143" ]]; then
    say "✗ 安装后 release143 目录或版本回读不正确。"
    return 13
  fi
  entry="$(readlink -f /usr/local/bin/vfops-rc143 2>/dev/null || true)"
  case "$entry" in
    /opt/vf-server-ops-rc143/bin/vfops|/opt/vf-server-ops-rc143/bin/vfops-user) ;;
    *) say "✗ 试用执行入口不属于独立安装目录。"; return 13 ;;
  esac
  if [[ "$(NO_COLOR=1 /usr/local/bin/vfops-rc143 --build-id 2>/dev/null || true)" != '0.1.0-release143' ]]; then
    say "✗ 独立执行文件构建回读失败。"
    return 13
  fi
  if [[ -n "$stable_before" ]]; then
    [[ -f /opt/vf-server-ops/BUILD_ID ]] || { say "✗ 正式版文件缺失，请停止。"; return 13; }
    stable_after="$(sha256sum /opt/vf-server-ops/BUILD_ID | awk '{print $1}')"
    [[ "$stable_after" == "$stable_before" ]] || { say "✗ 正式版版本文件发生变化，请停止。"; return 13; }
  fi
  if [[ -n "$stable_link" ]]; then
    [[ "$(readlink -f /usr/local/bin/vfops 2>/dev/null || true)" == "$stable_link" ]] ||
      { say "✗ 正式执行入口发生变化，请停止。"; return 13; }
  fi
  marker=/opt/vf-server-ops-rc143/.owner-trial-source
  [[ ! -L "$marker" ]] || { say "✗ 试用版来源标记路径不安全。"; return 13; }
  tmpmarker="$(mktemp -p /opt/vf-server-ops-rc143 .owner-trial-source.XXXXXXXX)" || return 13
  printf '%s\n' "$P07_OWNER143_SOURCE_SHA" > "$tmpmarker"
  chmod 600 "$tmpmarker"
  mv -f -- "$tmpmarker" "$marker"
  say "release143 已安装并核对；仅用于手工试用，正式版保持不变。"
  /usr/local/bin/vfops-rc143
}

run_server_ops() {
  screen_clear
  say "网站与数据"
  say "  1. 当前正式版 release115"
  say "  2. 历史试用 release124（原生只读分类）"
  say "  3. 最新试用 release143（原18站迁移；安装/只读验收）"
  say "  0. 返回"
  printf '请选择 [0-3]：'
  local selected
  read -r selected || return 0
  case "$selected" in
    1) ensure_server_ops_current || return $?; vfops ;;
    2) run_server_ops_owner124_trial ;;
    3) run_server_ops_owner143_trial ;;
    0) return 0 ;;
    *) say "请输入 0-3。"; return 0 ;;
  esac
}

ensure_system_care_current() {
  if [[ "$(local_system_care_version || true)" == "$SYSTEM_CARE_EXPECTED" ]]; then
    return 0
  fi

  command -v curl >/dev/null 2>&1 || { say "${C_RED}✗ 当前系统没有 curl。${C_RESET}" >&2; return 3; }
  local tmp rc
  tmp="$(mktemp -t p07-system-care.XXXXXX)"
  chmod 700 "$tmp"
  if ! curl -fsSL "$SYSTEM_CARE_INSTALLER" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 初始化所需的系统维护模块下载失败。${C_RESET}" >&2
    return 4
  fi
  if ! bash -n "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 初始化所需的系统维护模块校验失败。${C_RESET}" >&2
    return 5
  fi

  set +e
  P07_FORCE_INTERACTIVE=0 bash "$tmp" status >/dev/null 2>&1
  rc=$?
  set -e
  rm -f "$tmp"
  [[ $rc -eq 0 ]] || {
    say "${C_RED}✗ 初始化所需的系统维护模块准备失败。${C_RESET}" >&2
    return "$rc"
  }
  [[ "$(local_system_care_version || true)" == "$SYSTEM_CARE_EXPECTED" ]]
}

run_server_init() {
  screen_clear
  # Only P07-M05 新服务器初始化 may be called; nothing here installs,
  # upgrades, loads or restarts P07-M03 网站与数据 or P07-M04 系统维护与安全.
  if [[ ! -x "$M05_RUNTIME" ]]; then
    say "${C_YELLOW}P07-M05 新服务器初始化的独立安装包尚未正式分发。没有安装或升级其它模块。${C_RESET}"
    return 7
  fi

  local actual_version
  actual_version="$(NO_COLOR=1 bash "$M05_RUNTIME" --version 2>/dev/null || true)"
  if [[ "$actual_version" != "P07-M05 新服务器初始化 $M05_BUILD_EXPECTED" ]]; then
    say "${C_RED}P07-M05 新服务器初始化的独立构建身份不匹配，已停止；其它模块保持原样。${C_RESET}" >&2
    return 13
  fi

  bash "$M05_RUNTIME" menu
}

local_system_care_version() {
  command -v vf-system-care >/dev/null 2>&1 || return 1
  local version contract
  version="$(NO_COLOR=1 vf-system-care --version 2>/dev/null | awk '{print $NF}' || true)"
  contract="$(NO_COLOR=1 vf-system-care --ui-contract 2>/dev/null || true)"
  [[ "$contract" == 'P07_BEGINNER_ZH_V1' ]] || return 1
  printf '%s' "$version"
}

run_system_care() {
  screen_clear
  ensure_system_care_current || return $?
  vf-system-care menu
}

main_menu() {
  local choice rc
  while true; do
    show_menu
    printf '请选择 [0-5]：'
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
        [[ $rc -eq 0 ]] || say "${C_YELLOW}本次检测未完整结束（机器繁忙、超时或证据不足）；请稍后再试，没有修改服务器配置。${C_RESET}"
        pause_menu
        ;;
      3)
        set +e
        run_server_ops
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || { say "${C_YELLOW}⚠ 网站与数据模块返回退出码 ${rc}。${C_RESET}"; pause_menu; }
        ;;
      4)
        set +e
        run_system_care
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || { say "${C_YELLOW}⚠ 系统维护模块返回退出码 ${rc}。${C_RESET}"; pause_menu; }
        ;;
      5)
        set +e
        run_server_init
        rc=$?
        set -e
        [[ $rc -eq 0 ]] || { say "${C_YELLOW}⚠ 初始化服务器模块返回退出码 ${rc}。${C_RESET}"; pause_menu; }
        ;;
      0) return 0 ;;
      *) say "${C_YELLOW}⚠ 无效选择，请输入 0-5。${C_RESET}" ;;
    esac
  done
}

case "${1:-}" in
  --version|-V) printf '服务器工具箱 %s\n' "$VERSION" ;;
  --help|-h)
    cat <<EOF
服务器工具箱 ${VERSION}

用法：
  p07-toolbox

1. 网络代理节点          V2Ray代理   ${VF_NODE_PUBLIC}
2. 服务器性能检测        VPS验机     ${VPS_AUDIT_PUBLIC}
3. 网站与数据            网站/数据库/备份  ${VF_SERVER_OPS_PUBLIC}
4. 服务器维护与安全      更新/清理/安全    ${SYSTEM_CARE_PUBLIC}
5. 新服务器初始化        更新/面板/优化    ${VF_SERVER_OPS_PUBLIC}

说明：初始化服务器为独立脚本入口；普通界面只显示 Vx.x.x 公共版本。
EOF
    ;;
  "")
    if [[ -t 0 && -t 1 ]]; then main_menu; else printf '错误：服务器工具箱主菜单需要交互式终端。\n' >&2; exit 2; fi
    ;;
  *) printf '错误：未知参数：%s\n' "$1" >&2; exit 2 ;;
esac
