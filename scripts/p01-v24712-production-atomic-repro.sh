#!/usr/bin/env bash
set -Eeuo pipefail

BASELINE_ROOT=${BASELINE_ROOT:-$PWD/baseline}
CORE_ROOT=${CORE_ROOT:-$PWD/core}
ARTIFACT_ROOT=${ARTIFACT_ROOT:-$PWD/artifact}
SITE=/tmp/p01-v24712-prod-repro
EVID=/tmp/p01-v24712-prod-repro-evidence
UPDATE="$ARTIFACT_ROOT/VF_Start_V2.47.12_UPDATE.zip"
BRIDGE="$ARTIFACT_ROOT/P01_V24710_AUTH_BRIDGE.php"
MANIFEST="$CORE_ROOT/projects/P01.json"

rm -rf "$SITE" "$EVID"
cp -a "$BASELINE_ROOT/src" "$SITE"
mkdir -p "$EVID"

php -S 127.0.0.1:19912 -t "$SITE" >"$EVID/server.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true' EXIT

cookies="$EVID/cookies"
for _ in $(seq 1 80); do
  curl -fsS -c "$cookies" -b "$cookies" "http://127.0.0.1:19912/setup.php" -o "$EVID/setup.html" && break
  sleep .25
done
csrf=$(python3 - <<PY
import re
s=open('$EVID/setup.html',encoding='utf-8').read()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s)
assert m
print(m.group(1))
PY
)
curl -fsS -c "$cookies" -b "$cookies" -X POST "http://127.0.0.1:19912/setup.php"   --data-urlencode "setup_csrf=$csrf"   --data-urlencode 'site_title=P01 Prod Repro'   --data-urlencode 'admin_password=vf-prod-repro'   --data-urlencode 'admin_password_confirm=vf-prod-repro'   -o "$EVID/setup-post.html"

kill "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true
trap - EXIT

ROOT="$SITE" BRIDGE="$BRIDGE" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');
require $root.'/app/bootstrap.php';
define('VF_P01_V24710_AUTH_BRIDGE_LIBRARY_MODE', true);
require getenv('BRIDGE');
$r=VfP01V24710AuthBridge::run($root);
if (empty($r['ok'])) exit(1);
echo "BRIDGE=PASS\n";
PHP

ROOT="$SITE" php <<'PHP'
<?php
declare(strict_types=1);
require getenv('ROOT').'/app/FunctionalWorkspaceCore.php';
$db=vf_db();
$repo=new VfRepository($db);
$cat=$repo->createCategory(['name'=>'Prod Repro Preserve','description'=>'Updater e2e','is_private'=>0,'sort_order'=>100]);
$repo->saveLink(null,['title'=>'Prod Repro Link','url'=>'https://prod-repro.example/item','surface'=>'start','tags'=>['prod-repro'],'category_id'=>$cat],'manual');
echo "SEED=PASS\n";
PHP

ROOT="$SITE" MANIFEST="$MANIFEST" UPDATE="$UPDATE" OUT="$EVID" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');
require $root.'/app/bootstrap.php';
vf_security_headers();
$db=vf_db();
$manifest=json_decode((string)file_get_contents(getenv('MANIFEST')),true,512,JSON_THROW_ON_ERROR);
$update=getenv('UPDATE');
$fetch=static fn(string $repo,string $file,string $ref): array => $manifest;
$download=static function(array $m,string $dest) use($update): array {
    if (!copy($update,$dest)) throw new RuntimeException('local asset copy failed');
    return ['size'=>filesize($dest)];
};
$u=new VfUpdateManager($db,['manifest_fetcher'=>$fetch,'asset_downloader'=>$download]);
$db->prepare('INSERT INTO update_state(state_key,state_value,updated_at) VALUES(?,?,?) ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value,updated_at=excluded.updated_at')
   ->execute(['highest_verified_release_version','2.47.11',gmdate('c')]);
$db->prepare('INSERT INTO update_state(state_key,state_value,updated_at) VALUES(?,?,?) ON CONFLICT(state_key) DO UPDATE SET state_value=excluded.state_value,updated_at=excluded.updated_at')
   ->execute(['highest_verified_release_manifest_sha256',str_repeat('a',64),gmdate('c')]);
$c=$u->check(true);
if (($c['latest_version']??'')!=='2.47.12') throw new RuntimeException('freshness rotation failed');
$p=$u->prepare();
if (empty($p['operation_id'])) throw new RuntimeException('prepare operation missing');
file_put_contents(getenv('OUT').'/operation-id.txt',(string)$p['operation_id']);
echo "PREPARE=PASS ".$p['operation_id']."\n";
PHP

ROOT="$SITE" OUT="$EVID" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');
require $root.'/app/bootstrap.php';
vf_security_headers();
$db=vf_db();
/* Keep the request PDO and representative manager references alive, matching api.php shape. */
$holders=[
    new VfRepository($db),
    new VfBackupManager($db),
    new VfDisasterRecovery($db),
    new VfDataSafety($db),
    new VfOperationHistory($db),
    new VfSecurityManager($db),
    new VfSystemHealth($db),
];
$u=new VfUpdateManager($db);
$op=trim((string)file_get_contents(getenv('OUT').'/operation-id.txt'));
try {
    $r=$u->install($op);
    file_put_contents(getenv('OUT').'/install-result.json',json_encode($r,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));
    echo "INSTALL=PASS\n";
} catch (Throwable $e) {
    $journal=VF_PRIVATE_ROOT.'/updates/journals/'.$op.'.json';
    $data=is_file($journal)?json_decode((string)file_get_contents($journal),true):null;
    fwrite(STDERR,"INSTALL=FAIL\n");
    fwrite(STDERR,"PUBLIC=".$e->getMessage()."\n");
    fwrite(STDERR,"JOURNAL_ERROR=".($data['error']??'')."\n");
    fwrite(STDERR,"FAILURE_STAGE=".($data['failure_stage']??'')."\n");
    if (is_array($data)) file_put_contents(getenv('OUT').'/failed-journal.json',json_encode($data,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));
    exit(1);
}
PHP

ROOT="$SITE" php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');
if (trim((string)file_get_contents($root.'/VERSION.txt'))!=='2.47.12') throw new RuntimeException('target version not active');
require $root.'/app/FunctionalWorkspaceCore.php';
if ((int)vf_db()->query("SELECT COUNT(*) FROM links WHERE title='Prod Repro Link'")->fetchColumn()!==1) throw new RuntimeException('business data lost');
echo "POST_UPDATE=PASS\n";
PHP

cat >"$EVID/receipt.txt" <<EOF
P01_SOURCE_BASELINE=972541fd06c66044105ec1b19cf7738c340c90c1
P01_TARGET_VERSION=2.47.12
CORE_UPDATES_MAIN=68426c69669f0b6d65043bc8fecb5137d3465378
BRIDGE_SHAPE=PASS
FRESHNESS_OBSERVED_2.47.11_TO_2.47.12=PASS
PREPARE_REAL_BACKUP=PASS
INSTALL_IN_PROCESS_API_SHAPE=PASS
BUSINESS_DATA_PRESERVATION=PASS
P01_V24712_PRODUCTION_ATOMIC_REPRO=PASS
EOF
cat "$EVID/receipt.txt"
