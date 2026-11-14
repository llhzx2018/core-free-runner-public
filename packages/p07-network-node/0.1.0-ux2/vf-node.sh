#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

show_header() {
  [[ -t 1 ]] && clear 2>/dev/null || true
  say "${C_BOLD}网络代理节点${C_RESET}  ${C_GRAY}${VF_NODE_VERSION}${C_RESET}"
  say "${C_GRAY}────────────────────────────────────────${C_RESET}"
}

show_live_summary() {
  load_state
  if [[ -r "$VF_NODE_STATE_FILE" ]]; then
    if node_healthy; then
      say "当前状态：${C_GREEN}运行正常${C_RESET}"
    else
      say "当前状态：${C_YELLOW}需要检查${C_RESET}"
    fi
    if [[ -n "${PORT:-}" ]]; then
      say "节点端口：${PORT}/UDP"
    fi
  elif v2ray_cli >/dev/null 2>&1; then
    say "当前状态：${C_YELLOW}检测到外部 V2Ray（不接管）${C_RESET}"
  else
    say "当前状态：未安装"
  fi
}

show_menu() {
  show_header
  show_live_summary
  say
  if [[ -r "$VF_NODE_STATE_FILE" ]]; then
    if node_healthy; then
      say "  1. 检查节点（当前正常）"
    else
      say "  1. 修复节点（可能重启服务）"
    fi
  elif v2ray_cli >/dev/null 2>&1; then
    say "  1. 查看外部节点（不接管）"
  else
    say "  1. 安装节点"
  fi
  say "  2. 查看节点状态"
  say "  3. 查看分享链接"
  if [[ -r "$VF_NODE_STATE_FILE" ]]; then
    say "  4. 卸载节点"
  else
    say "  4. 卸载节点（未安装）"
  fi
  say "  5. 查看原作者作品版本（只读）"
  say "  0. 返回工具箱"
  say
}

run_and_pause() {
  if ! "$@"; then
    warn '操作未完成，节点状态未被假报为成功。'
  fi
  pause_if_tty
}

mark_state_healthy() {
  [[ -s "$VF_NODE_STATE_FILE" ]] || return 0
  if grep -q '^INSTALL_STATUS=' "$VF_NODE_STATE_FILE"; then
    sed -i 's/^INSTALL_STATUS=.*/INSTALL_STATUS=HEALTHY/' "$VF_NODE_STATE_FILE"
  else
    printf 'INSTALL_STATUS=HEALTHY\n' >> "$VF_NODE_STATE_FILE"
  fi
  chmod 0600 "$VF_NODE_STATE_FILE"
}

repair_managed_install() {
  info "检测到节点未通过健康检查，正在自动修复..."
  if restart_managed_node 20; then
    mark_state_healthy
    ok "节点自动修复完成，服务与 UDP 已恢复"
    return 0
  fi
  fail "自动修复未成功。不会覆盖配置、UUID 或端口。"
  bash "$SCRIPT_DIR/status.sh" || true
  return 1
}

install_from_menu() {
  local answer=''
  if [[ -r "$VF_NODE_STATE_FILE" ]]; then
    if node_healthy; then
      ok '节点正在运行；无需重复安装。'
    else
      warn '节点异常；修复可能重启 V2Ray 服务，但不会覆盖节点配置。'
      printf '确认修复？[y/N]：'
      read -r answer || answer=''
      if [[ "$answer" =~ ^[Yy]$ ]]; then
        repair_managed_install || true
      else
        info '已取消；服务没有改变。'
      fi
    fi
    pause_if_tty
    return 0
  fi
  if v2ray_cli >/dev/null 2>&1; then
    warn '这是其他工具安装的 V2Ray，P07 不会覆盖或接管。'
    pause_if_tty
    return 0
  fi
  printf '将安装新的 V2Ray 节点，确认继续？[y/N]：'
  read -r answer || answer=''
  if [[ "$answer" =~ ^[Yy]$ ]]; then
    run_and_pause bash "$SCRIPT_DIR/install.sh"
  else
    info '已取消；没有安装节点。'
    pause_if_tty
  fi
}

