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
# Real audited Owner site has ABSENT assets directory; this is synthetic
# genuine issued-v015 installation with equally absent directory, no fake PNG.
python3 - "$site" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])/'storage/app/private/adops'
assets=root/'landing-assets'
if assets.is_dir() and not assets.is_symlink():
    assert not list(assets.iterdir()),'fixture unexpectedly has media'
    assets.rmdir()  # disposable fixture only; never on Production
assert not assets.exists() and not assets.is_symlink()
token=root/'upgrade/github-read-token'
token.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
if token.is_symlink():raise SystemExit(9)
token.write_text('github_pat_'+'r'*45+'\n')
token.chmod(0o600)
print('P08_V015_EMPTY_MEDIA_FIXTURE_GENUINELY_ABSENT=PASS')
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
# Authentic old E2E first-install writes disposable synthetic landing rows.
# Assert real empty-media bridge REJECTS these rows before preparing any backup.
case_owner='Synthetic-Owner-Only-12345!'
if [[ "$engine" == sqlite ]]; then case_owner='Synthetic-SQLite-Owner-12345!'; fi
set +e
printf '%s\n' "$case_owner" |
 php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
 --isolated-apply "$site" "$full" "$root/update.zip" CONFIRM_MEDIA_SAFE_V015_TO_V016 \
 > "$root/dirty-db-neg-out" 2> "$root/dirty-db-neg-err"
denied=$?
set -e
[[ "$denied" -eq 2 ]] || { echo P08_EMPTY_MEDIA_DIRTY_DB_ALLOWED=FAIL; exit 50; }
grep -Fxq 'P08_V016_BRIDGE_EMPTY_SITE_DB_NOT_EMPTY' "$root/dirty-db-neg-err" || {
  echo P08_EMPTY_MEDIA_DB_DENIAL_WRONG_CLASS=FAIL
  exit 51
}
[[ "$(readlink "$site/current")" == "releases/$old" ]] || exit 52
echo P08_EMPTY_MEDIA_NONEMPTY_DB_FAILS_CLOSED=PASS

# ONLY in disposable synthetic runner fixture: remove sample landing rows
# created by old installer E2E so site matches user's observed zero-row
# v015 MySQL audit. User/Token/.env/other data remain unchanged.
php -r '
$site=$argv[1];$old=$argv[2];
require_once $site."/releases/".$old."/vendor/autoload.php";
$cfg=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($site);
$pdo=$cfg["driver"]==="sqlite"
 ?new PDO("sqlite:".$cfg["database"])
 :new PDO("mysql:host=".$cfg["host"].";port=".$cfg["port"].";dbname=".$cfg["database"].";charset=utf8mb4",$cfg["username"],$cfg["password"]);
$pdo->setAttribute(PDO::ATTR_ERRMODE,PDO::ERRMODE_EXCEPTION);
$pdo->beginTransaction();
try{
 foreach(["landing_assets","landing_revisions","landing_pages"] as $table){
  $pdo->exec("DELETE FROM ".$table);
 }
 $pdo->commit();
}catch(Throwable $e){$pdo->rollBack();exit(53);}
foreach(["users","landing_assets","landing_revisions","landing_pages"] as $table){
 $n=(int)$pdo->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 if(($table==="users"&&$n!==1)||($table!=="users"&&$n!==0))exit(54);
}
' "$site" "$old"
[[ ! -e "$site/storage/app/private/adops/landing-assets" && ! -L "$site/storage/app/private/adops/landing-assets" ]] || exit 55
echo P08_EMPTY_MEDIA_REAL_AUDIT_ZERO_DB_FIXTURE_PARITY=PASS
php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
 --audit "$site" "$full" "$root/update.zip"
echo "P08_V016_BRIDGE_$engine"_OLD_ISSUED_MEDIA_TOKEN_AUDIT=PASS
old_pointer="$(readlink "$site/current")"
[[ ! -e "$site/storage/app/private/adops/landing-assets" && ! -L "$site/storage/app/private/adops/landing-assets" ]] || exit 41
before_token="$(sha256sum "$site/storage/app/private/adops/upgrade/github-read-token" | cut -d' ' -f1)"
before_owner="$(sha256sum "$site/storage/app/private/adops/installation/installed.json" | cut -d' ' -f1)"
before_env="$(sha256sum "$site/.env" | cut -d ' ' -f1)"
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
[[ ! -e "$site/storage/app/private/adops/landing-assets" && ! -L "$site/storage/app/private/adops/landing-assets" ]] || exit 46
[[ "$before_token" == "$(sha256sum "$site/storage/app/private/adops/upgrade/github-read-token" | cut -d' ' -f1)" ]] || exit 46
[[ "$before_owner" == "$(sha256sum "$site/storage/app/private/adops/installation/installed.json" | cut -d' ' -f1)" ]] || exit 46
scope="$(printf '%s' "$site" | sha256sum | cut -c1-16)"
[[ ! -d "$HOME/.p08-v016-legacy-media-bridge-$scope" ]] || exit 47
echo "P08_V016_BRIDGE_$engine"_INVALID_OWNER_NO_MUTATION=PASS

