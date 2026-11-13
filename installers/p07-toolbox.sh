#!/usr/bin/env bash
set -Eeuo pipefail

# P07 V0.1.0 final public distribution readback marker.
# 公共版本保持简短稳定；内部构建身份仅用于精确校验和工程追溯。
VERSION="V0.1.0"
BUILD_ID="0.1.0-preview16"

VF_NODE_PUBLIC="V0.1.0"
VF_NODE_EXPECTED="0.1.0-rc13"
# Legacy M01 installer URL is retained for text/older regression compatibility,
# but is NEVER executed by this independently upgradable Toolbox route.
VF_NODE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/vf-node.sh"
M01_ROOT="/opt/vfops-modules/m01"
M01_RUNTIME="$M01_ROOT/current/vf-node.sh"
M01_INSTALLER_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/adf4d8cc0db69255fb4a6aff58857561a0652bf6/installers/p07-vf-node-independent-rc13.sh"
M01_INSTALLER_BLOB="8313adef7dd235b645fc815a7bded933fc289f82"
M01_MANIFEST_SHA256="1ca3dc95a5cc6e5aa35c9b7ead415d3b6ea6c6eb9e8307a76310d146ab53c47f"


VPS_AUDIT_PUBLIC="V2.1.0"
VPS_AUDIT_EXPECTED="V2.1.0"
VPS_AUDIT_BUILD_EXPECTED="2.1.0-rc7-field"
VPS_AUDIT_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/0a851b9fe1819c7970ed5bb8e3633f2fc8e73166/experiments/p07-vps-audit-v21.sh"
VPS_AUDIT_SHA256="d1846e751bba5c860c623e3db26641908e27ca43b39cf37016758853b65a952d"
M02_ROOT="/opt/vfops-modules/m02"  # 独立 VPS 验机版本；不写入 M01/M03/M04/M05

VF_SERVER_OPS_PUBLIC="V0.1.0"
VF_SERVER_OPS_EXPECTED="VF Server Ops 0.1.0"
VF_SERVER_OPS_BUILD_EXPECTED="0.1.0-release115"
VF_SERVER_OPS_INSTALLER_REF="1986fc0526f583a3a152d92980e21519926bc926"
VF_SERVER_OPS_INSTALLER_BLOB="c49b26eb900960eeaf3992eaa95f3d3a9a4feb31"
# Exact stable P07-M03 runtime manifest; reject a self-edited manifest before execution.
VF_SERVER_OPS_MANIFEST_BLOB="4acbaca22aac0da681b34376e2cc86d876593181"
VF_SERVER_OPS_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/${VF_SERVER_OPS_INSTALLER_REF}/installers/p07.sh"
M03_ROLLBACK_INSTALLER_REF="70836f5bba98e8d4ff32ccb6541b4ca1ffc80912"
M03_ROLLBACK_INSTALLER_BLOB="9571833c4e8a1d737ee47a60e946a030d94c8157"
M03_ROLLBACK_INSTALLER_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/${M03_ROLLBACK_INSTALLER_REF}/installers/p07-m03-restore-previous.sh"


SYSTEM_CARE_PUBLIC="V0.1.0"
SYSTEM_CARE_EXPECTED="0.1.0-rc82"
SYSTEM_CARE_INSTALLER="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/main/installers/p07-system-care.sh"
# P07-M04 服务器维护与安全 independent rc83 candidate, exact immutable source.
M04_BUILD_EXPECTED="0.1.0-rc83"
M04_INSTALLER_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/75c7336b8467114f8bc3396dc06144e48275a39a/installers/p07-system-care-rc83-isolated.sh"
M04_INSTALLER_BLOB="d39cef5d0915a99753d688f10fb1dbe74c0dac98"
M04_UI_BLOB="f140f1158351f9dce2e9f9159611af57047424b1"
M04_ROOT="/opt/vfops-modules/m04"
M04_RUNTIME="$M04_ROOT/current/vf-system-care.sh"


# P07-M05 新服务器初始化 has its OWN runtime/build and no M03/M04 installer calls.
# The isolated M05 artifact is not publicly distributed yet: do not invent a
# download URL or silently fall back to the legacy M03+M04 installers.
# Matches the private, exact-source M05 candidate; not a public distribution pin.
M05_BUILD_EXPECTED="0.1.0-m05-candidate2"
M05_ROOT="/opt/vfops-modules/m05"
M05_RUNTIME="$M05_ROOT/current/bin/vfops-init-entry"
# M05 official artifact has not been published. Never invent a URL or
# install M03/M04 in its place; only fill these pins after approved distribution.
M05_BUNDLE_URL=""
M05_BUNDLE_SHA256=""
# Immutable private Owner Trial .run identity, never a public download source.
M05_OFFLINE_TRIAL_SHA256="e42b6b3c59719f6ec189e4c62b7cfc54385aaa6e566c8f92ca5306246f022bbb"
M05_INSTALLER_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/35e3fbcb1e8c40042558f9f163e4215570074793/installers/p07-m05-atomic.py"
M05_INSTALLER_BLOB="17e47121ac27f31162d93a72aa0b1dbea602ea01"

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
  say "  ${C_GREEN}5.${C_RESET} 新服务器初始化      ${C_GRAY}系统更新/CloudPanel/数据库选择${C_RESET}"
  say "  ${C_GRAY}0.${C_RESET} 退出"
  say
  say "${C_GRAY}版本信息进入对应功能后查看；主菜单只保留常用操作。${C_RESET}"
}

