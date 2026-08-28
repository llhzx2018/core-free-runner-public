#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE=85e450ef146987fd6a950fd948ad58e81f5d3c95
CANDIDATE_TREE=d7238aec239fd8288ba47eb382ea65340f570e96
SOURCE=8c3d18e1243d4b6ddc40bc7922746131a5d0d9c3
SOURCE_TREE=6e9fb22d146b6b1e9ab276100331043c8ec647aa
VERSION=2.28.0
SOURCE_VERSION=2.27.0
SCHEMA=2026082801
OUT=/tmp/p01-v228-artifacts

# Exact source and identity fence.
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE"
test "$(git -C production rev-parse HEAD^{tree})" = "$SOURCE_TREE"
test "$(tr -d '\r\n' < candidate/VERSION)" = "$VERSION"
test "$(tr -d '\r\n' < candidate/src/VERSION.txt)" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.28.0');" candidate/src/app/bootstrap.php >/dev/null
grep -F '## V2.28.0 · Candidate / Not Released · 2026-08-29' candidate/CHANGELOG.md >/dev/null
test "$(tr -d '\r\n' < production/src/VERSION.txt)" = "$SOURCE_VERSION"
grep -Fx "define('VF_VERSION', '2.27.0');" production/src/app/bootstrap.php >/dev/null
if git -C candidate diff --name-only "$SOURCE"..HEAD -- database/migrations | grep .; then echo 'Unexpected migration change'; exit 1; fi
find candidate/src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/tmp/p01-v228-php-lint.txt
node --check candidate/src/assets/workspace.js
php candidate/src/cli/verify.php --help >/dev/null 2>&1 || true

echo P01_V228_EXACT_SOURCE=PASS

# Build deterministic non-published candidate artifacts.
rm -rf "$OUT" /tmp/p01-v228-first
mkdir -p "$OUT" /tmp/p01-v228-first
python3 runner/scripts/p01-v228-build-artifacts.py | tee /tmp/p01-v228-build1.json
php -l "$OUT/repair-v2.28.0.php" >/dev/null
php "$OUT/repair-v2.28.0.php" --self-test | tee "$OUT/atomic-self-test.json"
jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' "$OUT/atomic-self-test.json" >/dev/null
cp "$OUT/VF_Start_V2.28.0_UPDATE.zip" /tmp/p01-v228-first/update.zip
cp "$OUT/VF-Start-V2.28.0-CANDIDATE-FULL.zip" /tmp/p01-v228-first/full.zip
U1=$(sha256sum "$OUT/VF_Start_V2.28.0_UPDATE.zip"|awk '{print $1}')
F1=$(sha256sum "$OUT/VF-Start-V2.28.0-CANDIDATE-FULL.zip"|awk '{print $1}')
python3 runner/scripts/p01-v228-build-artifacts.py >/tmp/p01-v228-build2.json
U2=$(sha256sum "$OUT/VF_Start_V2.28.0_UPDATE.zip"|awk '{print $1}')
F2=$(sha256sum "$OUT/VF-Start-V2.28.0-CANDIDATE-FULL.zip"|awk '{print $1}')
test "$U1" = "$U2"; test "$F1" = "$F2"
cmp -s /tmp/p01-v228-first/update.zip "$OUT/VF_Start_V2.28.0_UPDATE.zip"
cmp -s /tmp/p01-v228-first/full.zip "$OUT/VF-Start-V2.28.0-CANDIDATE-FULL.zip"
printf 'UPDATE_SHA256=%s\nFULL_SHA256=%s\n' "$U2" "$F2" | tee "$OUT/candidate-artifact-digests.txt"
echo P01_V228_DETERMINISTIC_ARTIFACT=PASS

