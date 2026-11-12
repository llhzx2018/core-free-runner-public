#!/usr/bin/env bash
# P07-M01 网络代理节点（V2Ray） independent MANAGEMENT runtime ONLY.
# This installer never installs, starts, stops or changes an actual V2Ray node.
set -Eeuo pipefail

MODULE_ID='P07-M01'
MODULE_NAME='网络代理节点（V2Ray）'
VERSION='0.1.0-rc13'
SOURCE_COMMIT='07fdedf8e79f4ea15213c3653f63d5876e4f7552'
SOURCE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/${SOURCE_COMMIT}/packages/p07-network-node/${VERSION}"
MANIFEST_SHA256='1ca3dc95a5cc6e5aa35c9b7ead415d3b6ea6c6eb9e8307a76310d146ab53c47f'
MODULE_ROOT='/opt/vfops-modules/m01'

msg() { printf '%s\n' "$*"; }
deny() { msg 'P07-M01 网络代理节点（V2Ray）：管理器独立安装已阻断，其他模块不受影响。' >&2; exit 13; }
sha() { sha256sum "$1" | awk '{print $1}'; }

verify_release() {
  local root="$1" expected name total=0
  [[ -d "$root" && ! -L "$root" ]] || deny
  [[ -f "$root/MANIFEST.sha256" && ! -L "$root/MANIFEST.sha256" ]] || deny
  [[ "$(sha "$root/MANIFEST.sha256")" == "$MANIFEST_SHA256" ]] || deny
  [[ -f "$root/VERSION" && "$(cat "$root/VERSION")" == "$VERSION" ]] || deny
  declare -A seen=()
  while read -r expected name; do
    [[ -n "$expected" && -n "$name" ]] || continue
    [[ "$expected" =~ ^[a-f0-9]{64}$ ]] || deny
    [[ "$name" =~ ^(lib/)?[A-Za-z0-9._-]+$ && "$name" != '.' && "$name" != '..' ]] || deny
    [[ ! -v seen[$name] ]] || deny
    seen[$name]=1
    [[ -f "$root/$name" && ! -L "$root/$name" ]] || deny
    [[ "$(sha "$root/$name")" == "$expected" ]] || deny
    total=$((total + 1))
  done < "$root/MANIFEST.sha256"
  [[ "$total" -eq 10 ]] || deny
  [[ "$(NO_COLOR=1 bash "$root/vf-node.sh" --version 2>/dev/null | awk '{print $NF}')" == "$VERSION" ]] || deny
}

