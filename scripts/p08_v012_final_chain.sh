#!/usr/bin/env bash
set -Eeuo pipefail
test "$GITHUB_ACTIONS" = true && test "$P08_ISOLATED_INSTALL_TEST" = YES
test "$(id -u)" != 0
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
source_sha=b77c7e8563d93255f5f4a60bb8c5736a994d8151
target_sha="$P08_BASE010_SHA"
[[ "$target_sha" =~ ^[a-f0-9]{40}$ ]] || exit 3
test "$(git -C p08 rev-parse HEAD)" = "$target_sha"
test "$(git -C p08 rev-parse HEAD^{tree})" = 1c5975bad5b9795998d4afcedec47ba9d52769a4
test "$(cat p08/VERSION)" = 0.1.10
test -z "$(git -C p08 status --porcelain --untracked-files=all)"
tmp="$RUNNER_TEMP/p08-r208-$engine"
mkdir -m 700 "$tmp"
export GH_TOKEN="$P08_PRIVATE_READ_TOKEN"
gh release download v0.1.9 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.9_FULL.zip -D "$tmp" >/dev/null
unset GH_TOKEN
archive="$tmp/VF_AdOps_V0.1.9_FULL.zip"
echo "91a37e0116066bf0df32341cc0708b8b52eaaa998ea556a920b72ff3863a9232  $archive" | sha256sum --check --status
unzip -p "$archive" FULL_MANIFEST.json > "$tmp/019-manifest.json"
python3 - "$tmp/019-manifest.json" <<'PY'
import json,sys,hashlib
b=open(sys.argv[1],"rb").read(); m=json.loads(b)
assert m["source_sha"]=="b77c7e8563d93255f5f4a60bb8c5736a994d8151"
assert m["target_version"]=="0.1.9" and m["type"]=="CLEAN_FULL_ONLY"
assert m["data_included"] is False and len(m["files"])>6100
print("P08_R208_REAL_OFFICIAL_V019_FULL_SHA_MANIFEST=PASS")
print("P08_R208_PREVIOUS_MANIFEST_SHA256="+hashlib.sha256(b).hexdigest())
PY
prev="$(sha256sum "$tmp/019-manifest.json" | cut -d' ' -f1)"
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
  python3 -B p08/scripts/build_full.py --source p08 --output "$tmp/010-full-$part.zip" --version 0.1.10 --source-sha "$target_sha" --governance-root gov
  python3 -B p08/scripts/build_atomic.py --source p08 --output "$tmp/010-update-$part.zip" --source-version 0.1.9 --source-sha "$source_sha" --source-full-manifest-sha256 "$prev" --previous-full-manifest "$tmp/019-manifest.json" --target-version 0.1.10 --target-sha "$target_sha"
done
cmp "$tmp/010-full-A.zip" "$tmp/010-full-B.zip"
cmp "$tmp/010-update-A.zip" "$tmp/010-update-B.zip"
python3 - "$tmp/010-update-A.zip" "$tmp/010-full-A.zip" "$tmp/019-manifest.json" "$target_sha" <<'PY'
import json,hashlib,sys,zipfile
a,f,m,t=sys.argv[1:]
with zipfile.ZipFile(a) as z:
    x=json.loads(z.read("ATOMIC_MANIFEST.json"))
    assert x["source_version"]=="0.1.9" and x["target_version"]=="0.1.10"
    assert x["source_sha"]=="b77c7e8563d93255f5f4a60bb8c5736a994d8151"
    assert x["target_sha"]==t and x["schema_changes"] is False
    assert x["source_full_manifest_sha256"]==hashlib.sha256(open(m,"rb").read()).hexdigest()
    assert z.testzip() is None
with zipfile.ZipFile(f) as z:
    x=json.loads(z.read("FULL_MANIFEST.json"))
    assert x["target_version"]=="0.1.10" and x["source_sha"]==t and z.testzip() is None
