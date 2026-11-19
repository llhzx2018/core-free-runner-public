#!/usr/bin/env bash
set -Eeuo pipefail
test "$GITHUB_ACTIONS" = true && test "$P08_ISOLATED_INSTALL_TEST" = YES
test "$(id -u)" != 0
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
source_sha=ef78dcb21117c822e2756360280f2418f794704f
target_sha="$P08_TARGET_SHA"
[[ "$target_sha" =~ ^[a-f0-9]{40}$ ]] || exit 3
test "$(git -C p08 rev-parse HEAD)" = "$target_sha"
test "$(git -C p08 rev-parse HEAD^{tree})" = 675c73951b42adeaf5d52de8af836baaa616437c
test "$(cat p08/VERSION)" = 0.1.11
test -z "$(git -C p08 status --porcelain --untracked-files=all)"
tmp="$RUNNER_TEMP/p08-r198-$engine"
mkdir -m 700 "$tmp"
export GH_TOKEN="$P08_PRIVATE_READ_TOKEN"
gh release download v0.1.10 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.10_FULL.zip -D "$tmp" >/dev/null
unset GH_TOKEN
archive="$tmp/VF_AdOps_V0.1.10_FULL.zip"
echo "170dc7c46ff724061fa4264565e6ccac73d1c2a2b96c9c5525022e8348ae2ae1  $archive" | sha256sum --check --status
unzip -p "$archive" FULL_MANIFEST.json > "$tmp/010-manifest.json"
python3 - "$tmp/010-manifest.json" <<'PY'
import json,sys,hashlib
b=open(sys.argv[1],"rb").read(); m=json.loads(b)
assert m["source_sha"]=="ef78dcb21117c822e2756360280f2418f794704f"
assert m["target_version"]=="0.1.10" and m["type"]=="CLEAN_FULL_ONLY"
assert m["data_included"] is False and len(m["files"])>6100
print("P08_R198_REAL_OFFICIAL_V010_FULL_SHA_MANIFEST=PASS")
print("P08_R198_PREVIOUS_MANIFEST_SHA256="+hashlib.sha256(b).hexdigest())
PY
prev="$(sha256sum "$tmp/010-manifest.json" | cut -d' ' -f1)"
composer install --working-dir=p08 --no-dev --no-scripts --prefer-dist --no-interaction --no-progress --optimize-autoloader
npm ci --prefix p08 --ignore-scripts --no-audit --no-fund
npm run typecheck --prefix p08
npm run build --prefix p08
npm run test:unit --prefix p08
(cd p08 && composer check-platform-reqs --no-dev)
test -z "$(git -C p08 status --porcelain --untracked-files=all)"
php p08/tests/test_owner_next_release_gateway.php
php p08/tests/test_owner_future_atomic_status.php
php p08/tests/test_setup_guard.php
python3 -B p08/scripts/check_stack_contract.py --phase full --root p08
for part in A B; do
  python3 -B p08/scripts/build_full.py --source p08 --output "$tmp/011-full-$part.zip" --version 0.1.11 --source-sha "$target_sha" --governance-root gov
  python3 -B p08/scripts/build_atomic.py --source p08 --output "$tmp/011-update-$part.zip" --source-version 0.1.10 --source-sha "$source_sha" --source-full-manifest-sha256 "$prev" --previous-full-manifest "$tmp/010-manifest.json" --target-version 0.1.11 --target-sha "$target_sha"
done
cmp "$tmp/011-full-A.zip" "$tmp/011-full-B.zip"
cmp "$tmp/011-update-A.zip" "$tmp/011-update-B.zip"
python3 - "$tmp/011-update-A.zip" "$tmp/011-full-A.zip" "$tmp/010-manifest.json" "$target_sha" <<'PY'
import json,hashlib,sys,zipfile
a,f,m,t=sys.argv[1:]
with zipfile.ZipFile(a) as z:
    x=json.loads(z.read("ATOMIC_MANIFEST.json"))
    assert x["source_version"]=="0.1.10" and x["target_version"]=="0.1.11"
    assert x["source_sha"]=="ef78dcb21117c822e2756360280f2418f794704f"
    assert x["target_sha"]==t and x["schema_changes"] is False
    assert x["source_full_manifest_sha256"]==hashlib.sha256(open(m,"rb").read()).hexdigest()
    assert z.testzip() is None
with zipfile.ZipFile(f) as z:
    x=json.loads(z.read("FULL_MANIFEST.json"))
    assert x["target_version"]=="0.1.11" and x["source_sha"]==t and z.testzip() is None
