#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${ROOT:?}; PORT=${PORT:?}; ADMIN_PASS=${ADMIN_PASS:?}; EVID=${EVID:?}
mkdir -p "$EVID"
COOKIE=/tmp/p01-v2353-final.cookies
PIDFILE=/tmp/p01-v2353-final.pid
cleanup(){ if test -f "$PIDFILE"; then kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true; rm -f "$PIDFILE"; fi; }
trap cleanup EXIT
start_server(){ cleanup; php -S "127.0.0.1:${PORT}" -t "$ROOT" >"$EVID/server.log" 2>&1 & echo $! >"$PIDFILE"; for i in $(seq 1 80); do curl -fsS "http://127.0.0.1:${PORT}/setup.php" -o /dev/null && return 0 || sleep .25; done; echo SERVER_START_FAILED; return 1; }

# 1. Isolated Owner-like immutable V2.35.2 runtime.
rm -rf "$ROOT" "$COOKIE"; cp -a source/src "$ROOT"; start_server
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${PORT}/setup.php" -o /tmp/p01-v2353-final-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v2353-final-setup.html',encoding='utf-8').read();m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "http://127.0.0.1:${PORT}/setup.php" --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=P01 V2353 Final Remote' --data-urlencode "admin_password=$ADMIN_PASS" --data-urlencode "admin_password_confirm=$ADMIN_PASS" >/dev/null
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.35.2
grep -F "define('VF_VERSION', '2.35.2')" "$ROOT/app/bootstrap.php" >/dev/null
php "$ROOT/cli/verify.php" | tee "$EVID/pre-verify.txt" | grep -Fx VERIFY_PASS=YES

