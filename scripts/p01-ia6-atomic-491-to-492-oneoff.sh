#!/usr/bin/env bash
set -Eeuo pipefail
: "$CANDIDATE" "$EXPECTED_SHA" "$READ_TOKEN"
ROOT="/tmp/p01-ia6-atomic-$GITHUB_RUN_ID"
RELEASE="$ROOT/released"; OLD="$ROOT/old"; DIST="$ROOT/dist"
mkdir -p "$RELEASE" "$OLD" "$DIST"
trap 'rm -rf "$ROOT"' EXIT
test "$(git -C "$CANDIDATE" rev-parse HEAD)" = "$EXPECTED_SHA"
GH_TOKEN="$READ_TOKEN" gh release download v2.47.491 --repo llhzx2018/vf-start \
 --pattern 'VF-Start-V2.47.491-FULL.zip' --pattern 'VF_Start_V2.47.491_UPDATE.zip' \
 --dir "$RELEASE" --clobber >/dev/null
unzip -q "$RELEASE/VF-Start-V2.47.491-FULL.zip" -d "$OLD"
unzip -q "$RELEASE/VF_Start_V2.47.491_UPDATE.zip" -d "$RELEASE/repair"
test "$(cat "$OLD/VERSION.txt")" = "2.47.491"
test -s "$RELEASE/repair/repair-v2.47.491.php"
test -f "$OLD/release-manifest.json"
echo "P01_REAL_491_FORMAL_FULL_ATOMIC_BASELINE=PASS"

python3 scripts/p01-maintenance-release.py --candidate "$CANDIDATE/src" \
 --baseline-full "$OLD" --baseline-repair "$RELEASE/repair/repair-v2.47.491.php" \
 --out "$DIST" --version 2.47.492 --source-version 2.47.491 \
 --target-sha "$EXPECTED_SHA" \
 --target-tree "$(git -C "$CANDIDATE" rev-parse HEAD^{tree})" >"$ROOT/receipt.json"
python3 - "$DIST" "$ROOT/receipt.json" <<'PY'
import hashlib,json,sys,zipfile,pathlib
root=pathlib.Path(sys.argv[1]); receipt=json.loads(pathlib.Path(sys.argv[2]).read_text())
for name,h,b in [('full_name','full_sha256','full_bytes'),('update_name','update_sha256','update_bytes')]:
 p=root/receipt[name]; raw=p.read_bytes()
 assert hashlib.sha256(raw).hexdigest()==receipt[h] and len(raw)==receipt[b]
 with zipfile.ZipFile(p) as z:
  files=z.namelist();assert len(set(files))==len(files)
  for f in files:
   assert not f.startswith('/') and '..' not in pathlib.PurePosixPath(f).parts
   assert ((z.getinfo(f).external_attr>>16)&0o170000)!=0o120000
with zipfile.ZipFile(root/receipt['update_name']) as z:
 assert z.namelist()==['repair-v2.47.492.php']
with zipfile.ZipFile(root/receipt['full_name']) as z:
 assert 'VERSION.txt' in z.namelist()
 assert 'app/.runtime.php' not in z.namelist()
 assert not any('.vfnav-data-' in f or f.endswith('.sqlite') for f in z.namelist())
print('P01_REAL_492_FULL_AND_ATOMIC_PACKAGE_SHA_STRUCTURE=PASS')
PY
unzip -q "$DIST/VF_Start_V2.47.492_UPDATE.zip" -d "$DIST/repair"
REPAIR="$DIST/repair/repair-v2.47.492.php"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test >"$ROOT/selftest.json"
python3 - "$ROOT/selftest.json" <<'PY'
import json,sys
a=json.load(open(sys.argv[1])); assert a['ok'] and a['source_files']>100 and a['target_files']>100
print('P01_REAL_492_ATOMIC_SELFTEST=PASS')
PY

install(){
 local dest="$1" port="$2" mode="$3" pid='' csrf='' status=0
 if [ "$mode" = full ];then mkdir "$dest";unzip -q "$DIST/VF-Start-V2.47.492-FULL.zip" -d "$dest"
 else cp -a "$OLD" "$dest";fi
 php -S "127.0.0.1:$port" -t "$dest" >"$ROOT/server-$port.log" 2>&1 &
 pid=$!
 for i in $(seq 1 40);do
  if curl -fsS -c "$ROOT/cookie-$port" -b "$ROOT/cookie-$port" \
   "http://127.0.0.1:$port/setup.php" -o "$ROOT/setup-$port.html" 2>/dev/null;then status=1;break;fi
  sleep 1
 done
 if [ "$status" -ne 1 ];then kill "$pid"||true;return 1;fi
 csrf="$(python3 - "$ROOT/setup-$port.html" <<'PY'
import pathlib,re,sys
s=pathlib.Path(sys.argv[1]).read_text()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s)
assert m
print(m.group(1))
PY
 )"
 curl -fsS -c "$ROOT/cookie-$port" -b "$ROOT/cookie-$port" -X POST \
  "http://127.0.0.1:$port/setup.php" \
  --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=IA6 Synthetic" \
  --data-urlencode "admin_password=SyntheticAtomic!2026" \
  --data-urlencode "admin_password_confirm=SyntheticAtomic!2026" \
  -o "$ROOT/installed-$port.html"
 kill "$pid" 2>/dev/null||true;wait "$pid" 2>/dev/null||true
 test -f "$dest/app/.runtime.php"
 (cd "$dest" && php cli/verify.php)|grep -Fx 'VERIFY_PASS=YES'
}

