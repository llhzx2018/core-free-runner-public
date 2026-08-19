#!/usr/bin/env bash
set -Eeuo pipefail

: "${CANDIDATE:?}"
: "${CANDIDATE_TREE:?}"
: "${PRODUCTION:?}"
: "${VERSION:?}"
: "${SOURCE_VERSION:?}"
: "${SCHEMA:?}"
: "${RUNNER_TEMP:?}"

OUT="$RUNNER_TEMP/p01-v22121-artifact-gate"
REPAIR="$OUT/repair-v2.21.21.php"
rm -rf "$OUT" && mkdir -p "$OUT"

python3 runner/scripts/p01-build-maintenance-candidate-22121.py \
  --candidate candidate/src \
  --production production/src \
  --out "$OUT" \
  --candidate-commit "$CANDIDATE" \
  --candidate-tree "$CANDIDATE_TREE" \
  --production-commit "$PRODUCTION" \
  > "$RUNNER_TEMP/p01-v22121-build.json"

jq -e \
  --arg c "$CANDIDATE" --arg t "$CANDIDATE_TREE" --arg p "$PRODUCTION" \
  '.status=="BUILD_PASS" and .version=="2.21.21" and .source_version=="2.21.20" and .candidate_commit==$c and .candidate_tree==$t and .production_commit==$p and .runtime_added==["assets/data-recovery.js","assets/update-reload.js"] and (.runtime_delta|length)==23' \
  "$RUNNER_TEMP/p01-v22121-build.json" >/dev/null
echo 'DETERMINISTIC_FORMAL_BUILD=PASS'

(cd "$OUT" && sha256sum -c SHA256SUMS.txt >/dev/null)
for f in "$OUT"/*.zip; do unzip -t "$f" >/dev/null; done
python3 - "$OUT" <<'PY'
import pathlib,re,sys,zipfile
out=pathlib.Path(sys.argv[1])
forbidden_parts={'.git','PRIVATE_DATA','private_data','node_modules'}
forbidden_suffixes={'.sqlite','.sqlite3','.db','.env','.log'}
secret=re.compile(rb'(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|VF_PRIVATE_READ_TOKEN\s*=\s*[^\s]+|VF_RELEASE_WRITE_TOKEN\s*=\s*[^\s]+)')
for p in out.iterdir():
    if not p.is_file():
        continue
    data=p.read_bytes()
    if secret.search(data):
        raise SystemExit(f'secret-like payload in {p.name}')
    if p.suffix!='.zip':
        continue
    with zipfile.ZipFile(p) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):
            raise SystemExit(f'duplicate member: {p.name}')
        for n in names:
            q=pathlib.PurePosixPath(n)
            if n.startswith('/') or '\\' in n or '..' in q.parts:
                raise SystemExit(f'unsafe path: {p.name}:{n}')
            if any(x in forbidden_parts for x in q.parts):
                raise SystemExit(f'forbidden path: {p.name}:{n}')
            if any(n.lower().endswith(x) for x in forbidden_suffixes):
                raise SystemExit(f'forbidden runtime data: {p.name}:{n}')
            if ((z.getinfo(n).external_attr>>16)&0o170000)==0o120000:
                raise SystemExit(f'symlink member: {p.name}:{n}')
repair='repair-v2.21.21.php'
for kind in ['ATOMIC','UPDATE']:
    p=out/f'VF_Start_V2.21.21_{kind}.zip'
    with zipfile.ZipFile(p) as z:
        if z.namelist()!=[repair]:
            raise SystemExit(f'{kind} package shape mismatch')
        if z.read(repair)!=(out/repair).read_bytes():
            raise SystemExit(f'{kind} repair bytes mismatch')
with zipfile.ZipFile(out/'VF_Start_V2.21.21_FULL.zip') as z:
    names=set(z.namelist())
    for required in ['index.php','setup.php','VERSION.txt','app/bootstrap.php','assets/data-recovery.js','assets/update-reload.js']:
        if required not in names:
            raise SystemExit(f'FULL missing {required}')
print('SHA_ZIP_PATH_PRIVACY=PASS')
print('FORMAL_PACKAGE_SHAPE=PASS')
PY

docker run --rm -v "$OUT:/work:ro" -w /work php:8.0-cli php -l repair-v2.21.21.php >/dev/null
php "$REPAIR" --self-test > "$RUNNER_TEMP/p01-v22121-selftest.json"
jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true and (.target_files==(.source_files+2))' "$RUNNER_TEMP/p01-v22121-selftest.json" >/dev/null
php "$REPAIR" --verify-source=production/src > "$RUNNER_TEMP/p01-v22121-source-verify.json"
jq -e '.ok==true' "$RUNNER_TEMP/p01-v22121-source-verify.json" >/dev/null
rm -rf /tmp/p01-v22121-gate-only /tmp/p01-v22121-runtime-tamper
cp -a production/src /tmp/p01-v22121-gate-only
printf '\nP01_GATE_ONLY_VARIANT\n' >> /tmp/p01-v22121-gate-only/README.md
php "$REPAIR" --verify-source=/tmp/p01-v22121-gate-only | jq -e '.ok==true' >/dev/null
cp -a production/src /tmp/p01-v22121-runtime-tamper
printf '\n/* P01_TRUE_RUNTIME_TAMPER */\n' >> /tmp/p01-v22121-runtime-tamper/app/AdminShell.php
set +e
php "$REPAIR" --verify-source=/tmp/p01-v22121-runtime-tamper > "$RUNNER_TEMP/p01-runtime-tamper.out" 2>&1
rc=$?
set -e
test "$rc" -ne 0
grep -q 'app/AdminShell.php:sha' "$RUNNER_TEMP/p01-runtime-tamper.out"
echo 'ATOMIC_PHP80_SOURCE_TAMPER_GATE=PASS'

