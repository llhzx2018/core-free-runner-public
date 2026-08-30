#!/usr/bin/env bash
set -Eeuo pipefail

: "${SOURCE:?SOURCE required}"
: "${TREE:?TREE required}"
: "${BASELINE:?BASELINE required}"
ROOT=${ROOT:-/tmp/p01-l2-resource-efficiency}
COOKIE=${COOKIE:-/tmp/p01-l2-resource-efficiency.cookies}
PORT=${PORT:-18342}
EVIDENCE=${EVIDENCE:-/tmp/p01-l2-resource-efficiency-evidence}

rm -rf "$ROOT" "$COOKIE" "$EVIDENCE"
mkdir -p "$EVIDENCE"

test "$(git -C product rev-parse HEAD)" = "$SOURCE"
test "$(git -C product rev-parse HEAD^{tree})" = "$TREE"
test "$(cat product/VERSION)" = "2.33.0"
python3 - <<'PY'
import json
p=json.load(open('product/VF_PROJECT.json',encoding='utf-8'))
assert p['project_id']=='P01', p
assert p['repository']=='llhzx2018/vf-start', p
assert p['working_version']=='2.33.0', p
assert str(p['working_schema_version'])=='2026082901', p
print('P01_L2_AUTHORITY=PASS')
PY

git -C product diff --name-only "$BASELINE"..HEAD | sort > /tmp/p01-l2-files.txt
cat > /tmp/p01-l2-expected.txt <<'EOF'
.github/workflows/multi-surface.yml
.github/workflows/repository-health.yml
docs/authority/ACCEPTANCE_MATRIX.md
docs/authority/CURRENT.md
docs/evidence/P01_PRIVATE_ACTIONS_RUNNER_BOUNDARY_20260830.md
src/app/FunctionalWorkspace.php
src/app/SurfaceShell.php
src/assets/surface-home.js
src/assets/workspace-create-bundle.js
src/assets/workspace-primary-open.js
src/assets/workspace-rebaseline.js
src/assets/workspace.js
src/cli/surface-verify.php
src/workspace-action.php
EOF
diff -u /tmp/p01-l2-expected.txt /tmp/p01-l2-files.txt
printf '%s\n' 'P01_L2_EXACT_DIFF=PASS'

find product/src -type f -name '*.php' -print0 | xargs -0 -r -n1 php -l >/dev/null
find product/src -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >/dev/null
printf '%s\n' 'P01_L2_SYNTAX=PASS'

cp -a product/src "$ROOT"
php -S 127.0.0.1:$PORT -t "$ROOT" > /tmp/p01-l2-server.log 2>&1 &
echo $! > /tmp/p01-l2-server.pid
for i in $(seq 1 30); do
  if curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:$PORT/setup.php" -o /tmp/p01-l2-setup.html; then break; fi
  sleep 1
