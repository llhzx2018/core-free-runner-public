#!/usr/bin/env bash
set -Eeuo pipefail

: "${VF_PRIVATE_READ_TOKEN:?VF_PRIVATE_READ_TOKEN is required}"
PRODUCT_BRANCH='candidate/p01-v2390-unified-groups-20260902'
EXPECTED_HEAD='31ee6e2aa2e95d59852e32e134fc71e3100aac54'
EXPECTED_BASE='3ae355f7ec20e148acffbd15d17afb07472d09c1'
PRODUCT_URL="https://x-access-token:${VF_PRIVATE_READ_TOKEN}@github.com/llhzx2018/vf-start.git"
WORK="$RUNNER_TEMP/p01-v2390-pr226"
P="$WORK/product"
RUNTIME="$WORK/runtime"
BASE='http://127.0.0.1:18390'

rm -rf "$WORK"
mkdir -p "$WORK"

echo '== Exact private source checkout =='
git clone -q --branch "$PRODUCT_BRANCH" --single-branch "$PRODUCT_URL" "$P"
test "$(git -C "$P" rev-parse HEAD)" = "$EXPECTED_HEAD"
git -C "$P" fetch -q origin main:refs/remotes/origin/main
test "$(git -C "$P" rev-parse origin/main)" = "$EXPECTED_BASE"

test "$(cat "$P/VERSION")" = "$(git -C "$P" show origin/main:VERSION)"
test "$(cat "$P/VF_PROJECT.json")" = "$(git -C "$P" show origin/main:VF_PROJECT.json)"

cat > "$WORK/expected-files.txt" <<'EOF'
docs/evidence/V2.39.0_CANDIDATE_GATE_20260902.md
docs/evidence/V2.39.0_UNIFIED_RESOURCE_GROUPS_DESIGN.md
src/app/FunctionalWorkspace.php
src/app/FunctionalWorkspaceCore.php
src/app/FunctionalWorkspaceShell.php
src/app/KewaroProjectImporter.php
src/app/SurfaceRepository.php
src/app/SurfaceShell.php
src/assets/auth-controls.js
src/assets/workspace-create-bundle.js
src/assets/workspace-projects.css
src/assets/workspace.js
src/migrations/2026090201_v239_unified_resource_groups.php
src/projects-kewaro-import.php
src/projects.php
src/surface.php
src/workspace-action.php
src/workspace-create.php
src/workspace-save.php
EOF
git -C "$P" diff --name-only origin/main...HEAD | sort > "$WORK/actual-files.txt"
diff -u "$WORK/expected-files.txt" "$WORK/actual-files.txt"
echo 'P01_V2390_EXACT_SOURCE=PASS'

echo '== Full source syntax and destructive-move boundaries =='
find "$P/src" -type f -name '*.php' -print0 | xargs -0 -r -n1 php -l >/dev/null
find "$P/src" -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >/dev/null
grep -q "public const SURFACES = \['start', 'channels', 'watch', 'topics', 'projects'\]" "$P/src/app/SurfaceRepository.php"
grep -q 'Start is a peer group' "$P/src/app/SurfaceRepository.php"
grep -q 'group_state_json' "$P/src/app/SurfaceRepository.php"
grep -q '移动到分组' "$P/src/app/SurfaceShell.php"
grep -q 'option value="projects"' "$P/src/app/SurfaceShell.php"
! grep -q '\$projects = \[' "$P/src/projects.php"
! grep -q 'deleteHtml' "$P/src/workspace-action.php"
grep -q '\$dropCover = \$removeCover;' "$P/src/workspace-save.php"
! grep -q "\$dropCover = \$surface === 'start'" "$P/src/workspace-save.php"
grep -q 'saveLink(null' "$P/src/app/KewaroProjectImporter.php"
! grep -q 'INSERT INTO links' "$P/src/app/KewaroProjectImporter.php"
grep -q 'start.kewaro.com' "$P/src/projects-kewaro-import.php"
grep -q 'hash_equals(vf_csrf_token()' "$P/src/projects-kewaro-import.php"
! grep -q 'INSERT INTO links' "$P/src/migrations/2026090201_v239_unified_resource_groups.php"
echo 'P01_V2390_STATIC_BOUNDARIES=PASS'

