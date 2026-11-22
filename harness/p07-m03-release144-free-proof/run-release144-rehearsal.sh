set -Eeuo pipefail
stage="${P07_REHEARSAL_STAGE:?temporary isolated staging directory required}"
work=$(mktemp -d /tmp/p07-release-rehearsal.XXXXXXXX)
trap 'status=$?; rm -rf -- "$work"; exit "$status"' EXIT
exec > >(tee "$stage/p07-release144-rehearsal.log") 2>&1

echo "source=9010a6379f409d22888b3681e3561696f482660a mode=LOCAL_REHEARSAL"
python3 -B "$stage/prepare-release144-rehearsal.py" "$work" "$stage"
bash -n "$work/wrapper-rehearsal.sh"

old_asset="$work/official141.zip"
old_sha=22c23818bc7268e6d3d95bc2552f42a5a3c12e97e387fdc542d59934c658b6d1
check_sha() { printf '%s  %s\n' "$1" "$2" | sha256sum -c --status -; }
download_fixture() {
  local direct='https://github.com/llhzx2018/core-free-runner-public/releases/download/p07-m03-v0.1.0-release141-limited-20261119/P07-M03-0.1.0-release141.zip'
  local api='https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/assets/767910493'
  if curl --proto '=https' -fsSL --connect-timeout 6 --max-time 20 "$direct" -o "$old_asset" \
      && check_sha "$old_sha" "$old_asset"; then
    return 0
  fi
  curl --proto '=https' -fsSL --connect-timeout 8 --max-time 25 \
    -H 'Accept: application/octet-stream' "$api" -o "$old_asset"
  check_sha "$old_sha" "$old_asset"
}
download_fixture
current_asset="$stage/official142.zip"
check_sha dc6978463e8e73a224e7cccb2bdffe9710bc3bb478076b670703bbb164bda87e "$current_asset"
next_asset="$work/P07-M03-0.1.0-release144-rehearsal.zip"
python3 -B -m zipfile -e "$old_asset" "$work/141"
python3 -B -m zipfile -e "$current_asset" "$work/142"
python3 -B -m zipfile -e "$next_asset" "$work/144"

install_inner() {
  local package=$1 host=$2
  P07_INSTALL_DIR="$host/current" P07_PREVIOUS_DIR="$host/previous" \
  P07_BIN_LINK="$host/bin/vfops" P07_ALLOW_NONROOT=1 P07_NO_EXEC=1 \
  P07_PUBLIC_ROOT="file://$package" bash "$package/installers/p07-final.sh"
}

mkdir -m 700 "$work/fakebin"
cat > "$work/fakebin/curl" <<'CURL'
#!/usr/bin/env bash
set -Eeuo pipefail
for arg in "$@"; do
    case "$arg" in
    file://*) exec /usr/bin/curl "$@" ;;
    esac