done
CSRF=$(python3 - <<'PY'
import re
text=open('/tmp/p01-l2-setup.html',encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',text)
assert m, 'setup csrf missing'
print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:$PORT/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=P01 L2 Resource Efficiency Gate' \
  --data-urlencode 'admin_password=P01L2!Resource' \
  --data-urlencode 'admin_password_confirm=P01L2!Resource' \
  -o /tmp/p01-l2-setup-post.html
test -f "$ROOT/app/.runtime.php"

cat > /tmp/p01-l2-seed.php <<'PHP'
<?php
declare(strict_types=1);
require '/tmp/p01-l2-resource-efficiency/app/bootstrap.php';
require_once '/tmp/p01-l2-resource-efficiency/app/SurfaceRepository.php';
$r = new VfRepository(vf_db());
$s = new VfSurfaceRepository(vf_db());
$db = vf_db();
$dev = $r->createCategory(['name'=>'开发工具','description'=>'','is_private'=>false]);
$ai = $r->createCategory(['name'=>'AI 资料','description'=>'','is_private'=>false]);
$ops = $r->createCategory(['name'=>'运维工具','description'=>'','is_private'=>false]);
$ids = [];
for ($i=1; $i<=423; $i++) {
    $category = $i <= 210 ? $dev : ($i <= 360 ? $ai : $ops);
    $title = $i === 423 ? 'Needle Resource 423' : 'Resource '.str_pad((string)$i, 3, '0', STR_PAD_LEFT);
    $saved = $r->saveLink(null, [
        'category_id'=>$category,
        'title'=>$title,
        'url'=>'https://resource'.$i.'.example.com',
        'description'=>$i % 25 === 0 ? '常用效率工具' : 'resource fixture',
        'tags'=>$i % 10 === 0 ? '效率,常用' : '效率',
        'is_private'=>true,
        'is_favorite'=>$i % 37 === 0,
    ], 'manual');
    $ids[] = (int)$saved['id'];
}
$recent = [
    [$ids[0], 3],
    [$ids[1], 20],
    [$ids[2], 60],
    [$ids[3], 150],
];
$update = $db->prepare('UPDATE resource_domain_profiles SET last_opened_at=?, updated_at=? WHERE link_id=?');
foreach ($recent as [$id,$days]) {
    $s->recordOpen((int)$id);
    $stamp = gmdate('c', time() - ((int)$days * 86400));
    $update->execute([$stamp,$stamp,(int)$id]);
}
file_put_contents('/tmp/p01-l2-ids.json', json_encode([
    'all'=>$ids,
    'dev'=>$dev,
    'ai'=>$ai,
    'ops'=>$ops,
    'recent'=>array_map(static fn($x)=>(int)$x[0],$recent),
], JSON_THROW_ON_ERROR));
echo "P01_L2_SEED=PASS\n";
PHP
php /tmp/p01-l2-seed.php | grep -Fx 'P01_L2_SEED=PASS'

curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "http://127.0.0.1:$PORT/api.php?action=login" \
  --data '{"password":"P01L2!Resource"}' | jq -e '.ok==true' >/dev/null
printf '%s\n' 'P01_L2_RUNTIME=PASS'

BASE="http://127.0.0.1:$PORT"
curl -fsS -b "$COOKIE" "$BASE/surfaces.php?per=100" -o /tmp/p01-l2-all.html
grep -F '423 项' /tmp/p01-l2-all.html >/dev/null
grep -F '当前 1–100' /tmp/p01-l2-all.html >/dev/null
grep -F 'id="vf-workspace-data"' /tmp/p01-l2-all.html >/dev/null
curl -fsS -b "$COOKIE" --get "$BASE/surfaces.php" --data-urlencode 'q=Needle Resource 423' -o /tmp/p01-l2-search.html
grep -F '1 项' /tmp/p01-l2-search.html >/dev/null
grep -F 'Needle Resource 423' /tmp/p01-l2-search.html >/dev/null
printf '%s\n' 'P01_L2_SEARCH=PASS'

for window in 7 30 90; do
  curl -fsS -b "$COOKIE" "$BASE/surfaces.php?view=recent&recent_window=$window" -o "/tmp/p01-l2-recent-$window.html"
done
curl -fsS -b "$COOKIE" "$BASE/surfaces.php?view=recent" -o /tmp/p01-l2-recent-all.html
grep -F '1 项' /tmp/p01-l2-recent-7.html >/dev/null
grep -F '2 项' /tmp/p01-l2-recent-30.html >/dev/null
grep -F '3 项' /tmp/p01-l2-recent-90.html >/dev/null
grep -F '4 项' /tmp/p01-l2-recent-all.html >/dev/null
grep -F 'aria-label="最近使用时间范围"' /tmp/p01-l2-recent-7.html >/dev/null
printf '%s\n' 'P01_L2_RECENT_WINDOWS=PASS'

php "$ROOT/cli/verify.php" | tee /tmp/p01-l2-verify.txt
grep -Fx 'VERIFY_PASS=YES' /tmp/p01-l2-verify.txt
php "$ROOT/cli/surface-verify.php" | tee /tmp/p01-l2-surface.txt
grep -Fx 'CURRENT_DOMAIN_PASS=YES' /tmp/p01-l2-surface.txt
grep -Fx 'MULTI_SURFACE_PASS=YES' /tmp/p01-l2-surface.txt
grep -Fx 'WORKING_SCHEMA=2026082901' /tmp/p01-l2-surface.txt
php -r 'require "/tmp/p01-l2-resource-efficiency/app/bootstrap.php";$db=vf_db();if(strtolower((string)$db->query("PRAGMA integrity_check")->fetchColumn())!=="ok")exit(1);if($db->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC))exit(2);echo "P01_L2_SQLITE=PASS\n";' | grep -Fx 'P01_L2_SQLITE=PASS'
printf '%s\n' 'P01_L2_MACHINE_REGRESSION=PASS'

printf 'P01_L2_SOURCE=%s\n' "$SOURCE"
printf 'P01_L2_TREE=%s\n' "$TREE"
printf '%s\n' 'P01_L2_MACHINE_PREP=PASS'
