#!/usr/bin/env bash
# DEV ONLY: real immutable v015 FULL, native 3DB, media+token audit.
set -Eeuo pipefail
set +x
[[ "$GITHUB_ACTIONS" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
engine="$1"
[[ "$engine" =~ ^(sqlite|mysql|mariadb)$ ]] || exit 3
old=369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e
target=7c034eb267d7b34a90acfa35be8f64780ec39b47
old_zip_sha=538d161339849214999eb6f85da40623a149fc9cf1b592c9e5907f751c434f73
[[ "$(git -C target rev-parse HEAD)" == "$target" ]] || exit 3
root="$RUNNER_TEMP/p08-v016-legacy-issued-$engine"
site="$RUNNER_TEMP/p08-v016-legacy-oldsite-$engine"
full="$RUNNER_TEMP/p08-v016-legacy-full-$engine/full-first.zip"
[[ ! -e "$root" && ! -e "$site" && -s "$full" ]] || exit 3
mkdir -m 700 "$root" "$site"
gh release download v0.1.15 -R llhzx2018/vf-adops \
 -p VF_AdOps_V0.1.15_FULL.zip -D "$root" >/dev/null
archive="$root/VF_AdOps_V0.1.15_FULL.zip"
printf '%s  %s\n' "$old_zip_sha" "$archive" | sha256sum -c --status
unzip -q "$archive" -d "$site"
unzip -p "$archive" FULL_MANIFEST.json > "$root/old-manifest.json"
python3 - "$root/old-manifest.json" "$old" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d['source_sha']==sys.argv[2] and d['target_version']=='0.1.15'
assert d['project_id']=='P08' and d['type']=='CLEAN_FULL_ONLY'
PY
echo "P08_V016_BRIDGE_$engine"_REAL_ORIGINAL_015_ZIP_SHA_SOURCE=PASS
mkdir -p "$site/tests/compatibility"
cp target/tests/test_install_sqlite_e2e.php target/tests/test_install_mysql_e2e.php "$site/tests/"
cp target/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
if [[ "$engine" == sqlite ]]; then
  php "$site/tests/test_install_sqlite_e2e.php"
else
  export P08_TEST_DB_CLEAN=p08_ci_016_old
  export P08_TEST_DB_DIRTY=p08_ci_016_old_dirty
  mariadb -h127.0.0.1 -uroot -p"$P08_TEST_DB_PASSWORD" \
    -e 'CREATE DATABASE p08_ci_016_old; CREATE DATABASE p08_ci_016_old_dirty; CREATE TABLE p08_ci_016_old_dirty.synthetic_dirty(id integer primary key);'
  php "$site/tests/test_install_mysql_e2e.php"
fi
[[ "$(readlink "$site/current")" == "releases/$old" ]] || exit 42
python3 - "$site" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])/'storage/app/private/adops'
assets=root/'landing-assets'
if assets.is_dir() and not assets.is_symlink():
    assert not list(assets.iterdir())
    assets.rmdir() # disposable synthetic fixture only
assert not assets.exists() and not assets.is_symlink()
token=root/'upgrade/github-read-token'
token.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
token.write_text('github_pat_'+'r'*45+'\n')
token.chmod(0o600)
print('P08_EMPTY_MEDIA_PRE_CRASH_ORIGIN_ABSENT=PASS')
PY

old_manifest_sha="$(sha256sum "$root/old-manifest.json" | cut -d' ' -f1)"
python3 -B target/scripts/build_atomic.py \
 --source target --output "$root/update.zip" \
 --source-version 0.1.15 --source-sha "$old" \
 --source-full-manifest-sha256 "$old_manifest_sha" \
 --previous-full-manifest "$root/old-manifest.json" \
 --target-version 0.1.16 --target-sha "$target" >/dev/null
unzip -tqq "$root/update.zip"
mkdir -m 700 "$root/target-full"
unzip -q "$full" -d "$root/target-full"
php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
 --audit "$site" "$full" "$root/update.zip"