done
[[ "$*" == *"$P07_EXPECTED_REHEARSAL_URL"* ]] || exit 48
destination=''
while (( $# )); do
  if [[ "$1" == -o ]]; then destination="$2"; shift 2; else shift; fi
done
test -n "$destination" && cp -- "$P07_LOCAL_REHEARSAL_ASSET" "$destination"
CURL
chmod 0700 "$work/fakebin/curl"
run_wrapper() {
  local host=$1 archive=$2
  local url='https://github.com/llhzx2018/core-free-runner-public/releases/download/p07-m03-v0.1.0-release144-rehearsal/P07-M03-0.1.0-release144-rehearsal.zip'
  PATH="$work/fakebin:$PATH" P07_EXPECTED_REHEARSAL_URL="$url" P07_LOCAL_REHEARSAL_ASSET="$archive" \
  P07_INSTALL_DIR="$host/current" P07_PREVIOUS_DIR="$host/previous" \
  P07_BIN_LINK="$host/bin/vfops" P07_ALLOW_NONROOT=1 P07_NO_EXEC=1 \
  bash "$work/wrapper-rehearsal.sh" install
}

mkdir -p "$work/seed" "$work/baseline"
install_inner "$work/141" "$work/seed" > "$work/base141.log" 2>&1
install_inner "$work/142" "$work/baseline" > "$work/base142.log" 2>&1
test "$(cat "$work/seed/current/BUILD_ID")" = 0.1.0-release141
test "$(cat "$work/baseline/current/BUILD_ID")" = 0.1.0-release142

mkdir "$work/upgrade" "$work/collision" "$work/unknown" "$work/post-swap"
for host in upgrade collision unknown post-swap; do
  cp -a "$work/baseline/current" "$work/$host/current"
  mkdir "$work/$host/bin"
  ln -s "$work/$host/current/bin/vfops-user" "$work/$host/bin/vfops"
done
for host in upgrade collision unknown; do
  cp -a "$work/seed/current" "$work/$host/previous"
done

if run_wrapper "$work/upgrade" "$current_asset" > "$work/wrongzip.log" 2>&1; then exit 1; fi
grep -q 'HASH_MISMATCH' "$work/wrongzip.log"
cmp "$work/baseline/current/.runtime-manifest.gitblob" "$work/upgrade/current/.runtime-manifest.gitblob"
cmp "$work/seed/current/.runtime-manifest.gitblob" "$work/upgrade/previous/.runtime-manifest.gitblob"
test ! -e "$work/upgrade/previous.preserved-0.1.0-release141"
echo P07_RELEASE_REHEARSAL_OUTER_HASH_REJECTION=PASS

run_wrapper "$work/upgrade" "$next_asset" > "$work/upgrade.log" 2>&1
test "$(cat "$work/upgrade/current/BUILD_ID")" = 0.1.0-release144
test "$(NO_COLOR=1 "$work/upgrade/bin/vfops" --build-id)" = 0.1.0-release144
cmp "$work/baseline/current/.runtime-manifest.gitblob" "$work/upgrade/previous/.runtime-manifest.gitblob"
cmp "$work/seed/current/.runtime-manifest.gitblob" "$work/upgrade/previous.preserved-0.1.0-release141/.runtime-manifest.gitblob"
for name in bin/vfops-migrate-ui lib/migration_safe_batch_cli.py lib/migration_batch_withdraw.py lib/server_migration_pull.py; do
  cmp "$work/144/dist/p07/0.1.0/overlay/$name" "$work/upgrade/current/$name"
done
echo P07_RELEASE_REHEARSAL_UPGRADE_142_TO_144_PRESERVES_141_AND_142=PASS

mkdir "$work/collision/previous.preserved-0.1.0-release141"
printf 'keep\n' > "$work/collision/previous.preserved-0.1.0-release141/canary"
if run_wrapper "$work/collision" "$next_asset" > "$work/collision.log" 2>&1; then exit 1; fi
test "$(cat "$work/collision/previous.preserved-0.1.0-release141/canary")" = keep
cmp "$work/baseline/current/.runtime-manifest.gitblob" "$work/collision/current/.runtime-manifest.gitblob"
cmp "$work/seed/current/.runtime-manifest.gitblob" "$work/collision/previous/.runtime-manifest.gitblob"
printf 'unknown\n' > "$work/unknown/previous/BUILD_ID"
if run_wrapper "$work/unknown" "$next_asset" > "$work/unknown.log" 2>&1; then exit 1; fi
test "$(cat "$work/unknown/previous/BUILD_ID")" = unknown
cmp "$work/baseline/current/.runtime-manifest.gitblob" "$work/unknown/current/.runtime-manifest.gitblob"
test ! -e "$work/unknown/previous.preserved-0.1.0-release141"
echo P07_RELEASE_REHEARSAL_HISTORY_COLLISION_AND_UNKNOWN_RECOVERY_REFUSED=PASS

cp -a "$work/144" "$work/corrupt"
printf 'tampered\n' >> "$work/corrupt/dist/p07/0.1.0/overlay/lib/migration_safe_batch_cli.py"
if install_inner "$work/corrupt" "$work/post-swap" > "$work/corrupt.log" 2>&1; then exit 1; fi
cmp "$work/baseline/current/.runtime-manifest.gitblob" "$work/post-swap/current/.runtime-manifest.gitblob"
test ! -e "$work/post-swap/previous"
cp -a "$work/144" "$work/fault"
python3 -B - "$work/fault/installers/p07-final.sh" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "if ! verify_installed_current; then"
assert text.count(marker) == 1
path.write_text(text.replace(marker, "if true; then", 1), encoding="utf-8")
PY
if install_inner "$work/fault" "$work/post-swap" > "$work/fault.log" 2>&1; then exit 1; fi
test "$(cat "$work/post-swap/current/BUILD_ID")" = 0.1.0-release142
cmp "$work/baseline/current/.runtime-manifest.gitblob" "$work/post-swap/current/.runtime-manifest.gitblob"
test ! -e "$work/post-swap/previous" && test ! -e "$work/post-swap/current.new"
echo P07_RELEASE_REHEARSAL_TAMPER_AND_POST_SWAP_ROLLBACK=PASS
echo P07_LOCAL_RELEASE_REHEARSAL=PASS