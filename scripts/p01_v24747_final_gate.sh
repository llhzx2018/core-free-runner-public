#!/usr/bin/env bash
set -Eeuo pipefail

ART=/tmp/p01-v24747-artifacts
REL=/tmp/p01-rel46
TARGET=2.47.47
SOURCE=2.47.46
SCHEMA=2026090401

python3 scripts/p01_build_v24747_final.py | tee /tmp/p01-v24747-build.json

FULL="$ART/VF-Start-V2.47.47-FULL.zip"
UPDATE="$ART/VF_Start_V2.47.47_UPDATE.zip"

test -f "$FULL"
test -f "$UPDATE"
rm -rf /tmp/p01-v24747-update
unzip -q "$UPDATE" -d /tmp/p01-v24747-update
REPAIR=/tmp/p01-v24747-update/repair-v2.47.47.php
test -f "$REPAIR"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test | tee /tmp/p01-v24747-atomic-selftest.json
grep -Fq '"ok":true' /tmp/p01-v24747-atomic-selftest.json

assert_no_private_payload(){
  local zip="$1"
  if unzip -Z1 "$zip" | grep -Ei '(^|/)(\.runtime\.php|.*\.sqlite3?$|.*\.db$|private/|backups?/|sessions?/|tokens?/|staging/)' >/tmp/p01-private-hits.txt; then
    cat /tmp/p01-private-hits.txt
    echo "PRIVATE_PAYLOAD_LEAK"
    exit 90
  fi
}
assert_no_private_payload "$FULL"
assert_no_private_payload "$UPDATE"

install_full(){
  local zip="$1" root="$2" port="$3" title="$4"
  local cookie="/tmp/cookie-$port.txt"
  rm -rf "$root" "$cookie"
  mkdir -p "$root"
  unzip -q "$zip" -d "$root"
  (
    cd "$root"
    php -S 127.0.0.1:"$port" -t . >"/tmp/server-$port.log" 2>&1 &
    echo $! >"/tmp/server-$port.pid"
  )
  local pid
  pid="$(cat "/tmp/server-$port.pid")"
  trap 'kill "$pid" >/dev/null 2>&1 || true' RETURN
  for i in $(seq 1 50); do
    if curl -fsS -c "$cookie" -b "$cookie" "http://127.0.0.1:$port/setup.php" -o "/tmp/setup-$port.html"; then break; fi
    sleep 1
  done
  local csrf
  csrf="$(python3 - "/tmp/setup-$port.html" <<'PY'
import re,sys
t=open(sys.argv[1],encoding="utf-8").read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',t)
assert m
print(m.group(1))
PY
)"
  local pass
  pass="$(printf '%s%s%s' 'Release' 'Gate!' "$port")"
  curl -fsS -c "$cookie" -b "$cookie" -X POST "http://127.0.0.1:$port/setup.php"     --data-urlencode "setup_csrf=$csrf"     --data-urlencode "site_title=$title"     --data-urlencode "admin_password=$pass"     --data-urlencode "admin_password_confirm=$pass"     -o "/tmp/setup-post-$port.html"
  (cd "$root" && php cli/verify.php) | tee "/tmp/verify-$port.txt"
  grep -Fx 'VERIFY_PASS=YES' "/tmp/verify-$port.txt"
  local revisit
  revisit="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/setup.php")"
  echo "FULL_SETUP_REVISIT_STATUS=$revisit PORT=$port"
  test "$revisit" = 302
  local login
  local login_body
  login_body="$(php -r 'echo json_encode(["password"=>$argv[1]], JSON_UNESCAPED_SLASHES);' "$pass")"
  login="$(curl -sS -c "$cookie" -b "$cookie" -o "/tmp/login-$port.json" -w '%{http_code}' -H 'Content-Type: application/json' --data "$login_body" "http://127.0.0.1:$port/api.php?action=login")"
  echo "FULL_LOGIN_STATUS=$login PORT=$port"
  if [ "$login" != 200 ]; then cat "/tmp/login-$port.json" || true; fi
  test "$login" = 200
  grep -Fq '"ok":true' "/tmp/login-$port.json"
  echo "FULL_INSTALL_RUNTIME_PASS PORT=$port"
  kill "$pid" >/dev/null 2>&1 || true
  trap - RETURN
}

install_full "$FULL" /tmp/p01-v24747-full-runtime 18477 "VF Start V2.47.47 FULL Gate"
test "$(tr -d '\r\n ' </tmp/p01-v24747-full-runtime/VERSION.txt)" = "$TARGET"
echo P01_V24747_CLEAN_FULL_INSTALL=PASS

install_full "$REL/VF-Start-V2.47.46-FULL.zip" /tmp/p01-v24746-upgrade 18478 "VF Start V2.47.46 Upgrade Source"

cat >/tmp/p01-v24746-upgrade/sentinel.php <<'PHP'
<?php
declare(strict_types=1);
require __DIR__.'/app/bootstrap.php';
$db=vf_db();
$repo=new VfRepository($db);
$cat=$repo->createCategory(['name'=>'Release Sentinel','description'=>'','icon'=>'','is_private'=>1,'sort_order'=>0]);
$link=$repo->saveLink(null,['surface'=>'start','category_id'=>$cat,'title'=>'Release Sentinel Link','url'=>'https://example.com/release-sentinel','description'=>'must survive atomic','tags'=>['release-sentinel'],'is_private'=>1,'is_pending'=>0]);
file_put_contents('/tmp/p01-sentinel-id.txt',(string)$link['id']);
echo "SENTINEL_CREATED\n";
PHP
php /tmp/p01-v24746-upgrade/sentinel.php
rm /tmp/p01-v24746-upgrade/sentinel.php

