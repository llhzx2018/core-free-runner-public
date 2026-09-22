#!/usr/bin/env bash
set -Eeuo pipefail

RUNTIME=/tmp/p01-uxui-runtime
COOKIE=/tmp/p01-uxui-setup.cookies
TEST_CRED="$(printf '%s%s%s' 'P01UXUI' 'Visual!' '2026')"

rm -rf "$RUNTIME" "$COOKIE" /tmp/p01-uxui-screens
cp -a candidate/src "$RUNTIME"
cd "$RUNTIME"

php -S 127.0.0.1:"$target_port" -t . >/tmp/p01-uxui-server.log 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" >/tmp/p01-uxui-server.pid

for i in $(seq 1 40); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:$target_port/setup.php" -o /tmp/p01-uxui-setup.html; then break; fi
  sleep 1
done

SETUP_CSRF=$(python3 - <<'PY'
import re
text=open('/tmp/p01-uxui-setup.html',encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',text)
assert m
print(m.group(1))
PY
)

curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:$target_port/setup.php"   --data-urlencode "setup_csrf=$SETUP_CSRF"   --data-urlencode 'site_title=VF Start UXUI Audit'   --data-urlencode "admin_password=$TEST_CRED"   --data-urlencode "admin_password_confirm=$TEST_CRED"   -o /tmp/p01-uxui-setup-post.html

php cli/verify.php | grep -Fx 'VERIFY_PASS=YES'

cat >/tmp/p01-uxui-fixture.php <<'PHP'
<?php
declare(strict_types=1);
require __DIR__ . '/p01-uxui-runtime/app/bootstrap.php';
require_once __DIR__ . '/p01-uxui-runtime/app/SurfaceRepository.php';

$db=vf_db();
$repo=new VfRepository($db);
$surface=new VfSurfaceRepository($db);

$publicCat=$repo->createCategory([
  'name'=>'常用工具','description'=>'视觉审计公开分类','icon'=>'','is_private'=>0,'sort_order'=>0
]);
$privateCat=$repo->createCategory([
  'name'=>'私人收藏','description'=>'视觉审计私人分类','icon'=>'','is_private'=>1,'sort_order'=>10
]);

$save=function(array $row) use ($repo): int {
  return (int)$repo->saveLink(null,$row)['id'];
};

$save([
  'surface'=>'start','category_id'=>$publicCat,'title'=>'Google Search Console',
  'url'=>'https://search.google.com/search-console/about','description'=>'SEO 搜索表现与索引检查',
  'tags'=>['seo','站长','工具'],'is_private'=>0,'is_pending'=>0
]);
$save([
  'surface'=>'start','category_id'=>$publicCat,'title'=>'Everything',
  'url'=>'https://www.voidtools.com/','description'=>'Windows 文件搜索软件',
  'tags'=>['windows','文件搜索','软件'],'is_private'=>0,'is_pending'=>0
]);
$save([
  'surface'=>'start','category_id'=>$privateCat,'title'=>'待整理示例',
  'url'=>'https://example.com/pending','description'=>'用于后台待整理视觉审计',
  'tags'=>['待整理'],'is_private'=>1,'is_pending'=>1
]);
$save([
  'surface'=>'start','category_id'=>$privateCat,'title'=>'私人资源示例',
  'url'=>'https://example.com/private','description'=>'用于后台资源列表视觉审计',
  'tags'=>['私人'],'is_private'=>1,'is_pending'=>0
]);

$save([
  'surface'=>'channels','title'=>'Fireship','url'=>'https://www.youtube.com/@Fireship',
  'description'=>'开发频道示例','tags'=>['开发','YouTube'],'is_private'=>0,'is_pending'=>0
]);
$save([
  'surface'=>'watch','title'=>'示例影片','url'=>'https://example.com/watch/movie',
  'description'=>'影视资源示例','tags'=>['电影'],'is_private'=>0,'is_pending'=>0
]);
$save([
  'surface'=>'topics','title'=>'SEO 实战专题','url'=>'https://example.com/topic/seo',
  'description'=>'专题资源示例','tags'=>['SEO'],'is_private'=>0,'is_pending'=>0
]);
$save([
  'surface'=>'books','title'=>'一个人做出海网站','url'=>'https://example.com/course/solo-site',
  'description'=>'课程资源示例','tags'=>['课程'],'is_private'=>0,'is_pending'=>0
]);
$save([
  'surface'=>'projects','title'=>'P01 · VF Start','url'=>'https://example.com/projects/p01-vf-start',
  'description'=>'项目资源示例','tags'=>['VF','项目'],'is_private'=>0,'is_pending'=>0
]);

echo "P01_UXUI_FIXTURE=PASS\n";
PHP

php /tmp/p01-uxui-fixture.php
mkdir -p /tmp/p01-uxui-screens
echo "P01_UXUI_TEST_CRED=$TEST_CRED" >> "$GITHUB_ENV"
echo 'P01_UXUI_FRESH_RUNTIME=PASS'