print("P08_R208_TRUE_FULL_AND_ATOMIC_DOUBLE_BUILD_SCHEMA_EXACT=PASS")
print("P08_R208_ATOMIC_SHA256="+hashlib.sha256(open(a,"rb").read()).hexdigest())
print("P08_R208_FULL_SHA256="+hashlib.sha256(open(f,"rb").read()).hexdigest())
PY
python3 - "$tmp/r208-native.php" "$target_sha" <<'PY'
from pathlib import Path
import sys
s=Path("p08/tests/compatibility/r154_clean_full_to_two_native_atomic_cycles.php").read_text()
items=[
("'0.1.5':($phase==='recover'?'0.1.7':'0.1.6')","'0.1.9':($phase==='recover'?'0.1.10':'0.1.9')",1),
("trim((string)file_get_contents($site.'/current/VERSION'))!=='0.1.6'","trim((string)file_get_contents($site.'/current/VERSION'))!=='0.1.10'",1),
("'target_version'=>'0.1.7'","'target_version'=>'0.1.10'",1),
("str_repeat('1',40)","'"+sys.argv[2]+"'",1),
("str_repeat('2',40)","'"+sys.argv[2]+"'",4),
]
for before,after,n in items:
    assert s.count(before)==n,(before,s.count(before))
    s=s.replace(before,after)
Path(sys.argv[1]).write_text(s)
PY
php -l "$tmp/r208-native.php"
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
  media="$site/storage/app/private/adops/r202-media-proof.bin"
  printf 'R208_SYNTHETIC_MEDIA_%s\n' "$phase" > "$media"
  chmod 0600 "$media"
  mh="$(sha256sum "$media" | cut -d' ' -f1)"
  if [[ "$phase" == first ]]; then
    P08_R154_NATIVE=YES php "$tmp/r208-native.php" first "$site" "$source_sha" "$tmp/010-update-A.zip"
    test "$(readlink "$site/current")" = "releases/$target_sha"
    test "$(cat "$site/current/VERSION")" = 0.1.10
    echo "P08_R208_$engine"_OFFICIAL_019_TO_010_BACKUP_ATOMIC_OWNER_TOKEN=PASS
    # This is the exact missed journey: the user DID NOT freshly install v0.1.10.
    # All inputs come from immutable issued GitHub Releases. Never edit the site.
    export GH_TOKEN="$P08_PRIVATE_READ_TOKEN"
    gh release download v0.1.10 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.10_FULL.zip -D "$tmp" >/dev/null
    gh release download v0.1.11 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.11_UPDATE.zip -D "$tmp" >/dev/null
    gh api repos/llhzx2018/core-updates/contents/projects/P08-ADOPS.json --jq .content | base64 -d > "$tmp/live-channel.json"
    gh api repos/llhzx2018/vf-adops/releases/tags/v0.1.11 > "$tmp/live-release.json"
    gh api repos/llhzx2018/vf-adops/git/ref/tags/v0.1.11 > "$tmp/live-tag.json"
    unset GH_TOKEN
    printf '%s  %s\n' "170dc7c46ff724061fa4264565e6ccac73d1c2a2b96c9c5525022e8348ae2ae1" "$tmp/VF_AdOps_V0.1.10_FULL.zip" | sha256sum --check --status
    printf '%s  %s\n' "5d2ddeab283f0220dcc90d1f163d392c203677995518bcda6d77f60b8c6b1d08" "$tmp/VF_AdOps_V0.1.11_UPDATE.zip" | sha256sum --check --status
    python3 - "$site/current/FULL_MANIFEST.json" "$tmp/VF_AdOps_V0.1.10_FULL.zip" "$tmp/VF_AdOps_V0.1.11_UPDATE.zip" "$tmp/live-channel.json" <<'PY'
