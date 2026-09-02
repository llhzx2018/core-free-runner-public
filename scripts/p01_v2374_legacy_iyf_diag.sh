#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=/tmp/p01-v2374-legacy-iyf
EVID=/tmp/p01-v2374-legacy-iyf-evidence
rm -rf "$ROOT" "$EVID"
mkdir -p "$EVID"
cp -a product/src "$ROOT"

# Record DNS order and independently probe every IPv4 edge for the exact legacy page.
{
  echo '=== getent www.iyf.tv ==='
  getent ahosts www.iyf.tv || true
  echo '=== getent static.iyf.tv ==='
  getent ahosts static.iyf.tv || true
} | tee "$EVID/dns.txt"
mapfile -t PAGE_IPS < <(getent ahostsv4 www.iyf.tv 2>/dev/null | awk '{print $1}' | sort -u)
: > "$EVID/page-edges.txt"
for ip in "${PAGE_IPS[@]}"; do
  out="$EVID/page-${ip//:/_}.html"
  code=$(curl -L -sS --max-time 15 --resolve "www.iyf.tv:443:$ip" \
    -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/139 Safari/537.36' \
    -H 'Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.1' \
    -o "$out" -w '%{http_code}' 'https://www.iyf.tv/play/MRcWYmJRueF' || true)
  og=$(grep -Eio '<meta[^>]+(?:property|name)=["'"']og:image["'"'][^>]*>' "$out" 2>/dev/null | head -1 || true)
  printf 'PAGE_EDGE ip=%s http=%s bytes=%s og=%s\n' "$ip" "$code" "$(wc -c < "$out" 2>/dev/null || echo 0)" "${og:+yes}" | tee -a "$EVID/page-edges.txt"
done
mapfile -t STATIC_IPS < <(getent ahostsv4 static.iyf.tv 2>/dev/null | awk '{print $1}' | sort -u)
: > "$EVID/static-edges.txt"
for ip in "${STATIC_IPS[@]}"; do
  out="$EVID/static-${ip//:/_}.bin"
  meta=$(curl -sS --max-time 15 --resolve "static.iyf.tv:443:$ip" \
    -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/139 Safari/537.36' \
    -H 'Accept: image/webp,image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.1' \
    -o "$out" -w '%{http_code}|%{content_type}|%{size_download}' \
    'https://static.iyf.tv/upload/video/201912091636023668662.gif' || true)
  printf 'STATIC_EDGE ip=%s meta=%s\n' "$ip" "$meta" | tee -a "$EVID/static-edges.txt"
done

php -S 127.0.0.1:18641 -t "$ROOT" >"$EVID/server.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT
COOKIE="$EVID/cookies.txt"
for i in $(seq 1 80); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" http://127.0.0.1:18641/setup.php -o "$EVID/setup.html"; then break; fi
  sleep .25
done
CSRF=$(python3 - "$EVID/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST http://127.0.0.1:18641/setup.php \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=Legacy IYF Replay' \
  --data-urlencode 'admin_password=LegacyIYF!2026' \
  --data-urlencode 'admin_password_confirm=LegacyIYF!2026' \
  -o "$EVID/setup-post.html"

ROOT="$ROOT" php <<'PHP' | tee "$EVID/replay.jsonl"
<?php
require getenv('ROOT').'/app/bootstrap.php';
require getenv('ROOT').'/app/SurfaceRepository.php';
require getenv('ROOT').'/app/ResourceCoverCache.php';
$db=vf_db();
$repo=new VfRepository($db); $surface=new VfSurfaceRepository($db); $store=new VfResourceAssetStore($db);
$cat=$repo->createCategory(['name'=>'娱乐影音','description'=>'','is_private'=>true]);
$data=[
 'category_id'=>$cat,
 'title'=>'天真遇到现实',
 'url'=>'https://www.iyf.tv/play/MRcWYmJRueF',
 'description'=>'《天真遇到现实》回看入口，挂链后重新搜同名片源。',
 'tags'=>[],
 'is_private'=>true,
 'is_favorite'=>false,
 'is_pending'=>false,
 'sort_order'=>0,
 'click_count'=>0,
 'created_at'=>'2026-08-04T15:16:40.768280Z'
];
$saved=$repo->saveLink(null,$data,'import');
$id=(int)$saved['id'];
$surface->upsertProfile($id,['surface'=>'watch','resource_kind'=>'电影']);
$row=$db->query('SELECT id,url,normalized_url,is_private,is_pending,url_type,url_protected,sensitive_detected,source_type FROM links WHERE id='.(int)$id)->fetch(PDO::FETCH_ASSOC);
echo json_encode(['seed'=>$row],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE),"\n";
$cache=new VfResourceCoverCache($db);
for($i=1;$i<=12;$i++){
  $r=$cache->refreshOne($id,true);
  $record=$store->coverRecord($id);
  echo json_encode(['attempt'=>$i,'result'=>$r,'record'=>$record?['mime'=>$record['mime_type'],'bytes'=>$record['byte_size'],'width'=>$record['width'],'height'=>$record['height']]:null],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE),"\n";
  usleep(150000);
}
PHP

python3 - "$EVID/replay.jsonl" <<'PY'
import json,sys
rows=[json.loads(x) for x in open(sys.argv[1],encoding='utf-8') if x.strip().startswith('{')]
seed=rows[0]['seed']; attempts=rows[1:]
print('SEED='+json.dumps(seed,ensure_ascii=False,separators=(',',':')))
print('ATTEMPTS=%d SUCCESS=%d FAIL=%d' % (len(attempts),sum(1 for x in attempts if x['result'].get('success')),sum(1 for x in attempts if not x['result'].get('success'))))
for x in attempts:
    r=x['result']; print('ATTEMPT_%02d success=%s provider=%s source=%s error=%s mime=%s' % (x['attempt'],r.get('success'),r.get('provider'),r.get('source',''),r.get('error',''),(x.get('record') or {}).get('mime','')))
assert seed['url']=='https://www.iyf.tv/play/MRcWYmJRueF'
assert int(seed['is_pending'])==0 and int(seed['url_protected'])==0 and int(seed['sensitive_detected'])==0
PY

printf 'P01_V2374_LEGACY_IYF_REPLAY_DONE\n' | tee "$EVID/verdict.txt"
kill "$PID"; trap - EXIT
