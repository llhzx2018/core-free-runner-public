#!/usr/bin/env bash
set -Eeuo pipefail

BASE=6f09d59e3ecc0ed54b9a3ae6e3fc6ba22b109ea1
PRODUCT_BRANCH=hotfix/p01-iyf-gif-cover-20260902
PRODUCT_DIR="${PRODUCT_DIR:-product}"
ROOT=/tmp/p01-iyf-hotfix-r3
EVID=/tmp/p01-iyf-gif-hotfix-r3-evidence
rm -rf "$ROOT" "$EVID"
mkdir -p "$EVID"

cd "$PRODUCT_DIR"
test "$(git rev-parse HEAD)" = "$BASE"
test "$(cat VERSION)" = 2.37.2

python3 - <<'PY'
from pathlib import Path
p=Path('src/app/ResourceCoverCache.php')
s=p.read_text(encoding='utf-8')
old="""        elseif (substr($bytes, 0, 4) === 'RIFF' && substr($bytes, 8, 4) === 'WEBP') $mime = 'image/webp';
        $exts = ['image/png'=>'png','image/jpeg'=>'jpg','image/webp'=>'webp'];
        if (!isset($exts[$mime])) throw new RuntimeException('自动封面仅接受 PNG、JPG、WebP。');"""
new="""        elseif (substr($bytes, 0, 4) === 'RIFF' && substr($bytes, 8, 4) === 'WEBP') $mime = 'image/webp';
        elseif (substr($bytes, 0, 6) === 'GIF87a' || substr($bytes, 0, 6) === 'GIF89a') $mime = 'image/gif';
        $exts = ['image/png'=>'png','image/jpeg'=>'jpg','image/webp'=>'webp','image/gif'=>'gif'];
        if (!isset($exts[$mime])) throw new RuntimeException('自动封面仅接受 PNG、JPG、WebP、GIF。');"""
if s.count(old)!=1: raise SystemExit('ResourceCoverCache anchor mismatch')
p.write_text(s.replace(old,new),encoding='utf-8')

p=Path('src/assets/workspace.js')
s=p.read_text(encoding='utf-8')
old='const coverRetryKey=(id)=>`vf-cover-retry:v3:${id}`;'
new='const coverRetryKey=(id)=>`vf-cover-retry:v4:${id}`;'
if s.count(old)!=1: raise SystemExit('workspace retry anchor mismatch')
p.write_text(s.replace(old,new),encoding='utf-8')
PY

expected=$'src/app/ResourceCoverCache.php\nsrc/assets/workspace.js'
test "$(git diff --name-only | sort)" = "$expected"
test "$(cat VERSION)" = 2.37.2
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$BASE":database)"
git diff --check
php -l src/app/ResourceCoverCache.php | tee "$EVID/php-lint.txt"
node --check src/assets/workspace.js
grep -F "'image/gif'=>'gif'" src/app/ResourceCoverCache.php >/dev/null
grep -F 'vf-cover-retry:v4:' src/assets/workspace.js >/dev/null
grep -F "\$extMap = ['image/webp'=>'webp','image/jpeg'=>'jpg','image/png'=>'png'];" src/app/ResourceAssetStore.php >/dev/null
cp -a src "$ROOT"
cd - >/dev/null

php -S 127.0.0.1:18521 -t "$ROOT" >"$EVID/server.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
COOKIE="$EVID/setup.cookies"
for i in $(seq 1 80); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" http://127.0.0.1:18521/setup.php -o "$EVID/setup.html"; then break; fi
  sleep .25
