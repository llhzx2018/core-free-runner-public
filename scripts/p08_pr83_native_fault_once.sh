#!/usr/bin/env bash
# Source-bound, disposable v0.1.13 -> unissued v0.1.14 after-swap/SIGKILL regression.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
origin="98f219f386eb2a29b6ba75a2cf2994cc4057af85"
issued="8b385fecd132a02ac79f5b67e670783e98997c3e"
asset_sha="f8075f065d1413c984f80ef7531242cfc894bf272e90f6d89282074f6617c1ec"
[[ "$(git -C p08 rev-parse HEAD)" == "$origin" && "$(cat p08/VERSION)" == 0.1.13 ]] || exit 3
tmp="$RUNNER_TEMP/p08-r131-fault-$engine"
[[ ! -e "$tmp" ]] || exit 3
umask 077
mkdir -m 700 "$tmp"
log="$tmp/private.log"
phase(){
  local name="$1"; shift
  if "$@" >>"$log" 2>&1; then
    echo "P08_PR83_FAULT_$engine"_"$name=PASS"
  else
    echo "P08_PR83_FAULT_$engine"_"$name=FAIL"
    exit 43
  fi
}
phase DOWNLOAD_ISSUED_013 gh release download v0.1.13 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.13_FULL.zip -D "$tmp"
archive="$tmp/VF_AdOps_V0.1.13_FULL.zip"
printf '%s  %s\n' "$asset_sha" "$archive" | sha256sum -c --status || exit 4
unzip -p "$archive" FULL_MANIFEST.json > "$tmp/source-manifest.json"
python3 - "$tmp/source-manifest.json" "$issued" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
assert j["target_version"]=="0.1.13" and j["source_sha"]==sys.argv[2]
assert j["type"]=="CLEAN_FULL_ONLY" and j["project_id"]=="P08"
PY
digest="$(sha256sum "$tmp/source-manifest.json" | cut -d' ' -f1)"
phase COMPOSER composer install --working-dir=p08 --no-dev --no-scripts --prefer-dist --no-interaction --no-progress --optimize-autoloader
phase NODE npm ci --prefix p08 --ignore-scripts --no-audit --no-fund
phase ASSETS npm run build --prefix p08
python3 - <<'PY'
from pathlib import Path
a=Path('p08/VERSION')
assert a.read_text()=='0.1.13\n'
a.write_text('0.1.14\n')
p=Path('p08/public/p08-install-build.txt')
s=p.read_text()
assert '0.1.13' in s
p.write_text(s.replace('0.1.13','0.1.14').replace('DEVELOPMENT_CANDIDATE_NOT_ISSUED','ISOLATED_NOT_RELEASED'))
PY
git -C p08 config user.name "Ephemeral-P08-test"
git -C p08 config user.email "ephemeral-p08@invalid.example"
phase EPHEMERAL_GIT_ADD git -C p08 add VERSION public/p08-install-build.txt
phase EPHEMERAL_GIT_COMMIT git -C p08 commit -m "isolated unissued v0.1.14 fixture only"
target="$(git -C p08 rev-parse HEAD)"
[[ "$target" =~ ^[a-f0-9]{40}$ && "$target" != "$issued" ]] || exit 4
phase CANONICAL_FULL python3 -B p08/scripts/build_full.py --source p08 --output "$tmp/014-full.zip" --version 0.1.14 --source-sha "$target" --governance-root gov
phase NATIVE_ATOMIC_BUILD python3 -B p08/scripts/build_atomic.py --source p08 --output "$tmp/014-update.zip" --source-version 0.1.13 --source-sha "$issued" --source-full-manifest-sha256 "$digest" --previous-full-manifest "$tmp/source-manifest.json" --target-version 0.1.14 --target-sha "$target"
# Adapt only fixture version and SHA literals from the project's R154 test, never product code.
python3 - "$target" "$tmp/r154-version-adapted.php" <<'PY'
import sys
from pathlib import Path
s=Path('p08/tests/compatibility/r154_clean_full_to_two_native_atomic_cycles.php').read_text()
before="($phase==='first'?'0.1.5':($phase==='recover'?'0.1.7':'0.1.6'))"
assert s.count(before)==1
s=s.replace(before,"($phase==='recover'?'0.1.14':'0.1.13')")
for key,value,count in [
 ("'0.1.6'","'0.1.14'",1),
 ("'0.1.7'","'0.1.14'",1),
 ("str_repeat('1',40)","'"+sys.argv[1]+"'",1),
 ("str_repeat('2',40)","'"+sys.argv[1]+"'",4)]:
    assert s.count(key)==count,(key,s.count(key))
    s=s.replace(key,value)
