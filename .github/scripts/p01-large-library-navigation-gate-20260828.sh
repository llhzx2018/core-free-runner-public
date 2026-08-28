#!/usr/bin/env bash
set -Eeuo pipefail

: "${SOURCE:?SOURCE required}"
: "${TREE:?TREE required}"
ROOT=${ROOT:-/tmp/p01-large-library}
COOKIE=${COOKIE:-/tmp/p01-large-library.cookies}
PORT=${PORT:-18332}
BASE_SHA=803a14f16846965d61ea0c1b69014468f7e00275

test "$(git -C product rev-parse HEAD)" = "$SOURCE"
test "$(git -C product rev-parse HEAD^{tree})" = "$TREE"
test "$(cat product/VERSION)" = 2.27.0
php -l product/src/surfaces.php >/dev/null
php -l product/src/start.php >/dev/null
git -C product diff --name-only "$BASE_SHA"..HEAD | sort >/tmp/p01-large-library-files.txt
printf 'src/start.php\nsrc/surfaces.php\n' >/tmp/p01-large-library-expected.txt
diff -u /tmp/p01-large-library-expected.txt /tmp/p01-large-library-files.txt
echo P01_LARGE_LIBRARY_EXACT=PASS

rm -rf "$ROOT" "$COOKIE" /tmp/p01-large-library-ids.json
cp -a product/src "$ROOT"
php -S 127.0.0.1:$PORT -t "$ROOT" >/tmp/p01-large-library-server.log 2>&1 & echo $! >/tmp/p01-large-library.pid
for i in $(seq 1 30); do curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:$PORT/setup.php" -o /tmp/p01-large-library-setup.html && break || sleep 1; done
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-large-library-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:$PORT/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=Large Library Gate' \
  --data-urlencode 'admin_password=P01Large!Library' \
  --data-urlencode 'admin_password_confirm=P01Large!Library' \
  -o /tmp/p01-large-library-setup-post.html

