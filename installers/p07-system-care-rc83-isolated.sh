#!/usr/bin/env bash
# P07-M04 服务器维护与安全 · independent immutable candidate installer.
# No M03 runtime installation, no shared /usr/local/bin overwrite, no DNS/VPS migration.
set -Eeuo pipefail

MODULE_ID='P07-M04'
MODULE_VERSION='0.1.0-rc83'
MODULE_NAME='服务器维护与安全'
PIN_REF='3174bdebac97cbf1e2ca1d09038c2616576c518f'
MANIFEST_BLOB='f82c9e42297c45a54ec6dc2fc4d705cad316dfce'
UI_BLOB='f140f1158351f9dce2e9f9159611af57047424b1'
SOURCE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/${PIN_REF}/packages/p07-system-care/${MODULE_VERSION}"
MODULE_ROOT='/opt/vfops-modules/m04'

say() { printf '%s\n' "$*"; }
deny() { say 'P07-M04 服务器维护与安全：独立安装已停止，没有运行其他模块。' >&2; exit 13; }
blob_sha() {
  local file="$1" bytes
  bytes="$(wc -c < "$file" | tr -d '[:space:]')"
  { printf 'blob %s\0' "$bytes"; cat "$file"; } | sha1sum | awk '{print $1}'
}
lock_path() {
  local folder="$1"
  [[ ! -L "$folder" && -d "$folder" ]] || deny
}
verify_own_release() {
  local path="$1" name expected actual count=0
  [[ ! -L "$path" && -d "$path" ]] || deny
  [[ -f "$path/MANIFEST.gitblob" && ! -L "$path/MANIFEST.gitblob" ]] || deny
  [[ "$(blob_sha "$path/MANIFEST.gitblob")" == "$MANIFEST_BLOB" ]] || deny
  [[ "$(cat "$path/VERSION")" == "$MODULE_VERSION" ]] || deny
  declare -A seen=()
  while read -r expected name; do
    [[ -n "$expected" && -n "$name" ]] || continue
    [[ "$expected" =~ ^[a-f0-9]{40}$ ]] || deny
    [[ "$name" =~ ^(lib/)?[A-Za-z0-9._-]+$ && "$name" != '.' && "$name" != '..' ]] || deny
    [[ ! -v seen[$name] ]] || deny
    seen[$name]=1
    [[ -f "$path/$name" && ! -L "$path/$name" ]] || deny
    actual="$(blob_sha "$path/$name")"
    [[ "$actual" == "$expected" ]] || deny
    count=$((count + 1))
  done < "$path/MANIFEST.gitblob"
  [[ "$count" -eq 24 ]] || deny
  [[ "$(blob_sha "$path/vf-system-care.sh")" == "$UI_BLOB" ]] || deny
}

