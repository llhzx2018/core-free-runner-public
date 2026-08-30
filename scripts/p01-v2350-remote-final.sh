#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v2350-final.cookies
PIDFILE=/tmp/p01-v2350-final.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; rm -f "$PIDFILE"; fi; }
trap cleanup EXIT
start_server(){ cleanup; php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"; for i in $(seq 1 80); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done; echo SERVER_START_FAILED; return 1; }

# 1. Build isolated Owner-like V2.34 runtime and install normally.
rm -rf "$ROOT" "$COOKIE"; cp -a source/src "$ROOT"; start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v2350-final-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v2350-final-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V2350 Final Remote' --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.34.0
grep -F "define('VF_VERSION', '2.34.0')" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/pre-verify.txt" | grep -Fx VERIFY_PASS=YES

# 2. Seed representative public/private data and domain profiles.
cat >/tmp/p01-v2350-final-seed.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());$db=vf_db();
$pub=$r->createCategory(['name'=>'V235公开导航','description'=>'remote-public','is_private'=>false,'sort_order'=>100]);
$priv=$r->createCategory(['name'=>'V235私人导航','description'=>'remote-private','is_private'=>true,'sort_order'=>90]);
$ids=[];
for($i=1;$i<=20;$i++){$x=$r->saveLink(null,['category_id'=>$i%5===0?$priv:$pub,'title'=>'V235保留资源 '.$i,'url'=>'https://v235-resource-'.$i.'.example.com','description'=>'preserve','tags'=>$i%3===0?'V235,一致性':'V235','is_private'=>$i%5===0,'is_favorite'=>$i%7===0],'manual');$ids[]=(int)$x['id'];}
foreach([['channels','频道'],['watch','电影'],['topics','AI']] as [$domain,$kind]){for($i=0;$i<3;$i++){$id=$ids[3+$i+(($domain==='channels'?0:($domain==='watch'?3:6)))];$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'preserve-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2024+$i;$p['media_status']='want';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://v235-topic-'.$i.'.example.com';}$s->upsertProfile($id,$p);}}
for($i=0;$i<4;$i++){$s->recordOpen($ids[$i]);}
$before=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'private'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_private=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn(),'surface_counts'=>$s->counts(true)];
if($before['links']!==20||$before['categories']!==2||$before['private']!==4||$before['profiles']!==12||$before['schema']!=='2026082901')throw new RuntimeException('seed '.json_encode($before));
file_put_contents('/tmp/p01-v2350-final-before.json',json_encode($before,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "SEED_PASS\n";
PHP
ROOT="$ROOT" php /tmp/p01-v2350-final-seed.php | grep -Fx SEED_PASS
cp /tmp/p01-v2350-final-before.json "$EVID/before.json"

# 3. Real updater discovery/prepare/install through published core-updates/main + v2.35.0 Release.
cat >/tmp/p01-v2350-final-update.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/UpdateManager.php';
$m=new VfUpdateManager(vf_db(),['root'=>$root,'private_root'=>VF_PRIVATE_ROOT,'current_version'=>'2.34.0']);
$c=$m->check(true);
if(($c['ok']??false)!==true||($c['current_version']??'')!=='2.34.0'||($c['latest_version']??'')!=='2.35.0'||($c['available']??false)!==true||($c['can_update']??false)!==true)throw new RuntimeException('check '.json_encode($c));
$s=$c['requirements']['schema']??[];if(($s['current']??'')!=='2026082901'||($s['from']??'')!=='2026082901'||($s['target']??'')!=='2026082901'||($s['ok']??false)!==true)throw new RuntimeException('schema '.json_encode($s));
$p=$m->prepare();
if(($p['ok']??false)!==true||($p['from_version']??'')!=='2.34.0'||($p['to_version']??'')!=='2.35.0'||($p['release_tag']??'')!=='v2.35.0'||($p['asset_name']??'')!=='VF_Start_V2.35.0_UPDATE.zip'||(int)($p['update_package_bytes']??0)!==1381982||($p['update_package_sha256']??'')!=='73cbfabf9968c6366491a7f3caa6b70916432c638ac3e7df87479ccc2051e68a')throw new RuntimeException('prepare '.json_encode($p));
foreach(['manifest_identity','release_tag','release_asset','bytes','sha256','atomic_self_test','recovery_point'] as $k)if(($p['checks'][$k]??'')!=='pass')throw new RuntimeException('prepare '.$k.' '.json_encode($p['checks']??[]));
$i=$m->install((string)$p['operation_id']);
if(($i['ok']??false)!==true||($i['updated']??false)!==true||($i['from_version']??'')!=='2.34.0'||($i['to_version']??'')!=='2.35.0')throw new RuntimeException('install '.json_encode($i));
foreach(['release_identity','atomic_handoff','activation','cleanup'] as $k)if(($i['checks'][$k]??'')!=='pass')throw new RuntimeException('install '.$k.' '.json_encode($i['checks']??[]));
file_put_contents(getenv('EVID').'/update.json',json_encode(['check'=>$c,'prepare'=>$p,'install'=>$i],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "REMOTE_UPDATE_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2350-final-update.php | grep -Fx REMOTE_UPDATE_PASS

# 4. Post-upgrade exact version/schema/data/integrity and V2.35 runtime delta binding.
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.35.0
grep -F "define('VF_VERSION', '2.35.0')" "$ROOT/app/bootstrap.php" >/dev/null
for f in VERSION.txt app/FunctionalHome.php app/FunctionalWorkspace.php app/FunctionalWorkspaceCore.php app/FunctionalWorkspaceShell.php app/bootstrap.php assets/resource-actions.css assets/resource-media.css assets/workspace-domain-nav.css assets/workspace-home.css assets/workspace-primary-open.js assets/workspace-rebaseline.js assets/workspace-v228.css assets/workspace.js; do
  cmp "target/src/$f" "$ROOT/$f"
done
echo P01_V2350_REMOTE_RUNTIME_BYTES_MATCH_TAG=PASS | tee "$EVID/runtime-bytes.txt"
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
php "$ROOT/cli/surface-verify.php" | tee "$EVID/post-surface-verify.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES
cat >/tmp/p01-v2350-final-post.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');$before=json_decode((string)file_get_contents('/tmp/p01-v2350-final-before.json'),true,512,JSON_THROW_ON_ERROR);require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$db=vf_db();$s=new VfSurfaceRepository($db);$a=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'private'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_private=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'")->fetchColumn(),'integrity'=>strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn()),'fk'=>count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)),'surface_counts'=>$s->counts(true)];
if($a['schema']!=='2026082901'||$a['integrity']!=='ok'||$a['fk']!==0)throw new RuntimeException('db '.json_encode($a));foreach(['links','categories','favorites','private','profiles'] as $k)if($a[$k]!==$before[$k])throw new RuntimeException('preserve '.$k);foreach($before['surface_counts'] as $k=>$v)if((int)($a['surface_counts'][$k]??-1)!==(int)$v)throw new RuntimeException('surface '.$k);
file_put_contents(getenv('EVID').'/post.json',json_encode($a,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "POST_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2350-final-post.php | grep -Fx POST_PASS

# 5. Anonymous public/private boundary and five-domain HTTP remain intact after real remote update.
start_server
for page in index.php start.php channels.php watch.php topics.php; do code=$(curl -sSL -o "$EVID/${page%.php}-anonymous.html" -w '%{http_code}' "http://127.0.0.1:${PORT}/$page"); test "$code" = 200; done
grep -F 'V235公开导航' "$EVID/start-anonymous.html" >/dev/null
! grep -F 'V235私人导航' "$EVID/start-anonymous.html" >/dev/null
cat >"$EVID/runtime-verdict.txt" <<EOF
P01_V2340_TO_V2350_REMOTE_ONLINE_UPDATE=PASS
P01_V2350_REMOTE_DISCOVERY=PASS
P01_V2350_REMOTE_RELEASE_DOWNLOAD=PASS
P01_V2350_DATA_PRESERVATION=PASS
P01_V2350_SQLITE_INTEGRITY=PASS
P01_V2350_PUBLIC_PRIVATE_HTTP=PASS
P01_V2350_FIVE_DOMAIN_HTTP=PASS
P01_V2350_RUNTIME_FEATURE_BYTES=PASS
P01_V2350_SCHEMA_UNCHANGED_2026082901=PASS
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$EVID/runtime-verdict.txt"