echo '== Fresh isolated installation =='
cp -a "$P/src" "$RUNTIME"
cd "$RUNTIME"
php -S 127.0.0.1:18390 -t . > "$WORK/php-server.log" 2>&1 &
SERVER_PID=$!
cleanup(){ kill "$SERVER_PID" 2>/dev/null || true; }
trap cleanup EXIT

for i in $(seq 1 30); do
  if curl -fsS -c "$WORK/cookies" -b "$WORK/cookies" "$BASE/setup.php" -o "$WORK/setup.html"; then break; fi
  sleep 1
done
CSRF=$(python3 - "$WORK/setup.html" <<'PY'
import re,sys
text=open(sys.argv[1],encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',text)
assert m,'setup csrf missing'
print(m.group(1))
PY
)
curl -fsS -c "$WORK/cookies" -b "$WORK/cookies" -X POST "$BASE/setup.php" \
  --data-urlencode "setup_csrf=$CSRF" \
  --data-urlencode 'site_title=VF P01 V2.39 Gate' \
  --data-urlencode 'admin_password=V239Gate!2026' \
  --data-urlencode 'admin_password_confirm=V239Gate!2026' \
  -o "$WORK/setup-post.html"
test -f app/.runtime.php
php cli/verify.php | tee "$WORK/cli-verify.txt"
grep -Fx 'VERIFY_PASS=YES' "$WORK/cli-verify.txt"
php cli/surface-verify.php | tee "$WORK/surface-verify.txt"
grep -Fx 'CURRENT_DOMAIN_PASS=YES' "$WORK/surface-verify.txt"
grep -Fx 'MULTI_SURFACE_PASS=YES' "$WORK/surface-verify.txt"
echo 'P01_V2390_FRESH_INSTALL=PASS'

echo '== Anonymous HTTP / mutation boundary =='
for route in surfaces.php start.php channels.php watch.php topics.php projects.php; do
  curl -fsS "$BASE/$route" -o "$WORK/${route%.php}.html"
done
grep -F 'data-vf-mode="all"' "$WORK/surfaces.html" >/dev/null
grep -F 'data-vf-mode="start"' "$WORK/start.html" >/dev/null
grep -F 'data-vf-mode="channels"' "$WORK/channels.html" >/dev/null
grep -F 'data-vf-mode="watch"' "$WORK/watch.html" >/dev/null
grep -F 'data-vf-mode="topics"' "$WORK/topics.html" >/dev/null
grep -F 'data-vf-mode="projects"' "$WORK/projects.html" >/dev/null
if grep -F 'id="vf-workspace-data"' "$WORK/surfaces.html" >/dev/null; then
  echo 'anonymous workspace payload leaked' >&2
  exit 1
fi
test "$(curl -sS -o /dev/null -w '%{http_code}' "$BASE/workspace-action.php")" = '403'
test "$(curl -sS -o /dev/null -w '%{http_code}' "$BASE/projects-kewaro-import.php")" = '403'
echo 'P01_V2390_HTTP_BOUNDARY=PASS'

echo '== Real repository group round-trip + Kewaro importer =='
cat > "$WORK/real-runtime-gate.php" <<'PHP'
<?php
declare(strict_types=1);
require __DIR__ . '/runtime/app/bootstrap.php';
require_once __DIR__ . '/runtime/app/SurfaceRepository.php';
require_once __DIR__ . '/runtime/app/KewaroProjectImporter.php';

function gate_ok(bool $value, string $message): void {
    if ($value) return;
    fwrite(STDERR, "FAIL: {$message}\n");
    exit(1);
}

$db = vf_db();
gate_ok((int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn() === 0, 'fresh setup seeded business links');
gate_ok((int)$db->query("SELECT COUNT(*) FROM settings WHERE setting_key='projects_legacy_import_available'")->fetchColumn() === 0, 'fresh setup exposed Kewaro owner import');

$base = new VfRepository($db);
$bootstrap = $base->bootstrap(true);
$categories = (array)($bootstrap['categories'] ?? []);
if (!$categories) {
    $categoryId = $base->createCategory(['name'=>'Gate','description'=>'','icon'=>'','is_private'=>1,'sort_order'=>0]);
} else {
    $categoryId = (int)$categories[0]['id'];
}

$saved = $base->saveLink(null, [
    'category_id'=>$categoryId,
    'title'=>'Existing P01',
    'url'=>'https://start.kewaro.com/',
    'backup_url'=>'',
    'description'=>'Gate existing canonical resource',
    'icon'=>'',
    'tags'=>['gate'],
    'is_private'=>0,
    'is_favorite'=>0,
    'is_pending'=>0,
    'sort_order'=>0,
    'url_type'=>'normal',
    'url_protected'=>0,
], 'machine-gate');
$id = (int)$saved['id'];
gate_ok($id > 0, 'canonical link create failed');

$surface = new VfSurfaceRepository($db);
$surface->upsertProfile($id, ['surface'=>'watch','resource_kind'=>'电影','note'=>'watch-note','media_year'=>2024,'media_status'=>'watched']);
$surface->upsertProfile($id, ['surface'=>'topics','resource_kind'=>'研究','note'=>'topic-note','source_kind'=>'hosted_html','source_ref'=>'topic-gate.html']);
$surface->upsertProfile($id, ['surface'=>'projects','resource_kind'=>'产品','note'=>'project-note','project_code'=>'P01','project_status'=>'optimizing']);
$surface->resetToStart($id);
$stmt=$db->prepare('SELECT * FROM resource_domain_profiles WHERE link_id=?');$stmt->execute([$id]);$p=$stmt->fetch(PDO::FETCH_ASSOC);
gate_ok((string)$p['domain_key']==='start','Start not explicit peer group');
$states=json_decode((string)$p['group_state_json'],true);
gate_ok(($states['watch']['media_status']??'')==='watched','Watch dormant state lost');
gate_ok(($states['topics']['source_kind']??'')==='hosted_html','Topic dormant state lost');
gate_ok(($states['projects']['project_code']??'')==='P01','Project dormant state lost');
$surface->upsertProfile($id,['surface'=>'watch']);
$stmt->execute([$id]);$p=$stmt->fetch(PDO::FETCH_ASSOC);
gate_ok((int)$p['media_year']===2024 && (string)$p['media_status']==='watched','Watch restore failed');
$surface->upsertProfile($id,['surface'=>'topics']);
$stmt->execute([$id]);$p=$stmt->fetch(PDO::FETCH_ASSOC);
gate_ok((string)$p['source_kind']==='hosted_html' && (string)$p['source_ref']==='topic-gate.html','Topic restore failed');
$surface->upsertProfile($id,['surface'=>'projects']);
$stmt->execute([$id]);$p=$stmt->fetch(PDO::FETCH_ASSOC);
gate_ok((string)$p['project_code']==='P01' && (string)$p['project_status']==='optimizing','Project restore failed');

gate_ok((string)$db->query("SELECT url FROM links WHERE id={$id}")->fetchColumn()==='https://start.kewaro.com/','canonical URL changed during moves');
$now=gmdate('c');
$set=$db->prepare("INSERT OR REPLACE INTO settings(setting_key,setting_value,updated_at) VALUES('projects_legacy_import_available','1',?)");$set->execute([$now]);
$importer = new VfKewaroProjectImporter($db,$base,$surface);
$result = $importer->import();
gate_ok($result['already_completed']===false,'owner importer unexpectedly no-op');
gate_ok((int)$result['created']===5 && (int)$result['reused']===1,'Kewaro created/reused mismatch');
gate_ok((int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn()===6,'Kewaro import canonical link count mismatch');
gate_ok((int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_private=1")->fetchColumn()===5,'missing Kewaro links not private');
$rows=$db->query("SELECT project_code,project_status FROM resource_domain_profiles WHERE domain_key='projects'")->fetchAll(PDO::FETCH_KEY_PAIR);
gate_ok(($rows['P03']??'')==='retired' && ($rows['P06']??'')==='retired','retired project authority lost');
gate_ok(($rows['P05']??'')==='optimizing','P05 optimizing authority lost');
$again=$importer->import();
gate_ok($again['already_completed']===true,'Kewaro importer not idempotent');
gate_ok((int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn()===6,'second import duplicated links');

echo "P01_V2390_REAL_REPOSITORY=PASS\n";
PHP
cd "$WORK"
php real-runtime-gate.php

echo 'P01_V2390_PUBLIC_MACHINE_GATE=PASS'
