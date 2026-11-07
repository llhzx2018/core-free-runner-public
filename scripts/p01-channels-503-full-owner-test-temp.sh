#!/usr/bin/env bash
set -Eeuo pipefail
candidate="$WORK/candidate"
node --check "$candidate/src/assets/local-subsite-management.js"
node --check "$candidate/src/assets/global-remote-channels.js"
php -l "$candidate/src/app/ChannelLibraryPage.php"
php -l "$candidate/src/app/bootstrap.php"
for name in p01_channels_full_inventory_failure_receipt_contract.cjs p01_ia5_remote_channels_r34_contract.cjs p01_ia6_advanced_field_readback_contract.cjs p01_local_management_empty_resources_contract.cjs; do
  node "$candidate/tests/unit/$name"
done
echo P01_503_EXACT_SOURCE_FOCUSED_CONTRACTS=PASS

(cd "$candidate" && bash tests/canonical_release_regression.sh . "$WORK/baseline" --require-zero-debt) > "$WORK/canonical.log" 2>&1 || {
  tail -n 120 "$WORK/canonical.log"; exit 31;
}
tail -n 10 "$WORK/canonical.log"
grep -Fx 'P01_CANONICAL_UNIT_REGRESSION=PASS' "$WORK/canonical.log"
grep -Fx 'P01_CANONICAL_ZERO_DEBT_REQUIRED=PASS' "$WORK/canonical.log"
echo P01_503_CANONICAL_REGRESSION=PASS

mkdir -p "$WORK/site"
cp -a "$candidate/src/." "$WORK/site/"
port=18153
cookie="$WORK/cookies.txt"
php -S 127.0.0.1:"$port" -t "$WORK/site" > "$WORK/server.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
for n in $(seq 1 40); do
  if curl -fsS -c "$cookie" -b "$cookie" "http://127.0.0.1:$port/setup.php" -o "$WORK/setup.html"; then break; fi
  sleep 1
done
test -s "$WORK/setup.html"
csrf="$(python3 - "$WORK/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s)
assert m
print(m.group(1))
PY
)"
pass='Disposable-503-Only!'
curl -fsS -c "$cookie" -b "$cookie" -X POST "http://127.0.0.1:$port/setup.php" \
  --data-urlencode "setup_csrf=$csrf" --data-urlencode "site_title=Disposable Channel" \
  --data-urlencode "admin_password=$pass" --data-urlencode "admin_password_confirm=$pass" \
  -o "$WORK/setup-post.html"
(cd "$WORK/site" && php cli/verify.php) | grep -Fx 'VERIFY_PASS=YES'
test "$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/setup.php")" = 302
login="$(curl -fsS -c "$cookie" -b "$cookie" -H 'Content-Type: application/json' \
  -d "{\"password\":\"$pass\"}" "http://127.0.0.1:$port/api.php?action=login")"
token="$(printf '%s' "$login" | jq -r '.csrf // empty')"
test -n "$token"
echo P01_503_REAL_CLEAN_INSTALL_LOGIN_SETUP_LOCK=PASS

P01_SYNTHETIC_CHANNEL_PARITY=YES P01_CHANNEL_SITE_ROOT="$WORK/site" \
  php "$candidate/tests/integration/p01_channels_130_parity_fixture.php"
for off in 0 60 120; do
  curl -fsS -c "$cookie" -b "$cookie" \
    "http://127.0.0.1:$port/api.php?action=resource_inventory&surface=channels&organized_only=1&limit=60&offset=$off" \
    -o "$WORK/p$off.json"
done
python3 - "$WORK" <<'PY'
import json,sys
w=sys.argv[1]; pages=[json.load(open(f'{w}/p{x}.json')) for x in (0,60,120)]
assert all(x['ok'] and x['total']==130 and x['organized_only']==1 for x in pages)
assert [len(x['rows']) for x in pages]==[60,60,10]
ids=[r['id'] for p in pages for r in p['rows']]
assert len(ids)==len(set(ids))==130
assert all(r['is_pending']==0 and r['surface']=='channels' for p in pages for r in p['rows'])
print('P01_503_REAL_130_ORGANIZED_3_PAGES_IDENTITIES=PASS')
PY
id="$(jq -r '.rows[-1].id' "$WORK/p120.json")"
test "$id" -gt 0
curl -fsS -c "$cookie" -b "$cookie" \
  "http://127.0.0.1:$port/api.php?action=resource_inventory_detail&id=$id" \
  -o "$WORK/detail.json"