cat >"$ROOT/sentinel.php" <<'PHP'
<?php
declare(strict_types=1);
$r=realpath($argv[1]);
if(!$r||!str_starts_with($r,'/tmp/p01-ia6-atomic-'))exit(91);
require $r.'/app/bootstrap.php';
$db=vf_db();$repo=new VfRepository($db);
if($argv[2]==='seed'){
 $cat=$repo->createCategory(['name'=>'Synthetic Private','is_private'=>1,'description'=>'','icon'=>'','sort_order'=>0]);
 $x=$repo->saveLink(null,['surface'=>'start','category_id'=>$cat,'title'=>'Atomic Sentinel',
 'url'=>'https://example.org/p01-atomic-sentinel','description'=>'','tags'=>['synthetic'],
 'is_private'=>1,'is_pending'=>0],'admin');
 if(empty($x['id']))exit(92);
}
if((int)$db->query("SELECT COUNT(*) FROM links WHERE url='https://example.org/p01-atomic-sentinel' AND is_private=1")->fetchColumn()!==1)exit(93);
if($db->query('PRAGMA integrity_check')->fetchColumn()!=='ok')exit(94);
if($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)!==[])exit(95);
echo "P01_ATOMIC_SYNTHETIC_PRIVATE_DATA_AND_DB_INTEGRITY=PASS\n";
PHP

install "$ROOT/fresh" 18591 full
test "$(cat "$ROOT/fresh/VERSION.txt")" = 2.47.492
echo "P01_REAL_492_FULL_CLEAN_SETUP=PASS"

install "$ROOT/success" 18592 old
php "$ROOT/sentinel.php" "$ROOT/success" seed
php "$REPAIR" "--verify-source=$ROOT/success" >"$ROOT/source.json"
python3 - "$ROOT/source.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['ok'] is True
PY
php "$REPAIR" "--run=$ROOT/success" >"$ROOT/success.json"
python3 - "$ROOT/success.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); assert r['ok'] is True and r.get('rollback_supported') is True
print('P01_REAL_491_TO_492_ATOMIC_APPLY=PASS')
PY
php "$REPAIR" "--verify-target=$ROOT/success" >"$ROOT/target.json"
python3 - "$ROOT/target.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['ok'] is True
PY
test "$(cat "$ROOT/success/VERSION.txt")" = 2.47.492
php "$ROOT/sentinel.php" "$ROOT/success" check
(cd "$ROOT/success" && php cli/verify.php)|grep -Fx 'VERIFY_PASS=YES'
echo "P01_REAL_ATOMIC_TARGET_AND_DATA_READBACK=PASS"

install "$ROOT/rollback" 18593 old
php "$ROOT/sentinel.php" "$ROOT/rollback" seed
if VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$REPAIR" "--run=$ROOT/rollback" \
 >"$ROOT/expected-error.txt" 2>&1;then echo "INJECTION_UNEXPECTED_PASS";exit 97;fi
test "$(cat "$ROOT/rollback/VERSION.txt")" = 2.47.491
php "$REPAIR" "--verify-source=$ROOT/rollback" >"$ROOT/rollback.json"
python3 - "$ROOT/rollback.json" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['ok'] is True
PY
php "$ROOT/sentinel.php" "$ROOT/rollback" check
(cd "$ROOT/rollback" && php cli/verify.php)|grep -Fx 'VERIFY_PASS=YES'
echo "P01_REAL_ATOMIC_INJECTED_FAILURE_ROLLBACK=PASS"

if grep -Fq 'VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY' "$REPAIR"; then
 install "$ROOT/crash" 18594 old
 php "$ROOT/sentinel.php" "$ROOT/crash" seed
 set +e
 VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$REPAIR" "--run=$ROOT/crash" \
  >"$ROOT/expected-hard-exit.txt" 2>&1
 code=$?
 set -e
 test "$code" -eq 97
 php "$REPAIR" "--run=$ROOT/crash" >"$ROOT/crash.json"
 python3 - "$ROOT/crash.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
assert r['ok'] is True and r.get('interrupted_recovered') is True
print('P01_REAL_ATOMIC_INTERRUPTED_RECOVERY=PASS')
PY
 test "$(cat "$ROOT/crash/VERSION.txt")" = 2.47.492
 php "$ROOT/sentinel.php" "$ROOT/crash" check
 (cd "$ROOT/crash" && php cli/verify.php)|grep -Fx 'VERIFY_PASS=YES'
 echo "P01_REAL_ATOMIC_CRASH_RECOVERY_PRIVATE_DATA=PASS"
else
 echo "P01_REAL_ATOMIC_HARD_EXIT_RECOVERY_UNAVAILABLE=FAIL"
 exit 99
fi
echo "P01_REAL_FULL_ATOMIC_PACKAGE_INSTALL_ROLLBACK_AND_CRASH_RECOVERY=PASS"