# P07-M01 网络代理节点（V2Ray） · 原作者版本为独立只读入口。
# 原作者安装脚本与 V2Fly Core 是不同来源；查询永不运行最新远端代码。
node_original_version_query() {
  local project="$1" json='' url=''
  if ! command -v curl >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
    warn '无法查询官方更新：缺少 curl 或 Python3；没有安装任何组件。'
    return 0
  fi
  case "$project" in
    author)
      say '原安装脚本：xyz690/v2ray（作者仓库，没有确认的语义版本号）'
      say '原作者仓库：https://github.com/xyz690/v2ray'
      say 'P07 经过审核的原脚本提交：b73e9c35bb11（非最新版本）'
      url='https://api.github.com/repos/xyz690/v2ray/commits?per_page=1'
      ;;
    core)
      say '官方核心项目：https://github.com/v2fly/v2ray-core/releases'
      say 'P07 当前固定审核的 Core：v5.53.0（不是自动跟随最新）'
      url='https://api.github.com/repos/v2fly/v2ray-core/releases?per_page=12'
      ;;
    *) return 2 ;;
  esac
  if ! json="$(curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 5 --max-time 12 \
    -H 'Accept: application/vnd.github+json' "$url" 2>/dev/null)"; then
    warn '当前无法读取 GitHub 官方版本；以上原作者链接可手工查看。'
    return 0
  fi
  if [[ "$project" == 'author' ]]; then
    if ! printf '%s' "$json" | python3 -c 'import json,re,sys; d=json.load(sys.stdin); s=d[0].get("sha","") if isinstance(d,list) and d else ""; print(("原作者仓库最近提交："+s[:12]+"（仅提交号，非发行版）") if re.fullmatch("[0-9a-f]{40}",s) else "原作者当前无可核实的发行版本")'; then
      warn '原作者版本格式异常，已忽略；节点保持原样。'
    fi
  else
    if ! printf '%s' "$json" | python3 -c 'import json,re,sys; d=json.load(sys.stdin); v=[(x.get("tag_name",""),bool(x.get("prerelease"))) for x in d if isinstance(x,dict) and re.fullmatch(r"v[0-9]+(?:\.[0-9]+){2}",x.get("tag_name",""))] if isinstance(d,list) else []; stable=next((s for s,p in v if not p),None); latest=v[0] if v else None; print("最新公开发布："+latest[0]+("（预发布）" if latest[1] else "（正式）") if latest else "当前无法核实官方发布版本"); print("最新正式版本："+stable if stable else "没有找到已核实的正式版本")'; then
      warn 'V2Ray Core 官方版本格式异常，已忽略；节点保持原样。'
    fi
  fi
  say '本页只读，不执行原脚本，不下载升级，也不改节点配置。'
}

node_original_version_menu() {
  local selection=''
  while true; do
    say
    say '原作者作品版本（不是 P07 管理器版本）'
    say '  1. xyz690 原安装脚本 · 最新提交'
    say '  2. V2Fly V2Ray Core · 正式/预发布版本'
    say '  0. 返回网络代理节点'
    printf '请选择 [0-2]：'
    read -r selection || return 0
    case "$selection" in
      1) node_original_version_query author ;;
      2) node_original_version_query core ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0、1 或 2。' ;;
    esac
  done
}

menu_loop() {
  while true; do
    show_menu
    printf '%b' "${C_BOLD}请选择 [0-5]：${C_RESET}"
    read -r choice || return 0
    case "$choice" in
      1) install_from_menu ;;
      2) run_and_pause bash "$SCRIPT_DIR/status.sh" ;;
      3) run_and_pause bash "$SCRIPT_DIR/share.sh" ;;
      4) run_and_pause bash "$SCRIPT_DIR/uninstall.sh" ;;
      5) node_original_version_menu ;;
      0) return 0 ;;
      *) warn '无效选择，请输入 0-5。' ;;
    esac
  done
}

usage() {
  cat <<EOF
网络代理节点 ${VF_NODE_VERSION}

用法：
  vf-node                    进入彩色菜单
  vf-node --version          显示模块版本
  vf-node originals author   查看原作者安装脚本提交（只读）
  vf-node originals core     查看 V2Fly 官方 Core 版本（只读）
  vf-node install [args]     安装稳定节点
  vf-node status             查看节点状态
  vf-node check              静默健康检查
  vf-node url                仅健康时显示分享链接
  vf-node share              同 url
  vf-node uninstall          数字菜单确认后卸载

兼容：
  v2ray url                  保留原脚本兼容命令
EOF
}

case "${1:-}" in
  --version|version)
    printf 'VF Network Node %s\n' "$VF_NODE_VERSION"
    ;;
  install)
    shift
    if [[ -r "$VF_NODE_STATE_FILE" ]]; then
      if node_healthy; then
        warn "节点已经安装并运行正常，无需重装。"
        exit 0
      fi
      repair_managed_install
      exit $?
    fi
    exec bash "$SCRIPT_DIR/install.sh" "$@"
    ;;
  originals)
    case "${2:-}" in
      author|core) node_original_version_query "$2" ;;
      *) say '请输入 originals author 或 originals core。'; exit 2 ;;
    esac
    ;;
  status)
    exec bash "$SCRIPT_DIR/status.sh"
    ;;
  check)
    exec bash "$SCRIPT_DIR/status.sh" --quiet
    ;;
  url|share)
    exec bash "$SCRIPT_DIR/share.sh"
    ;;
  uninstall)
    exec bash "$SCRIPT_DIR/uninstall.sh"
    ;;
  -h|--help|help)
    usage
    ;;
  '')
    if [[ -t 0 ]]; then
      menu_loop
    else
      usage
    fi
    ;;
  *)
    fail "未知命令：$1"
    usage
    exit 2
    ;;
esac