setup_root(){
  local ROOT="$1" PORT="$2" PASS="$3"
  rm -rf "$ROOT" "/tmp/p01-v228-${PORT}.cookies"
  cp -a production/src "$ROOT"
  php -S "127.0.0.1:${PORT}" -t "$ROOT" >"/tmp/p01-v228-${PORT}.log" 2>&1 &
  local PID=$!
  echo "$PID" >"/tmp/p01-v228-${PORT}.pid"
  local COOKIE="/tmp/p01-v228-${PORT}.cookies"
  for i in $(seq 1 30); do curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o "/tmp/p01-v228-${PORT}-setup.html" && break || sleep 1; done
  local CSRF
  CSRF=$(python3 - "$PORT" <<'PY'
import re,sys
p=sys.argv[1]
s=open(f'/tmp/p01-v228-{p}-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
  curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" \
    --data-urlencode "setup_csrf=$CSRF" \
    --data-urlencode "site_title=V228 Gate ${PORT}" \
    --data-urlencode "admin_password=$PASS" \
    --data-urlencode "admin_password_confirm=$PASS" \
    -o "/tmp/p01-v228-${PORT}-post.html"
  test -f "$ROOT/app/.runtime.php"
}

# Actual V2.27.0 -> V2.28.0 updater with significant real data.
ROOT=/tmp/p01-v228-owner; PORT=18338; PASS='P01V228!Owner'; COOKIE=/tmp/p01-v228-18338.cookies
setup_root "$ROOT" "$PORT" "$PASS"
cat >/tmp/p01-v228-owner-seed.php <<'PHP'
<?php
require '/tmp/p01-v228-owner/app/bootstrap.php'; require_once '/tmp/p01-v228-owner/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());
$start=$r->createCategory(['name'=>'Keep Start','description'=>'','is_private'=>false]);
$ch=$r->createCategory(['name'=>'Keep Channels','description'=>'','is_private'=>false]);
$wa=$r->createCategory(['name'=>'Keep Watch','description'=>'','is_private'=>false]);
$first=0;
for($i=1;$i<=15;$i++){ $x=$r->saveLink(null,['category_id'=>$start,'title'=>'Keep Start '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://keep-start'.$i.'.example.com','description'=>'preserve start','tags'=>'keep','is_private'=>false,'is_favorite'=>$i===1],'manual');if($i===1)$first=(int)$x['id']; }
$channel=0;
for($i=1;$i<=65;$i++){ $x=$r->saveLink(null,['category_id'=>$ch,'title'=>'Keep Channel '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://youtube.com/@keep228'.$i,'description'=>'preserve channel','tags'=>'keep,频道','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'channels','resource_kind'=>'creator','background_friendly'=>$i%2===0,'note'=>$i===1?'preserve channel note':'']);if($i===1)$channel=(int)$x['id']; }
$statuses=['want','watching','watched','favorite'];$watch=0;
for($i=1;$i<=45;$i++){ $x=$r->saveLink(null,['category_id'=>$wa,'title'=>'Keep Watch '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://keep-watch'.$i.'.example.com','description'=>'preserve watch','tags'=>'keep,影视','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'watch','resource_kind'=>'movie','media_year'=>2000+$i%24,'media_status'=>$statuses[($i-1)%4],'note'=>$i===1?'preserve watch note':'']);if($i===1)$watch=(int)$x['id']; }
file_put_contents('/tmp/p01-v228-owner-ids.json',json_encode(['start_cat'=>$start,'ch_cat'=>$ch,'watch_cat'=>$wa,'first'=>$first,'channel'=>$channel,'watch'=>$watch],JSON_THROW_ON_ERROR));
echo "OWNER_SEED=PASS\n";
PHP
php /tmp/p01-v228-owner-seed.php | grep -Fx OWNER_SEED=PASS
cp "$OUT/repair-v2.28.0.php" "$ROOT/repair-v2.28.0.php"
php "$ROOT/repair-v2.28.0.php" --verify-source="$ROOT" | tee /tmp/p01-v228-source.json | jq -e '.ok==true' >/dev/null
php "$ROOT/repair-v2.28.0.php" --run="$ROOT" | tee /tmp/p01-v228-update.json
jq -e '.ok==true and .already_current==false and .schema=="2026082801" and .integrity=="ok" and .fk==0 and .rollback_supported==true' /tmp/p01-v228-update.json >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = "$VERSION"
grep -Fx "define('VF_VERSION', '2.28.0');" "$ROOT/app/bootstrap.php" >/dev/null
test -f "$ROOT/assets/workspace-v228.css"
php "$ROOT/cli/verify.php" | grep -Fx VERIFY_PASS=YES
php "$ROOT/cli/surface-verify.php" | tee /tmp/p01-v228-owner-surface.txt
grep -Fx MULTI_SURFACE_PASS=YES /tmp/p01-v228-owner-surface.txt
grep -Fx WORKING_SCHEMA=2026082801 /tmp/p01-v228-owner-surface.txt
php "$ROOT/cli/baseline-verify.php" | tee /tmp/p01-v228-owner-base.txt
grep -Fx BASELINE_CORE_PASS=YES /tmp/p01-v228-owner-base.txt
grep -Fx DRIFT_COUNT=0 /tmp/p01-v228-owner-base.txt
grep -Fx UNKNOWN_COUNT=0 /tmp/p01-v228-owner-base.txt
php -r '$ids=json_decode(file_get_contents("/tmp/p01-v228-owner-ids.json"),true);require "/tmp/p01-v228-owner/app/bootstrap.php";$p=vf_db();if((int)$p->query("SELECT COUNT(*) FROM links")->fetchColumn()!==125)exit(1);if((int)$p->query("SELECT COUNT(*) FROM resource_surface_profiles")->fetchColumn()!==110)exit(2);$q=$p->prepare("SELECT surface,note FROM resource_surface_profiles WHERE link_id=?");$q->execute([(int)$ids["channel"]]);$x=$q->fetch(PDO::FETCH_ASSOC);if(($x["surface"]??"")!=="channels"||($x["note"]??"")!=="preserve channel note")exit(3);$q->execute([(int)$ids["watch"]]);$x=$q->fetch(PDO::FETCH_ASSOC);if(($x["surface"]??"")!=="watch"||($x["note"]??"")!=="preserve watch note")exit(4);$q=$p->prepare("SELECT is_favorite FROM links WHERE id=?");$q->execute([(int)$ids["first"]]);if((int)$q->fetchColumn()!==1)exit(5);echo "P01_V228_DATA_PRESERVED=PASS\n";' | grep -Fx P01_V228_DATA_PRESERVED=PASS
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -X POST "http://127.0.0.1:${PORT}/api.php?action=login" --data "{\"password\":\"$PASS\"}" | jq -e '.ok==true' >/dev/null
CH=$(jq -r .ch_cat /tmp/p01-v228-owner-ids.json); WA=$(jq -r .watch_cat /tmp/p01-v228-owner-ids.json)
curl -fsS -b "$COOKIE" "http://127.0.0.1:${PORT}/channels.php?category=$CH&per=30&page=2" -o /tmp/p01-v228-owner-channels.html
grep -F '65 项' /tmp/p01-v228-owner-channels.html >/dev/null; grep -F '当前 31–60' /tmp/p01-v228-owner-channels.html >/dev/null; grep -F 'aria-label="分类筛选"' /tmp/p01-v228-owner-channels.html >/dev/null
curl -fsS -b "$COOKIE" "http://127.0.0.1:${PORT}/watch.php?category=$WA&per=30" -o /tmp/p01-v228-owner-watch.html
grep -F '45 项' /tmp/p01-v228-owner-watch.html >/dev/null; grep -F '想看' /tmp/p01-v228-owner-watch.html >/dev/null
CSRF2=$(python3 - <<'PY'
import re,json,html
s=open('/tmp/p01-v228-owner-channels.html',encoding='utf-8').read();m=re.search(r'<script type="application/json" id="vf-workspace-data">(.*?)</script>',s,re.S);assert m;print(json.loads(html.unescape(m.group(1)))['csrf'])
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/workspace-action.php" --data-urlencode "csrf=$CSRF2" --data-urlencode 'action=create' --data-urlencode "category_id=$CH" --data-urlencode 'title=Post Upgrade V228' --data-urlencode 'url=https://post-upgrade-v228.example.com' --data-urlencode 'surface=channels' --data-urlencode 'resource_kind=creator' --data-urlencode 'background_friendly=1' | tee /tmp/p01-v228-create.json | jq -e '.ok==true and .duplicate==false' >/dev/null
NEW_ID=$(jq -r .id /tmp/p01-v228-create.json)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/workspace-action.php" --data-urlencode "csrf=$CSRF2" --data-urlencode 'action=favorite' --data-urlencode "id=$NEW_ID" --data-urlencode 'favorite=1' | jq -e '.ok==true' >/dev/null
php -r '$id=(int)$argv[1];require "/tmp/p01-v228-owner/app/bootstrap.php";$p=vf_db();$fav=(int)$p->query("SELECT is_favorite FROM links WHERE id=$id")->fetchColumn();$surface=(string)$p->query("SELECT surface FROM resource_surface_profiles WHERE link_id=$id")->fetchColumn();if($fav!==1||$surface!=="channels")exit(1);echo "P01_V228_POST_UPGRADE_WORKSPACE=PASS\n";' "$NEW_ID" | grep -Fx P01_V228_POST_UPGRADE_WORKSPACE=PASS
php "$ROOT/repair-v2.28.0.php" --run="$ROOT" | jq -e '.ok==true and .already_current==true and .schema=="2026082801"' >/dev/null
kill "$(cat /tmp/p01-v228-18338.pid)" 2>/dev/null || true
echo P01_V228_ACTUAL_UPDATER=PASS

# Automatic rollback on failure injection.
ROOT=/tmp/p01-v228-rollback; PORT=18341; PASS='P01V228!Rollback'
setup_root "$ROOT" "$PORT" "$PASS"
cat >/tmp/p01-v228-rb-seed.php <<'PHP'
<?php
require '/tmp/p01-v228-rollback/app/bootstrap.php';$r=new VfRepository(vf_db());$c=$r->createCategory(['name'=>'Rollback Keep','description'=>'','is_private'=>false]);$x=$r->saveLink(null,['category_id'=>$c,'title'=>'Rollback Keep','url'=>'https://rollback-keep.example.com','description'=>'keep','is_private'=>true],'manual');file_put_contents('/tmp/p01-v228-rb-id',(string)$x['id']);
PHP
php /tmp/p01-v228-rb-seed.php
cp "$OUT/repair-v2.28.0.php" "$ROOT/repair-v2.28.0.php"
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$ROOT/repair-v2.28.0.php" --run="$ROOT" >/tmp/p01-v228-rb-result.txt 2>&1
RC=$?
set -e
test "$RC" -ne 0
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = "$SOURCE_VERSION"
grep -Fx "define('VF_VERSION', '2.27.0');" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/repair-v2.28.0.php" --verify-source="$ROOT" | jq -e '.ok==true' >/dev/null
php -r '$id=(int)file_get_contents("/tmp/p01-v228-rb-id");require "/tmp/p01-v228-rollback/app/bootstrap.php";$p=vf_db();$q=$p->prepare("SELECT title FROM links WHERE id=?");$q->execute([$id]);if((string)$q->fetchColumn()!=="Rollback Keep")exit(1);if(strtolower((string)$p->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(2);if($p->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC))exit(3);echo "P01_V228_ROLLBACK=PASS\n";' | grep -Fx P01_V228_ROLLBACK=PASS
kill "$(cat /tmp/p01-v228-18341.pid)" 2>/dev/null || true

# Hard interruption + recovery on next run.
ROOT=/tmp/p01-v228-interrupt; PORT=18342; PASS='P01V228!Interrupt'
setup_root "$ROOT" "$PORT" "$PASS"
cat >/tmp/p01-v228-int-seed.php <<'PHP'
<?php
require '/tmp/p01-v228-interrupt/app/bootstrap.php';$r=new VfRepository(vf_db());$c=$r->createCategory(['name'=>'Interrupt Keep','description'=>'','is_private'=>false]);$x=$r->saveLink(null,['category_id'=>$c,'title'=>'Interrupt Keep','url'=>'https://interrupt-keep.example.com','description'=>'keep','is_private'=>true],'manual');file_put_contents('/tmp/p01-v228-int-id',(string)$x['id']);
PHP
php /tmp/p01-v228-int-seed.php
cp "$OUT/repair-v2.28.0.php" "$ROOT/repair-v2.28.0.php"
set +e
VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY=1 php "$ROOT/repair-v2.28.0.php" --run="$ROOT" >/tmp/p01-v228-int-hard.txt 2>&1
RC=$?
set -e
test "$RC" -eq 97
php "$ROOT/repair-v2.28.0.php" --run="$ROOT" | tee /tmp/p01-v228-int-recover.json
jq -e '.ok==true and .already_current==false and .interrupted_recovered==true and .schema=="2026082801"' /tmp/p01-v228-int-recover.json >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = "$VERSION"
php -r '$id=(int)file_get_contents("/tmp/p01-v228-int-id");require "/tmp/p01-v228-interrupt/app/bootstrap.php";$p=vf_db();$q=$p->prepare("SELECT title FROM links WHERE id=?");$q->execute([$id]);if((string)$q->fetchColumn()!=="Interrupt Keep")exit(1);echo "P01_V228_INTERRUPTION_RECOVERY=PASS\n";' | grep -Fx P01_V228_INTERRUPTION_RECOVERY=PASS
kill "$(cat /tmp/p01-v228-18342.pid)" 2>/dev/null || true

echo P01_V228_CORE_GATE=PASS