jq -n --slurpfile d "$WORK/detail.json" \
 '($d[0]) | {id,title:(.title+" verified"),url,description,tags,
  expected_title:.title,expected_url:.url,
  expected_description:.description,expected_tags:.tags,
  expected_updated_at:.updated_at}' > "$WORK/patch.json"
curl -fsS -c "$cookie" -b "$cookie" -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $token" \
  --data-binary @"$WORK/patch.json" \
  "http://127.0.0.1:$port/api.php?action=link_basic_patch" \
  -o "$WORK/patch-result.json"
jq -e --argjson id "$id" '.ok==true and .id==$id and (.title | endswith(" verified"))' "$WORK/patch-result.json" >/dev/null
curl -fsS -c "$cookie" -b "$cookie" \
  "http://127.0.0.1:$port/api.php?action=resource_inventory_detail&id=$id" \
  -o "$WORK/after.json"
jq -e --argjson id "$id" '.id==$id and (.title | endswith(" verified"))' "$WORK/after.json" >/dev/null
guest_code="$(curl -sS -o /dev/null -w '%{http_code}' \
 "http://127.0.0.1:$port/api.php?action=resource_inventory&surface=channels")"
test "$guest_code" = 401 || test "$guest_code" = 403
echo P01_503_LAST_PAGE_CAS_EDIT_READBACK_GUEST_DENY=PASS

cat > "$WORK/failures.php" <<'PHP'
<?php
declare(strict_types=1);
$site=getenv('P01_SITE_ROOT');
require $site.'/app/bootstrap.php';
require $site.'/app/Repository.php';
require $site.'/app/SurfaceRepository.php';
$repo=new VfRepository(vf_db());
$codes=['YT_ATOM_HTTP_404','YT_HTTP_403','YT_TIMEOUT','YT_CHANNEL_ID_UNRESOLVED'];
$texts=['订阅源暂不可用','YouTube 拒绝访问','连接超时','频道 ID 无法识别'];
$cache=[];
foreach($codes as $i=>$code){
  $url='https://www.youtube.com/channel/UC'.str_pad((string)($i+1),22,'0',STR_PAD_LEFT);
  $r=$repo->saveLink(null,['surface'=>'channels',
    'title'=>'Synthetic failed channel '.($i+1),'url'=>$url,
    'description'=>'test only','is_private'=>1,'is_pending'=>0]);
  $id=(int)$r['id'];
  if($id<=0)throw new RuntimeException('Synthetic seed failed');
  $cache[(string)$id]=['url_hash'=>hash('sha256',$url),'attempted_at'=>time()-600,
    'error_code'=>$code,'error'=>$texts[$i],'checked_at'=>0,'items'=>[],'new_count'=>0];
}
file_put_contents(VF_PRIVATE_ROOT.'/youtube-channel-updates.json',
  json_encode($cache,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
echo VF_PRIVATE_ROOT.'/youtube-channel-updates.json';
PHP
cache="$(P01_SITE_ROOT="$WORK/site" php "$WORK/failures.php")"
test -s "$cache"
sha="$(sha256sum "$cache" | awk '{print $1}')"
curl -fsS -c "$cookie" -b "$cookie" \
 "http://127.0.0.1:$port/channels.php?view=directory" -o "$WORK/owner.html"
curl -fsS "http://127.0.0.1:$port/channels.php?view=directory" -o "$WORK/guest.html"
python3 - "$WORK" <<'PY'
import re,html,json,sys
w=sys.argv[1];owner=open(w+'/owner.html').read();guest=open(w+'/guest.html').read()
match=re.search(r'<script type="application/json" id="vf-channel-failure-receipt">(.*?)</script>',owner,re.S)
assert match,'owner failure receipt missing'
rows=json.loads(html.unescape(match.group(1)))
assert len(rows)==4,rows
assert set(r['code'] for r in rows)=={'YT_ATOM_HTTP_404','YT_HTTP_403','YT_TIMEOUT','YT_CHANNEL_ID_UNRESOLVED'}
assert 'vf-channel-failure-receipt' not in guest
print('P01_503_REAL_4_FAILURE_CODES_OWNER_ONLY=PASS')
PY
test "$(sha256sum "$cache" | awk '{print $1}')" = "$sha"
echo P01_503_CACHED_FAILURE_READBACK_NO_WRITE=PASS
