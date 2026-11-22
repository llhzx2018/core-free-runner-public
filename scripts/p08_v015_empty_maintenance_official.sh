#!/usr/bin/env bash
# P08 unique Owner-approved maintenance PREISSUE MACHINE PROOF.
# ONLY disposable real official issued v015 MySQL + actual unmodified v016
# FULL/UPDATE. Never run on Owner's Production, never log read token.
set -Eeuo pipefail
set +x
umask 077
[[ "$GITHUB_ACTIONS" == true && "$CI" == true && "$P08_ISOLATED_INSTALL_TEST" == YES && "$(id -u)" != 0 ]] || exit 3
[[ "$(git -C target rev-parse HEAD)" == 54f8a1230d64a152f9da159766b9a9e4346cabcd ]] || exit 3
[[ "$RUNNER_TEMP" == /home/runner/work/_temp ]] || exit 3
[[ -n "$GH_TOKEN" && ${#GH_TOKEN} -ge 20 ]] || exit 3
old=369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e
target=ed96b18627cd0a63b1da20a1fd8c9b6c1808f159
site="$RUNNER_TEMP/p08-v016-legacy-oldsite-mysql"
t="$RUNNER_TEMP/p08-v016-official-maintenance"
base="$HOME/.p08-v015-empty-media-once"
[[ ! -e "$site" && ! -e "$t" && ! -e "$base" ]] || exit 4
mkdir -m 700 "$site" "$t" "$base"
mkdir -m 700 "$base/official-full"
gh release download v0.1.15 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.15_FULL.zip -D "$t" > /dev/null
gh release download v0.1.16 -R llhzx2018/vf-adops -p VF_AdOps_V0.1.16_FULL.zip -p VF_AdOps_V0.1.16_UPDATE.zip -D "$t" > /dev/null
oldZip="$t/VF_AdOps_V0.1.15_FULL.zip"
full="$t/VF_AdOps_V0.1.16_FULL.zip"
update="$t/VF_AdOps_V0.1.16_UPDATE.zip"
printf '%s  %s\n' 538d161339849214999eb6f85da40623a149fc9cf1b592c9e5907f751c434f73 "$oldZip" | sha256sum -c --status
printf '%s  %s\n' 7f6a3050db060448df391f0dc5a8a3a2de45c9f28a704cb76606694b82bd084f "$full" | sha256sum -c --status
printf '%s  %s\n' 6cd533631c3651117f09ffce3829a565d16d945f7f1e4938c27d678c75e3c399 "$update" | sha256sum -c --status
unzip -tqq "$oldZip"; unzip -tqq "$full"; unzip -tqq "$update"
unzip -q "$oldZip" -d "$site"
unzip -q "$full" -d "$base/official-full"
[[ "$(readlink "$site/current" 2>/dev/null || true)" == "" ]] || exit 5
mkdir -p "$site/tests/compatibility"
cp target/tests/test_install_mysql_e2e.php "$site/tests/"
cp target/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
export P08_TEST_DB_CLEAN=p08_ci_016_old
export P08_TEST_DB_DIRTY=p08_ci_016_old_dirty
mariadb -h127.0.0.1 -uroot -p"$P08_TEST_DB_PASSWORD" -e 'CREATE DATABASE p08_ci_016_old; CREATE DATABASE p08_ci_016_old_dirty; CREATE TABLE p08_ci_016_old_dirty.synthetic_dirty(id integer primary key);'
php "$site/tests/test_install_mysql_e2e.php" > "$t/install.log" 2>&1 || {
    echo P08_EMPTY_OFFICIAL_ORIGINAL_V015_INSTALL_FAILED
    exit 6
}
[[ "$(readlink "$site/current")" == "releases/$old" ]] || exit 7
[[ "$(cat "$site/current/VERSION")" == "0.1.15" ]] || exit 7
[[ "$(cat "$base/official-full/VERSION")" == "0.1.16" ]] || exit 7
# The original first-install E2E *intentionally* creates sample landing rows.
# Only on the disposable fixture remove those synthetic sample rows, retaining
# one true Owner and ensuring zero asset rows matches the Owner's live audit.
php -r '
$s=$argv[1];require_once $s."/releases/".$argv[2]."/vendor/autoload.php";
$c=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($s);
$db=new PDO("mysql:host=".$c["host"].";port=".$c["port"].";dbname=".$c["database"].";charset=utf8mb4",$c["username"],$c["password"],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$db->beginTransaction();
try{foreach(["landing_assets","landing_revisions","landing_pages"] as $table)$db->exec("DELETE FROM ".$table);$db->commit();}
catch(Throwable $x){$db->rollBack();exit(7);}
foreach(["users","landing_pages","landing_revisions","landing_assets"] as $table){
 $n=(int)$db->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 if(($table==="users"&&$n!==1)||($table!=="users"&&$n!==0))exit(8);
}
' "$site" "$old"
assets="$site/storage/app/private/adops/landing-assets"
if [[ -d "$assets" && ! -L "$assets" ]]; then
   [[ -z "$(find "$assets" -type f -print -quit)" ]] || exit 8
   rmdir "$assets"
fi
[[ ! -e "$assets" && ! -L "$assets" ]] || exit 8
private="$site/storage/app/private/adops"
mkdir -p "$private/upgrade"
chmod 700 "$private/upgrade"
printf '%s\n' "$GH_TOKEN" > "$private/upgrade/github-read-token"
chmod 600 "$private/upgrade/github-read-token"
initial_token="$(sha256sum "$private/upgrade/github-read-token" | cut -d' ' -f1)"
initial_owner="$(sha256sum "$private/installation/installed.json" | cut -d' ' -f1)"
initial_env="$(sha256sum "$site/.env" | cut -d' ' -f1)"
# Test the *actual extracted final maintenance ZIP file*, not development source.
zip="$t/VF_P08_015_MYSQL_EMPTY_MEDIA_ONCE_20261122.zip"
rebuild="$t/rebuild-twice.zip"
python3 -B scripts/p08_pr99_onefile_package.py --source "$GITHUB_WORKSPACE/target" --output "$zip"
python3 -B scripts/p08_pr99_onefile_package.py --source "$GITHUB_WORKSPACE/target" --output "$rebuild"
cmp -s "$zip" "$rebuild" || { echo P08_PR99_DETERMINISTIC_REBUILD=FAIL; exit 15; }
python3 -B scripts/p08_pr99_onefile_package.py --source "$GITHUB_WORKSPACE/target" --verify "$zip"
unzip -tqq "$zip"
bridge="$base/P08_015_EmptyMedia_Once.php"
unzip -p "$zip" P08_015_EmptyMedia_Once.php > "$bridge"
chmod 600 "$bridge"
[[ "$(sha256sum "$bridge" | cut -d' ' -f1)" == "$(sha256sum "$GITHUB_WORKSPACE/target/src/Upgrade/LegacyMediaUpgradeBridgeCli.php" | cut -d' ' -f1)" ]] || exit 15
[[ "$(stat -c '%a' "$bridge")" == 600 && "$(stat -c '%a' "$base")" == 700 ]] || exit 15
# Deliberate negative: make an altered PHP entry inside an otherwise valid ZIP.
python3 - "$zip" "$t/forged.zip" <<'PY'
import sys,zipfile
src,dst=sys.argv[1:3]
with zipfile.ZipFile(src) as zin,zipfile.ZipFile(dst,'w') as zout:
 for info in zin.infolist():
  body=zin.read(info.filename)
  if info.filename=='P08_015_EmptyMedia_Once.php':body+=b'\n# FORGED PAYLOAD\n'
  zout.writestr(info,body)
PY
if python3 -B scripts/p08_pr99_onefile_package.py --source "$GITHUB_WORKSPACE/target" --verify "$t/forged.zip" > "$t/forged.out" 2>&1; then
 echo P08_PR99_FORGED_ZIP_ACCEPTED=FAIL; exit 16
fi
echo P08_PR99_EXTRACTED_EXACT_ONEPHP_ZIP_AND_FORGED_DENIAL=PASS

# Shared Public Authority structural delivery lint on this exact, already-built
# executable archive. It is a generic ZIP profile, not a fake Atomic/FULL.
cat > "$t/receipt.json" <<'JSON'
{
 "schema":"vf.public-authority.task-delivery-check.v1",
 "project":"P08",
 "source":"349f4c0d46a8350c18cb36b6c8b0c60d2c096c6b",
 "project_authority":{
   "agents":"AGENTS.md",
   "current":"docs/authority/CURRENT.md",
   "acceptance":"docs/authority/ACCEPTANCE_MATRIX.md",
   "applicability":"docs/authority/PUBLIC_AUTHORITY_APPLICABILITY.md"
 },
 "acceptance_markers":["## RP-07AA","PR #99"],
 "required_domains":["INSTALL","SECURITY","TESTING","UPGRADE","DATA_SCHEMA","API_PROVIDER","OBSERVABILITY","GIT"],
 "task_capabilities":["release","auth","existing_install_transition","backup","credentials","production_runtime","release_source"],
 "delivery":{
   "profile":"static_bundle_zip",
   "kind":"STANDALONE_PHP_ONEFILE_MAINTENANCE_NOT_ATOMIC",
   "artifact":"VF_P08_015_MYSQL_EMPTY_MEDIA_ONCE_20261122.zip",
   "entrypoint":"P08_015_EmptyMedia_Once.php",
   "requires_git":false,
   "requires_manual_source_copy":false
 }
}
JSON
python3 - "$t/receipt.json" "$zip" <<'PY'
import hashlib,json,sys
p,zip=sys.argv[1:3]
d=json.load(open(p))
d['delivery']['sha256']=hashlib.sha256(open(zip,'rb').read()).hexdigest()
with open(p,'w') as out:json.dump(d,out)
PY
for phase in resolve delivery; do
  python3 -B "$GITHUB_WORKSPACE/gov/governance/public-authority/tools/task_delivery_contract_lint.py" \
   --phase "$phase" --receipt "$t/receipt.json" --project-root "$GITHUB_WORKSPACE/target" \
   --artifact-root "$t" \
   --public-router "$GITHUB_WORKSPACE/gov/governance/public-authority/VF_PUBLIC_AUTHORITY_APPLICABILITY_ROUTER_V1.0.json" \
   > "$t/lint-$phase.log" || { echo P08_PR99_DELIVERY_CONTRACT_LINT=BLOCKED; exit 19; }
  grep -q 'RULES_RESOLVED=YES' "$t/lint-$phase.log" || exit 19
done
grep -Fxq 'CONTRACT_CHECK=STRUCTURAL_PASS' "$t/lint-delivery.log" || exit 19
echo P08_PR99_FINAL_REAL_ARCHIVE_SHARED_DELIVERY_STRUCTURAL=PASS

set +e
php "$bridge" --maintenance-audit "$RUNNER_TEMP/untrusted-unrelated-site" "$full" "$update" "$base/official-full" > "$t/wrong-site.out" 2> "$t/wrong-site.err"
wrongsite=$?
set -e
[[ "$wrongsite" -eq 2 ]] || exit 16
grep -Fxq 'P08_EMPTY_MAINTENANCE_OTHER_SITE_REFUSED' "$t/wrong-site.err" || exit 16
echo P08_PR99_WRONG_SITE_DENIED_BEFORE_BACKUP=PASS
php -l "$bridge" > "$t/lint.log"
php "$bridge" --maintenance-audit "$site" "$full" "$update" "$base/official-full" > "$t/audit.log"
grep -Fxq 'P08_V016_BRIDGE_OLD_AND_BUNDLE=STRUCTURAL_PASS_NOT_RELEASE_AUTHORITY' "$t/audit.log"
echo P08_EMPTY_MAINTENANCE_REAL_V015_AND_IMMUTABLE_V016_AUDIT=PASS
set +e
printf 'incorrect-owner-password\n' | php "$bridge" --maintenance-apply "$site" "$full" "$update" CONFIRM_MEDIA_SAFE_V015_TO_V016 "$base/official-full" > "$t/wrong.out" 2> "$t/wrong.err"
denied=$?
set -e
[[ "$denied" == 2 ]] || exit 9
grep -Fxq P08_V016_BRIDGE_OWNER_AUTH_REFUSED "$t/wrong.err" || exit 9
[[ "$(readlink "$site/current")" == "releases/$old" ]] || exit 9
[[ ! -e "$private/maintenance/maintenance.json" ]] || exit 9
echo P08_EMPTY_MAINTENANCE_REAL_OLD_OWNER_WRONG_PASSWORD_FAILCLOSED=PASS
printf 'Synthetic-Owner-Only-12345!\n' |
 php "$bridge" --maintenance-apply "$site" "$full" "$update" CONFIRM_MEDIA_SAFE_V015_TO_V016 "$base/official-full" > "$t/applied.log" 2> "$t/applied.err" || {
    grep -E '^P08_[A-Z0-9_]+$' "$t/applied.err" || true
    echo P08_EMPTY_MAINTENANCE_OFFICIAL_PAIR_APPLY=FAIL
    exit 10
 }
grep -Fxq 'P08_V016_BRIDGE_ISSUED_V015_NATIVE_MEDIA_SAFE_ATOMIC=SUCCEEDED' "$t/applied.log"
[[ "$(readlink "$site/current")" == "releases/$target" ]] || exit 11
[[ "$(cat "$site/current/VERSION")" == 0.1.16 ]] || exit 11
[[ ! -e "$assets" && ! -L "$assets" ]] || exit 11
[[ "$(sha256sum "$private/upgrade/github-read-token" | cut -d' ' -f1)" == "$initial_token" ]] || exit 12
[[ "$(sha256sum "$private/installation/installed.json" | cut -d' ' -f1)" == "$initial_owner" ]] || exit 12
[[ "$(sha256sum "$site/.env" | cut -d' ' -f1)" == "$initial_env" ]] || exit 12
python3 - "$site" <<'PY'
import hashlib,json,sys
from pathlib import Path
s=Path(sys.argv[1]);p=s/'storage/app/private/adops'
def h(f):return hashlib.sha256(f.read_bytes()).hexdigest()
snaps=list((p/'recovery').glob('*/files-manifest.json'))
assert len(snaps)>=2
count=0
for x in snaps:
 d=json.loads(x.read_text()); e={a['path']:a for a in d['files']}
 required={'config/.env':s/'.env','config/installed.json':p/'installation/installed.json','config/github-read-token':p/'upgrade/github-read-token'}
 if not all(k in e for k in required):continue
 assert not any(k.startswith('private/landing-assets/') for k in e)
 for k,original in required.items():
  saved=x.parent/'payload'/k
  assert saved.is_file() and h(saved)==h(original)==e[k]['sha256']
 db=json.loads((x.parent/'manifest.json').read_text())
 archive=x.parent/db['file']
 assert archive.is_file() and h(archive)==db['sha256'] and archive.stat().st_size==db['bytes']
 scope=hashlib.sha256(str(s).encode()).hexdigest()[:16]
 stage=Path.home()/f'.p08-v016-legacy-media-bridge-{scope}'/('stage-'+x.parent.name)
 assert stage.is_dir() and h(stage/'config/github-read-token')==h(p/'upgrade/github-read-token')
 count+=1
assert count>=2
print('P08_EMPTY_MAINTENANCE_REAL_OFFICIAL_TWO_BACKUPS_TOKEN_OWNER=PASS')
PY
php -r '
$s=$argv[1];require_once $s."/current/vendor/autoload.php";
$c=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($s);
$paths=glob($s."/storage/app/private/adops/recovery/*/files-manifest.json");
$id=basename(dirname(end($paths)));
$dest=$c;$dest["database"]="p08_ci_016_official_restore";
$root=new PDO("mysql:host=".$c["host"].";port=".$c["port"].";charset=utf8mb4",$c["username"],$c["password"]);
$root->exec("CREATE DATABASE ".$dest["database"]);$root=null;
(new \VF\AdOps\Recovery\DatabaseSnapshot())->restoreToEmpty($s,$id,$dest);
$a=new PDO("mysql:host=".$c["host"].";port=".$c["port"].";dbname=".$c["database"].";charset=utf8mb4",$c["username"],$c["password"]);
$b=new PDO("mysql:host=".$c["host"].";port=".$c["port"].";dbname=".$dest["database"].";charset=utf8mb4",$c["username"],$c["password"]);
foreach(["users","landing_pages","landing_revisions","landing_assets"] as $table){
 $x=(int)$a->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 $y=(int)$b->query("SELECT COUNT(*) FROM ".$table)->fetchColumn();
 if($x!==$y||($table==="users"&&$x!==1)||($table!=="users"&&$x!==0))exit(15);
}
echo "P08_EMPTY_MAINTENANCE_REAL_OFFICIAL_MYSQL_INDEPENDENT_DB_RESTORE=PASS\n";
' "$site"
echo P08_EMPTY_MAINTENANCE_OFFICIAL_V015_TO_IMMUTABLE_016_NATIVE_ATOMIC=PASS