m01_verified_current() {
  local current="$M01_ROOT/current" root="$M01_ROOT/current" name expected count=0 version='' installed=''
  [[ -L "$current" ]] || return 1
  local link
  link="$(readlink "$current")"
  [[ "$link" =~ ^releases/([A-Za-z0-9._-]+)$ ]] || return 1
  installed="${BASH_REMATCH[1]}"
  [[ -f "$root/MANIFEST.sha256" && ! -L "$root/MANIFEST.sha256" &&
     -f "$root/VERSION" && ! -L "$root/VERSION" ]] || return 1
  [[ "$(cat "$root/VERSION")" == "$installed" ]] || return 1
  # Bootstrap rc13 is checked against the original public SHA pin.
  # A newer release may carry its OWN verified manifest and version identity.
  if [[ "$installed" == "$VF_NODE_EXPECTED" ]]; then
    [[ "$(sha256_file "$root/MANIFEST.sha256" 2>/dev/null || true)" == "$M01_MANIFEST_SHA256" ]] || return 1
  fi
  declare -A seen=()
  while read -r expected name; do
    [[ -n "$expected" && -n "$name" ]] || continue
    [[ "$expected" =~ ^[a-f0-9]{64}$ ]] || return 1
    [[ "$name" =~ ^(lib/)?[A-Za-z0-9._-]+$ && "$name" != '.' && "$name" != '..' ]] || return 1
    [[ ! -v seen[$name] ]] || return 1
    seen[$name]=1
    [[ -f "$root/$name" && ! -L "$root/$name" ]] || return 1
    [[ "$(sha256_file "$root/$name" 2>/dev/null || true)" == "$expected" ]] || return 1
    count=$((count + 1))
  done < "$root/MANIFEST.sha256"
  [[ "$count" -eq 10 ]] || return 1
  version="$(NO_COLOR=1 bash "$M01_RUNTIME" --version 2>/dev/null | awk '{print $NF}' || true)"
  [[ "$version" == "$installed" ]]
}

ensure_m01_current() {
  m01_verified_current && return 0
  if [[ -e "$M01_ROOT/current" || -L "$M01_ROOT/current" ]]; then
    say "${C_RED}P07-M01 网络代理节点（V2Ray）：已安装模块身份异常；拒绝用旧版回退或覆盖，请从本模块更新器修复。${C_RESET}" >&2
    return 13
  fi
  if [[ "$(id -u)" != "0" ]]; then
    say "${C_RED}P07-M01 网络代理节点（V2Ray）：独立管理器首次安装/升级需要 root。${C_RESET}" >&2
    return 3
  fi
  for tool in curl sha1sum sha256sum mktemp; do
    command -v "$tool" >/dev/null 2>&1 || {
      say "${C_RED}P07-M01 网络代理节点（V2Ray）：缺少 $tool，其他模块保持不变。${C_RESET}" >&2
      return 3
    }
  done
  local tmp actual rc
  tmp="$(mktemp -t p07-m01-module-installer.XXXXXXXX)" || return 13
  chmod 0600 "$tmp"
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 60 "$M01_INSTALLER_URL" -o "$tmp"; then
    rm -f "$tmp"
    return 4
  fi
  actual="$(p07_git_blob_sha1 "$tmp" 2>/dev/null || true)"
  if [[ "$actual" != "$M01_INSTALLER_BLOB" ]]; then
    rm -f "$tmp"
    say "${C_RED}P07-M01 网络代理节点（V2Ray）：管理器安装文件身份不匹配。${C_RESET}" >&2
    return 6
  fi
  set +e
  bash "$tmp" install
  rc=$?
  set -e
  rm -f "$tmp"
  [[ "$rc" == 0 ]] || return "$rc"
  m01_verified_current || return 13
}