owner_password='Synthetic-Owner-Only-12345!'
if [[ "$engine" == sqlite ]]; then owner_password='Synthetic-SQLite-Owner-12345!'; fi
printf '%s\n' "$owner_password" | php "$root/target-full/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" \
 --isolated-apply "$site" "$full" "$root/update.zip" CONFIRM_MEDIA_SAFE_V015_TO_V016
[[ "$(readlink "$site/current")" == "releases/$target" ]] || {
  echo "P08_V016_BRIDGE_$engine"_FINAL_POINTER_MISMATCH=FAIL
  exit 48
}
[[ ! -e "$site/storage/app/private/adops/landing-assets" && ! -L "$site/storage/app/private/adops/landing-assets" ]] || exit 49
[[ "$before_token" == "$(sha256sum "$site/storage/app/private/adops/upgrade/github-read-token" | cut -d' ' -f1)" ]] || exit 49
[[ "$before_owner" == "$(sha256sum "$site/storage/app/private/adops/installation/installed.json" | cut -d' ' -f1)" ]] || exit 49
[[ "$before_env" == "$(sha256sum "$site/.env" | cut -d ' ' -f1)" ]] || exit 49
python3 - "$site" <<'PY'
import sys,json,hashlib
from pathlib import Path
site=Path(sys.argv[1]);private=site/'storage/app/private/adops'
assert not (private/'landing-assets').exists()
token=private/'upgrade/github-read-token'
assert token.is_file()
records=list((private/'recovery').glob('*/files-manifest.json'))
assert len(records)>=2
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
complete=0
for m in records:
    o=json.loads(m.read_text())
    entries={item['path']:item for item in o['files']}
    names=['config/github-read-token','config/.env','config/installed.json']
    if not all(k in entries for k in names): continue
    assert not any(k.startswith('private/landing-assets/') for k in entries)
    for k in names:
        original=token if k=='config/github-read-token' else (site/'.env' if k=='config/.env' else private/'installation/installed.json')
        saved=m.parent/'payload'/k
        assert saved.is_file() and entries[k]['sha256']==sha(saved)==sha(original)
        assert saved.stat().st_size==entries[k]['bytes']
    db=json.loads((m.parent/'manifest.json').read_text())
    saved=m.parent/db['file']
    assert saved.is_file() and db['sha256']==sha(saved) and db['bytes']==saved.stat().st_size
    scope=hashlib.sha256(str(site).encode()).hexdigest()[:16]
    stage=Path.home()/f'.p08-v016-legacy-media-bridge-{scope}'/('stage-'+m.parent.name)
    assert stage.is_dir() and sha(stage/'config/github-read-token')==sha(token)
    assert sha(stage/'config/.env')==sha(site/'.env')
    assert sha(stage/'config/installed.json')==sha(private/'installation/installed.json')
    assert not (stage/'private/landing-assets').exists()
    complete+=1
assert complete>=2,'two fresh real DB + private Token/Owner backups required'
assert not (private/'maintenance/maintenance.json').exists()
print('P08_EMPTY_MEDIA_TWO_DB_OWNER_TOKEN_BACKUPS_AND_INDEPENDENT_STAGE=PASS')
PY
# Fresh-stage native DB restore is independent of the running site database:
# compare Owner count and landing tables in restored isolated DB to originals.
php -r '
$s=$argv[1];$e=$argv[2];
require_once $s."/current/vendor/autoload.php";
$cfg=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($s);
$files=glob($s."/storage/app/private/adops/recovery/*/files-manifest.json");
if(count($files)<2)exit(81);
$id=basename(dirname(end($files)));
$restore=$cfg;
if($cfg["driver"]==="sqlite"){
  $restore["database"]=$s."/database/".str_repeat("b",32).".sqlite";
}else {
  $restore["database"]="p08_ci_016_restore_empty";
}
if($cfg["driver"]!=="sqlite"){
  $p=new PDO("mysql:host=".$cfg["host"].";port=".$cfg["port"].";charset=utf8mb4",$cfg["username"],$cfg["password"]);
  $p->exec("CREATE DATABASE ".$restore["database"]);
  $p=null;
}
(new \VF\AdOps\Recovery\DatabaseSnapshot())->restoreToEmpty($s,$id,$restore);
$pdo=function($data){return $data["driver"]==="sqlite"
  ?new PDO("sqlite:".$data["database"])
  :new PDO("mysql:host=".$data["host"].";port=".$data["port"].";dbname=".$data["database"].";charset=utf8mb4",$data["username"],$data["password"]);};
$a=$pdo($cfg);$b=$pdo($restore);
foreach(["users","landing_pages","landing_revisions","landing_assets"] as $table){
 $x=(int)$a->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 $y=(int)$b->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 if($x!==$y||($table==="users"&&$x!==1)||($table!=="users"&&$x!==0))exit(82);
}
echo "P08_EMPTY_MEDIA_REAL_NATIVE_DB_INDEPENDENT_RESTORE_OWNER_ZERO_ASSETS=PASS\n";
' "$site" "$engine"

echo "P08_V016_BRIDGE_$engine"_ORIGINAL_015_TO_CANDIDATE_016_NATIVE_ATOMIC=PASS

