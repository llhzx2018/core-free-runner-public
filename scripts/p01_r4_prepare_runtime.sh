#!/usr/bin/env bash
set -Eeuo pipefail

RUNTIME=/tmp/p01-r4-runtime
COOKIE=/tmp/p01-r4-setup.cookies
TEST_CRED="$(printf '%s%s%s' 'P01R4' 'Browser!' '2026')"

rm -rf "$RUNTIME" "$COOKIE"
cp -a candidate/src "$RUNTIME"
cd "$RUNTIME"
php -S 127.0.0.1:"$target_port" -t . >/tmp/p01-r4-server.log 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" >/tmp/p01-r4-server.pid

for i in $(seq 1 40); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:$target_port/setup.php" -o /tmp/p01-r4-setup.html; then break; fi
  sleep 1
done

SETUP_CSRF=$(python3 - <<'PY'
import re
text=open('/tmp/p01-r4-setup.html',encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',text)
assert m
print(m.group(1))
PY
)

curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:$target_port/setup.php"   --data-urlencode "setup_csrf=$SETUP_CSRF"   --data-urlencode 'site_title=VF Start R4 Browser'   --data-urlencode "admin_password=$TEST_CRED"   --data-urlencode "admin_password_confirm=$TEST_CRED"   -o /tmp/p01-r4-setup-post.html

php cli/verify.php | grep -Fx 'VERIFY_PASS=YES'

cat >/tmp/p01-r4-fixture.php <<'PHP'
<?php
declare(strict_types=1);
require __DIR__ . '/p01-r4-runtime/app/bootstrap.php';
require_once __DIR__ . '/p01-r4-runtime/app/SurfaceRepository.php';

$db=vf_db();
$repo=new VfRepository($db);
$surface=new VfSurfaceRepository($db);
$category=$repo->createCategory(['name'=>'R4 Browser','description'=>'','icon'=>'','is_private'=>0,'sort_order'=>0]);

$tool=(int)$repo->saveLink(null,[
    'surface'=>'start','category_id'=>$category,'title'=>'R4 Browser SEO Tool',
    'url'=>'https://example.com/r4-browser-tool','description'=>'R4 browser interactive fixture',
    'tags'=>['seo','关键词','工具'],'is_private'=>0,'is_pending'=>0
])['id'];

$software=(int)$repo->saveLink(null,[
    'surface'=>'start','category_id'=>$category,'title'=>'R4 Browser Search Software',
    'url'=>'https://example.com/r4-browser-software','description'=>'R4 browser software fixture',
    'tags'=>['windows','文件搜索','软件'],'is_private'=>0,'is_pending'=>0
])['id'];

$topic=(int)$repo->saveLink(null,[
    'surface'=>'topics','title'=>'R4 Browser Hosted Topic','url'=>'https://example.com/r4-topic',
    'description'=>'R4 hosted html','tags'=>[],'is_private'=>0,'is_pending'=>0
])['id'];
$surface->upsertProfile($topic,['surface'=>'topics','resource_kind'=>'guide','source_kind'=>'hosted_html','source_ref'=>'r4-topic.html']);

$htmlDir=VF_PRIVATE_ROOT.'/resource-assets/html';
if(!is_dir($htmlDir))mkdir($htmlDir,0750,true);
vf_write_storage_guards($htmlDir);
$html='<!doctype html><html><body><h1>R4 Hosted Browser Body</h1></body></html>';
$hash=hash('sha256',$html);
$file='topic-'.$topic.'-'.substr($hash,0,20).'.html';
file_put_contents($htmlDir.'/'.$file,$html,LOCK_EX);
chmod($htmlDir.'/'.$file,0640);
$now=gmdate('c');
$stmt=$db->prepare("INSERT INTO resource_asset_files(link_id,asset_kind,file_name,original_name,mime_type,byte_size,width,height,file_hash,created_at,updated_at) VALUES(?,'html',?,'r4-topic.html','text/html',?,NULL,NULL,?,?,?)");
$stmt->execute([$topic,$file,strlen($html),$hash,$now,$now]);

file_put_contents('/tmp/p01-r4-fixture.json',json_encode(['tool'=>$tool,'software'=>$software,'topic'=>$topic],JSON_UNESCAPED_SLASHES));
echo "P01_R4_FIXTURE=PASS\n";
PHP

php /tmp/p01-r4-fixture.php
echo "P01_R4_TEST_CRED=$TEST_CRED" >> "$GITHUB_ENV"
echo 'P01_R4_FRESH_RUNTIME=PASS'