print("P08_R198_TRUE_FULL_AND_ATOMIC_DOUBLE_BUILD_SCHEMA_EXACT=PASS")
print("P08_R198_ATOMIC_SHA256="+hashlib.sha256(open(a,"rb").read()).hexdigest())
print("P08_R198_FULL_SHA256="+hashlib.sha256(open(f,"rb").read()).hexdigest())
PY
python3 - "$tmp/r198-native.php" "$target_sha" <<'PY'
from pathlib import Path
import sys
s=Path("p08/tests/compatibility/r154_clean_full_to_two_native_atomic_cycles.php").read_text()
items=[
("'0.1.5':($phase==='recover'?'0.1.7':'0.1.6')","'0.1.10':($phase==='recover'?'0.1.11':'0.1.10')",1),
("trim((string)file_get_contents($site.'/current/VERSION'))!=='0.1.6'","trim((string)file_get_contents($site.'/current/VERSION'))!=='0.1.11'",1),
("'target_version'=>'0.1.7'","'target_version'=>'0.1.11'",1),
("str_repeat('1',40)","'"+sys.argv[2]+"'",1),
("str_repeat('2',40)","'"+sys.argv[2]+"'",4),
]
for before,after,n in items:
    assert s.count(before)==n,(before,s.count(before))
    s=s.replace(before,after)
Path(sys.argv[1]).write_text(s)
PY
php -l "$tmp/r198-native.php"
for phase in first fault kill; do
  site="$RUNNER_TEMP/p08-r129-real-issued-r131-r155-$engine-$phase"
  mkdir -m 700 "$site"
  unzip -q "$archive" -d "$site"
  mkdir -p "$site/tests/compatibility"
  cp p08/tests/test_install_sqlite_e2e.php p08/tests/test_install_mysql_e2e.php "$site/tests/"
  cp p08/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
  if [[ "$engine" == sqlite ]]; then
    php "$site/tests/test_install_sqlite_e2e.php"
  else
    export P08_TEST_DB_DRIVER="$engine" P08_TEST_DB_HOST=127.0.0.1
    export P08_TEST_DB_CLEAN="p08_ci_$engine"_"$phase" P08_TEST_DB_DIRTY="p08_ci_$engine"_dirty_"$phase"
    export P08_TEST_DB_USER=root P08_TEST_DB_PASSWORD=synthetic-only-p08-ci-pass
    php p08/tests/fixtures/create_ci_databases.php
    php "$site/tests/test_install_mysql_e2e.php"
  fi
  test "$(readlink "$site/current")" = "releases/$source_sha"
  token="$site/storage/app/private/adops/upgrade/github-read-token"
  if [[ "$phase" == first ]]; then
    rm -f -- "$token"
  else
    mkdir -p "$(dirname "$token")"
    printf 'github_pat_%s\n' "$(printf '%040d' 0 | tr 0 Q)" > "$token"
    chmod 0600 "$token"
  fi
  media="$site/storage/app/private/adops/r198-media-proof.bin"
  printf 'R198_SYNTHETIC_MEDIA_%s\n' "$phase" > "$media"
  chmod 0600 "$media"
  mh="$(sha256sum "$media" | cut -d' ' -f1)"
  if [[ "$phase" == first ]]; then
    P08_R154_NATIVE=YES php "$tmp/r198-native.php" first "$site" "$source_sha" "$tmp/011-update-A.zip"
    test "$(readlink "$site/current")" = "releases/$target_sha"
    test "$(cat "$site/current/VERSION")" = 0.1.11
    echo "P08_R198_$engine"_OFFICIAL_010_TO_011_BACKUP_ATOMIC_OWNER_TOKEN=PASS
  elif [[ "$phase" == fault ]]; then
    P08_R154_NATIVE=YES php "$tmp/r198-native.php" fault "$site" "$source_sha" "$tmp/011-update-A.zip"
    test "$(readlink "$site/current")" = "releases/$source_sha"
    echo "P08_R198_$engine"_AFTER_SWAP_FAULT_ROLLBACK=PASS
  else
    set +e
    P08_R154_NATIVE=YES P08_R131_DISPOSABLE=YES php "$tmp/r198-native.php" kill "$site" "$source_sha" "$tmp/011-update-A.zip"
    ec=$?
    set -e
    test "$ec" -eq 137
    P08_R154_NATIVE=YES php "$tmp/r198-native.php" recover "$site" "$source_sha" "$tmp/011-update-A.zip"
    test "$(readlink "$site/current")" = "releases/$source_sha"
    echo "P08_R198_$engine"_SIGKILL_INDEPENDENT_WORKER_RECOVERY=PASS
  fi
  test "$(sha256sum "$media" | cut -d' ' -f1)" = "$mh"
  echo "P08_R198_$engine"_"$phase"_SHARED_MEDIA_UNCHANGED=PASS
done
echo "P08_R198_$engine"_REAL_NATIVE_010_TO_011_FULL_ATOMIC=PASS
