#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/tmp/p01-v2373-iyf-readiness
EVID=${EVID:-/tmp/p01-v2373-candidate-evidence}
rm -rf "$ROOT"
cp -a candidate/src "$ROOT"
mkdir -p "$EVID"

php -S 127.0.0.1:18531 -t "$ROOT" >"$EVID/iyf-server.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
COOKIE="$EVID/iyf.cookies"
for i in $(seq 1 80); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" http://127.0.0.1:18531/setup.php -o "$EVID/iyf-setup.html"; then break; fi
  sleep .25
done
CSRF=$(python3 - "$EVID/iyf-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST http://127.0.0.1:18531/setup.php \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=V2373 IYF Readiness' \
  --data-urlencode 'admin_password=V2373IYF!2026' \
  --data-urlencode 'admin_password_confirm=V2373IYF!2026' \
  -o "$EVID/iyf-setup-post.html"

test -f "$ROOT/app/.runtime.php"
ROOT="$ROOT" php <<'PHP' | tee "$EVID/iyf-e2e.jsonl"
<?php
require getenv('ROOT').'/app/bootstrap.php';
require getenv('ROOT').'/app/SurfaceRepository.php';
require getenv('ROOT').'/app/ResourceCoverCache.php';
$db=vf_db(); $repo=new VfRepository($db); $surface=new VfSurfaceRepository($db); $store=new VfResourceAssetStore($db);
$cat=$repo->createCategory(['name'=>'IYF READINESS','description'=>'','is_private'=>false]);
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
python3 - "$EVID/iyf-e2e.jsonl" <<'PY'
import json,sys
rows=[json.loads(x) for x in open(sys.argv[1],encoding='utf-8') if x.strip().startswith('{')]
assert len(rows)==3 and len({x['id'] for x in rows})==3, rows
for x in rows:
    assert x['result'].get('success') is True, x
    r=x['record']; assert r['mime'] in ('image/gif','image/webp','image/jpeg','image/png'), r
    assert int(r['bytes'])>64 and int(r['width'])>=32 and int(r['height'])>=32, r
print('P01_V2373_IYF_FIRST_ATTEMPT=3/3 PASS')
PY
for id in 1 2 3; do
  curl -fsS -D "$EVID/iyf-cover-$id.headers" "http://127.0.0.1:18531/resource-cover.php?id=$id" -o "$EVID/iyf-cover-$id.bin"
  grep -Eiq '^Content-Type: image/(gif|webp|jpeg|png)' "$EVID/iyf-cover-$id.headers"
  test "$(stat -c%s "$EVID/iyf-cover-$id.bin")" -gt 64
done
printf 'P01_V2373_IYF_RESOURCE_COVER_SERVE=3/3 PASS\n' | tee "$EVID/iyf-verdict.txt"
kill "$PID"; trap - EXIT