Path(sys.argv[2]).write_text(s)
PY
phase CHECK_ADAPTED_HARNESS php -l "$tmp/r154-version-adapted.php"
for operation in fault kill; do
  site="$RUNNER_TEMP/p08-r129-real-issued-r131-r155-$engine-$operation"
  [[ ! -e "$site" ]] || exit 3
  mkdir -m 700 "$site"
  phase EXTRACT unzip -q "$archive" -d "$site"
  mkdir -p "$site/tests/compatibility" "$site/tests/fixtures"
  cp p08/tests/test_install_sqlite_e2e.php p08/tests/test_install_mysql_e2e.php "$site/tests/"
  cp p08/tests/fixtures/create_ci_databases.php "$site/tests/fixtures/"
  cp p08/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
  if [[ "$engine" == sqlite ]]; then
    phase REAL_INSTALL php "$site/tests/test_install_sqlite_e2e.php"
  else
    export P08_TEST_DB_DRIVER="$engine" P08_TEST_DB_HOST=127.0.0.1
    export P08_TEST_DB_CLEAN="p08_ci_$engine"_"$operation" P08_TEST_DB_DIRTY="p08_ci_$engine"_dirty_"$operation"
    export P08_TEST_DB_USER=root P08_TEST_DB_PASSWORD=p08-pr83-isolated-only
    phase NATIVE_DATABASE php "$site/tests/fixtures/create_ci_databases.php"
    phase REAL_INSTALL php "$site/tests/test_install_mysql_e2e.php"
  fi
  [[ "$(readlink "$site/current")" == "releases/$issued" ]] || exit 5
  token="$site/storage/app/private/adops/upgrade/github-read-token"
  mkdir -p "$(dirname "$token")"
  printf 'github_pat_%s\n' "$(printf '%040d' 0 | tr 0 Q)" > "$token"
  chmod 0600 "$token"
  media="$site/storage/app/private/adops/r202-media-proof.bin"
  printf 'P08_SYNTHETIC_MEDIA_%s_%s\n' "$engine" "$operation" > "$media"
  chmod 0600 "$media"
  token_before="$(sha256sum "$token" | cut -d' ' -f1)"
  media_before="$(sha256sum "$media" | cut -d' ' -f1)"
  if [[ "$operation" == fault ]]; then
    phase AFTER_SWAP_FAULT_NATIVE_ROLLBACK env P08_R154_NATIVE=YES php "$tmp/r154-version-adapted.php" fault "$site" "$issued" "$tmp/014-update.zip"
  else
    set +e
    env P08_R154_NATIVE=YES P08_R131_DISPOSABLE=YES php "$tmp/r154-version-adapted.php" kill "$site" "$issued" "$tmp/014-update.zip" >>"$log" 2>&1
    code=$?
    set -e
    [[ "$code" == 137 ]] || { echo "P08_PR83_FAULT_$engine"_ACTUAL_SIGKILL_EXIT_137=FAIL;exit 45; }
    echo "P08_PR83_FAULT_$engine"_ACTUAL_SIGKILL_EXIT_137=PASS
    phase INDEPENDENT_OWNER_WORKER_RECOVERY env P08_R154_NATIVE=YES php "$tmp/r154-version-adapted.php" recover "$site" "$issued" "$tmp/014-update.zip"
  fi
  [[ "$(readlink "$site/current")" == "releases/$issued" ]] || exit 46
  [[ "$(sha256sum "$token" | cut -d' ' -f1)" == "$token_before" ]] || exit 47
  [[ "$(sha256sum "$media" | cut -d' ' -f1)" == "$media_before" ]] || exit 48
  [[ ! -f "$site/storage/app/private/adops/maintenance/maintenance.json" ]] || exit 49
  echo "P08_PR83_FAULT_$engine"_"$operation"_OFFICIAL_SOURCE_RESTORED_AND_OWNER_MEDIA_SAFE=PASS
done
echo "P08_PR83_FAULT_$engine"_CANDIDATE_NOT_ISSUED=CONFIRMED
echo "P08_PR83_FAULT_$engine"_REAL_HTTPS_BROWSER=NOT_RUN
echo "P08_PR83_FAULT_$engine"_FORMAL_RELEASE_READY=NO
