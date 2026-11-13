#!/usr/bin/env bash
# P07-M03 网站与数据 · guarded restore of its own previous runtime only.
# Does NOT restore websites/databases, switch DNS, start migration, or call M04.
set -Eeuo pipefail
M03_ROOT='/opt/vf-server-ops'
M03_PREVIOUS='/opt/vf-server-ops.previous'
M03_ENTRY='/usr/local/bin/vfops'
M03_LOCK='/opt/vf-server-ops.rollback.lock'
msg() { printf '%s\n' "$*"; }
deny() { msg 'P07-M03 网站与数据：旧版运行时恢复已停止，未触碰网站、数据库、其他模块或 DNS。' >&2; exit 13; }
verify_runtime() {
  local folder="$1" expected_build="$2" build reported version
  [[ -d "$folder" && ! -L "$folder" &&
     -f "$folder/.runtime-manifest.gitblob" &&
     ! -L "$folder/.runtime-manifest.gitblob" &&
     -f "$folder/BUILD_ID" && ! -L "$folder/BUILD_ID" &&
     -f "$folder/bin/vfops-user" && ! -L "$folder/bin/vfops-user" ]] || deny
  build="$(cat "$folder/BUILD_ID")"
  [[ "$build" == "$expected_build" &&
     "$build" =~ ^0[.]1[.]0-release[0-9]+$ ]] || deny
  python3 -B - "$folder" <<'PY' || exit 13
import hashlib,pathlib,re,sys
root=pathlib.Path(sys.argv[1])
manifest=root/'.runtime-manifest.gitblob'
lines=manifest.read_text(encoding='utf-8').splitlines()
if not 50<=len(lines)<=240:
    raise SystemExit(13)
seen=set()
for line in lines:
    entry=re.fullmatch(r'([0-9a-f]{40})  ((?:bin|lib)/[A-Za-z0-9_./-]+|BUILD_ID)',line)
    if entry is None:
        raise SystemExit(13)
    sha,name=entry.groups()
    parts=pathlib.PurePosixPath(name).parts
    if '..' in parts or name in seen:
        raise SystemExit(13)
    seen.add(name)
    item=root/name
    if item.is_symlink() or not item.is_file():
        raise SystemExit(13)
    data=item.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if actual!=sha:
        raise SystemExit(13)
PY
  reported="$(NO_COLOR=1 bash "$folder/bin/vfops-user" --build-id 2>/dev/null || true)"
  version="$(NO_COLOR=1 bash "$folder/bin/vfops-user" --version 2>/dev/null || true)"
  [[ "$reported" == "$build" && "$version" == 'VF Server Ops 0.1.0' ]] || deny
}
restore_previous() {
  local requested="${1:-}" confirmation="${2:-}" running temp lock_fd
  [[ "$(id -u)" -eq 0 &&
     "$requested" =~ ^0[.]1[.]0-release[0-9]+$ &&
     "$confirmation" == "P07-M03:$requested" ]] || deny
  for tool in python3 flock readlink bash; do command -v "$tool" >/dev/null 2>&1 || deny; done
  [[ -d /opt && ! -L /opt && ! -L "$M03_LOCK" ]] || deny
  [[ -d "$M03_ROOT" && ! -L "$M03_ROOT" &&
     -d "$M03_PREVIOUS" && ! -L "$M03_PREVIOUS" &&
     -L "$M03_ENTRY" ]] || deny
  [[ "$(readlink "$M03_ENTRY")" == "$M03_ROOT/bin/vfops-user" ]] || deny
  temp="$M03_ROOT.rollback-stage-$$"
  [[ ! -e "$temp" && ! -L "$temp" ]] || deny
  exec {lock_fd}>"$M03_LOCK" || deny
  flock -x "$lock_fd" || deny
  verify_runtime "$M03_PREVIOUS" "$requested"
  running="$(cat "$M03_ROOT/BUILD_ID")"
  verify_runtime "$M03_ROOT" "$running"
  [[ "$running" != "$requested" ]] || deny
  # Keep both runtimes: swap directory paths only. Never rm -rf.
  mv -T -- "$M03_ROOT" "$temp" || deny
  if ! mv -T -- "$M03_PREVIOUS" "$M03_ROOT"; then
    mv -T -- "$temp" "$M03_ROOT" || true
    deny
  fi
  if ! mv -T -- "$temp" "$M03_PREVIOUS"; then
    mv -T -- "$M03_ROOT" "$M03_PREVIOUS" || true
    mv -T -- "$temp" "$M03_ROOT" || true
    deny
  fi
  msg "P07-M03 网站与数据：已恢复独立运行时 $requested，原版本保存在 .previous；不操作其他模块。"
}
case "${1:-}" in
  --help) msg 'P07-M03 网站与数据：restore-previous <BUILD_ID> <P07-M03:BUILD_ID>（仅运行时，非网站数据）' ;;
  --version) msg 'P07-M03 网站与数据 · 仅运行时恢复 V1' ;;
  restore-previous) [[ "$#" -eq 3 ]] || deny; restore_previous "$2" "$3" ;;
  *) deny ;;
esac