import hashlib,json,sys,zipfile
live,clean,update,channel=sys.argv[1:]
b=open(live,'rb').read(); actual=json.loads(b)
with zipfile.ZipFile(clean) as z: official=z.read('FULL_MANIFEST.json')
with zipfile.ZipFile(update) as z: am=json.loads(z.read('ATOMIC_MANIFEST.json'))
meta=json.load(open(channel))
h=lambda x:hashlib.sha256(x).hexdigest()
assert actual["source_sha"]=="ef78dcb21117c822e2756360280f2418f794704f"
assert actual["target_version"]=="0.1.10"
assert h(official)=="ab7f6b6f5e484c8efdf96d1b0a531b114d2ac1b1a3b45e52a072345a2ea0f110"
assert meta['source_full_manifest_sha256']==h(official)
assert am['source_full_manifest_sha256']==h(official)
assert h(b)!=h(official), "Unexpectedly identical; full lineage bug not reproduced"
actualpaths={v['path']:v['sha256'] for v in actual['files']}
officialpaths={v['path']:v['sha256'] for v in json.loads(official)['files']}
diff=sorted(p for p in set(actualpaths)|set(officialpaths) if actualpaths.get(p)!=officialpaths.get(p))
assert 'CLOUDPANEL_INSTALL.txt' in diff
print('P08_R208_ACTUAL_ATOMIC_010_MANIFEST_SHA256='+h(b))
print('P08_R208_OFFICIAL_CLEAN_010_MANIFEST_SHA256='+h(official))
print('P08_R208_LEGITIMATE_ATOMIC_LINEAGE_SOURCE_MISMATCH=REPRODUCED')
print('P08_R208_DIFFERENT_INDEX_PATH_COUNT='+str(len(diff)))
print('P08_R208_DIFFERENT_PATHS='+','.join(diff[:12]))
PY
    P08_R145_ISOLATED=YES php -r '
      $site=$argv[1];$tmp=$argv[2];
      require $site."/current/vendor/autoload.php";
      $transport=static function($url,$accept)use($tmp){
        $part=str_contains($url,"contents/projects/")?"live-channel.json":(str_contains($url,"releases/tags/")?"live-release.json":"live-tag.json");
        return [200,(string)file_get_contents($tmp."/".$part)];
      };
      $g=new \VF\AdOps\Upgrade\OwnerNextReleaseGateway($transport);
      $installed=$g->installed($site);
      try{$g->check(str_repeat("Z",40),$installed);}catch(\RuntimeException $e){
        if($e->getMessage()==="P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED"){
          echo "P08_R208_REAL_ISSUED_010_CLIENT_REFUSES_NEXT_V011=PASS\n";exit(0);
        }
        echo "P08_R208_UNEXPECTED_FAILURE_CODE=".$e->getMessage()."\n";exit(3);
      }
      echo "P08_R208_UNEXPECTEDLY_ACCEPTED=FAIL\n";exit(4);
    ' -- "$site" "$tmp"

    # Reconstruct the new candidate on the disposable machine from its exact
    # private source, while the installed site is still running old v0.1.10 PHP.
    test "$(cat target/VERSION)" = 0.1.12
    test "$(git -C target rev-parse HEAD)" = "$P08_FINAL012_SHA"
    composer install --working-dir=target --no-dev --no-scripts --prefer-dist --no-interaction --no-progress --optimize-autoloader
    npm ci --prefix target --ignore-scripts --no-audit --no-fund
    npm run typecheck --prefix target
    npm run test:unit --prefix target
    npm run build --prefix target
    php target/tests/test_owner_next_release_gateway.php
    php target/tests/test_owner_check_failure_classes.php
    (cd target && composer check-platform-reqs --no-dev)
    test -z "$(git -C target status --porcelain --untracked-files=all)"
    actual="$(sha256sum "$site/current/FULL_MANIFEST.json" | cut -d' ' -f1)"
    test "$actual" = efebfefde3115864dba71c2e56fedae2f7ada8ad4064010473d716b689f67fe9
    for part in A B; do
      python3 -B target/scripts/build_full.py --source target --output "$tmp/012-full-$part.zip" --version 0.1.12 --source-sha "$P08_FINAL012_SHA" --governance-root gov
      python3 -B target/scripts/build_atomic.py --source target --output "$tmp/012-update-$part.zip" --source-version 0.1.10 --source-sha "$target_sha" --source-full-manifest-sha256 "$actual" --previous-full-manifest "$site/current/FULL_MANIFEST.json" --target-version 0.1.12 --target-sha "$P08_FINAL012_SHA"
    done
    cmp "$tmp/012-full-A.zip" "$tmp/012-full-B.zip"
    cmp "$tmp/012-update-A.zip" "$tmp/012-update-B.zip"
    python3 - "$tmp/012-update-A.zip" "$actual" "$P08_FINAL012_SHA" <<'PY'
import json,sys,zipfile
name,digest,target=sys.argv[1:]
with zipfile.ZipFile(name) as z:
    m=json.loads(z.read('ATOMIC_MANIFEST.json'))
    indexed={x['path'] for x in m['files']}
    assert m['source_version']=='0.1.10'
    assert m['source_full_manifest_sha256']==digest
    assert m['target_version']=='0.1.12' and m['target_sha']==target
    assert not ({'CLOUDPANEL_INSTALL.txt','public/setup.php','public/p08-install-build.txt','.env.example'} & indexed)
    assert z.testzip() is None
