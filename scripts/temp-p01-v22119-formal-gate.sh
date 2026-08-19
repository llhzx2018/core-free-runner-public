#!/usr/bin/env bash
set -Eeuo pipefail
: "${CANDIDATE:?}" "${CANDIDATE_TREE:?}" "${PRODUCTION:?}" "${VERSION:?}" "${SOURCE_VERSION:?}" "${ADMIN_PASS:?}"
OUT="$RUNNER_TEMP/p01-v22119-formal";mkdir -p "$OUT"
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C production rev-parse HEAD)" = "$PRODUCTION"
test "$(tr -d '\r\n' < candidate/src/VERSION.txt)" = "$VERSION"
test "$(tr -d '\r\n' < production/src/VERSION.txt)" = "$SOURCE_VERSION"
find candidate/src -type f -name '*.php' -print0|xargs -0 -n1 php -l >/dev/null
for f in candidate/src/assets/*.js;do node --check "$f";done
python3 scripts/temp-p01-v22119-build.py --candidate candidate/src --production production/src --out "$OUT" --candidate-commit "$CANDIDATE" --candidate-tree "$CANDIDATE_TREE" --production-commit "$PRODUCTION" >/tmp/build.json
jq -e '.status=="BUILD_PASS" and .version==env.VERSION and .source_version==env.SOURCE_VERSION and .candidate_commit==env.CANDIDATE and .candidate_tree==env.CANDIDATE_TREE and .production_commit==env.PRODUCTION' /tmp/build.json >/dev/null
(cd "$OUT"&&sha256sum -c SHA256SUMS.txt >/dev/null);for f in "$OUT"/*.zip;do unzip -t "$f" >/dev/null;done
python3 - <<'PY'
import os,pathlib,re,zipfile
out=pathlib.Path(os.environ['RUNNER_TEMP'])/'p01-v22119-formal';secret=re.compile(rb'(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})')
for p in out.iterdir():
  if not p.is_file():continue
  if secret.search(p.read_bytes()):raise SystemExit('secret-like material detected')
  if p.suffix!='.zip':continue
  with zipfile.ZipFile(p) as z:
    names=z.namelist()
    if len(names)!=len(set(names)):raise SystemExit('duplicate zip member')
    for n in names:
      q=pathlib.PurePosixPath(n)
      if n.startswith('/') or '\\' in n or '..' in q.parts:raise SystemExit('unsafe zip path')
      if any(x in {'.git','PRIVATE_DATA','private_data','node_modules'} for x in q.parts):raise SystemExit('forbidden path')
      if n.lower().endswith(('.sqlite','.sqlite3','.db','.env','.log')):raise SystemExit('runtime/private file in package')
      if ((z.getinfo(n).external_attr>>16)&0o170000)==0o120000:raise SystemExit('symlink member')
repair='repair-v2.21.19.php'
for kind in ('ATOMIC','UPDATE'):
  with zipfile.ZipFile(out/f'VF_Start_V2.21.19_{kind}.zip') as z:
    assert z.namelist()==[repair];assert z.read(repair)==(out/repair).read_bytes()
PY
docker run --rm -v "$OUT:/work:ro" -w /work php:8.0-cli php -l repair-v2.21.19.php >/dev/null
php "$OUT/repair-v2.21.19.php" --self-test >/tmp/selftest.json
jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true and .source_files>0 and .target_files>0' /tmp/selftest.json >/dev/null
php "$OUT/repair-v2.21.19.php" --verify-source=production/src >/tmp/source.json;jq -e '.ok==true' /tmp/source.json >/dev/null
cp -a production/src /tmp/p01-tamper;printf '\n/* P01_V22119_TAMPER */\n' >>/tmp/p01-tamper/app/AdminShell.php
set +e;php "$OUT/repair-v2.21.19.php" --verify-source=/tmp/p01-tamper >/tmp/tamper.out 2>&1;rc=$?;set -e
test "$rc" -ne 0;grep -q 'app/AdminShell.php:sha' /tmp/tamper.out
setup_root(){ local root="$1" port="$2" title="$3";cp -a production/src "$root";php -S 127.0.0.1:$port -t "$root" >/tmp/server-$port.log 2>&1&local pid=$!;for i in $(seq 1 30);do curl -fsS -c /tmp/c-$port http://127.0.0.1:$port/setup.php -o /tmp/s-$port&&break||sleep 1;done;local csrf;csrf=$(python3 - "$port" <<'PY'
import re,sys
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',open('/tmp/s-'+sys.argv[1]).read());assert m;print(m.group(1))
PY
);curl -fsSL -b /tmp/c-$port -c /tmp/c-$port -X POST http://127.0.0.1:$port/setup.php --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=$title" --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null;kill "$pid" 2>/dev/null||true;}
mkdir -p /tmp/p01-fresh;unzip -q "$OUT/VF_Start_V2.21.19_FULL.zip" -d /tmp/p01-fresh
php -S 127.0.0.1:18219 -t /tmp/p01-fresh >/tmp/fresh.log 2>&1&pid=$!;for i in $(seq 1 30);do curl -fsS -c /tmp/fresh.c http://127.0.0.1:18219/setup.php -o /tmp/fresh.html&&break||sleep 1;done
csrf=$(python3 - <<'PY'
import re
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',open('/tmp/fresh.html').read());assert m;print(m.group(1))
PY
);curl -fsSL -b /tmp/fresh.c -c /tmp/fresh.c -X POST http://127.0.0.1:18219/setup.php --data-urlencode "setup_csrf=$csrf" --data-urlencode 'site_title=VF Start V22119 Fresh' --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null;kill "$pid" 2>/dev/null||true
php /tmp/p01-fresh/cli/verify.php|grep -q 'VERIFY_PASS=YES'
php -r 'require "/tmp/p01-fresh/app/bootstrap.php";$d=vf_db();if((int)$d->query("SELECT COUNT(*) FROM categories")->fetchColumn()!==0)exit(1);if((int)$d->query("SELECT COUNT(*) FROM links")->fetchColumn()!==0)exit(2);if(strtolower((string)$d->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(3);'
setup_root /tmp/p01-upgrade 18220 'VF Start Upgrade Gate'
php -r 'require "/tmp/p01-upgrade/app/bootstrap.php";$r=new VfRepository(vf_db());$c=$r->createCategory(["name"=>"V22119 Sentinel","description"=>"synthetic","is_private"=>1]);$r->saveLink(null,["category_id"=>$c,"title"=>"V22119 Preserve","url"=>"https://example.com/v22119-preserve","description"=>"keep","is_private"=>1],"manual");$b=(new VfBackupManager(vf_db()))->create("V22119 pre-upgrade","pre-update",true);file_put_contents("/tmp/backup-key",$b["backup_key"]);if(($b["validation_status"]??"")!=="valid")exit(2);'
php "$OUT/repair-v2.21.19.php" --run=/tmp/p01-upgrade >/tmp/upgrade.json
jq -e '.ok==true and .already_current==false and .schema=="2026080902" and .integrity=="ok" and .fk==0' /tmp/upgrade.json >/dev/null
test "$(tr -d '\r\n' </tmp/p01-upgrade/VERSION.txt)" = "$VERSION";php /tmp/p01-upgrade/cli/verify.php|grep -q 'VERIFY_PASS=YES'
php -r 'require "/tmp/p01-upgrade/app/bootstrap.php";$d=vf_db();$q=$d->prepare("SELECT COUNT(*) FROM links WHERE title=? AND url=?");$q->execute(["V22119 Preserve","https://example.com/v22119-preserve"]);if((int)$q->fetchColumn()!==1)exit(1);$v=(new VfBackupManager($d))->verify(trim(file_get_contents("/tmp/backup-key")));if(($v["validation_status"]??"")!=="valid")exit(2);if(strtolower((string)$d->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(3);if($d->query("PRAGMA foreign_key_check")->fetchAll())exit(4);'
php "$OUT/repair-v2.21.19.php" --run=/tmp/p01-upgrade >/tmp/repeat.json;jq -e '.ok==true and .already_current==true' /tmp/repeat.json >/dev/null
setup_root /tmp/p01-soft 18221 'VF Start Soft Rollback'
set +e;VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$OUT/repair-v2.21.19.php" --run=/tmp/p01-soft >/tmp/soft.out 2>&1;rc=$?;set -e
test "$rc" -ne 0;test "$(tr -d '\r\n' </tmp/p01-soft/VERSION.txt)" = "$SOURCE_VERSION";php /tmp/p01-soft/cli/verify.php|grep -q 'VERIFY_PASS=YES'
setup_root /tmp/p01-hard 18222 'VF Start Hard Recovery'
set +e;VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$OUT/repair-v2.21.19.php" --run=/tmp/p01-hard >/tmp/hard.out 2>&1;rc=$?;set -e
test "$rc" = 97
php "$OUT/repair-v2.21.19.php" --run=/tmp/p01-hard >/tmp/recover.json;jq -e '.ok==true and .already_current==false and .interrupted_recovered==true' /tmp/recover.json >/dev/null
test "$(tr -d '\r\n' </tmp/p01-hard/VERSION.txt)" = "$VERSION";php /tmp/p01-hard/cli/verify.php|grep -q 'VERIFY_PASS=YES'
echo P01_V22119_FORMAL_CANDIDATE_GATE=PASS