csrf_from() {
  python3 -c 'import re,sys;s=open(sys.argv[1],encoding="utf-8").read();m=re.search(r"name=\"setup_csrf\"\s+value=\"([^\"]+)\"",s);assert m;print(m.group(1))' "$1"
}

setup_instance() {
  local ROOT="$1" PORT="$2" LABEL="$3" PASSWORD="$4"
  php -S "127.0.0.1:${PORT}" -t "$ROOT" > "$RUNNER_TEMP/${LABEL}-server.log" 2>&1 &
  local pid=$!
  for i in $(seq 1 30); do
    if curl -fsS -c "$RUNNER_TEMP/${LABEL}.cookies" "http://127.0.0.1:${PORT}/" -o "$RUNNER_TEMP/${LABEL}-root.html"; then break; fi
    sleep 1
  done
  curl -fsS -c "$RUNNER_TEMP/${LABEL}.cookies" -b "$RUNNER_TEMP/${LABEL}.cookies" "http://127.0.0.1:${PORT}/setup.php" -o "$RUNNER_TEMP/${LABEL}-setup.html"
  local csrf
  csrf="$(csrf_from "$RUNNER_TEMP/${LABEL}-setup.html")"
  curl -fsS -L -b "$RUNNER_TEMP/${LABEL}.cookies" -c "$RUNNER_TEMP/${LABEL}.cookies" -X POST "http://127.0.0.1:${PORT}/setup.php" \
    --data-urlencode "setup_csrf=$csrf" \
    --data-urlencode "site_title=$LABEL" \
    --data-urlencode "admin_password=$PASSWORD" \
    --data-urlencode "admin_password_confirm=$PASSWORD" \
    -o "$RUNNER_TEMP/${LABEL}-post.html"
  kill "$pid" 2>/dev/null || true
}