run_network_node() {
  screen_clear
  ensure_m01_current || return $?
  # Explicitly open ONLY the manager menu: never run implicit non-TTY install.
  bash "$M01_RUNTIME"
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

m02_verified_current() {
  local current="$M02_ROOT/current" script="$M02_ROOT/current/vps-audit.sh"
  local installed='' link actual version build
  [[ -L "$current" ]] || return 1
  link="$(readlink "$current")"
  [[ "$link" =~ ^releases/([A-Za-z0-9._-]+)$ ]] || return 1
  installed="${BASH_REMATCH[1]}"
  [[ -f "$script" && ! -L "$script" ]] || return 1
  actual="$(sha256_file "$script" 2>/dev/null || true)"
  [[ "$actual" =~ ^[a-f0-9]{64}$ ]] || return 1
  if [[ -f "$current/MANIFEST.sha256" && ! -L "$current/MANIFEST.sha256" ]]; then
    local expected name
    read -r expected name < "$current/MANIFEST.sha256" || return 1
    [[ "$name" == "vps-audit.sh" && "$expected" == "$actual" ]] || return 1
    [[ "$(wc -l < "$current/MANIFEST.sha256")" -eq 1 ]] || return 1
  else
    # Legacy first-install candidate had no local manifest.
    [[ "$installed" == "$VPS_AUDIT_BUILD_EXPECTED" &&
       "$actual" == "$VPS_AUDIT_SHA256" ]] || return 1
  fi
  version="$(NO_COLOR=1 bash "$script" --version 2>/dev/null | awk '{print $NF}' || true)"
  build="$(NO_COLOR=1 bash "$script" --build-id 2>/dev/null || true)"
  [[ -n "$version" && "$version" =~ ^V[0-9]+\.[0-9]+\.[0-9]+$ &&
     "$build" == "$installed" ]]
}

ensure_m02_current() {
  if m02_verified_current; then return 0; fi
  if [[ -e "$M02_ROOT/current" || -L "$M02_ROOT/current" ]]; then
    say "${C_RED}P07-M02 服务器性能检测（VPS 验机）：现有版本或文件校验异常；拒绝自动回退。${C_RESET}" >&2
    return 13
  fi
  if [[ "$(id -u)" != "0" ]]; then
    say "${C_RED}P07-M02 服务器性能检测：独立模块首次安装或升级需要 root；未修改其他模块。${C_RESET}" >&2
    return 3
  fi
  for cmd in curl flock sha256sum mktemp; do
    command -v "$cmd" >/dev/null 2>&1 || {
      say "${C_RED}P07-M02 服务器性能检测：缺少命令 $cmd；没有安装其他模块。${C_RESET}" >&2
      return 3
    }
  done
  [[ ! -L /opt/vfops-modules && ! -L "$M02_ROOT" ]] || return 13
  mkdir -p "$M02_ROOT/releases" || return 13
  local fd current dest tmp stage link version build actual
  exec {fd}>"$M02_ROOT/.install.lock" || return 13
  flock -x "$fd" || return 13
  if m02_verified_current; then return 0; fi
  current="$M02_ROOT/current"
  dest="$M02_ROOT/releases/$VPS_AUDIT_BUILD_EXPECTED"
  if [[ -e "$current" || -L "$current" ]]; then
    [[ -L "$current" ]] || return 13
    [[ "$(readlink "$current")" =~ ^releases/[A-Za-z0-9._-]+$ ]] || return 13
  fi
  # Existing immutable release with wrong bytes must never be overwritten
  # or 'repaired' by a different module's installer.
  if [[ -e "$dest" || -L "$dest" ]]; then
    say "${C_RED}P07-M02 服务器性能检测：已有候选身份未通过校验，已保护原文件。${C_RESET}" >&2
    return 13
  fi
  tmp="$(mktemp -t p07-m02-download.XXXXXXXX)" || return 13
  chmod 0600 "$tmp"
  if ! curl -fsSL --proto '=https' --tlsv1.2 --max-time 90 "$VPS_AUDIT_URL" -o "$tmp"; then
    rm -f "$tmp"; return 4
  fi
  actual="$(sha256_file "$tmp" 2>/dev/null || true)"
  if [[ "$actual" != "$VPS_AUDIT_SHA256" ]]; then
    rm -f "$tmp"; return 6
  fi
  version="$(NO_COLOR=1 bash "$tmp" --version 2>/dev/null | awk '{print $NF}' || true)"
  build="$(NO_COLOR=1 bash "$tmp" --build-id 2>/dev/null || true)"
  if [[ "$version" != "$VPS_AUDIT_EXPECTED" || "$build" != "$VPS_AUDIT_BUILD_EXPECTED" ]]; then
    rm -f "$tmp"; return 7
  fi
  stage="$M02_ROOT/releases/.stage-$$"
  link="$M02_ROOT/.current-$$"
  [[ ! -e "$stage" && ! -L "$stage" && ! -e "$link" && ! -L "$link" ]] || { rm -f "$tmp"; return 13; }
  mkdir -m 0755 "$stage" || { rm -f "$tmp"; return 13; }
  if ! install -m 0755 -- "$tmp" "$stage/vps-audit.sh"; then
    rm -f "$tmp"; rm -rf -- "$stage"; return 13
  fi
  printf '%s  vps-audit.sh\n' "$actual" > "$stage/MANIFEST.sha256" || { rm -f "$tmp"; rm -rf -- "$stage"; return 13; }
  chmod 0644 "$stage/MANIFEST.sha256"
  rm -f "$tmp"
  if ! mv -T -- "$stage" "$dest"; then rm -rf -- "$stage"; return 13; fi
  ln -s "releases/$VPS_AUDIT_BUILD_EXPECTED" "$link" || return 13
  mv -Tf -- "$link" "$current" || return 13
  if ! m02_verified_current; then
    say "${C_RED}P07-M02 服务器性能检测：本模块原子升级后回读失败。${C_RESET}" >&2
    return 13
  fi
  say "${C_GREEN}P07-M02 服务器性能检测：独立版本已就绪。${C_RESET}"
}

rollback_m02_current() {
  # P07-M02 服务器性能检测（VPS 验机）: revert ONLY its current pointer.
  # A valid newer M02 build can roll back to any retained verified M02 build.
  local build="${1:-}" confirm="${2:-}" current old target actual version reported fd link
  local staged_back=""
  [[ "$(id -u)" == "0" &&
     "$build" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ &&
     "$confirm" == "P07-M02:$build" ]] || return 13
  for cmd in flock sha256sum readlink; do command -v "$cmd" >/dev/null 2>&1 || return 13; done
  [[ -d /opt/vfops-modules && ! -L /opt/vfops-modules &&
     -d "$M02_ROOT" && ! -L "$M02_ROOT" &&
     -d "$M02_ROOT/releases" && ! -L "$M02_ROOT/releases" &&
     ! -L "$M02_ROOT/.install.lock" ]] || return 13
  exec {fd}>"$M02_ROOT/.install.lock" || return 13
  flock -x "$fd" || return 13
  # A failed M02 upgrade may leave a damaged active build; allow an explicit
  # rollback to a VERIFIED retained M02 version, but never follow foreign links.
  current="$M02_ROOT/current"
  [[ -L "$current" ]] || return 13
  old="$(readlink "$current")"
  [[ "$old" =~ ^releases/[A-Za-z0-9._-]+$ &&
     -d "$M02_ROOT/$old" && ! -L "$M02_ROOT/$old" ]] || return 13
  target="$M02_ROOT/releases/$build"
  [[ -d "$target" && ! -L "$target" &&
     -f "$target/MANIFEST.sha256" && ! -L "$target/MANIFEST.sha256" &&
     -f "$target/vps-audit.sh" && ! -L "$target/vps-audit.sh" ]] || return 13
  local manifest_line line_count
  manifest_line="$(cat "$target/MANIFEST.sha256")" || return 13
  line_count="$(wc -l < "$target/MANIFEST.sha256")" || return 13
  [[ "$line_count" == 1 ]] || return 13
  actual="$(sha256_file "$target/vps-audit.sh" 2>/dev/null || true)"
  [[ "$actual" =~ ^[a-f0-9]{64}$ &&
     "$manifest_line" == "$actual  vps-audit.sh" ]] || return 13
  version="$(NO_COLOR=1 bash "$target/vps-audit.sh" --version 2>/dev/null | awk '{print $NF}' || true)"
  reported="$(NO_COLOR=1 bash "$target/vps-audit.sh" --build-id 2>/dev/null || true)"
  [[ "$version" =~ ^V[0-9]+\.[0-9]+\.[0-9]+$ &&
     "$reported" == "$build" ]] || return 13
  if [[ "$build" == "$VPS_AUDIT_BUILD_EXPECTED" ]]; then
    [[ "$actual" == "$VPS_AUDIT_SHA256" &&
       "$version" == "$VPS_AUDIT_EXPECTED" ]] || return 13
  fi
  if [[ "$old" != "releases/$build" ]]; then
    link="$M02_ROOT/.current-rollback-$$"
    [[ ! -e "$link" && ! -L "$link" ]] || return 13
    ln -s "releases/$build" "$link" || return 13
    mv -Tf -- "$link" "$current" || { rm -f -- "$link"; return 13; }
    if ! m02_verified_current; then
      # The original verified release remains on disk. Restore only m02/current.
      staged_back="$M02_ROOT/.current-recovery-$$"
      if [[ ! -e "$staged_back" && ! -L "$staged_back" ]]; then
        ln -s "$old" "$staged_back" &&
          mv -Tf -- "$staged_back" "$current" || true
      fi
      rm -f -- "$staged_back" 2>/dev/null || true
      return 13
    fi
  fi
  say "P07-M02 服务器性能检测（VPS 验机）：已恢复本模块 $build；其他模块未操作。"
}
run_vps_audit() {
  screen_clear
  say "${C_CYAN}正在启动 P07-M02 服务器性能检测 ${VPS_AUDIT_PUBLIC}…${C_RESET}"
  ensure_m02_current || return $?
  # Only the explicit M02 executable runs; no M01/M03/M04/M05 install path.
  bash "$M02_ROOT/current/vps-audit.sh"
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

m03_verified_current() {
  local root='/opt/vf-server-ops' entry entry_rel expected name actual count=0
  [[ -d "$root" && ! -L "$root" ]] || return 1
  command -v vfops >/dev/null 2>&1 || return 1
  entry="$(readlink -f "$(command -v vfops)" 2>/dev/null || true)"
  case "$entry" in
    /opt/vf-server-ops/bin/vfops|/opt/vf-server-ops/bin/vfops-user) ;;
    *) return 1 ;;
  esac
  [[ -f "$root/BUILD_ID" && ! -L "$root/BUILD_ID" &&
     -f "$root/.runtime-manifest.gitblob" &&
     ! -L "$root/.runtime-manifest.gitblob" ]] || return 1
  local installed
  installed="$(cat "$root/BUILD_ID")"
  # This menu selects the pinned public stable M03, never an older trial
  # or a different future build masquerading as release115.
  [[ "$installed" == "$VF_SERVER_OPS_BUILD_EXPECTED" ]] || return 1
  # A mutable manifest checking mutable files against itself is NOT trusted.
  # Verify the immutably published manifest before parsing or executing M03.
  [[ "$(p07_git_blob_sha1 "$root/.runtime-manifest.gitblob" 2>/dev/null || true)" == "$VF_SERVER_OPS_MANIFEST_BLOB" ]] || return 1
  declare -A seen=()
  while read -r expected name; do
    [[ -n "$expected" && -n "$name" ]] || continue
    [[ "$expected" =~ ^[a-f0-9]{40}$ ]] || return 1
    [[ "$name" =~ ^(bin|lib)/[A-Za-z0-9_./-]+$ || "$name" == BUILD_ID ]] || return 1
    [[ "$name" != /* && "$name" != *../* && "$name" != */.. && "$name" != '..' ]] || return 1
    [[ ! -v seen[$name] ]] || return 1
    seen[$name]=1
    [[ -f "$root/$name" && ! -L "$root/$name" ]] || return 1
    actual="$(p07_git_blob_sha1 "$root/$name" 2>/dev/null || true)"
    [[ "$actual" == "$expected" ]] || return 1
    count=$((count + 1))
    [[ "$count" -le 240 ]] || return 1
  done < "$root/.runtime-manifest.gitblob"
  [[ "$count" -ge 50 ]] || return 1
  # The CLI that will execute must itself be in the verified manifest.
  entry_rel="${entry#/opt/vf-server-ops/}"
  [[ -v seen[$entry_rel] ]] || return 1
  # Only after the pinned manifest and runtime tree pass may root execute
  # even harmless-looking --build-id/--version calls from the installed tree.
  [[ "$(NO_COLOR=1 vfops --build-id 2>/dev/null || true)" == "$installed" ]] || return 1
  [[ "$(NO_COLOR=1 vfops --version 2>/dev/null || true)" == "$VF_SERVER_OPS_EXPECTED" ]]
}