# 2. Representative data, visibility and all domain profiles.
cat >/tmp/p01-v2353-final-seed.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$r=new VfRepository(vf_db());$s=new VfSurfaceRepository(vf_db());$db=vf_db();
$pub=$r->createCategory(['name'=>'V2353公开导航','description'=>'remote-public','is_private'=>false,'sort_order'=>100]);
$priv=$r->createCategory(['name'=>'V2353私人导航','description'=>'remote-private','is_private'=>true,'sort_order'=>90]);
$ids=[];
for($i=1;$i<=24;$i++){$x=$r->saveLink(null,['category_id'=>$i%6===0?$priv:$pub,'title'=>'V2353保留资源 '.$i,'url'=>'https://v2353-resource-'.$i.'.example.com','description'=>'preserve','tags'=>$i%3===0?'V2353,一致性':'V2353','is_private'=>$i%6===0,'is_favorite'=>$i%8===0],'manual');$ids[]=(int)$x['id'];}
foreach([['channels','频道'],['watch','电影'],['topics','AI']] as [$domain,$kind]){for($i=0;$i<4;$i++){$offset=$domain==='channels'?2:($domain==='watch'?7:12);$id=$ids[$offset+$i];$p=['surface'=>$domain,'resource_kind'=>$kind,'note'=>'preserve-'.$domain.'-'.$i];if($domain==='channels')$p['background_friendly']=true;if($domain==='watch'){$p['media_year']=2023+$i;$p['media_status']='want';}if($domain==='topics'){$p['source_kind']='remote_url';$p['source_ref']='https://v2353-topic-'.$i.'.example.com';}$s->upsertProfile($id,$p);}}
for($i=0;$i<5;$i++){$s->recordOpen($ids[$i]);}
$before=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'private'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_private=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT MAX(version) FROM schema_migrations WHERE status='success'")->fetchColumn(),'surface_counts'=>$s->counts(true)];
$sc=$before['surface_counts'];
if($before['links']!==24||$before['categories']!==2||$before['favorites']!==3||$before['private']!==4||$before['profiles']<12||$before['schema']!=='2026082901'||(int)($sc['start']??-1)!==12||(int)($sc['channels']??-1)!==4||(int)($sc['watch']??-1)!==4||(int)($sc['topics']??-1)!==4||(int)($sc['total']??-1)!==24)throw new RuntimeException('seed '.json_encode($before));
file_put_contents('/tmp/p01-v2353-final-before.json',json_encode($before,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "SEED_PASS\n";
PHP
ROOT="$ROOT" php /tmp/p01-v2353-final-seed.php | grep -Fx SEED_PASS
cp /tmp/p01-v2353-final-before.json "$EVID/before.json"

# 3. Real updater discovery, authenticated Release download, prepare and Atomic install.
cat >/tmp/p01-v2353-final-update.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/UpdateManager.php';
$m=new VfUpdateManager(vf_db(),['root'=>$root,'private_root'=>VF_PRIVATE_ROOT,'current_version'=>'2.35.2']);
$c=$m->check(true);
if(($c['ok']??false)!==true||($c['current_version']??'')!=='2.35.2'||($c['latest_version']??'')!=='2.35.3'||($c['available']??false)!==true||($c['can_update']??false)!==true)throw new RuntimeException('check '.json_encode($c));
$s=$c['requirements']['schema']??[];if(($s['current']??'')!=='2026082901'||($s['from']??'')!=='2026082901'||($s['target']??'')!=='2026082901'||($s['ok']??false)!==true)throw new RuntimeException('schema '.json_encode($s));
$p=$m->prepare();
if(($p['ok']??false)!==true||($p['from_version']??'')!=='2.35.2'||($p['to_version']??'')!=='2.35.3'||($p['release_tag']??'')!=='v2.35.3'||($p['asset_name']??'')!=='VF_Start_V2.35.3_UPDATE.zip'||(int)($p['update_package_bytes']??0)!==1378346||($p['update_package_sha256']??'')!=='ca128a49c56901fe4ea7c108b7b78bde25584973362bf22e6fdc874782b390c9')throw new RuntimeException('prepare '.json_encode($p));
foreach(['manifest_identity','release_tag','release_asset','bytes','sha256','atomic_self_test','recovery_point'] as $k)if(($p['checks'][$k]??'')!=='pass')throw new RuntimeException('prepare '.$k.' '.json_encode($p['checks']??[]));
$i=$m->install((string)$p['operation_id']);
if(($i['ok']??false)!==true||($i['updated']??false)!==true||($i['from_version']??'')!=='2.35.2'||($i['to_version']??'')!=='2.35.3')throw new RuntimeException('install '.json_encode($i));
foreach(['release_identity','atomic_handoff','activation','cleanup'] as $k)if(($i['checks'][$k]??'')!=='pass')throw new RuntimeException('install '.$k.' '.json_encode($i['checks']??[]));
file_put_contents(getenv('EVID').'/update.json',json_encode(['check'=>$c,'prepare'=>$p,'install'=>$i],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "REMOTE_UPDATE_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2353-final-update.php | grep -Fx REMOTE_UPDATE_PASS

# 4. Post-upgrade exact hotfix bytes, data preservation and integrity.
test "$(tr -d '\r\n' < "$ROOT/VERSION.txt")" = 2.35.3
grep -F "define('VF_VERSION', '2.35.3')" "$ROOT/app/bootstrap.php" >/dev/null
for f in VERSION.txt app/bootstrap.php assets/admin-consolidation.css assets/update-core.js assets/update-reload.js; do cmp "target/src/$f" "$ROOT/$f"; done
echo P01_V2353_REMOTE_RUNTIME_BYTES_MATCH_TAG=PASS | tee "$EVID/runtime-bytes.txt"
php "$ROOT/cli/verify.php" | tee "$EVID/post-verify.txt" | grep -Fx VERIFY_PASS=YES
php "$ROOT/cli/surface-verify.php" | tee "$EVID/post-surface-verify.txt" | grep -Fx CURRENT_DOMAIN_PASS=YES
cat >/tmp/p01-v2353-final-post.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');$before=json_decode((string)file_get_contents('/tmp/p01-v2353-final-before.json'),true,512,JSON_THROW_ON_ERROR);require $root.'/app/bootstrap.php';require_once $root.'/app/SurfaceRepository.php';
$db=vf_db();$s=new VfSurfaceRepository($db);$a=['links'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active'")->fetchColumn(),'categories'=>(int)$db->query("SELECT COUNT(*) FROM categories WHERE lifecycle_state='active'")->fetchColumn(),'favorites'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_favorite=1")->fetchColumn(),'private'=>(int)$db->query("SELECT COUNT(*) FROM links WHERE lifecycle_state='active' AND is_private=1")->fetchColumn(),'profiles'=>(int)$db->query('SELECT COUNT(*) FROM resource_domain_profiles')->fetchColumn(),'schema'=>(string)$db->query("SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'")->fetchColumn(),'integrity'=>strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn()),'fk'=>count($db->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)),'surface_counts'=>$s->counts(true)];
if($a['schema']!=='2026082901'||$a['integrity']!=='ok'||$a['fk']!==0)throw new RuntimeException('db '.json_encode($a));foreach(['links','categories','favorites','private','profiles'] as $k)if($a[$k]!==$before[$k])throw new RuntimeException('preserve '.$k);foreach($before['surface_counts'] as $k=>$v)if((int)($a['surface_counts'][$k]??-1)!==(int)$v)throw new RuntimeException('surface '.$k);
file_put_contents(getenv('EVID').'/post.json',json_encode($a,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));echo "POST_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2353-final-post.php | grep -Fx POST_PASS

# 5. New manager must converge to a clean current==latest terminal state.
cat >/tmp/p01-v2353-final-latest.php <<'PHP'
<?php
declare(strict_types=1);
$root=getenv('ROOT');require $root.'/app/bootstrap.php';require_once $root.'/app/UpdateManager.php';
$m=new VfUpdateManager(vf_db(),['root'=>$root,'private_root'=>VF_PRIVATE_ROOT,'current_version'=>'2.35.3']);
$c=$m->check(true);
if(($c['ok']??false)!==true||($c['current_version']??'')!=='2.35.3'||($c['latest_version']??'')!=='2.35.3'||($c['available']??true)!==false||($c['can_update']??true)!==false)throw new RuntimeException('latest check '.json_encode($c));
$noop=false;try{$m->prepare();}catch(RuntimeException $e){$noop=$e->getMessage()==='当前已经是最新版本。';if(!$noop)throw $e;}
if(!$noop)throw new RuntimeException('prepare did not no-op');
file_put_contents(getenv('EVID').'/latest-state.json',json_encode(['check'=>$c,'prepare_noop'=>'当前已经是最新版本。'],JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));echo "LATEST_STATE_PASS\n";
PHP
ROOT="$ROOT" EVID="$EVID" php /tmp/p01-v2353-final-latest.php | grep -Fx LATEST_STATE_PASS

# 6. Public/private and five-domain HTTP boundary after the real remote update.
start_server
for page in index.php start.php channels.php watch.php topics.php; do code=$(curl -sSL -o "$EVID/${page%.php}-anonymous.html" -w '%{http_code}' "http://127.0.0.1:${PORT}/$page"); test "$code" = 200; done
grep -F 'V2353公开导航' "$EVID/start-anonymous.html" >/dev/null
! grep -F 'V2353私人导航' "$EVID/start-anonymous.html" >/dev/null
cat >"$EVID/runtime-verdict.txt" <<EOF
P01_V2352_TO_V2353_REMOTE_ONLINE_UPDATE=PASS
P01_V2353_REMOTE_DISCOVERY=PASS
P01_V2353_REMOTE_RELEASE_DOWNLOAD=PASS
P01_V2353_DATA_PRESERVATION=PASS
P01_V2353_SQLITE_INTEGRITY=PASS
P01_V2353_PUBLIC_PRIVATE_HTTP=PASS
P01_V2353_FIVE_DOMAIN_HTTP=PASS
P01_V2353_RUNTIME_FEATURE_BYTES=PASS
P01_V2353_SCHEMA_UNCHANGED_2026082901=PASS
P01_V2353_LATEST_TERMINAL_STATE=PASS
OWNER_PRODUCTION_WRITE=NO
EOF
cat "$EVID/runtime-verdict.txt"