done
CSRF=$(python3 - "$EVID/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST http://127.0.0.1:18521/setup.php \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=IYF GIF Hotfix R3' \
  --data-urlencode 'admin_password=IYFGIF!2026' \
  --data-urlencode 'admin_password_confirm=IYFGIF!2026' \
  -o "$EVID/setup-post.html"

test -f "$ROOT/app/.runtime.php"

ROOT="$ROOT" php <<'PHP' | tee "$EVID/e2e.jsonl"
<?php
require getenv('ROOT').'/app/bootstrap.php';
require getenv('ROOT').'/app/SurfaceRepository.php';
require getenv('ROOT').'/app/ResourceCoverCache.php';
$db=vf_db(); $repo=new VfRepository($db); $surface=new VfSurfaceRepository($db); $store=new VfResourceAssetStore($db);
$cat=$repo->createCategory(['name'=>'IYF HOTFIX','description'=>'','is_private'=>false]);
$urls=[
 'https://www.iyf.tv/play/kr8SspeNzb3',
 'https://www.iyf.tv/play/MRcWYmJRueF',
 'https://mview.iyf.tv/play/27Qr2mVwuzJ'
];
foreach($urls as $i=>$url){
  $saved=$repo->saveLink(null,['category_id'=>$cat,'title'=>'IYF '.($i+1),'url'=>$url,'description'=>'','tags'=>'iyf','is_private'=>false,'is_favorite'=>false],'manual');
  $id=(int)($saved['id']??0); if($id<=0) throw new RuntimeException('seed id missing');
  $surface->upsertProfile($id,['surface'=>'watch','resource_kind'=>'电影']);
  $result=(new VfResourceCoverCache($db))->refreshOne($id,true);
  $record=$store->coverRecord($id);
  if(!$result['success'] || !$record || !is_file((string)$record['path'])) throw new RuntimeException('first-attempt cover persistence failed: '.$id);
  echo json_encode(['id'=>$id,'url'=>$url,'result'=>$result,'record'=>['mime'=>$record['mime_type'],'bytes'=>$record['byte_size'],'width'=>$record['width'],'height'=>$record['height'],'file'=>basename((string)$record['path'])]],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE),"\n";
}
PHP

python3 - "$EVID/e2e.jsonl" <<'PY'
import json,sys
rows=[json.loads(x) for x in open(sys.argv[1],encoding='utf-8') if x.strip().startswith('{')]
assert len(rows)==3 and len({x['id'] for x in rows})==3, rows
for x in rows:
    assert x['result'].get('success') is True, x
    r=x['record']; assert r['mime'] in ('image/gif','image/webp','image/jpeg','image/png'), r
    assert int(r['bytes'])>64 and int(r['width'])>=32 and int(r['height'])>=32, r
print('P01_IYF_FIRST_ATTEMPT_PERSIST=3/3 PASS')
PY

# Public test rows let us verify the actual resource-cover.php response without coupling the gate to login-form UX.
for id in 1 2 3; do
  curl -fsS -D "$EVID/cover-$id.headers" "http://127.0.0.1:18521/resource-cover.php?id=$id" -o "$EVID/cover-$id.bin"
  grep -Eiq '^Content-Type: image/(gif|webp|jpeg|png)' "$EVID/cover-$id.headers"
  test "$(stat -c%s "$EVID/cover-$id.bin")" -gt 64
done
printf 'P01_IYF_RESOURCE_COVER_SERVE=3/3 PASS\n' | tee "$EVID/serve-verdict.txt"

kill "$PID"; trap - EXIT

cd "$PRODUCT_DIR"
test "$(git diff --name-only | sort)" = "$expected"
test "$(cat VERSION)" = 2.37.2
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$BASE":database)"
git diff --check
git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add src/app/ResourceCoverCache.php src/assets/workspace.js
git commit -m 'fix(P01): support IYF GIF auto covers'
test "$(git diff --name-only "$BASE" HEAD | sort)" = "$expected"
CANDIDATE=$(git rev-parse HEAD)
TREE=$(git rev-parse HEAD^{tree})
RUNTIME_TREE=$(git rev-parse HEAD:src)
git push origin HEAD:"$PRODUCT_BRANCH"
printf 'P01_IYF_GIF_HOTFIX_GATE=PASS\nBASE=%s\nCANDIDATE=%s\nTREE=%s\nRUNTIME_TREE=%s\nFILES=2\nFIRST_ATTEMPT_E2E=3/3\nRESOURCE_COVER_SERVE=3/3\nVERSION_UNCHANGED=2.37.2\nSCHEMA_CHANGE=NO\nMIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' "$BASE" "$CANDIDATE" "$TREE" "$RUNTIME_TREE" | tee "$EVID/verdict.txt"