install_only_m04() {
  [[ "$(id -u)" == 0 ]] || deny
  for bin in curl mktemp sha1sum flock bash; do command -v "$bin" >/dev/null 2>&1 || deny; done
  [[ ! -L /opt/vfops-modules ]] || deny
  mkdir -p /opt/vfops-modules
  [[ -d /opt/vfops-modules ]] || deny
  [[ ! -L "$MODULE_ROOT" ]] || deny
  mkdir -p "$MODULE_ROOT/releases"
  lock_path "$MODULE_ROOT"
  lock_path "$MODULE_ROOT/releases"
  [[ ! -L "$MODULE_ROOT/.install.lock" ]] || deny
  local lock_fd
  exec {lock_fd}>"$MODULE_ROOT/.install.lock"
  flock -x "$lock_fd" || deny

  local active="$MODULE_ROOT/current" dest="$MODULE_ROOT/releases/$MODULE_VERSION"
  if [[ -e "$active" || -L "$active" ]]; then
    [[ -L "$active" ]] || deny
    case "$(readlink "$active")" in
      releases/0.1.0-rc[0-9]*) ;;
      *) deny ;;
    esac
  fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    verify_own_release "$dest"
    [[ -L "$active" && "$(readlink "$active")" == "releases/$MODULE_VERSION" ]] || deny
    say 'P07-M04 服务器维护与安全：已是当前独立版本，无需重复安装。'
    return 0
  fi
  local tmp stage link manifest expected rel actual count=0
  tmp="$(mktemp -d /tmp/p07-m04-rc83.XXXXXXXX)" || deny
  stage="$MODULE_ROOT/releases/.stage-$$"
  link="$MODULE_ROOT/.current-$$"
  [[ ! -e "$stage" && ! -L "$stage" && ! -e "$link" && ! -L "$link" ]] || deny
  chmod 0700 "$tmp"
  mkdir -m 0700 "$stage" || deny
  # Verify exact immutable archived manifest before unpacking a single script.
  manifest="$tmp/MANIFEST.gitblob"
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 30 "$SOURCE_URL/MANIFEST.gitblob" -o "$manifest"; then
    rm -rf -- "$tmp" "$stage"; deny
  fi
  [[ "$(blob_sha "$manifest")" == "$MANIFEST_BLOB" ]] || { rm -rf -- "$tmp" "$stage"; deny; }
  declare -A seen=()
  while read -r expected rel; do
    [[ -n "$expected" && -n "$rel" ]] || continue
    [[ "$expected" =~ ^[a-f0-9]{40}$ ]] || { rm -rf -- "$tmp" "$stage"; deny; }
    [[ "$rel" =~ ^(lib/)?[A-Za-z0-9._-]+$ && "$rel" != '..' && "$rel" != '.' ]] || { rm -rf -- "$tmp" "$stage"; deny; }
    [[ ! -v seen[$rel] ]] || { rm -rf -- "$tmp" "$stage"; deny; }
    seen[$rel]=1
    count=$((count + 1))
    [[ "$count" -le 24 ]] || { rm -rf -- "$tmp" "$stage"; deny; }
    mkdir -p -- "$(dirname "$stage/$rel")"
    if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 30 "$SOURCE_URL/$rel" -o "$stage/$rel"; then
      rm -rf -- "$tmp" "$stage"; deny
    fi
    actual="$(blob_sha "$stage/$rel")"
    [[ "$actual" == "$expected" ]] || { rm -rf -- "$tmp" "$stage"; deny; }
    case "$rel" in
      *.sh) chmod 0755 "$stage/$rel" ;;
      *) chmod 0644 "$stage/$rel" ;;
    esac
  done < "$manifest"
  [[ "$count" -eq 24 ]] || { rm -rf -- "$tmp" "$stage"; deny; }
  cp -- "$manifest" "$stage/MANIFEST.gitblob"
  chmod 0644 "$stage/MANIFEST.gitblob"
  verify_own_release "$stage"
  bash -n "$stage/vf-system-care.sh" || { rm -rf -- "$tmp" "$stage"; deny; }
  [[ "$(NO_COLOR=1 bash "$stage/vf-system-care.sh" --version)" == "服务器维护与安全 $MODULE_VERSION" ]] || { rm -rf -- "$tmp" "$stage"; deny; }
  [[ "$(NO_COLOR=1 bash "$stage/vf-system-care.sh" --ui-contract)" == 'P07_BEGINNER_ZH_V1' ]] || { rm -rf -- "$tmp" "$stage"; deny; }
  chmod 0755 "$stage" || { rm -rf -- "$tmp" "$stage"; deny; }
  mv -T -- "$stage" "$dest" || { rm -rf -- "$tmp" "$stage"; deny; }
  ln -s "releases/$MODULE_VERSION" "$link" || deny
  mv -Tf -- "$link" "$active" || deny
  rm -rf -- "$tmp"
  say 'P07-M04 服务器维护与安全：独立模块已安装，其他模块未更新。'
}

rollback_m04_only() {
  # Restore only the selected verified M04 release. Never call M03/VF Ops.
  local build="${1:-}" confirmation="${2:-}" old current target link lock_fd
  [[ "$(id -u)" == "0" && "$build" == "$MODULE_VERSION" &&
     "$confirmation" == "P07-M04:$MODULE_VERSION" ]] || deny
  for tool in flock readlink sha1sum; do
    command -v "$tool" >/dev/null 2>&1 || deny
  done
  lock_path /opt/vfops-modules
  lock_path "$MODULE_ROOT"
  lock_path "$MODULE_ROOT/releases"
  [[ ! -L "$MODULE_ROOT/.install.lock" ]] || deny
  exec {lock_fd}>"$MODULE_ROOT/.install.lock" || deny
  flock -x "$lock_fd" || deny
  current="$MODULE_ROOT/current"
  [[ -L "$current" ]] || deny
  old="$(readlink "$current")"
  [[ "$old" =~ ^releases/[A-Za-z0-9._-]+$ &&
     -d "$MODULE_ROOT/$old" && ! -L "$MODULE_ROOT/$old" ]] || deny
  target="$MODULE_ROOT/releases/$MODULE_VERSION"
  verify_own_release "$target"
  if [[ "$old" != "releases/$MODULE_VERSION" ]]; then
    link="$MODULE_ROOT/.current-rollback-$"
    [[ ! -e "$link" && ! -L "$link" ]] || deny
    ln -s "releases/$MODULE_VERSION" "$link" || deny
    mv -Tf -- "$link" "$current" || { rm -f "$link"; deny; }
  fi
  say 'P07-M04 服务器维护与安全：仅本模块已恢复指定版本，其他模块未改变。'
}

case "${1:-}" in
  --version) say "P07-M04 服务器维护与安全 $MODULE_VERSION" ;;
  --help) say 'P07-M04 服务器维护与安全：install 安装；rollback <版本> <P07-M04:版本> 回退本模块。' ;;
  install) install_only_m04 ;;
  rollback) [[ "$#" == 3 ]] || deny; rollback_m04_only "$2" "$3" ;;
  *) deny ;;
esac
