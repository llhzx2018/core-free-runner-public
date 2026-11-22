#!/usr/bin/env bash
set -Eeuo pipefail
official="$1"
older="$2"
candidate="$3"
wrapper="$4"
work="$(mktemp -d -t p07-ux-upgrade.XXXXXXXX)"
trap 'rm -rf -- "$work"' EXIT

extract() { python3 -B -m zipfile -e "$1" "$2"; }
install_inner() {
  local contents="$1" host="$2"
  P07_INSTALL_DIR="$host/current" P07_PREVIOUS_DIR="$host/previous" \
    P07_BIN_LINK="$host/bin/vfops" P07_ALLOW_NONROOT=1 P07_NO_EXEC=1 \
    P07_PUBLIC_ROOT="file://$contents" bash "$contents/installers/p07-final.sh"
}
mkdir -p "$work/base/bin" "$work/older/bin" "$work/fakebin"
extract "$official" "$work/144"
extract "$older" "$work/142"
extract "$candidate" "$work/145"
install_inner "$work/144" "$work/base" >"$work/base.log" 2>&1 || { tail -15 "$work/base.log"; exit 1; }
install_inner "$work/142" "$work/older" >"$work/older.log" 2>&1 || { tail -15 "$work/older.log"; exit 1; }
[[ "$(cat "$work/base/current/BUILD_ID")" == '0.1.0-release144' ]]
[[ "$(cat "$work/older/current/BUILD_ID")" == '0.1.0-release142' ]]

cat >"$work/fakebin/curl" <<'CURL'
#!/usr/bin/env bash
set -Eeuo pipefail
case " $* " in *' file://'*) exec /usr/bin/curl "$@" ;; esac
[[ " $* " == *' https://github.com/llhzx2018/core-free-runner-public/releases/download/p07-m03-v0.1.0-release145-20261122/P07-M03-0.1.0-release145.zip '* ]]
destination=
while (( $# )); do
  if [[ "$1" == -o ]]; then destination="$2"; shift 2; else shift; fi
done
[[ -n "$destination" ]]
cp -- "$P07_LOCAL_UPGRADE_ASSET" "$destination"
CURL
chmod 0700 "$work/fakebin/curl"
install_outer() {
  local host="$1" payload="$2"
  PATH="$work/fakebin:$PATH" P07_LOCAL_UPGRADE_ASSET="$payload" \
    P07_INSTALL_DIR="$host/current" P07_PREVIOUS_DIR="$host/previous" \
    P07_BIN_LINK="$host/bin/vfops" P07_ALLOW_NONROOT=1 P07_NO_EXEC=1 bash "$wrapper" install
}
seed_host() {
  local host="$1"
  mkdir -p "$host/bin" "$host/data" "$host/other-modules"
  cp -a "$work/base/current" "$host/current"
  ln -s "$host/current/bin/vfops-user" "$host/bin/vfops"
  printf '{"migration":"unchanged"}\n' >"$host/data/state.json"
  for id in 01 02 04 05; do printf 'P07-M%s\n' "$id" >"$host/other-modules/$id"; done
}

seed_host "$work/upgrade"
cp -a "$work/older/current" "$work/upgrade/previous"
cp "$candidate" "$work/corrupt.zip"
printf 'corrupt archive\n' >>"$work/corrupt.zip"
if install_outer "$work/upgrade" "$work/corrupt.zip" >"$work/reject.log" 2>&1; then exit 1; fi
grep -Fq HASH_MISMATCH "$work/reject.log"
cmp "$work/upgrade/current/.runtime-manifest.gitblob" "$work/base/current/.runtime-manifest.gitblob"
cmp "$work/upgrade/previous/.runtime-manifest.gitblob" "$work/older/current/.runtime-manifest.gitblob"
echo P07_145_WRONG_HASH_REJECTED=PASS

install_outer "$work/upgrade" "$candidate" >"$work/upgrade.log" 2>&1 || { tail -15 "$work/upgrade.log"; exit 1; }
[[ "$("$work/upgrade/bin/vfops" --build-id)" == '0.1.0-release145' ]]
cmp "$work/upgrade/previous/.runtime-manifest.gitblob" "$work/base/current/.runtime-manifest.gitblob"
cmp "$work/upgrade/previous.preserved-0.1.0-release142/.runtime-manifest.gitblob" "$work/older/current/.runtime-manifest.gitblob"
for rel in bin/vfops-migrate-ui components/p07-m03-failed-task-ux.sh components/p07-m03-safe-batch-ui.sh; do
  cmp "$work/upgrade/current/$rel" "$work/145/dist/p07/0.1.0/overlay/$rel"
done
[[ "$(cat "$work/upgrade/data/state.json")" == '{"migration":"unchanged"}' ]]
for id in 01 02 04 05; do [[ "$(cat "$work/upgrade/other-modules/$id")" == "P07-M$id" ]]; done
echo P07_145_UPGRADE_PRESERVES_144_AND_142=PASS

seed_host "$work/rollback"
cp -a "$work/145" "$work/fault"
python3 -B - "$work/fault/installers/p07-final.sh" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
check = "if ! verify_installed_current; then"
assert source.count(check) == 1
path.write_text(source.replace(check, "if true; then"), encoding="utf-8")
PY
if install_inner "$work/fault" "$work/rollback" >"$work/rollback.log" 2>&1; then exit 1; fi
[[ "$("$work/rollback/bin/vfops" --build-id)" == '0.1.0-release144' ]]
cmp "$work/rollback/current/.runtime-manifest.gitblob" "$work/base/current/.runtime-manifest.gitblob"
[[ ! -e "$work/rollback/previous" && ! -e "$work/rollback/current.new" ]]
echo P07_145_POST_SWAP_ROLLBACK_TO_144=PASS