echo "P08_V016_BRIDGE_$engine"_OLD_ISSUED_MEDIA_TOKEN_AUDIT=PASS
old_pointer="$(readlink "$site/current")"
old_image_hash="$(sha256sum "$site/storage/app/private/adops/landing-assets/00000000-0000-4000-8000-000000000001.png" | cut -d' ' -f1)"
set +e
printf 'wrong-synthetic-password\n' | php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
 --apply "$site" "$full" "$root/update.zip" CONFIRM_MEDIA_SAFE_V015_TO_V016 \
 > "$root/negative-out" 2> "$root/negative-err"
rc=$?
set -e
[[ "$rc" -eq 2 ]] || { echo 'P08_V016_BRIDGE_NEGATIVE_NONBLOCKING=FAIL'; exit 43; }
grep -Fxq 'P08_V016_BRIDGE_OWNER_AUTH_REFUSED' "$root/negative-err" || {
  grep -E '^P08_V016_BRIDGE_[A-Z_]+$' "$root/negative-err" || true
  echo "P08_V016_BRIDGE_$engine"_OWNER_REFUSAL=FAIL
  exit 44
}
[[ "$(readlink "$site/current")" == "$old_pointer" ]] || exit 45
[[ "$old_image_hash" == "$(sha256sum "$site/storage/app/private/adops/landing-assets/00000000-0000-4000-8000-000000000001.png" | cut -d' ' -f1)" ]] || exit 46
scope="$(printf '%s' "$site" | sha256sum | cut -c1-16)"
[[ ! -d "$HOME/.p08-v016-legacy-media-bridge-$scope" ]] || exit 47
echo "P08_V016_BRIDGE_$engine"_INVALID_OWNER_NO_MUTATION=PASS

owner_password='Synthetic-Owner-Only-12345!'
[[ "$engine" != sqlite ]] || owner_password='Synthetic-SQLite-Owner-12345!'
old_pointer="$(readlink "$site/current")"
assets="$site/storage/app/private/adops/landing-assets"
[[ ! -e "$assets" && ! -L "$assets" ]] || exit 38
token="$site/storage/app/private/adops/upgrade/github-read-token"
marker="$site/storage/app/private/adops/installation/installed.json"
before="$(sha256sum "$token" "$marker" "$site/.env" | cut -d ' ' -f1 | tr '\n' ':')"
set +e
printf '%s\n' "$owner_password" |
  env P08_V016_BRIDGE_KILL_AFTER_SWAP=YES P08_R131_DISPOSABLE=YES \
    php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
      --isolated-apply "$site" "$full" "$root/update.zip" CONFIRM_MEDIA_SAFE_V015_TO_V016 \
      > "$root/kill-out" 2> "$root/kill-err"
rc=$?
set -e
if [[ "$rc" -ne 137 ]]; then
  grep -E '^P08_V016_BRIDGE_[A-Z0-9_]+$' "$root/kill-err" || true
  echo P08_V016_BRIDGE_REAL_SIGKILL_EXIT137=FAIL
  exit 61
fi
[[ "$(readlink "$site/current")" == "releases/$target" ]] || exit 62
[[ -f "$site/storage/app/private/adops/maintenance/maintenance.json" ]] || exit 63
php -r '
$site=$argv[1];$old=$argv[2];$target=$argv[3];
require $site."/releases/".$old."/vendor/autoload.php";
$j=glob($site."/storage/app/private/adops/upgrade/*/pointer-transaction.json");
if(count($j)!==1)exit(71);
$d=json_decode(file_get_contents($j[0]),true,32,JSON_THROW_ON_ERROR);
if(($d["status"]??null)!=="PREPARED"||($d["type"]??null)!=="P08_POINTER_TRANSACTION_V1"
 ||($d["previous"]??null)!=="releases/".$old ||($d["next"]??null)!=="releases/".$target)exit(72);
$id=$d["stage_id"]??"";
if(!preg_match("/^[a-f0-9]{32}$/D",$id))exit(73);
echo "P08_V016_BRIDGE_ACTUAL_SIGKILL_PREPARED_NEW_POINTER=PASS\n";
$rec=(new \VF\AdOps\Upgrade\AtomicReleasePointer())->recover($site,$id);
if(($rec["status"]??null)!=="ROLLED_BACK_INTERRUPTED"
 ||($rec["current"]??null)!=="releases/".$old)exit(74);
