#!/usr/bin/env bash
set -Eeuo pipefail
repo="$(realpath "$1")"
proof="$(realpath -m "$2")"
mkdir -p "$proof/native"
: "$TARGET_VERSION" "$TARGET_SHA" "$TARGET_TREE" "$SOURCE_VERSION"
trap 'code=$?; printf "exit=%s\n" "$code" >> "$proof/stage.txt"' EXIT
echo "stage=IDENTITY" > "$proof/stage.txt"
test "$(git -C "$repo" rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C "$repo" rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(tr -d '\r\n' < "$repo/VERSION")" = "$TARGET_VERSION"
grep -Fq " * Version: $TARGET_VERSION" "$repo/vf-ops.php"
grep -Fq "define('VF_OPS_VERSION', '$TARGET_VERSION')" "$repo/vf-ops.php"
echo "stage=SOURCE_CHECKS" >> "$proof/stage.txt"
find "$repo" -type f -name '*.php' -not -path '*/.git/*' -print0 | xargs -0 -n 1 php -l > "$proof/php-lint.txt"
for f in assets/js/v13/system/plugins.js assets/js/admin-publish-zip.js \
 assets/js/admin-acceptance-components.js assets/js/admin-acceptance-overview.js \
 assets/js/admin-o11-source.js assets/js/admin-online-acceptance.js \
 assets/js/admin-dashboard-workbench.js assets/js/admin-content-management.js \
 assets/js/admin-seo-refine.js assets/js/admin-seo-governance-job.js \
 assets/js/admin-seo-gaps.js assets/js/admin-o9-multilingual.js \
 assets/js/admin-o8-keywords.js assets/js/v13/content/briefs.js \
 assets/js/admin-content-status.js assets/js/admin-media-resources.js
do node --check "$repo/$f"; done
node "$repo/tests/s01-c02-1211094-media-confirm-native-regression.js" | tee "$proof/regression.txt"
node "$repo/tests/s01-c02-1211094-seo-links-stale-error-regression.js" | tee -a "$proof/regression.txt"
php "$repo/tests/s01-c02-1211094-keyword-map-export-current-filters.php" | tee -a "$proof/regression.txt"
php "$repo/tests/s01-c02-1211094-upgrade-idempotent-bridge.php" | tee -a "$proof/regression.txt"
php "$repo/tests/s01-c02-1211095-system-update-blocker-visibility.php" | tee -a "$proof/regression.txt"
php "$repo/tests/s01-c02-1211096-current-update-offer-order.php" | tee -a "$proof/regression.txt"
php "$repo/tests/s01-c02-1211101-seed-scan-truth-contract.php" | tee -a "$proof/regression.txt"
echo "stage=PACKAGE" >> "$proof/stage.txt"
candidate="$proof/vf-tools-ops_V$TARGET_VERSION.zip"
python3 "$repo/.github/release/build-ops-package.py" --source "$repo" --output "$candidate" > "$proof/candidate.json"
python3 - "$candidate" "$proof/candidate.json" "$TARGET_VERSION" <<'PY'
import hashlib,json,pathlib,sys,zipfile
a=pathlib.Path(sys.argv[1]); m=json.loads(pathlib.Path(sys.argv[2]).read_text()); v=sys.argv[3]
with zipfile.ZipFile(a) as z:
 ns=z.namelist()
 assert ns and all(n.startswith('vf-ops/') and not n.startswith('vf-ops/vf-ops/') for n in ns)
 assert 'vf-ops/vf-ops.php' in ns and len(ns)==m['runtime_files']
 assert all('/tests/' not in n and '/.github/' not in n and not n.endswith(('.pem','.key','.sqlite','.sql','.db','.env','.bak')) for n in ns)
 assert (' * Version: '+v).encode() in z.read('vf-ops/vf-ops.php')