cp "$REPAIR" /tmp/p01-v24746-upgrade/repair-v2.47.47.php
php /tmp/p01-v24746-upgrade/repair-v2.47.47.php --verify-source=/tmp/p01-v24746-upgrade | tee /tmp/p01-source-verify.json
grep -Fq '"ok":true' /tmp/p01-source-verify.json

php /tmp/p01-v24746-upgrade/repair-v2.47.47.php --run=/tmp/p01-v24746-upgrade | tee /tmp/p01-atomic-success.json
grep -Fq '"ok":true' /tmp/p01-atomic-success.json
test "$(tr -d '\r\n ' </tmp/p01-v24746-upgrade/VERSION.txt)" = "$TARGET"
(cd /tmp/p01-v24746-upgrade && php cli/verify.php) | grep -Fx 'VERIFY_PASS=YES'
php -r 'require "/tmp/p01-v24746-upgrade/app/bootstrap.php"; $id=(int)trim(file_get_contents("/tmp/p01-sentinel-id.txt")); $s=vf_db()->prepare("SELECT title,is_private FROM links WHERE id=?"); $s->execute([$id]); $r=$s->fetch(PDO::FETCH_ASSOC); if(!$r||$r["title"]!=="Release Sentinel Link"||(int)$r["is_private"]!==1) exit(1); echo "SENTINEL_PRESERVED\n";'

cp "$REPAIR" /tmp/p01-v24746-upgrade/repair-v2.47.47.php
php /tmp/p01-v24746-upgrade/repair-v2.47.47.php --run=/tmp/p01-v24746-upgrade | tee /tmp/p01-atomic-idempotent.json
grep -Fq '"already_current":true' /tmp/p01-atomic-idempotent.json
echo P01_V24747_ATOMIC_UPGRADE=PASS
echo P01_V24747_ATOMIC_IDEMPOTENCY=PASS

install_full "$REL/VF-Start-V2.47.46-FULL.zip" /tmp/p01-v24746-rollback 18479 "VF Start V2.47.46 Rollback Source"
cat >/tmp/p01-v24746-rollback/sentinel.php <<'PHP'
<?php
declare(strict_types=1);
require __DIR__.'/app/bootstrap.php';
$db=vf_db();
$repo=new VfRepository($db);
$cat=$repo->createCategory(['name'=>'Rollback Sentinel','description'=>'','icon'=>'','is_private'=>1,'sort_order'=>0]);
$link=$repo->saveLink(null,['surface'=>'start','category_id'=>$cat,'title'=>'Rollback Sentinel Link','url'=>'https://example.com/rollback-sentinel','description'=>'must survive rollback','tags'=>['rollback-sentinel'],'is_private'=>1,'is_pending'=>0]);
file_put_contents('/tmp/p01-rollback-id.txt',(string)$link['id']);
PHP
php /tmp/p01-v24746-rollback/sentinel.php
rm /tmp/p01-v24746-rollback/sentinel.php
cp "$REPAIR" /tmp/p01-v24746-rollback/repair-v2.47.47.php
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php /tmp/p01-v24746-rollback/repair-v2.47.47.php --run=/tmp/p01-v24746-rollback >/tmp/p01-atomic-failure.out 2>/tmp/p01-atomic-failure.err
status=$?
set -e
test "$status" -ne 0
test "$(tr -d '\r\n ' </tmp/p01-v24746-rollback/VERSION.txt)" = "$SOURCE"
(cd /tmp/p01-v24746-rollback && php cli/verify.php) | grep -Fx 'VERIFY_PASS=YES'
php -r 'require "/tmp/p01-v24746-rollback/app/bootstrap.php"; $id=(int)trim(file_get_contents("/tmp/p01-rollback-id.txt")); $s=vf_db()->prepare("SELECT title FROM links WHERE id=?"); $s->execute([$id]); if($s->fetchColumn()!=="Rollback Sentinel Link") exit(1); echo "ROLLBACK_SENTINEL_PRESERVED\n";'
echo P01_V24747_ATOMIC_ROLLBACK=PASS

unzip -p "$FULL" VERSION.txt | tr -d '\r\n ' | grep -Fx "$TARGET"
unzip -p "$FULL" release-manifest.json | php -r '$m=json_decode(stream_get_contents(STDIN),true); if(($m["version"]??"")!=="2.47.47"||($m["source_version"]??"")!=="2.47.46"||($m["schema_version"]??"")!=="2026090401")exit(1); echo "CANDIDATE_MANIFEST_IDENTITY=PASS\n";'
(
  cd "$ART"
  sha256sum -c "VF-Start-V2.47.47-FULL.zip.sha256"
  sha256sum -c "VF_Start_V2.47.47_UPDATE.zip.sha256"
)
echo P01_V24747_MACHINE_ARTIFACT_GATE=PASS
