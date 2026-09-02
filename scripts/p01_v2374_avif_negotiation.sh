#!/usr/bin/env bash
set -Eeuo pipefail

BASE=740610e6529dbc0997af3112d83c0aa95bd8d0ac
BRANCH=hotfix/p01-v2374-iyf-avif-negotiation-20260902
ROOT="$PWD/product"
EVID=/tmp/p01-v2374-avif-evidence
E2E=/tmp/p01-v2374-avif-e2e
rm -rf "$EVID" "$E2E"
mkdir -p "$EVID"

cd "$ROOT"
test "$(git rev-parse HEAD)" = "$BASE"
git fetch origin main --quiet
test "$(git rev-parse origin/main)" = "$BASE"
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  echo "product branch already exists: $BRANCH" >&2
  exit 11
fi

git checkout -b "$BRANCH"
python3 - <<'PY'
from pathlib import Path
p=Path('src/app/ResourceCoverCache.php')
s=p.read_text(encoding='utf-8')
old="image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1"
new="image/webp,image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.1"
assert s.count(old)==1, s.count(old)
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

p=Path('src/assets/workspace.js')
s=p.read_text(encoding='utf-8')
old='vf-cover-retry:v4:'
new='vf-cover-retry:v5:'
assert s.count(old)==1, s.count(old)
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
PY

mapfile -t changed < <(git diff --name-only | sort)
printf '%s\n' "${changed[@]}" | tee "$EVID/changed-files.txt"
test "${#changed[@]}" -eq 2
test "${changed[0]}" = 'src/app/ResourceCoverCache.php'
test "${changed[1]}" = 'src/assets/workspace.js'

grep -F "image/webp,image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.1" src/app/ResourceCoverCache.php >/dev/null
! grep -F "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1" src/app/ResourceCoverCache.php >/dev/null
grep -F 'vf-cover-retry:v5:' src/assets/workspace.js >/dev/null
! grep -F 'vf-cover-retry:v4:' src/assets/workspace.js >/dev/null
php -l src/app/ResourceCoverCache.php
node --check src/assets/workspace.js
git diff --check

cp -a src "$E2E"
php -S 127.0.0.1:18571 -t "$E2E" >"$EVID/server.log" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
COOKIE="$EVID/cookies.txt"
for i in $(seq 1 80); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" http://127.0.0.1:18571/setup.php -o "$EVID/setup.html"; then break; fi
  sleep .25
done
CSRF=$(python3 - "$EVID/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST http://127.0.0.1:18571/setup.php \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=V2374 AVIF Negotiation' \
  --data-urlencode 'admin_password=V2374Avif!2026' \
  --data-urlencode 'admin_password_confirm=V2374Avif!2026' \
  -o "$EVID/setup-post.html"

E2E="$E2E" php <<'PHP' | tee "$EVID/iyf-e2e.jsonl"
<?php
require getenv('E2E').'/app/bootstrap.php';
require getenv('E2E').'/app/SurfaceRepository.php';
require getenv('E2E').'/app/ResourceCoverCache.php';
require getenv('E2E').'/app/ResourceAssetStore.php';
$db=vf_db(); $repo=new VfRepository($db); $surface=new VfSurfaceRepository($db); $store=new VfResourceAssetStore($db);
$cat=$repo->createCategory(['name'=>'IYF V2374','description'=>'','is_private'=>false]);
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
  echo json_encode(['id'=>$id,'url'=>$url,'result'=>$result,'mime'=>$record['mime_type']??null,'bytes'=>$record['byte_size']??null],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE),"\n";
  if(empty($result['success']) || !$record || !is_file((string)$record['path'])) throw new RuntimeException('IYF cover failed: '.$url.' / '.($result['error']??'unknown'));
  if(!in_array((string)$record['mime_type'],['image/gif','image/webp','image/jpeg','image/png'],true)) throw new RuntimeException('unexpected stored mime: '.(string)$record['mime_type']);
}
PHP
kill "$PID"; trap - EXIT
python3 - "$EVID/iyf-e2e.jsonl" <<'PY'
import json,sys
rows=[json.loads(x) for x in open(sys.argv[1],encoding='utf-8') if x.strip().startswith('{')]
assert len(rows)==3 and all(x['result'].get('success') is True for x in rows), rows
assert all(x.get('mime') in ('image/gif','image/webp','image/jpeg','image/png') for x in rows), rows
print('P01_V2374_IYF_E2E=3/3 PASS')
PY

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add src/app/ResourceCoverCache.php src/assets/workspace.js
git commit -m 'fix(P01): align remote cover negotiation with validator'
CANDIDATE=$(git rev-parse HEAD)
git push origin "HEAD:refs/heads/$BRANCH"
printf 'P01_V2374_AVIF_NEGOTIATION_GATE=PASS\nBASE=%s\nCANDIDATE=%s\nFILES=2\nAVIF_ADVERTISED=NO\nGIF_WEBP_JPEG_PNG=YES\nRETRY_REVISION=v5\nIYF_E2E=3/3\nVERSION_CHANGE=NO\nSCHEMA_CHANGE=NO\nMAIN_WRITE=NO\nOWNER_PRODUCTION_WRITE=NO\n' "$BASE" "$CANDIDATE" | tee "$EVID/verdict.txt"
