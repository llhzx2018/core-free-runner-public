#!/usr/bin/env bash
set -Eeuo pipefail
cd product
PRODUCT_REF="${PRODUCT_REF:?}"
test "$(git rev-parse HEAD)" = "$PRODUCT_REF"
test "$(tr -d '\r\n' < VERSION)" = 2.5.13
test "$(jq -r .version SOURCE_MANIFEST.json)" = 2.5.13
test "$(jq -r .schema SOURCE_MANIFEST.json)" = 2401
python3 scripts/repository-gates.py
bash scripts/verify-repository.sh
node --check public/assets/app.js
node --check public/assets/scratch-tabs.js
php -l src/app/ScratchTabsService.php >/dev/null
php -l public/scratch-action.php >/dev/null

echo EXACT_TARGET_SOURCE_AND_GATES=PASS
TREE=$(git show -s --format=%T "$PRODUCT_REF")

build_for(){
  local src="$1" out="$2" builder="$RUNNER_TEMP/build-v2513-${src}.py"
  cp scripts/build-release-v2.5.4.py "$builder"
  python3 - "$builder" "$src" "$out" <<'PY'
from pathlib import Path
import sys,re
p=Path(sys.argv[1]);src=sys.argv[2];out=sys.argv[3];s=p.read_text(encoding='utf-8')
s=s.replace("ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.5.2'; VER='2.5.4'; SCHEMA=2401; DT=(2026,8,19,2,0,0)",f"ROOT=Path.cwd(); SRCVER='{src}'; VER='2.5.13'; SCHEMA=2401; DT=(2026,8,19,9,10,0)",1)
s=s.replace("default='build/release-v2.5.4'",f"default='{out}'",1).replace("default='release/v2.5.4'","default='release/v2.5.13'",1)
# Keep preflight release notes accurate enough that the generated artifacts never masquerade as V2.5.4.
start="notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''";end="''')\n arts=[sz,fz,uz,az,rf,notes]"
i=s.index(start);j=s.index(end,i)
notes="""notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''# VF Library V{VER} PRE-RELEASE PREFLIGHT\n\nPersonal-use workflow refinement candidate.\n\n- Explicit notebook category/range navigation starts title list at top.\n- Scratch pin/reorder, safe Alt shortcuts and /scratch quick entry.\n- Reader opens at top with optional deliberate resume; H2 and screenshots can fold.\n- Schema remains {SCHEMA}; no migration.\n- This preflight artifact is verified from source {SRCVER} but is not published.\n''')\n arts=[sz,fz,uz,az,rf,notes]"""
s=s[:i]+notes+s[j+len(end):]
p.write_text(s,encoding='utf-8')
PY
  python3 -m py_compile "$builder"
  rm -rf "$out-a" "$out-b"
  python3 "$builder" --out "$out-a" --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.13 >/dev/null
  python3 "$builder" --out "$out-b" --source-commit "$PRODUCT_REF" --source-tree "$TREE" --source-ref release/v2.5.13 >/dev/null
  python3 - "$out-a" "$out-b" "$src" <<'PY'
from pathlib import Path
import hashlib,json,sys,zipfile
a,b=Path(sys.argv[1]),Path(sys.argv[2]);src=sys.argv[3]
ha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.iterdir() if p.is_file()};hb={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.iterdir() if p.is_file()};assert ha==hb,(ha,hb)
name='VF_Library_V2.5.13_UPDATE.zip';assert name in ha
with zipfile.ZipFile(a/name) as z:m=json.loads(z.read('atomic-manifest.json'));assert m['source_version']==src and m['target_version']=='2.5.13' and m['source_schema']==2401 and m['target_schema']==2401
print('DETERMINISTIC_'+src.replace('.','_')+'=PASS')
print('UPDATE_'+src+'_BYTES='+str((a/name).stat().st_size))
print('UPDATE_'+src+'_SHA256='+ha[name])
PY
}

