#!/usr/bin/env bash
set -Eeuo pipefail
out="$GITHUB_WORKSPACE/proof-native"
mkdir -p "$out"
: "$GH_TOKEN" "$VF_PRIVATE_READ_TOKEN" "$TARGET_VERSION" "$SOURCE_VERSION" "$EXPECTED_SHA" "$EXPECTED_BYTES" "$CHANNEL_SHA"
echo "stage=LIVE_PUBLICATION_PREFLIGHT" > "$out/stage.txt"
gh api "repos/llhzx2018/core-updates/commits/$CHANNEL_SHA" --jq '{sha:.sha}' > "$out/channel-commit.json"
gh api "repos/llhzx2018/vf-tools-ops/releases/tags/v$TARGET_VERSION" --jq '{tag_name,draft,prerelease,assets:[.assets[]|{name,size,digest}]}' > "$out/release.json"
gh api -H "Accept: application/vnd.github.raw+json" "repos/llhzx2018/core-updates/contents/projects/S01-C02.json?ref=main" > "$out/published-channel.json"
python3 - "$out" <<'PY'
import json,os,pathlib,sys
p=pathlib.Path(sys.argv[1]); c=json.loads((p/'published-channel.json').read_text());r=json.loads((p/'release.json').read_text())
assert json.loads((p/'channel-commit.json').read_text())['sha']==os.environ['CHANNEL_SHA']
assert c['target_version']==os.environ['TARGET_VERSION'] and c['release_tag']==r['tag_name']
assert os.environ['SOURCE_VERSION'] in c['from_versions']
assert c['plugin_file']=='vf-ops/vf-ops.php' and c['schema_from']==c['schema_to']=='6.0.0'
a=[x for x in r['assets'] if x['name']==c['asset_name']]
assert len(a)==1 and not r['draft'] and not r['prerelease']
assert a[0]['size']==int(os.environ['EXPECTED_BYTES'])==c['asset_bytes']
assert a[0]['digest']=='sha256:'+os.environ['EXPECTED_SHA']=='sha256:'+c['asset_sha256']
print("LIVE_PUBLISHED_CHANNEL_ASSET_AND_SOURCE_VERSION=PASS")
PY
echo "stage=INSTALL_FORMAL_SOURCE" >> "$out/stage.txt"
mkdir -p "$out/old"
gh release download "v$SOURCE_VERSION" --repo llhzx2018/vf-tools-ops --pattern "vf-tools-ops_V$SOURCE_VERSION.zip" --dir "$out/old" --clobber
old="$out/old/vf-tools-ops_V$SOURCE_VERSION.zip"
old_digest="$(gh api "repos/llhzx2018/vf-tools-ops/releases/tags/v$SOURCE_VERSION" --jq '.assets[] | select(.name | endswith(".zip")) | .digest')"
test "sha256:$(sha256sum "$old" | awk '{print $1}')" = "$old_digest"
wp="$RUNNER_TEMP/s01-c02-published-native"
mkdir -p "$wp"
wp core download --path="$wp" --version=7.0.2 --force >/dev/null
wp config create --path="$wp" --dbname=vf_ops_discovery --dbuser=vf --dbpass=vf --dbhost=127.0.0.1:3306 --skip-check >/dev/null
# Isolated WP-CLI has no interactive FTP credentials; use direct local FS writes.
wp config set --path="$wp" FS_METHOD direct --type=constant >/dev/null
wp core install --path="$wp" --url=http://127.0.0.1:18104 --title='Published Native Discovery' --admin_user=admin --admin_password='fixture-only-not-user' --admin_email=synthetic@example.invalid --skip-email >/dev/null
wp plugin install "$old" --path="$wp" --activate >/dev/null
wp eval --path="$wp" '$v=VF_OPS_VERSION;if($v!==getenv("SOURCE_VERSION"))exit(2);do_action("admin_init");$authority=VF_Ops_Runtime_Authority_V1::verify($v,WP_PLUGIN_DIR."/vf-ops/");if(is_wp_error($authority)){echo "SOURCE_AUTHORITY_FAILED=",$authority->get_error_code(),"\\n";exit(2);}update_option("vf_ops_published_update_fixture",["sentinel"=>"retained"],false);echo "FORMAL_BASELINE_INSTALLED=PASS\n";' | tee "$out/wordpress-native.txt"
echo "stage=LIVE_WORDPRESS_MANUAL_AND_NATIVE_DISCOVERY" >> "$out/stage.txt"
wp eval --path="$wp" '$r=vf_ops_wp_update_client_v1()->manual_check(true);if(($r["status"]??"")!=="UPDATE_AVAILABLE"||($r["manifest"]["target_version"]??"")!==getenv("TARGET_VERSION")||($r["release"]["asset_sha256"]??"")!==getenv("EXPECTED_SHA")){echo "MANUAL_DISCOVERY_ERROR=",(string)($r["error_code"]??$r["status"]??"UNKNOWN"),"\n";exit(3);}echo "PUBLISHED_MANUAL_CHECK_UPDATE_AVAILABLE=PASS\n";' | tee -a "$out/wordpress-native.txt"
wp eval --path="$wp" 'delete_site_transient("update_plugins");VF_Ops_Update_Client_V1::clear_cache();wp_update_plugins();$u=get_site_transient("update_plugins");$f=VF_Ops_Update_Contract_V1::PLUGIN_FILE;if(!is_object($u)||empty($u->response[$f])||($u->response[$f]->new_version??"")!==getenv("TARGET_VERSION"))exit(4);echo "WORDPRESS_UPDATE_PLUGINS_NATIVE_OFFER=PASS\n";' | tee -a "$out/wordpress-native.txt"
echo "stage=LIVE_PUBLISHED_ASSET_UPGRADE" >> "$out/stage.txt"
wp eval --path="$wp" '$r=vf_ops_wp_update_execute_v1();if(empty($r["ok"])){echo "UPGRADE_RESULT=",(string)($r["status"]??"FAILED")," CODE=",(string)($r["error_code"]??""),"\n";foreach(["message","error","stage","code"] as $key){if(isset($r[$key])&&is_scalar($r[$key])){echo "DIAGNOSTIC_",$key,"=",substr(preg_replace("/[^A-Za-z0-9 _.,:\\/-]/","?",(string)$r[$key]),0,240),"\n";}}echo "RESULT_KEYS=",implode(",",array_keys($r)),"\n";$f=(array)($r["final"]??[]);echo "FINAL_KEYS=",implode(",",array_keys($f)),"\n";foreach(array_slice((array)($f["attempts"]??[]),-5) as $a){echo "ATTEMPT_STAGE=",preg_replace("/[^A-Za-z0-9_]/","?",(string)($a["stage"]??""))," RESULT=",preg_replace("/[^A-Za-z0-9_]/","?",(string)($a["result"]??""))," CODE=",preg_replace("/[^A-Za-z0-9_]/","?",(string)($a["error_code"]??"")),"\n";}foreach(["final_result","reason","error_code","target_version"] as $key){if(isset($f[$key])&&is_scalar($f[$key]))echo "FINAL_",$key,"=",substr(preg_replace("/[^A-Za-z0-9 _.,:\\/-]/","?",(string)$f[$key]),0,180),"\n";}exit(5);}echo "PUBLISHED_ASSET_NATIVE_UPGRADE=PASS\n";' | tee -a "$out/wordpress-native.txt"
wp eval --path="$wp" 'do_action("admin_init");require_once ABSPATH."wp-admin/includes/plugin.php";$data=get_plugin_data(WP_PLUGIN_DIR."/vf-ops/vf-ops.php",false,false);$s=get_option("vf_ops_published_update_fixture",[]);if(($data["Version"]??"")!==getenv("TARGET_VERSION")||!is_plugin_active("vf-ops/vf-ops.php")||($s["sentinel"]??"")!=="retained")exit(6);if(is_wp_error(VF_Ops_Runtime_Authority_V1::verify(getenv("TARGET_VERSION"),WP_PLUGIN_DIR."/vf-ops/")))exit(7);echo "POST_UPGRADE_ACTIVATION_AUTHORITY_DATA=PASS\n";' | tee -a "$out/wordpress-native.txt"
echo "stage=LIVE_NATIVE_DISCOVERY_PASS" >> "$out/stage.txt"
python3 - "$out" <<'PY'
import json,os,pathlib,sys
p=pathlib.Path(sys.argv[1]); log=(p/'wordpress-native.txt').read_text()
stages=['FORMAL_BASELINE_INSTALLED','PUBLISHED_MANUAL_CHECK_UPDATE_AVAILABLE','WORDPRESS_UPDATE_PLUGINS_NATIVE_OFFER','PUBLISHED_ASSET_NATIVE_UPGRADE','POST_UPGRADE_ACTIVATION_AUTHORITY_DATA']
assert all(s+'=PASS' in log for s in stages)
out={'result':'PASS','component_id':'S01-C02','source_version':os.environ['SOURCE_VERSION'],
'target_version':os.environ['TARGET_VERSION'],'channel_main_sha':os.environ['CHANNEL_SHA'],
'formal_asset_sha256':os.environ['EXPECTED_SHA'],'native_manual_check':'PASS',
'wp_update_plugins_offer':'PASS','real_release_asset_upgrade':'PASS','business_preservation':'PASS','post_update_activation_and_authority':'PASS',
'production':'UNCHANGED'}
(p/'FINAL_DISCOVERY.json').write_text(json.dumps(out,indent=2)+'\n')
print("S01_C02_1211094_PUBLISHED_WORDPRESS_NATIVE_DISCOVERY_PASS")
PY