$r=(new \VF\AdOps\Upgrade\OwnerNextReleaseGateway())->installed($site);
if(($r["version"]??null)!=="0.1.15"||($r["source_sha"]??null)!==$old)exit(75);
echo "P08_V016_BRIDGE_NEW_PROCESS_ISSUED_V015_RECOVERY=PASS\n";
' "$site" "$old" "$target"
[[ "$(readlink "$site/current")" == "$old_pointer" ]] || exit 76
[[ ! -e "$site/storage/app/private/adops/maintenance/maintenance.json" ]] || exit 77
[[ ! -e "$assets" && ! -L "$assets" ]] || exit 77
after="$(sha256sum "$token" "$marker" "$site/.env" | cut -d ' ' -f1 | tr '\n' ':')"
[[ "$after" == "$before" ]] || exit 78
python3 - "$site" <<'PY'
from pathlib import Path
import hashlib,json,sys
s=Path(sys.argv[1]);root=s/'storage/app/private/adops'
assert not (root/'landing-assets').exists()
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
names={'config/github-read-token':root/'upgrade/github-read-token',
       'config/.env':s/'.env',
       'config/installed.json':root/'installation/installed.json'}
count=0
for f in (root/'recovery').glob('*/files-manifest.json'):
 d=json.loads(f.read_text());entries={x['path']:x for x in d['files']}
 if not all(k in entries for k in names):continue
 assert not any(k.startswith('private/landing-assets/') for k in entries)
 for k,p in names.items():
  snap=f.parent/'payload'/k
  assert snap.is_file() and entries[k]['sha256']==h(snap)==h(p)
  assert entries[k]['bytes']==snap.stat().st_size
 db=json.loads((f.parent/'manifest.json').read_text())
 assert h(f.parent/db['file'])==db['sha256']
 scope=hashlib.sha256(str(s).encode()).hexdigest()[:16]
 stage=Path.home()/f'.p08-v016-legacy-media-bridge-{scope}'/('stage-'+f.parent.name)
 assert stage.is_dir() and h(stage/'config/github-read-token')==h(names['config/github-read-token'])
 assert not (stage/'private/landing-assets').exists()
 count+=1
assert count>=2,'pre and fresh native backup stages required'
print('P08_EMPTY_MEDIA_SIGKILL_TWO_NATIVE_DB_OWNER_TOKEN_BACKUPS=PASS')
PY
php -r '
$s=$argv[1];require_once $s."/current/vendor/autoload.php";
$cfg=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($s);
$files=glob($s."/storage/app/private/adops/recovery/*/files-manifest.json");
$id=basename(dirname(end($files)));
$restore=$cfg;
if($cfg["driver"]==="sqlite"){$restore["database"]=$s."/database/".str_repeat("b",32).".sqlite";}
else {
 $restore["database"]="p08_ci_016_fault_restore_empty";
 $p=new PDO("mysql:host=".$cfg["host"].";port=".$cfg["port"].";charset=utf8mb4",$cfg["username"],$cfg["password"]);
 $p->exec("CREATE DATABASE ".$restore["database"]);
 $p=null;
}
(new \VF\AdOps\Recovery\DatabaseSnapshot())->restoreToEmpty($s,$id,$restore);
$pdo=function($c){return $c["driver"]==="sqlite"?new PDO("sqlite:".$c["database"]):
 new PDO("mysql:host=".$c["host"].";port=".$c["port"].";dbname=".$c["database"].";charset=utf8mb4",$c["username"],$c["password"]);};
$a=$pdo($cfg);$b=$pdo($restore);
foreach(["users","landing_pages","landing_assets","landing_revisions"] as $table){
 $n=(int)$a->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 $m=(int)$b->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 if($n!==$m||($table==="users"&&$n!==1)||($table!=="users"&&$n!==0))exit(84);
}
echo "P08_EMPTY_MEDIA_POST_SIGKILL_DB_INDEPENDENT_RESTORE=PASS\n";
' "$site"

echo "P08_V016_BRIDGE_REAL_SIGKILL_137_AND_NATIVE_RECOVERY=PASS"