FRESH=/tmp/p01-v22121-fresh
rm -rf "$FRESH" && mkdir -p "$FRESH"
unzip -q "$OUT/VF_Start_V2.21.21_FULL.zip" -d "$FRESH"
setup_instance "$FRESH" 18171 p01-fresh 'FormalFresh-P01-22121!Strong'
test -f "$FRESH/app/.runtime.php"
php "$FRESH/cli/verify.php" > "$RUNNER_TEMP/p01-v22121-fresh-verify.txt"
grep -q 'VERIFY_PASS=YES' "$RUNNER_TEMP/p01-v22121-fresh-verify.txt"
php -r 'require "/tmp/p01-v22121-fresh/app/bootstrap.php";$d=vf_db();if((int)$d->query("SELECT COUNT(*) FROM categories")->fetchColumn()!==0)exit(1);if((int)$d->query("SELECT COUNT(*) FROM links")->fetchColumn()!==0)exit(2);if(strtolower((string)$d->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(3);if($d->query("PRAGMA foreign_key_check")->fetchAll())exit(4);echo "FRESH_FULL_ZERO_DATA=PASS\n";'
php -S 127.0.0.1:18171 -t "$FRESH" > "$RUNNER_TEMP/p01-fresh-browser-server.log" 2>&1 & echo $! > /tmp/p01-v22121-browser.pid
npm init -y >/dev/null 2>&1
npm install --no-audit --no-fund playwright@1.57.0 >/dev/null 2>&1
npx playwright install chromium >/dev/null
cat > "$RUNNER_TEMP/p01-full-owner.mjs" <<'JS'
import { chromium } from 'playwright';
const b=await chromium.launch({headless:true});
try {
  const p=await b.newPage({viewport:{width:1440,height:900}}),base='http://127.0.0.1:18171/';
  await p.goto(base,{waitUntil:'networkidle'});
  await p.click('#loginButton');
  await p.fill('[name=password]','FormalFresh-P01-22121!Strong');
  await p.click('#loginSubmit');
  await p.waitForFunction(()=>document.body.classList.contains('is-admin'));
  await p.goto(base+'links-admin.php',{waitUntil:'networkidle'});
  const top=await p.locator('.vf-rail-item>span').allTextContents();
  const expected=['网址','浏览器助手','备份与恢复','设置','更新'];
  if(JSON.stringify(top)!==JSON.stringify(expected)) throw new Error('FULL ADMIN '+JSON.stringify(top));
  await p.goto(base+'settings.php',{waitUntil:'networkidle'});
  if(!(await p.locator('.vf-admin-page-body').isVisible())) throw new Error('settings unavailable');
  console.log('FULL_OWNER_LOGIN_CORE_BACKEND=PASS');
} finally { await b.close(); }
JS
node "$RUNNER_TEMP/p01-full-owner.mjs"
kill "$(cat /tmp/p01-v22121-browser.pid)" 2>/dev/null || true
echo 'USER_INSTALLABLE_FULL_PACKAGE_GATE=PASS'

UPGRADE=/tmp/p01-v22121-upgrade
rm -rf "$UPGRADE" && cp -a production/src "$UPGRADE"
setup_instance "$UPGRADE" 18172 p01-upgrade 'FormalUpgrade-P01-22120!Strong'
php -r 'require "/tmp/p01-v22121-upgrade/app/bootstrap.php";$r=new VfRepository(vf_db());$c=$r->createCategory(["name"=>"Formal Upgrade Sentinel","description"=>"synthetic preservation","is_private"=>1]);$r->saveLink(null,["category_id"=>$c,"title"=>"Formal Upgrade Link","url"=>"https://example.com/p01-v22121","description"=>"keep","is_private"=>1]);$b=(new VfBackupManager(vf_db()))->create("Formal artifact pre-upgrade","pre-update",true);file_put_contents(getenv("RUNNER_TEMP")."/p01-upgrade-backup-key",$b["backup_key"]);'
php "$REPAIR" --run="$UPGRADE" > "$RUNNER_TEMP/p01-v22121-upgrade.json"
test "$(tr -d '\r\n' < "$UPGRADE/VERSION.txt")" = "$VERSION"
test -f "$UPGRADE/assets/data-recovery.js"
test -f "$UPGRADE/assets/update-reload.js"
php "$UPGRADE/cli/verify.php" > "$RUNNER_TEMP/p01-v22121-upgrade-verify.txt"
grep -q 'VERIFY_PASS=YES' "$RUNNER_TEMP/p01-v22121-upgrade-verify.txt"
php -r 'require "/tmp/p01-v22121-upgrade/app/bootstrap.php";$d=vf_db();if((int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Formal Upgrade Link\" AND url=\"https://example.com/p01-v22121\"")->fetchColumn()!==1)exit(1);$key=trim(file_get_contents(getenv("RUNNER_TEMP")."/p01-upgrade-backup-key"));$v=(new VfBackupManager($d))->verify($key);if(($v["validation_status"]??"")!=="valid")exit(2);if(strtolower((string)$d->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(3);if($d->query("PRAGMA foreign_key_check")->fetchAll())exit(4);'
php "$REPAIR" --run="$UPGRADE" > "$RUNNER_TEMP/p01-v22121-upgrade-repeat.json"
jq -e '.ok==true and .already_current==false' "$RUNNER_TEMP/p01-v22121-upgrade.json" >/dev/null
jq -e '.ok==true and .already_current==true' "$RUNNER_TEMP/p01-v22121-upgrade-repeat.json" >/dev/null
echo 'EXACT_UPGRADE_DATA_BACKUP_IDEMPOTENCY=PASS'

