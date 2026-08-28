#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/tmp/p01-v228-final
COOKIE=/tmp/p01-v228-final.cookies
PORT=18340
rm -rf "$ROOT" "$COOKIE" /tmp/p01-v228-final-ids.json /tmp/p01-v228-final-ui /tmp/p01-v228-playwright
mkdir -p /tmp/p01-v228-final-ui
cp -a candidate/src "$ROOT"
php -S 127.0.0.1:$PORT -t "$ROOT" >/tmp/p01-v228-final-server.log 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in $(seq 1 30); do curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:$PORT/setup.php" -o /tmp/p01-v228-final-setup.html && break || sleep 1; done
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v228-final-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:$PORT/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=V228 Final Candidate' \
  --data-urlencode 'admin_password=P01V228!Final' \
  --data-urlencode 'admin_password_confirm=P01V228!Final' \
  -o /tmp/p01-v228-final-post.html

test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = '2.28.0'
grep -Fx "define('VF_VERSION', '2.28.0');" "$ROOT/app/bootstrap.php" >/dev/null
cat >/tmp/p01-v228-final-seed.php <<'PHP'
<?php
require '/tmp/p01-v228-final/app/bootstrap.php'; require_once '/tmp/p01-v228-final/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());
$start=$r->createCategory(['name'=>'开发工具','description'=>'','is_private'=>false]);
$chA=$r->createCategory(['name'=>'频道 A','description'=>'','is_private'=>false]);
$chB=$r->createCategory(['name'=>'频道 B','description'=>'','is_private'=>false]);
$wa=$r->createCategory(['name'=>'影视 A','description'=>'','is_private'=>false]);
$wb=$r->createCategory(['name'=>'影视 B','description'=>'','is_private'=>false]);
for($i=1;$i<=120;$i++)$r->saveLink(null,['category_id'=>$start,'title'=>'Dev Tool '.str_pad((string)$i,3,'0',STR_PAD_LEFT),'url'=>'https://dev-final'.$i.'.example.com','description'=>'developer tool','tags'=>$i%8===0?'工具,常用':'工具','is_private'=>true,'is_favorite'=>$i%19===0],'manual');
for($i=1;$i<=70;$i++){ $x=$r->saveLink(null,['category_id'=>$chA,'title'=>'Channel A '.str_pad((string)$i,3,'0',STR_PAD_LEFT),'url'=>'https://youtube.com/@finala'.$i,'description'=>'channel A','tags'=>'频道','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'channels','resource_kind'=>'creator','background_friendly'=>$i%3===0]); }
for($i=1;$i<=35;$i++){ $x=$r->saveLink(null,['category_id'=>$chB,'title'=>'Channel B '.str_pad((string)$i,3,'0',STR_PAD_LEFT),'url'=>'https://youtube.com/@finalb'.$i,'description'=>'channel B','tags'=>'频道','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'channels','resource_kind'=>'creator','background_friendly'=>$i%4===0]); }
$statuses=['want','watching','watched','favorite'];
for($i=1;$i<=50;$i++){ $x=$r->saveLink(null,['category_id'=>$wa,'title'=>'Movie A '.str_pad((string)$i,3,'0',STR_PAD_LEFT),'url'=>'https://movie-final-a'.$i.'.example.com','description'=>'movie A','tags'=>'影视','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'watch','resource_kind'=>'movie','media_year'=>2000+$i%25,'media_status'=>$statuses[($i-1)%4]]); }
for($i=1;$i<=20;$i++){ $x=$r->saveLink(null,['category_id'=>$wb,'title'=>'Movie B '.str_pad((string)$i,3,'0',STR_PAD_LEFT),'url'=>'https://movie-final-b'.$i.'.example.com','description'=>'movie B','tags'=>'影视','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'watch','resource_kind'=>'series','media_year'=>1990+$i%30,'media_status'=>$statuses[($i-1)%4]]); }
file_put_contents('/tmp/p01-v228-final-ids.json',json_encode(['start'=>$start,'chA'=>$chA,'chB'=>$chB,'wa'=>$wa,'wb'=>$wb],JSON_THROW_ON_ERROR));
echo "P01_V228_FINAL_SEED=PASS\n";
PHP
php /tmp/p01-v228-final-seed.php | grep -Fx P01_V228_FINAL_SEED=PASS

mkdir -p /tmp/p01-v228-playwright
cd /tmp/p01-v228-playwright
npm init -y >/dev/null 2>&1
npm install playwright >/dev/null 2>&1
npx playwright install chromium >/dev/null 2>&1
cp "$GITHUB_WORKSPACE/runner/scripts/p01-v228-candidate-ui-gate.js" ./gate.js
node gate.js | tee /tmp/p01-v228-final-ui/result.txt
grep -Fx P01_V228_FINAL_UI=PASS /tmp/p01-v228-final-ui/result.txt

php "$ROOT/cli/verify.php" | grep -Fx VERIFY_PASS=YES
php "$ROOT/cli/surface-verify.php" | tee /tmp/p01-v228-final-surface.txt
grep -Fx MULTI_SURFACE_PASS=YES /tmp/p01-v228-final-surface.txt
grep -Fx WORKING_SCHEMA=2026082801 /tmp/p01-v228-final-surface.txt
php "$ROOT/cli/baseline-verify.php" | tee /tmp/p01-v228-final-baseline.txt
grep -Fx BASELINE_CORE_PASS=YES /tmp/p01-v228-final-baseline.txt
grep -Fx DRIFT_COUNT=0 /tmp/p01-v228-final-baseline.txt
grep -Fx UNKNOWN_COUNT=0 /tmp/p01-v228-final-baseline.txt
php -r 'require "/tmp/p01-v228-final/app/bootstrap.php";$p=vf_db();if(strtolower((string)$p->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(1);if($p->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC))exit(2);echo "P01_V228_FINAL_SQLITE=PASS\n";' | grep -Fx P01_V228_FINAL_SQLITE=PASS

echo P01_V228_FRESH_INSTALL_UI_GATE=PASS