ensure_server_ops_current() {
  if m03_verified_current; then
    return 0
  fi
  if [[ -e /opt/vf-server-ops || -L /opt/vf-server-ops ]]; then
    say "${C_RED}P07-M03 网站与数据：现有模块的独立版本或完整性无法确认，已停止；拒绝降级覆盖。${C_RESET}" >&2
    return 13
  fi

  for cmd in curl sha1sum mktemp; do
    command -v "$cmd" >/dev/null 2>&1 || {
      say "${C_RED}P07-M03 网站与数据：缺少 $cmd；未执行安装。${C_RESET}" >&2
      return 3
    }
  done
  local tmp rc
  tmp="$(mktemp -t p07-server-ops.XXXXXX)"
  chmod 700 "$tmp"
  if ! curl -fsSL "$VF_SERVER_OPS_INSTALLER" -o "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 网站与数据模块入口下载失败。${C_RESET}" >&2
    return 4
  fi
  # Fetch one immutable M03-only source. Never run the mutable main branch
  # installer, even though its nested runtime blobs are checked separately.
  if [[ "$(p07_git_blob_sha1 "$tmp" 2>/dev/null || true)" != "$VF_SERVER_OPS_INSTALLER_BLOB" ]]; then
    rm -f "$tmp"
    say "${C_RED}P07-M03 网站与数据：安装器身份不匹配，已停止；其他模块未操作。${C_RESET}" >&2
    return 6
  fi
  if ! bash -n "$tmp"; then
    rm -f "$tmp"
    say "${C_RED}✗ 网站与数据模块入口语法异常。${C_RESET}" >&2
    return 5
  fi

  set +e
  P07_TOOLBOX_PARENT=1 P07_NO_EXEC=1 bash "$tmp"
  rc=$?
  set -e
  rm -f "$tmp"
  return "$rc"
}