seed_recovery() {
  local ROOT="$1" PORT="$2" LABEL="$3"
  rm -rf "$ROOT" && cp -a production/src "$ROOT"
  setup_instance "$ROOT" "$PORT" "$LABEL" 'FormalRecovery-P01-22120!Strong'
  php -r "require '$ROOT/app/bootstrap.php';\$r=new VfRepository(vf_db());\$c=\$r->createCategory(['name'=>'Recovery Sentinel','description'=>'keep','is_private'=>1]);\$r->saveLink(null,['category_id'=>\$c,'title'=>'Recovery Link','url'=>'https://example.com/$LABEL','description'=>'keep','is_private'=>1]);"
}

SOFT=/tmp/p01-v22121-soft
seed_recovery "$SOFT" 18173 p01-soft
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$REPAIR" --run="$SOFT" > "$RUNNER_TEMP/p01-soft.out" 2>&1
rc=$?
set -e
test "$rc" -ne 0
test "$(tr -d '\r\n' < "$SOFT/VERSION.txt")" = "$SOURCE_VERSION"
php "$REPAIR" --verify-source="$SOFT" | jq -e '.ok==true' >/dev/null
php -r 'require "/tmp/p01-v22121-soft/app/bootstrap.php";$d=vf_db();if((int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Recovery Link\"")->fetchColumn()!==1)exit(1);if(strtolower((string)$d->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(2);'
echo 'SOFT_FAILURE_ROLLBACK=PASS'

HARD=/tmp/p01-v22121-hard
seed_recovery "$HARD" 18174 p01-hard
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$REPAIR" --run="$HARD" > "$RUNNER_TEMP/p01-hard.out" 2>&1
rc=$?
set -e
test "$rc" -eq 97
php "$REPAIR" --run="$HARD" > "$RUNNER_TEMP/p01-hard-recover.json"
test "$(tr -d '\r\n' < "$HARD/VERSION.txt")" = "$VERSION"
jq -e '.ok==true and .interrupted_recovered==true' "$RUNNER_TEMP/p01-hard-recover.json" >/dev/null
php -r 'require "/tmp/p01-v22121-hard/app/bootstrap.php";$d=vf_db();if((int)$d->query("SELECT COUNT(*) FROM links WHERE title=\"Recovery Link\"")->fetchColumn()!==1)exit(1);if(strtolower((string)$d->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(2);'
echo 'HARD_INTERRUPTION_RECOVERY=PASS'

UPDATE="$OUT/VF_Start_V2.21.21_UPDATE.zip"
FULL="$OUT/VF_Start_V2.21.21_FULL.zip"
jq -n \
  --arg candidate "$CANDIDATE" --arg tree "$CANDIDATE_TREE" --arg production "$PRODUCTION" \
  --arg update_sha "$(sha256sum "$UPDATE"|awk '{print $1}')" --argjson update_bytes "$(stat -c%s "$UPDATE")" \
  --arg full_sha "$(sha256sum "$FULL"|awk '{print $1}')" --argjson full_bytes "$(stat -c%s "$FULL")" \
  --arg repair_sha "$(sha256sum "$REPAIR"|awk '{print $1}')" \
  '{schema:"vf-public-runner-result/v1",project_id:"P01",gate:"V2.21.21_FORMAL_ARTIFACT_GATE",status:"SUCCESS",pass:true,candidate_source_sha:$candidate,candidate_source_tree:$tree,production_source_sha:$production,source_version:"2.21.20",version:"2.21.21",schema_version:"2026080902",schema_changed:false,browser_helper:"1.6.4",full_package_gate:true,exact_atomic_upgrade:true,soft_rollback:true,hard_interruption_recovery:true,idempotency:true,sqlite_integrity:true,business_data_preserved:true,backup_preserved:true,runtime_added:["assets/data-recovery.js","assets/update-reload.js"],artifacts:{update:{name:"VF_Start_V2.21.21_UPDATE.zip",bytes:$update_bytes,sha256:$update_sha},full:{name:"VF_Start_V2.21.21_FULL.zip",bytes:$full_bytes,sha256:$full_sha},repair:{name:"repair-v2.21.21.php",sha256:$repair_sha}},release_authorized:false,production_changed:false,private_data_used:false,private_source_persisted_publicly:false}' \
  > /tmp/p01-v22121-formal-evidence.json

echo 'FORMAL_ARTIFACT_GATE_LOCAL_VERDICT=PASS'