assert a.stat().st_size==m['asset_bytes']
assert hashlib.sha256(a.read_bytes()).hexdigest()==m['asset_sha256']
assert m['root_contract']=='PASS_SINGLE_VF_OPS_ROOT'
print('PACKAGE_ROOT_SHA_FILECOUNT=PASS')
PY
sha256sum "$candidate" > "$proof/SHA256SUMS.txt"
echo "stage=WORDPRESS_NATIVE_HARNESS" >> "$proof/stage.txt"
# The existing product-owned harness uses a historical fixed fixture version.
# Adapt only in the transient Runner workspace, never in product main.
fixture_version="$(python3 - "$TARGET_VERSION" <<'PY'
import sys
parts=sys.argv[1].split('.');parts[-1]=str(int(parts[-1])+1);print('.'.join(parts))
PY
)"
target_patch="$(printf %s "$TARGET_VERSION" | awk -F. '{print $NF}')"
fixture_patch="$(printf %s "$fixture_version" | awk -F. '{print $NF}')"
sed -e "s/789/$target_patch/g" -e "s/790/$fixture_patch/g" \
    "$repo/.github/wp-update/run.sh" > "$proof/run-native.sh"
if grep -nE '1[.]21[.](789|790)|21\\\\[.]789|21\\\\[.]790' "$proof/run-native.sh"; then
  echo "HISTORICAL_HARNESS_TARGET_IDENTITY_REMAINS" >&2; exit 12
fi
bash -n "$proof/run-native.sh"
# Diagnose the owned preservation gate without exposing synthetic secret values.
python3 - "$proof/run-native.sh" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
old='if(is_wp_error($v))exit(2);$after='
new='''if(is_wp_error($v)){echo "PRESERVATION_GATE_ERROR=",$v->get_error_code(),"\\\\n";$afterState=VF_Ops_Update_Preservation_V1::snapshot();foreach(["options","secrets","cron","capabilities"] as $k){$b=(array)($before["preservation"][$k]??[]);$a=(array)($afterState[$k]??[]);if(($b["fingerprint"]??"")!==($a["fingerprint"]??"")){echo "PRESERVATION_DRIFT_AREA=",$k," COUNT=",(int)($b["count"]??0),"/",(int)($a["count"]??0),"\\\\n";if($k==="options"){$oldItems=(array)($b["items"]??[]);$newItems=(array)($a["items"]??[]);foreach(array_unique(array_merge(array_keys($oldItems),array_keys($newItems))) as $optionName){if(($oldItems[$optionName]??"")!==($newItems[$optionName]??""))echo "PRESERVATION_OPTION_NAME=",$optionName,"\\\\n";}}}}exit(2);}$after='''
assert s.count(old)==1, 'exact preservation gate anchor changed'
p.write_text(s.replace(old,new))
PY
bash -n "$proof/run-native.sh"
bash "$proof/run-native.sh" "$repo" "$proof/native"
echo "stage=FORMAL_SOURCE_UPGRADE_ROLLBACK" >> "$proof/stage.txt"
: "$GH_TOKEN" "$MARIADB_ROOT_PASSWORD"
mkdir -p "$proof/source-download"
gh release download "v$SOURCE_VERSION" --repo llhzx2018/vf-tools-ops \
 --pattern "vf-tools-ops_V$SOURCE_VERSION.zip" --dir "$proof/source-download" --clobber
old="$proof/source-download/vf-tools-ops_V$SOURCE_VERSION.zip"
digest="$(gh api "repos/llhzx2018/vf-tools-ops/releases/tags/v$SOURCE_VERSION" \
 --jq '.assets[] | select(.name | endswith(".zip")) | .digest')"
test "sha256:$(sha256sum "$old" | awk '{print $1}')" = "$digest"
mysql --protocol=tcp -h127.0.0.1 -uroot -p"$MARIADB_ROOT_PASSWORD" \
 -e "CREATE DATABASE IF NOT EXISTS vf_ops_formal_upgrade CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON vf_ops_formal_upgrade.* TO 'vf'@'%';"
wp2="$RUNNER_TEMP/s01-c02-formal-upgrade"
mkdir -p "$wp2"
wp core download --path="$wp2" --version=7.0.2 --force --allow-root >/dev/null
wp config create --path="$wp2" --dbname=vf_ops_formal_upgrade --dbuser=vf --dbpass=vf \
 --dbhost=127.0.0.1:3306 --skip-check --allow-root >/dev/null
wp core install --path="$wp2" --url=http://127.0.0.1:18096 --title='S01 Candidate' \
 --admin_user=admin --admin_password='synthetic-ci-admin-only' \
 --admin_email=synthetic@example.invalid --skip-email --allow-root >/dev/null