rollback_m03_previous() {
  # P07-M03 网站与数据: independent runtime restore, NOT site backup restore.
  # All site migration, data restoration, CloudPanel and DNS functions remain off.
  local build="${1:-}" confirmation="${2:-}" tmp actual rc
  [[ "$(id -u)" == 0 &&
     "$build" =~ ^0[.]1[.]0-release[0-9]+$ &&
     "$confirmation" == "P07-M03:$build" ]] || return 13
  for cmd in curl sha1sum mktemp; do command -v "$cmd" >/dev/null 2>&1 || return 13; done
  tmp="$(mktemp -t p07-m03-module-rollback.XXXXXXXX)" || return 13
  chmod 0600 "$tmp"
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 60 "$M03_ROLLBACK_INSTALLER_URL" -o "$tmp"; then
    rm -f "$tmp"; return 4
  fi
  actual="$(p07_git_blob_sha1 "$tmp" 2>/dev/null || true)"
  if [[ "$actual" != "$M03_ROLLBACK_INSTALLER_BLOB" ]]; then
    rm -f "$tmp"; return 6
  fi
  set +e
  bash "$tmp" restore-previous "$build" "$confirmation"
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


m05_verified_current() {
  local current="$M05_ROOT/current" installed='' link actual_version
  [[ -L "$current" ]] || return 1
  link="$(readlink "$current")"
  [[ "$link" =~ ^releases/([A-Za-z0-9._-]+)$ ]] || return 1
  installed="${BASH_REMATCH[1]}"
  [[ -d "$M05_ROOT/releases/$installed" &&
     ! -L "/opt/vfops-modules/m05/releases/$installed" ]] || return 1
  command -v python3 >/dev/null 2>&1 || return 1
  # Read-only module-own manifest, NOT the Toolbox's hardcoded bootstrap build:
  # a properly upgraded local M05 can continue working without changing M01-M04.
  python3 -B - "$current" "$installed" <<'PY'
import hashlib,json,pathlib,re,sys
root,build=pathlib.Path(sys.argv[1]),sys.argv[2]
try:
    manifest=root/"MODULE_MANIFEST.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("manifest")
    data=json.loads(manifest.read_text(encoding="utf-8"))
    if (data.get("schema")!="vf.p07.module-bundle.v1" or
        data.get("module_id")!="P07-M05" or
        data.get("module_build_id")!=build or
        data.get("entrypoint")!="bin/vfops-init-entry" or
        data.get("installation_isolation")!="P07-M05_ONLY"):
        raise ValueError("identity")
    if (root/"MODULE_ID").read_text(encoding="utf-8").strip()!="P07-M05":
        raise ValueError("module")
    if (root/"MODULE_BUILD_ID").read_text(encoding="utf-8").strip()!=build:
        raise ValueError("build")
    files=data.get("files")
    if not isinstance(files,dict) or not 20<=len(files)<=400:
        raise ValueError("files")
    if not {"bin/vfops-init-entry","bin/vfops-init-ui",
            "bin/vfops-init-core","MODULE_ID","MODULE_BUILD_ID"}.issubset(files):
        raise ValueError("expected")
    for name,digest in files.items():
        if not isinstance(name,str) or not isinstance(digest,str):
            raise ValueError("types")
        if not re.fullmatch("[a-f0-9]{64}",digest):
            raise ValueError("hash")
        if (name.startswith("/") or "\\" in name or ".." in pathlib.PurePosixPath(name).parts
            or not (name.startswith(("bin/","lib/")) or name in
                    ("VERSION","BUILD_ID","MODULE_ID","MODULE_BUILD_ID"))):
            raise ValueError("path")
        item=root/name
        if item.is_symlink() or not item.is_file():
            raise ValueError("file")
        if hashlib.sha256(item.read_bytes()).hexdigest()!=digest:
            raise ValueError("changed")
except (OSError,UnicodeError,ValueError,TypeError,KeyError,RecursionError):
    raise SystemExit(13)
PY
  [[ "$?" == 0 ]] || return 1
  actual_version="$(NO_COLOR=1 bash "$M05_RUNTIME" --version 2>/dev/null || true)"
  [[ "$actual_version" == "P07-M05 新服务器初始化 $installed" ]]
}

ensure_m05_current() {
  m05_verified_current && return 0
  if [[ -e "$M05_ROOT/current" || -L "$M05_ROOT/current" ]]; then
    say "${C_RED}P07-M05 新服务器初始化：已有模块身份或文件异常，拒绝覆盖/回退。${C_RESET}" >&2
    return 13
  fi
  if [[ -z "$M05_BUNDLE_URL" || -z "$M05_BUNDLE_SHA256" ]]; then
    say "${C_YELLOW}P07-M05 新服务器初始化独立安装包尚未正式分发；没有安装其他模块。${C_RESET}"
    return 7
  fi
  [[ "$M05_BUNDLE_URL" == https://* &&
     "$M05_BUNDLE_SHA256" =~ ^[a-f0-9]{64}$ ]] || return 13
  if [[ "$(id -u)" != "0" ]]; then
    say "${C_RED}P07-M05 新服务器初始化：首次独立安装需要 root。${C_RESET}" >&2
    return 3
  fi
  for tool in curl sha256sum sha1sum python3 mktemp; do
    command -v "$tool" >/dev/null 2>&1 || {
      say "${C_RED}P07-M05 新服务器初始化：缺少 $tool，其他模块未操作。${C_RESET}" >&2
      return 3
    }
  done
  local bundle installer actual rc
  bundle="$(mktemp -t p07-m05-package.XXXXXXXX)" || return 13
  installer="$(mktemp -t p07-m05-installer.XXXXXXXX)" || { rm -f "$bundle"; return 13; }
  chmod 0600 "$bundle" "$installer"
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 90 \
        "$M05_BUNDLE_URL" -o "$bundle"; then
    rm -f "$bundle" "$installer"; return 4
  fi
  actual="$(sha256_file "$bundle" 2>/dev/null || true)"
  if [[ "$actual" != "$M05_BUNDLE_SHA256" ]]; then
    rm -f "$bundle" "$installer"; return 6
  fi
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 60 \
        "$M05_INSTALLER_URL" -o "$installer"; then
    rm -f "$bundle" "$installer"; return 4
  fi
  actual="$(p07_git_blob_sha1 "$installer" 2>/dev/null || true)"
  if [[ "$actual" != "$M05_INSTALLER_BLOB" ]]; then
    rm -f "$bundle" "$installer"; return 6
  fi
  set +e
  python3 -B "$installer" install "$bundle" "$M05_BUNDLE_SHA256"
  rc=$?
  set -e
  rm -f "$bundle" "$installer"
  [[ "$rc" -eq 0 ]] || return "$rc"
  m05_verified_current || return 13
}

run_server_init() {
  screen_clear
  # Independent artifact only: must not install M03/M04 or provision CloudPanel
  # until the user actually chooses operations inside the M05 menu.
  ensure_m05_current || return $?
  bash "$M05_RUNTIME" menu
}

# Independent explicit operations. Never implicitly run these during startup,
# and never accept a private ZIP URL as public distribution.
p07_owned_helper() {
  local module="${1:-}" source="${2:-}" identity="${3:-}" kind="${4:-}" verb="${5:-}" build="${6:-}" confirm="${7:-}"
  local tmp actual rc
  [[ "$module" =~ ^P07-M0[145]$ &&
     "$confirm" == "$module:$build" &&
     "$build" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ &&
     "$source" == https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/* &&
     "$identity" =~ ^[a-f0-9]{40}$ &&
     "$verb" == rollback &&
     "$(id -u)" == 0 ]] || return 13
  case "$module:$kind" in
    P07-M01:bash|P07-M04:bash|P07-M05:python3) ;;
    *) return 13 ;;
  esac
  for cmd in curl sha1sum mktemp; do command -v "$cmd" >/dev/null 2>&1 || return 3; done
  [[ "$kind" != python3 ]] || command -v python3 >/dev/null 2>&1 || return 3
  tmp="$(mktemp -t p07-module-own-helper.XXXXXXXX)" || return 13
  chmod 0600 "$tmp"
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 60 \
       "$source" -o "$tmp"; then
    rm -f -- "$tmp"; return 4
  fi
  actual="$(p07_git_blob_sha1 "$tmp" 2>/dev/null || true)"
  if [[ "$actual" != "$identity" ]]; then
    rm -f -- "$tmp"
    say "${C_RED}$module：独立恢复器来源校验失败，未操作任何模块。${C_RESET}" >&2
    return 6
  fi
  set +e
  if [[ "$kind" == python3 ]]; then
    python3 -B "$tmp" rollback "$build" --confirm "$confirm"
  else
    bash "$tmp" rollback "$build" "$confirm"
  fi
  rc=$?
  set -e
  rm -f -- "$tmp"
  [[ "$rc" -eq 0 ]] || return "$rc"
  case "$module" in
    P07-M01) m01_verified_current ;;
    P07-M04) m04_verified_current ;;
    P07-M05) m05_verified_current ;;
  esac || return 13
}

# Manually chosen local M05 Owner Trial ZIP: no auto-publication or CloudPanel.
# Confirm SHA-256 explicitly; only install/update the M05 runtime files.
install_m05_local_candidate() {
  local archive="${1:-}" checksum="${2:-}" confirmation="${3:-}" tmp actual rc
  [[ "$(id -u)" == 0 &&
     "$archive" == /* && -f "$archive" && ! -L "$archive" &&
     "$archive" != *"/../"* && "$archive" != *"/./"* &&
     "$checksum" =~ ^[a-f0-9]{64}$ &&
     "$confirmation" == "P07-M05:INSTALL:$checksum" ]] || return 13
  for cmd in curl sha1sum sha256sum mktemp python3; do
    command -v "$cmd" >/dev/null 2>&1 || return 3
  done
  # Exclude all module runtime trees and the existing website runtime,
  # including aliases via parent symlinks (canonical path must be identical).
  local canonical
  canonical="$(realpath -e -- "$archive" 2>/dev/null || true)"
  [[ "$canonical" == "$archive" &&
     "$archive" != /opt/vfops-modules/* &&
     "$archive" != /opt/vf-server-ops/* &&
     "$archive" != /opt/vf-server-ops.previous/* ]] || return 13
  if ! m05_verified_current && [[ -e "$M05_ROOT/current" || -L "$M05_ROOT/current" ]]; then
    say "${C_RED}P07-M05 新服务器初始化：已有运行时身份异常，拒绝覆盖。${C_RESET}" >&2
    return 13
  fi
  actual="$(sha256_file "$archive" 2>/dev/null || true)"
  [[ "$actual" == "$checksum" ]] || {
    say "${C_RED}P07-M05 新服务器初始化：本地 ZIP SHA-256 不匹配；未执行安装。${C_RESET}" >&2
    return 6
  }
  tmp="$(mktemp -t p07-m05-local-installer.XXXXXXXX)" || return 13
  chmod 0600 "$tmp"
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 60 \
       "$M05_INSTALLER_URL" -o "$tmp"; then
    rm -f -- "$tmp"; return 4
  fi
  actual="$(p07_git_blob_sha1 "$tmp" 2>/dev/null || true)"
  if [[ "$actual" != "$M05_INSTALLER_BLOB" ]]; then
    rm -f -- "$tmp"
    say "${C_RED}P07-M05 新服务器初始化：独立原子安装器校验失败。${C_RESET}" >&2
    return 6
  fi
  set +e
  python3 -B "$tmp" install "$archive" "$checksum"
  rc=$?
  set -e
  rm -f -- "$tmp"
  [[ "$rc" -eq 0 ]] || return "$rc"
  m05_verified_current || return 13
  say "${C_GREEN}P07-M05 新服务器初始化：仅本模块本地候选安装通过；不等于正式发布或 CloudPanel 已初始化。${C_RESET}"
}

# P07-M05 新服务器初始化: an Owner-supplied ONE-FILE private trial.
# No Git/token, no public URL, no separate installer, no CloudPanel apply.
# The private executable is copied into a root-owned 0600 temporary file,
# verified against the immutable owner-trial hash, then executed ONLY for
# the independent M05 runtime install. Not an automatic Toolbox upgrade.
install_m05_offline_trial() {
  local archive="${1:-}" confirmation="${2:-}" canonical tmp actual rc
  [[ "$(id -u)" == 0 &&
     "$confirmation" == "P07-M05:INSTALL" &&
     "$archive" == /* && -f "$archive" && ! -L "$archive" &&
     "$M05_OFFLINE_TRIAL_SHA256" =~ ^[a-f0-9]{64}$ ]] || return 13
  for cmd in realpath cp curl sha256sum mktemp python3; do
    # curl is NOT required for this offline-only path.
    [[ "$cmd" != curl ]] || continue
    command -v "$cmd" >/dev/null 2>&1 || return 3
  done
  canonical="$(realpath -e -- "$archive" 2>/dev/null || true)"
  [[ "$canonical" == "$archive" &&
     "$canonical" != /opt/vfops-modules/* &&
     "$canonical" != /opt/vf-server-ops/* &&
     "$canonical" != /opt/vf-server-ops.previous/* &&
     ! -L /opt/vfops-modules && ! -L "$M05_ROOT" ]] || return 13
  if ! m05_verified_current && [[ -e "$M05_ROOT/current" || -L "$M05_ROOT/current" ]]; then
    say "${C_RED}P07-M05 新服务器初始化：已有模块校验异常，拒绝覆盖。${C_RESET}" >&2
    return 13
  fi
  tmp="$(mktemp -t p07-m05-one-file.XXXXXXXX)" || return 13
  chmod 0600 "$tmp"
  if ! cp -- "$archive" "$tmp"; then rm -f -- "$tmp"; return 13; fi
  actual="$(sha256_file "$tmp" 2>/dev/null || true)"
  if [[ "$actual" != "$M05_OFFLINE_TRIAL_SHA256" ]]; then
    rm -f -- "$tmp"
    say "${C_RED}P07-M05 新服务器初始化：私有单文件哈希不匹配；没有安装。${C_RESET}" >&2
    return 6
  fi
  set +e
  bash "$tmp" --verify-only >/dev/null
  rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then rm -f -- "$tmp"; return 13; fi
  set +e
  bash "$tmp" --install-only
  rc=$?
  set -e
  rm -f -- "$tmp"
  [[ "$rc" -eq 0 ]] || return "$rc"
  m05_verified_current || return 13
  say "${C_GREEN}P07-M05 新服务器初始化：仅独立模块试用运行时已安装；CloudPanel 未自动初始化。${C_RESET}"
}

p07_git_blob_sha1() {
  local file="$1" bytes
  bytes="$(wc -c < "$file" | tr -d '[:space:]')"
  { printf 'blob %s\0' "$bytes"; cat "$file"; } | sha1sum | awk '{print $1}'
}

m04_verified_current() {
  local current="$M04_ROOT/current" root="$M04_ROOT/current"
  local link installed='' name expected count=0 actual version contract
  [[ -L "$current" ]] || return 1
  link="$(readlink "$current")"
  [[ "$link" =~ ^releases/([A-Za-z0-9._-]+)$ ]] || return 1
  installed="${BASH_REMATCH[1]}"
  [[ -f "$root/MANIFEST.gitblob" && ! -L "$root/MANIFEST.gitblob" &&
     -f "$root/VERSION" && ! -L "$root/VERSION" &&
     -f "$M04_RUNTIME" && ! -L "$M04_RUNTIME" ]] || return 1
  [[ "$(cat "$root/VERSION")" == "$installed" ]] || return 1
  # The bootstrapped rc83 retains the exact public Git blob pin.
  if [[ "$installed" == "$M04_BUILD_EXPECTED" ]]; then
    [[ "$(p07_git_blob_sha1 "$M04_RUNTIME" 2>/dev/null || true)" == "$M04_UI_BLOB" ]] || return 1
  fi
  declare -A seen=()
  while read -r expected name; do
    [[ -n "$expected" && -n "$name" ]] || continue
    [[ "$expected" =~ ^[0-9a-f]{40}$ ]] || return 1
    [[ "$name" =~ ^(lib/)?[A-Za-z0-9._-]+$ &&
       "$name" != '.' && "$name" != '..' ]] || return 1
    [[ ! -v seen[$name] ]] || return 1
    seen[$name]=1
    [[ -f "$root/$name" && ! -L "$root/$name" ]] || return 1
    actual="$(p07_git_blob_sha1 "$root/$name" 2>/dev/null || true)"
    [[ "$actual" == "$expected" ]] || return 1
    count=$((count + 1))
    [[ "$count" -le 128 ]] || return 1
  done < "$root/MANIFEST.gitblob"
  [[ "$count" -ge 20 ]] || return 1
  version="$(NO_COLOR=1 bash "$M04_RUNTIME" --version 2>/dev/null || true)"
  contract="$(NO_COLOR=1 bash "$M04_RUNTIME" --ui-contract 2>/dev/null || true)"
  [[ "$version" == "服务器维护与安全 $installed" &&
     "$contract" == "P07_BEGINNER_ZH_V1" ]]
}

ensure_m04_current() {
  m04_verified_current && return 0
  if [[ -e "$M04_ROOT/current" || -L "$M04_ROOT/current" ]]; then
    say "${C_RED}P07-M04 服务器维护与安全：现有版本文件验收失败，拒绝退回旧版。${C_RESET}" >&2
    return 13
  fi
  if [[ "$(id -u)" != "0" ]]; then
    say "${C_RED}P07-M04 服务器维护与安全：首次独立安装需要 root。${C_RESET}" >&2
    return 3
  fi
  for cmd in curl sha1sum mktemp; do
    command -v "$cmd" >/dev/null 2>&1 || {
      say "${C_RED}P07-M04 服务器维护与安全：缺少 $cmd，没有升级任何模块。${C_RESET}" >&2
      return 3
    }
  done
  local tmp actual rc
  tmp="$(mktemp -t p07-m04-installer.XXXXXXXX)" || return 13
  chmod 0600 "$tmp"
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 60 "$M04_INSTALLER_URL" -o "$tmp"; then
    rm -f "$tmp"; return 4
  fi
  actual="$(p07_git_blob_sha1 "$tmp" 2>/dev/null || true)"
  if [[ "$actual" != "$M04_INSTALLER_BLOB" ]]; then
    rm -f "$tmp"
    say "${C_RED}P07-M04 服务器维护与安全：独立安装器文件校验失败。${C_RESET}" >&2
    return 6
  fi
  set +e
  bash "$tmp" install
  rc=$?
  set -e
  rm -f "$tmp"
  [[ "$rc" -eq 0 ]] || return "$rc"
  m04_verified_current || return 13
}

run_system_care() {
  screen_clear
  ensure_m04_current || return $?
  bash "$M04_RUNTIME" menu
}

# Read-only reporting only. No module installers/CLI are executed and no
# version directories are modified. Plain output also supports Owner SSH.
modules_status_readonly() {
  local slot display installed link marker
  printf '五模块本机版本（只读，未证明业务功能和制品完整性）\n'
  for slot in m01 m02 m03 m04 m05; do
    case "$slot" in
      m01) display="P07-M01 网络代理节点（V2Ray）"; installed="$M01_ROOT/current" ;;
      m02) display="P07-M02 服务器性能检测（VPS 验机）"; installed="$M02_ROOT/current" ;;
      m03) display="P07-M03 网站与数据"; installed="/opt/vf-server-ops" ;;
      m04) display="P07-M04 服务器维护与安全"; installed="$M04_ROOT/current" ;;
      m05) display="P07-M05 新服务器初始化"; installed="$M05_ROOT/current" ;;
    esac
    if [[ "$slot" == "m03" ]]; then
      if [[ -f "$installed/BUILD_ID" && ! -L "$installed/BUILD_ID" ]]; then
        IFS= read -r marker < "$installed/BUILD_ID" || marker=""
        [[ "$marker" =~ ^[A-Za-z0-9._-]+$ ]] || marker="身份异常"
      else
        marker="未安装"
      fi
    elif [[ -L "$installed" ]]; then
      link="$(readlink "$installed")"
      if [[ "$link" =~ ^releases/([A-Za-z0-9._-]+)$ && -d "$installed" && ! -L "$installed/BUILD_ID" ]]; then
        marker="${BASH_REMATCH[1]}"
      else
        marker="身份异常"
      fi
    elif [[ -e "$installed" ]]; then
      marker="身份异常"
    else
      marker="未安装"
    fi
    printf '%s：%s\n' "$display" "$marker"
  done
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
  --rollback-m01) [[ "$#" == 3 ]] || exit 13; p07_owned_helper P07-M01 "$M01_INSTALLER_URL" "$M01_INSTALLER_BLOB" bash rollback "$2" "$3" ;;
  --rollback-m02) [[ "$#" == 3 ]] || exit 13; rollback_m02_current "$2" "$3" ;;
  --rollback-m03) [[ "$#" == 3 ]] || exit 13; rollback_m03_previous "$2" "$3" ;;
  --rollback-m04) [[ "$#" == 3 ]] || exit 13; p07_owned_helper P07-M04 "$M04_INSTALLER_URL" "$M04_INSTALLER_BLOB" bash rollback "$2" "$3" ;;
  --rollback-m05) [[ "$#" == 3 ]] || exit 13; p07_owned_helper P07-M05 "$M05_INSTALLER_URL" "$M05_INSTALLER_BLOB" python3 rollback "$2" "$3" ;;
  --install-m05-local) [[ "$#" == 4 ]] || exit 13; install_m05_local_candidate "$2" "$3" "$4" ;;
  --install-m05-offline) [[ "$#" == 3 ]] || exit 13; install_m05_offline_trial "$2" "$3" ;;
  --modules) modules_status_readonly ;;
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
5. 新服务器初始化        系统更新/CloudPanel/数据库选择  V0.1.0（独立模块）

说明：5 个模块各自安装与升级；选择未分发模块时会明确提示，不会安装其他模块。
恢复既存的独立模块：
  --rollback-m01 <版本> <P07-M01:版本>
  --rollback-m02 <版本> <P07-M02:版本>
  --rollback-m03 <版本> <P07-M03:版本>
  --rollback-m04 <版本> <P07-M04:版本>
  --rollback-m05 <版本> <P07-M05:版本>
M05 私有单文件试用安装（无 Git/Token/网络/额外安装器，不会初始化 CloudPanel）：
  --install-m05-offline <RUN绝对路径> <P07-M05:INSTALL>
M05 私有 ZIP 候选手动验证安装（可能需要在线取得安装器）：
  --install-m05-local <ZIP绝对路径> <SHA-256> <P07-M05:INSTALL:SHA-256>
正式公共版本尚未发布；请勿在已有业务生产环境试装候选。
EOF
    ;;
  "")
    if [[ -t 0 && -t 1 ]]; then main_menu; else printf '错误：服务器工具箱主菜单需要交互式终端。\n' >&2; exit 2; fi
    ;;
  *) printf '错误：未知参数：%s\n' "$1" >&2; exit 2 ;;
esac