install_m01_manager() {
  [[ "$(id -u)" == "0" ]] || deny
  for cmd in curl sha256sum mktemp flock awk; do command -v "$cmd" >/dev/null 2>&1 || deny; done
  [[ ! -L /opt/vfops-modules && ! -L "$MODULE_ROOT" ]] || deny
  mkdir -p "$MODULE_ROOT/releases"
  [[ -d "$MODULE_ROOT/releases" && ! -L "$MODULE_ROOT/releases" ]] || deny
  local fd current dest temp stage link expected name total=0
  [[ ! -L "$MODULE_ROOT/.install.lock" ]] || deny
  exec {fd}>"$MODULE_ROOT/.install.lock"
  flock -x "$fd" || deny
  current="$MODULE_ROOT/current"
  dest="$MODULE_ROOT/releases/$VERSION"
  if [[ -e "$current" || -L "$current" ]]; then
    [[ -L "$current" ]] || deny
    [[ "$(readlink "$current")" =~ ^releases/[A-Za-z0-9._-]+$ ]] || deny
  fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    verify_release "$dest"
    [[ -L "$current" && "$(readlink "$current")" == "releases/$VERSION" ]] || deny
    msg 'P07-M01 网络代理节点（V2Ray）：独立管理器版本已是当前版本，无需更新。'
    return 0
  fi
  temp="$(mktemp -d /tmp/p07-m01-runtime.XXXXXXXX)" || deny
  stage="$MODULE_ROOT/releases/.stage-$$"
  link="$MODULE_ROOT/.current-$$"
  [[ ! -e "$stage" && ! -L "$stage" && ! -e "$link" && ! -L "$link" ]] || deny
  mkdir -m 0700 "$stage" || deny
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 45 "$SOURCE_URL/MANIFEST.sha256" -o "$temp/MANIFEST.sha256"; then
    rm -rf -- "$temp" "$stage"; deny
  fi
  [[ "$(sha "$temp/MANIFEST.sha256")" == "$MANIFEST_SHA256" ]] || { rm -rf -- "$temp" "$stage"; deny; }
  declare -A seen=()
  while read -r expected name; do
    [[ -n "$expected" && -n "$name" ]] || continue
    [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || { rm -rf -- "$temp" "$stage"; deny; }
    [[ "$name" =~ ^(lib/)?[A-Za-z0-9._-]+$ && "$name" != '..' && "$name" != '.' ]] || { rm -rf -- "$temp" "$stage"; deny; }
    [[ ! -v seen[$name] ]] || { rm -rf -- "$temp" "$stage"; deny; }
    seen[$name]=1
    total=$((total + 1))
    [[ "$total" -le 10 ]] || { rm -rf -- "$temp" "$stage"; deny; }
    mkdir -p -- "$(dirname "$stage/$name")"
    if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 45 "$SOURCE_URL/$name" -o "$stage/$name"; then
      rm -rf -- "$temp" "$stage"; deny
    fi
    [[ "$(sha "$stage/$name")" == "$expected" ]] || { rm -rf -- "$temp" "$stage"; deny; }
    case "$name" in
      *.sh|lib/patch_upstream_core.py) chmod 0755 "$stage/$name" ;;
      *) chmod 0644 "$stage/$name" ;;
    esac
  done < "$temp/MANIFEST.sha256"
  [[ "$total" -eq 10 ]] || { rm -rf -- "$temp" "$stage"; deny; }
  cp -- "$temp/MANIFEST.sha256" "$stage/MANIFEST.sha256"
  chmod 0644 "$stage/MANIFEST.sha256"
  verify_release "$stage"
  bash -n "$stage/vf-node.sh" || { rm -rf -- "$temp" "$stage"; deny; }
  chmod 0755 "$stage"
  mv -T -- "$stage" "$dest" || { rm -rf -- "$temp" "$stage"; deny; }
  ln -s "releases/$VERSION" "$link" || deny
  mv -Tf -- "$link" "$current" || deny
  rm -rf -- "$temp"
  msg 'P07-M01 网络代理节点（V2Ray）：独立管理器已安装；未安装代理节点，也未修改其他模块。'
}

rollback_m01_manager() {
  # Restore only a verified previously installed management runtime.
  # The actual V2Ray node/service is never started, stopped or reconfigured.
  local target_build="${1:-}" confirmation="${2:-}" current old fd switch
  [[ "$(id -u)" == "0" &&
     "$target_build" == "$VERSION" &&
     "$confirmation" == "P07-M01:$VERSION" ]] || deny
  for cmd in flock sha256sum readlink; do
    command -v "$cmd" >/dev/null 2>&1 || deny
  done
  [[ -d /opt/vfops-modules && ! -L /opt/vfops-modules &&
     -d "$MODULE_ROOT" && ! -L "$MODULE_ROOT" &&
     -d "$MODULE_ROOT/releases" && ! -L "$MODULE_ROOT/releases" &&
     ! -L "$MODULE_ROOT/.install.lock" ]] || deny
  exec {fd}>"$MODULE_ROOT/.install.lock" || deny
  flock -x "$fd" || deny
  current="$MODULE_ROOT/current"
  [[ -L "$current" ]] || deny
  old="$(readlink "$current")"
  [[ "$old" =~ ^releases/[A-Za-z0-9._-]+$ &&
     -d "$MODULE_ROOT/$old" && ! -L "$MODULE_ROOT/$old" ]] || deny
  verify_release "$MODULE_ROOT/releases/$VERSION"
  if [[ "$old" != "releases/$VERSION" ]]; then
    switch="$MODULE_ROOT/.current-rollback-$"
    [[ ! -e "$switch" && ! -L "$switch" ]] || deny
    ln -s "releases/$VERSION" "$switch" || deny
    mv -Tf -- "$switch" "$current" || { rm -f "$switch"; deny; }
  fi
  msg 'P07-M01 网络代理节点（V2Ray）：仅管理器已恢复到指定历史版本，其他四模块和真实节点均未操作。'
}

case "${1:-}" in
  --version) msg "P07-M01 网络代理节点（V2Ray） $VERSION" ;;
  --help) msg 'P07-M01 网络代理节点（V2Ray）：install 安装管理器；rollback <版本> <P07-M01:版本> 独立恢复管理器' ;;
  install) install_m01_manager ;;
  rollback) [[ "$#" == 3 ]] || deny; rollback_m01_manager "$2" "$3" ;;
  *) deny ;;
esac