wp plugin install "$old" --path="$wp2" --activate --allow-root >/dev/null
wp eval --path="$wp2" 'do_action("admin_init");update_option("vf_s01_release_fixture",["preserve"=>"yes","sentinel"=>42],false);echo "BASELINE=",VF_OPS_VERSION,"\n";' \
 --allow-root > "$proof/formal-upgrade.txt"
wp plugin install "$candidate" --force --path="$wp2" --allow-root >/dev/null
wp eval --path="$wp2" 'do_action("admin_init");require_once ABSPATH."wp-admin/includes/plugin.php";$p=get_plugin_data(WP_PLUGIN_DIR."/vf-ops/vf-ops.php",false,false);$s=get_option("vf_s01_release_fixture",[]);if(($p["Version"]??"")!==getenv("TARGET_VERSION")||!is_plugin_active("vf-ops/vf-ops.php")||($s["preserve"]??"")!=="yes"||($s["sentinel"]??0)!==42)exit(3);echo "FORMAL_SOURCE_UPGRADE_AND_PRESERVATION=PASS\n";' \
 --allow-root >> "$proof/formal-upgrade.txt"
# Exercise the real WordPress SQL-backed seed scanner on disposable MariaDB.
# The fixture is created and deleted ONLY inside the Runner's temporary site.
wp eval --path="$wp2" '
    do_action("admin_init");
    if (!function_exists("vf_ops_seed_residue_migration_state")) { echo "SEED_SERVICE_ABSENT\n"; exit(8); }
    $before=vf_ops_seed_residue_migration_state();
    if (($before["status"]??"")!=="PASS" || ($before["count"]??-1)!==0 || empty($before["scanComplete"])) { echo "SEED_EMPTY_SCAN_FAIL\n"; exit(8); }
    $id=wp_insert_post(["post_type"=>"page","post_status"=>"draft","post_title"=>"Disposable signed migration probe"],true);
    if (is_wp_error($id)) exit(8);
    update_post_meta($id,"_vf_toolsite_seed_can_delete","yes");
    $found=vf_ops_seed_residue_migration_state();
    if (($found["status"]??"")!=="ATTENTION" || ($found["count"]??-1)!==1 || !in_array((int)$id,(array)($found["ids"]??[]),true)) exit(8);
    wp_delete_post($id,true);
    $after=vf_ops_seed_residue_migration_state();
    if (($after["status"]??"")!=="PASS" || ($after["count"]??-1)!==0 || empty($after["scanComplete"])) exit(8);
    echo "REAL_WP_MARIADB_SEED_SCANNER_ZERO_POSITIVE_ZERO=PASS\n";
' --allow-root >> "$proof/formal-upgrade.txt"
wp plugin install "$old" --force --path="$wp2" --allow-root >/dev/null
wp eval --path="$wp2" 'do_action("admin_init");require_once ABSPATH."wp-admin/includes/plugin.php";$p=get_plugin_data(WP_PLUGIN_DIR."/vf-ops/vf-ops.php",false,false);$s=get_option("vf_s01_release_fixture",[]);if(($p["Version"]??"")!==getenv("SOURCE_VERSION")||!is_plugin_active("vf-ops/vf-ops.php")||($s["preserve"]??"")!=="yes"||($s["sentinel"]??0)!==42)exit(3);echo "FORMAL_SOURCE_ROLLBACK_AND_PRESERVATION=PASS\n";' \
 --allow-root >> "$proof/formal-upgrade.txt"
python3 - "$proof" "$TARGET_VERSION" "$TARGET_SHA" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); pack=json.loads((p/'candidate.json').read_text())
native=json.loads((p/'native/FINAL_EVIDENCE.json').read_text())
assert native['result']=='PASS' and pack['version']==sys.argv[2]
log=(p/'formal-upgrade.txt').read_text()
assert 'FORMAL_SOURCE_UPGRADE_AND_PRESERVATION=PASS' in log
assert 'FORMAL_SOURCE_ROLLBACK_AND_PRESERVATION=PASS' in log
result={'gate':'S01-C02 exact 1.21.1101 machine','result':'PASS','source_sha':sys.argv[3],
 'version':sys.argv[2],'package':pack,'native_wp':'PASS','formal_upgrade':'PASS',
 'formal_rollback':'PASS','production_write':False,'owner_real_use':'PENDING'}
(p/'RESULT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print('EXACT_CANDIDATE_MACHINE_PASS')
PY
echo "stage=PASS" >> "$proof/stage.txt"