print('P08_R208_GENUINE_010_LINEAGE_BACKCOMPAT_STAGE=PASS')
PY
    P08_R205_CHAINED=YES php target/tests/compatibility/r205_chained_atomic_apply.php \
      "$site" "$target_sha" "$actual" "$tmp/012-update-A.zip" "$P08_FINAL012_SHA" 0.1.12
    echo "P08_R208_$engine"_REAL_019_TO_010_TO_012_SOURCE_BACKCOMPAT=PASS

    # The newly installed v0.1.12 PHP can now stage full target metadata.
    # Synthetic v0.1.13 is an isolated successor, NOT a released version.
    cp -a target "$tmp/synthetic-013"
    printf '0.1.13\n' > "$tmp/synthetic-013/VERSION"
    sed -i 's/0\.1\.12/0.1.13/g' "$tmp/synthetic-013/CLOUDPANEL_INSTALL.txt" "$tmp/synthetic-013/public/p08-install-build.txt"
    synthetic_sha="$(printf '3%.0s' {1..40})"
    new_source_digest="$(sha256sum "$site/current/FULL_MANIFEST.json" | cut -d' ' -f1)"
    python3 - "$tmp/synthetic-013" "$tmp/013-synthetic-full.zip" "$synthetic_sha" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0,"target/scripts")
from build_full import write_full
source,dest,sha=sys.argv[1:]
result=write_full(Path(source),Path(dest),"0.1.13",sha)
assert result["status"]=="FULL_BUILT_NOT_RELEASED"
print("P08_R208_SYNTHETIC_ONLY_FULL=PASS")
PY
    python3 -B target/scripts/build_atomic.py --source "$tmp/synthetic-013" --output "$tmp/013-synthetic-update.zip" --source-version 0.1.12 --source-sha "$P08_FINAL012_SHA" --source-full-manifest-sha256 "$new_source_digest" --previous-full-manifest "$site/current/FULL_MANIFEST.json" --target-version 0.1.13 --target-sha "$synthetic_sha"
    python3 - "$tmp/013-synthetic-update.zip" <<'PY'
import json,zipfile,sys
with zipfile.ZipFile(sys.argv[1]) as z:
    paths={i['path'] for i in json.loads(z.read('ATOMIC_MANIFEST.json'))['files']}
    assert {'CLOUDPANEL_INSTALL.txt','public/setup.php','public/p08-install-build.txt','.env.example'} <= paths
print('P08_R208_FUTURE_ATOMIC_COMPLETE_TARGET_METADATA=PASS')
PY
    P08_R205_CHAINED=YES php target/tests/compatibility/r205_chained_atomic_apply.php \
      "$site" "$P08_FINAL012_SHA" "$new_source_digest" "$tmp/013-synthetic-update.zip" "$synthetic_sha" 0.1.13
    unzip -p "$tmp/013-synthetic-full.zip" FULL_MANIFEST.json > "$tmp/013-canonical.json"
    cmp "$tmp/013-canonical.json" "$site/current/FULL_MANIFEST.json"
    echo "P08_R208_$engine"_FUTURE_ATOMIC_MANIFEST_EQUALS_CLEAN_FULL=PASS

  elif [[ "$phase" == fault ]]; then
    P08_R154_NATIVE=YES php "$tmp/r208-native.php" fault "$site" "$source_sha" "$tmp/010-update-A.zip"
    test "$(readlink "$site/current")" = "releases/$source_sha"
    echo "P08_R208_$engine"_AFTER_SWAP_FAULT_ROLLBACK=PASS
  else
    set +e
    P08_R154_NATIVE=YES P08_R131_DISPOSABLE=YES php "$tmp/r208-native.php" kill "$site" "$source_sha" "$tmp/010-update-A.zip"
    ec=$?
    set -e
    test "$ec" -eq 137
    P08_R154_NATIVE=YES php "$tmp/r208-native.php" recover "$site" "$source_sha" "$tmp/010-update-A.zip"
    test "$(readlink "$site/current")" = "releases/$source_sha"
    echo "P08_R208_$engine"_SIGKILL_INDEPENDENT_WORKER_RECOVERY=PASS
  fi
  test "$(sha256sum "$media" | cut -d' ' -f1)" = "$mh"
  echo "P08_R208_$engine"_"$phase"_SHARED_MEDIA_UNCHANGED=PASS
done
echo "P08_R208_$engine"_REAL_NATIVE_019_TO_010_FULL_ATOMIC=PASS