build_for 2.5.10 build/preflight-2513-from-2510
build_for 2.5.12 build/preflight-2513-from-2512

install_site(){
  local site="$1" port="$2" pw="$3"
  php -S 127.0.0.1:"$port" -t "$site" >"$site-server.log" 2>&1 & local pid=$!
  for _ in $(seq 1 80);do curl -fsS "http://127.0.0.1:$port/setup.php" >/dev/null 2>&1&&break;sleep .2;done
  local c="$site-cookie" page="$site-setup" token
  curl -fsS -c "$c" "http://127.0.0.1:$port/setup.php" > "$page"
  token=$(python3 - "$page" <<'PY'
import re,html,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(html.unescape(m.group(1)))
PY
)
  test "$(curl -sS -o /dev/null -w '%{http_code}' -b "$c" -c "$c" -H "Origin: http://127.0.0.1:$port" --data-urlencode "setup_csrf=$token" --data-urlencode "password=$pw" --data-urlencode "password_confirm=$pw" "http://127.0.0.1:$port/setup.php")" = 303
  kill "$pid";wait "$pid" 2>/dev/null||true
}

verify_upgrade(){
  local src="$1" out="$2" tag="v$1" root="$RUNNER_TEMP/up-${src//./}" srcdir="$root/src" site="$root/site" pkg
  rm -rf "$root";mkdir -p "$root" "$site"
  git worktree add --detach "$srcdir" "$tag" >/dev/null
  bash "$srcdir/scripts/build-deploy-tree.sh" "$site" >/dev/null
  test "$(cat "$site/VERSION.txt")" = "$src"
  install_site "$site" "18${src//./}" "P02-V2513-${src}-Preflight!"
  cat > "$root/seed.php" <<'PHP'
<?php
$site=$argv[1];$out=$argv[2];require $site.'/app/bootstrap.php';require_once $site.'/app/ScratchTabsService.php';
$repo=new VfTextBoxRepository(vftb_db());$cid=$repo->saveCategory(null,['name'=>'V2513 Preserve','icon'=>'folder']);$iid=$repo->saveItem(null,['category_id'=>$cid,'title'=>'V2513 Existing','description'=>'','content'=>'keep-existing-data','content_mode'=>'article','content_format'=>'markdown','primary_action'=>'read','status'=>'active','aliases'=>[],'tags'=>[],'is_favorite'=>true,'is_pinned'=>false]);$s=new VfLibraryScratchTabsService(vftb_db());$tab=$s->create();$s->save((int)$tab['id'],'pre-upgrade scratch',5,11);file_put_contents($out,json_encode(['iid'=>$iid,'sid'=>(int)$tab['id']]));
PHP
  php "$root/seed.php" "$site" "$root/ids.json"
  pkg="$(pwd)/$out-a/VF_Library_V2.5.13_UPDATE.zip";local bytes sha;bytes=$(stat -c%s "$pkg");sha=$(sha256sum "$pkg"|awk '{print $1}')
  cat > "$root/upgrade.php" <<'PHP'
<?php
$site=$argv[1];$pkg=$argv[2];$bytes=(int)$argv[3];$sha=$argv[4];$src=$argv[5];$out=$argv[6];require $site.'/app/bootstrap.php';require_once $site.'/app/CoreUpdates/UpdateAdapter.php';require_once $site.'/app/CoreUpdates/UpdateCore.php';require_once $site.'/app/VfLibraryCoreUpdateAdapter.php';
$m=['schema_version'=>'1.0','project_id'=>'P02','component_id'=>'APP','enabled'=>true,'current_version'=>$src,'target_version'=>'2.5.13','update_type'=>'ATOMIC','from_versions'=>[$src],'schema_from'=>'2401','schema_to'=>'2401','repository'=>'llhzx2018/vf-library','release_tag'=>'v2.5.13','asset_name'=>'VF_Library_V2.5.13_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-08-19T09:10:00Z'];$core=new CoreUpdates\UpdateCore('P02','APP');$check=$core->check($src,'2401',$m);$verified=$core->verifyPackage($pkg,$m);if(($check['status']??'')!=='AVAILABLE'||($verified['status']??'')!=='VERIFIED')exit(2);$r=$core->upgrade($src,'2401',new VfLibraryCoreUpdateAdapter(),$pkg,$m);file_put_contents($out,json_encode(['check'=>$check,'verify'=>$verified,'result'=>$r]));if(!in_array($r['status']??'',['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING'],true)||empty($r['backup_locator']))exit(3);
PHP
  php "$root/upgrade.php" "$site" "$pkg" "$bytes" "$sha" "$src" "$root/result.json"
  test "$(cat "$site/VERSION.txt")" = 2.5.13
  cat > "$root/post.php" <<'PHP'
<?php
$site=$argv[1];$ids=json_decode(file_get_contents($argv[2]),true);require $site.'/app/bootstrap.php';require_once $site.'/app/ScratchTabsService.php';$pdo=vftb_db();$stmt=$pdo->prepare('SELECT content,is_favorite FROM text_items WHERE id=?');$stmt->execute([(int)$ids['iid']]);$row=$stmt->fetch(PDO::FETCH_ASSOC);if(!$row||$row['content']!=='keep-existing-data'||(int)$row['is_favorite']!==1)exit(2);$s=new VfLibraryScratchTabsService($pdo);$snap=$s->snapshot();$found=null;foreach($snap['open'] as $t)if((int)$t['id']===(int)$ids['sid'])$found=$t;if(!$found||$found['content']!=='pre-upgrade scratch')exit(3);$s->pin((int)$ids['sid'],true);$new=$s->create();$s->save((int)$new['id'],'post-upgrade scratch',4,0);$snap=$s->snapshot();if(empty($snap['open'][0]['is_pinned']))exit(4);$integrity=$pdo->query('PRAGMA integrity_check')->fetchAll(PDO::FETCH_COLUMN);$fk=$pdo->query('PRAGMA foreign_key_check')->fetchAll();if(count($integrity)!==1||strtolower((string)$integrity[0])!=='ok'||count($fk)!==0)exit(5);echo "POST_UPGRADE_DATA_SCRATCH_SQLITE=PASS\n";
PHP
  php "$root/post.php" "$site" "$root/ids.json"
  jq -e '.result.backup_locator|length>0' "$root/result.json" >/dev/null
  php "$site/cli/verify.php" | jq -e '.ok==true and .version=="2.5.13" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null
  git worktree remove --force "$srcdir" >/dev/null
  echo "EXISTING_DATA_${src//./_}_TO_2_5_13=PASS"
  echo "AUTOMATIC_BACKUP_${src//./_}=PASS"
}

verify_upgrade 2.5.10 build/preflight-2513-from-2510
verify_upgrade 2.5.12 build/preflight-2513-from-2512

# Clean target FULL fresh install smoke from the 2.5.12 candidate build.
FRESH="$RUNNER_TEMP/fresh2513";mkdir -p "$FRESH";unzip -q build/preflight-2513-from-2512-a/VF_Library_V2.5.13_FULL.zip -d "$FRESH";test "$(cat "$FRESH/VERSION.txt")" = 2.5.13
install_site "$FRESH" 18913 'P02-V2513-Fresh-Preflight!'
php "$FRESH/cli/verify.php" | jq -e '.ok==true and .version=="2.5.13" and .schema_version==2401 and .integrity=="ok" and .foreign_key_errors==0' >/dev/null

echo FULL_FRESH_INSTALL=PASS
echo DUAL_SOURCE_PREFLIGHT=PASS
echo RELEASE_PUBLICATION=NOT_EXECUTED
echo CORE_UPDATES_WRITE=NO
echo PRODUCTION_WRITE=NO