cat >/tmp/p01-large-library-seed.php <<'PHP'
<?php
require '/tmp/p01-large-library/app/bootstrap.php';
require_once '/tmp/p01-large-library/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());
$a=$r->createCategory(['name'=>'开发工具','description'=>'','is_private'=>false]);
$b=$r->createCategory(['name'=>'AI 资料','description'=>'','is_private'=>false]);
$c=$r->createCategory(['name'=>'频道','description'=>'','is_private'=>false]);
$d=$r->createCategory(['name'=>'影视','description'=>'','is_private'=>false]);
for($i=1;$i<=180;$i++)$r->saveLink(null,['category_id'=>$a,'title'=>'Dev Tool '.str_pad((string)$i,3,'0',STR_PAD_LEFT),'url'=>'https://dev'.$i.'.example.com','description'=>'developer tool','tags'=>$i%10===0?'工具,常用':'工具','is_private'=>true,'is_favorite'=>$i%17===0],'manual');
for($i=1;$i<=60;$i++)$r->saveLink(null,['category_id'=>$b,'title'=>'AI Resource '.str_pad((string)$i,3,'0',STR_PAD_LEFT),'url'=>'https://ai'.$i.'.example.com','description'=>'ai resource','tags'=>'AI','is_private'=>true],'manual');
for($i=1;$i<=20;$i++){ $x=$r->saveLink(null,['category_id'=>$c,'title'=>'Channel '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://youtube.com/@large'.$i,'description'=>'channel','tags'=>'频道','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'channels','resource_kind'=>'creator','background_friendly'=>$i%2===0]); }
for($i=1;$i<=20;$i++){ $x=$r->saveLink(null,['category_id'=>$d,'title'=>'Movie '.str_pad((string)$i,2,'0',STR_PAD_LEFT),'url'=>'https://movie'.$i.'.example.com','description'=>'movie','tags'=>'影视','is_private'=>true],'manual');$s->upsertProfile((int)$x['id'],['surface'=>'watch','resource_kind'=>'movie','media_status'=>$i%2===0?'want':'watched']); }
file_put_contents('/tmp/p01-large-library-ids.json',json_encode(['dev'=>$a,'ai'=>$b,'channel'=>$c,'watch'=>$d],JSON_THROW_ON_ERROR));
echo "P01_LARGE_LIBRARY_SEED=PASS\n";
PHP
php /tmp/p01-large-library-seed.php | grep -Fx P01_LARGE_LIBRARY_SEED=PASS
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -X POST "http://127.0.0.1:$PORT/api.php?action=login" --data '{"password":"P01Large!Library"}' | jq -e '.ok==true' >/dev/null
echo P01_LARGE_LIBRARY_RUNTIME=PASS

BASE="http://127.0.0.1:$PORT"
DEV=$(jq -r .dev /tmp/p01-large-library-ids.json)

curl -fsS -b "$COOKIE" "$BASE/surfaces.php?per=30" -o /tmp/all-30.html
grep -F '280 项' /tmp/all-30.html >/dev/null
grep -F '当前 1–30' /tmp/all-30.html >/dev/null
grep -F 'aria-label="分类筛选"' /tmp/all-30.html >/dev/null
grep -F 'aria-label="资源模式筛选"' /tmp/all-30.html >/dev/null
grep -F 'aria-label="每页数量"' /tmp/all-30.html >/dev/null
grep -F 'page=2' /tmp/all-30.html >/dev/null
grep -F 'page=10' /tmp/all-30.html >/dev/null
curl -fsS -b "$COOKIE" "$BASE/surfaces.php?category=$DEV&per=30&page=2" -o /tmp/all-dev.html
grep -F '180 项' /tmp/all-dev.html >/dev/null
grep -F '开发工具' /tmp/all-dev.html >/dev/null
grep -F '当前 31–60' /tmp/all-dev.html >/dev/null
! grep -F 'AI Resource 001' /tmp/all-dev.html
curl -fsS -b "$COOKIE" "$BASE/surfaces.php?surface=channels&per=30" -o /tmp/all-channels.html
grep -F '20 项' /tmp/all-channels.html >/dev/null
grep -F 'Channels' /tmp/all-channels.html >/dev/null
! grep -F 'Movie 01' /tmp/all-channels.html
curl -fsS -b "$COOKIE" "$BASE/surfaces.php?per=100&page=2" -o /tmp/all-100-p2.html
grep -F '当前 101–200' /tmp/all-100-p2.html >/dev/null
grep -F '100 / 页' /tmp/all-100-p2.html >/dev/null
echo P01_LARGE_LIBRARY_ALL=PASS

curl -fsS -b "$COOKIE" "$BASE/start.php?per=30&page=3" -o /tmp/start-p3.html
grep -F '240 个网站与工具' /tmp/start-p3.html >/dev/null
grep -F '当前 61–90' /tmp/start-p3.html >/dev/null
grep -F 'aria-label="每页数量"' /tmp/start-p3.html >/dev/null
grep -F 'page=1' /tmp/start-p3.html >/dev/null
grep -F 'page=8' /tmp/start-p3.html >/dev/null
curl -fsS -b "$COOKIE" --get "$BASE/start.php" --data-urlencode 'category=AI 资料' --data-urlencode 'per=30' -o /tmp/start-ai.html
grep -F '60 个网站与工具' /tmp/start-ai.html >/dev/null
grep -F 'AI 资料' /tmp/start-ai.html >/dev/null
! grep -F 'Dev Tool 001' /tmp/start-ai.html
echo P01_LARGE_LIBRARY_START=PASS

php "$ROOT/cli/verify.php" | grep -Fx VERIFY_PASS=YES
php "$ROOT/cli/surface-verify.php" | grep -Fx MULTI_SURFACE_PASS=YES
php "$ROOT/cli/baseline-verify.php" | tee /tmp/p01-large-library-baseline.txt
grep -Fx BASELINE_CORE_PASS=YES /tmp/p01-large-library-baseline.txt
grep -Fx DRIFT_COUNT=0 /tmp/p01-large-library-baseline.txt
grep -Fx UNKNOWN_COUNT=0 /tmp/p01-large-library-baseline.txt
php -r 'require "/tmp/p01-large-library/app/bootstrap.php";$db=vf_db();if(strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(1);if($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC))exit(2);echo "P01_LARGE_LIBRARY_SQLITE=PASS\n";' | grep -Fx P01_LARGE_LIBRARY_SQLITE=PASS
echo P01_LARGE_LIBRARY_REGRESSION=PASS

echo P01_LARGE_LIBRARY_SOURCE=$SOURCE
echo P01_LARGE_LIBRARY_TREE=$TREE
echo P01_LARGE_LIBRARY_NAVIGATION_GATE=PASS
echo PRODUCT_FILES_CHANGED=2
echo SCHEMA_CHANGE=NO
echo PRODUCTION_WRITE=NO
