#!/usr/bin/env bash
# P07-M03 网站与数据 · standalone runtime package. Installs NO websites,
# databases, services, backup tasks, migration tasks or other P07 module.
set -Eeuo pipefail

MODULE_ID='P07-M03'
MODULE_NAME='网站与数据'
MODULE_BUILD='0.1.0-release115'
PIN_REF='07fdedf8e79f4ea15213c3653f63d5876e4f7552'
PIN_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/$PIN_REF"
INSTALLER_BLOB='204f40e9db7c139910b6e1086d9cd520f3dc7fea'
MANIFEST_BLOB='4acbaca22aac0da681b34376e2cc86d876593181'
MODULE_ROOT='/opt/vfops-modules/m03'

msg() { printf '%s\n' "$*"; }
deny() { msg 'P07-M03 网站与数据：独立安装检查失败，其他模块未安装、升级或修改。' >&2; exit 13; }
git_blob() {
  local path="$1" size
  size="$(wc -c < "$path" | tr -d '[:space:]')"
  { printf 'blob %s\0' "$size"; cat "$path"; } | sha1sum | awk '{print $1}'
}
verify_release() {
  local root="$1" expected path count=0
  [[ -d "$root" && ! -L "$root" ]] || deny
  [[ -f "$root/BUILD_ID" && ! -L "$root/BUILD_ID" ]] || deny
  [[ "$(cat "$root/BUILD_ID")" == "$MODULE_BUILD" ]] || deny
  [[ -f "$root/.runtime-manifest.gitblob" && ! -L "$root/.runtime-manifest.gitblob" ]] || deny
  [[ "$(git_blob "$root/.runtime-manifest.gitblob")" == "$MANIFEST_BLOB" ]] || deny
  declare -A seen=()
  while read -r expected path; do
    [[ -n "$expected" && -n "$path" ]] || continue
    [[ "$expected" =~ ^[a-f0-9]{40}$ ]] || deny
    [[ "$path" =~ ^[A-Za-z0-9._/-]+$ ]] || deny
    [[ "$path" != /* && "$path" != ../* && "$path" != */../* && "$path" != */.. ]] || deny
    [[ ! -v seen[$path] ]] || deny
    seen[$path]=1
    [[ -f "$root/$path" && ! -L "$root/$path" ]] || deny
    [[ "$(git_blob "$root/$path")" == "$expected" ]] || deny
    count=$((count + 1))
  done < "$root/.runtime-manifest.gitblob"
  [[ "$count" -gt 10 ]] || deny
  [[ -x "$root/bin/vfops-user" ]] || deny
  [[ "$(NO_COLOR=1 bash "$root/bin/vfops-user" --build-id 2>/dev/null)" == "$MODULE_BUILD" ]] || deny
}

install_m03() {
  [[ "$(id -u)" == 0 ]] || deny
  for cmd in curl sha1sum mktemp flock python3 tar; do command -v "$cmd" >/dev/null 2>&1 || deny; done
  [[ ! -L /opt/vfops-modules && ! -L "$MODULE_ROOT" ]] || deny
  mkdir -p "$MODULE_ROOT/releases" || deny
  [[ -d "$MODULE_ROOT/releases" && ! -L "$MODULE_ROOT/releases" ]] || deny
  local fd current dest tmp link stage_old entry candidate_sha rc
  [[ ! -L "$MODULE_ROOT/.install.lock" ]] || deny
  exec {fd}>"$MODULE_ROOT/.install.lock"
  flock -x "$fd" || deny
  current="$MODULE_ROOT/current"
  dest="$MODULE_ROOT/releases/$MODULE_BUILD"
  if [[ -e "$current" || -L "$current" ]]; then
    [[ -L "$current" && "$(readlink "$current")" =~ ^releases/[A-Za-z0-9._-]+$ ]] || deny
  fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    verify_release "$dest"
    [[ -L "$current" && "$(readlink "$current")" == "releases/$MODULE_BUILD" ]] || deny
    msg 'P07-M03 网站与数据：独立模块已是当前版本，不重复安装。'
    return 0
  fi
  tmp="$(mktemp -t p07-m03-installer.XXXXXXXX)" || deny
  if ! curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --max-time 45 "$PIN_URL/installers/p07-final.sh" -o "$tmp"; then
    rm -f "$tmp"; deny
  fi
  candidate_sha="$(git_blob "$tmp")"
  [[ "$candidate_sha" == "$INSTALLER_BLOB" ]] || { rm -f "$tmp"; deny; }
  entry="$MODULE_ROOT/.candidate-entry-$$"
  stage_old="$MODULE_ROOT/.previous-unused-$$"
  link="$MODULE_ROOT/.current-$$"
  [[ ! -e "$entry" && ! -L "$entry" && ! -e "$stage_old" && ! -L "$stage_old" &&
     ! -e "$link" && ! -L "$link" ]] || { rm -f "$tmp"; deny; }
  set +e
  P07_INSTALL_DIR="$dest" \
  P07_PREVIOUS_DIR="$stage_old" \
  P07_BIN_LINK="$entry" \
  P07_PUBLIC_ROOT="$PIN_URL" \
  P07_NO_EXEC=1 bash "$tmp" >"$MODULE_ROOT/.last-install-output" 2>&1
  rc=$?
  set -e
  rm -f "$tmp" "$entry"
  if [[ "$rc" -ne 0 ]]; then
    rm -f "$MODULE_ROOT/.last-install-output"
    # No current pointer switch happened. Never delete a partial directory
    # if its provenance is not proven; the Owner can inspect it.
    deny
  fi
  rm -f "$MODULE_ROOT/.last-install-output"
  verify_release "$dest"
  ln -s "releases/$MODULE_BUILD" "$link" || deny
  mv -Tf -- "$link" "$current" || deny
  msg 'P07-M03 网站与数据：独立运行包安装完成，未创建网站或执行迁移。'
}

case "${1:-}" in
  --version) msg "P07-M03 网站与数据 $MODULE_BUILD" ;;
  --help) msg 'P07-M03 独立运行包安装器：install 仅安装固定软件，不执行迁移。' ;;
  install) install_m03 ;;
  *) deny ;;
esac
