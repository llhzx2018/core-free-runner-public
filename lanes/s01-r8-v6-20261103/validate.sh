#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C candidate rev-parse HEAD)" = "c1a69da4c5c6c40954a3319cc0976065324c77ed"
node candidate/tests/r8-v6-runtime-asset-seal.node.cjs
WP=/tmp/s01-r8-v6-wp
curl -fsSLo /tmp/s01-r8-wpcli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
wp(){ php /tmp/s01-r8-wpcli.phar "$@" --path="$WP"; }
mkdir -p "$WP/wp-content/plugins/vf-tool-m3u8"
wp core download --skip-content --quiet
wp config create --dbname=wordpress --dbuser=wordpress --dbpass=synthetic-wp --dbhost=127.0.0.1:3306 --skip-check
wp core install --url=http://127.0.0.1:18881 --title="S01 V6 sealed fixture" --admin_user=synthetic --admin_password=only-synthetic --admin_email=synthetic@example.invalid --skip-email
cp -a candidate/src/. "$WP/wp-content/plugins/vf-tool-m3u8/"
wp eval '
  define("VF_TOOL_M3U8_DIR", WP_PLUGIN_DIR."/vf-tool-m3u8/");
  require_once VF_TOOL_M3U8_DIR."includes/v6-provider-schema.php";
  if(!vf_tools_m3u8_v6_schema_install())throw new RuntimeException("V6_SCHEMA_INSTALL_FAILED");
  global $wpdb;
  $t=vf_tools_m3u8_v6_table_names();
  $old=json_decode(file_get_contents(VF_TOOL_M3U8_DIR."config/v6/history/1.25.0/runtime-bundle.json"),true);
  if(($old["version"]??"")!=="1.25.0"||($old["lifecycle"]??"")!=="SEALED")throw new RuntimeException("LEGACY_SNAPSHOT_INVALID");
  $now=gmdate("Y-m-d H:i:s");
  $row=["uid"=>"00000000-0000-4000-8000-000000000125","provider_key"=>"vf.m3u8","bundle_key"=>"vf.m3u8.browser-runtime","version"=>"1.25.0","lifecycle_state"=>"SEALED","definition"=>wp_json_encode($old),"content_hash"=>$old["content_hash"],"created_at"=>$now,"updated_at"=>$now,"sealed_at"=>$now];
  if($wpdb->insert($t["runtime_bundles"],$row)===false)throw new RuntimeException("LEGACY_INSERT_FAILED:".$wpdb->last_error);
  $id=(int)$wpdb->insert_id;
  foreach($old["assets"] as $i=>$a){
    $item=["runtime_bundle_id"=>$id,"asset_order"=>$i,"path"=>$a["path"],"sha256"=>$a["sha256"],"bytes"=>$a["bytes"],"load_phase"=>$a["load_phase"],"self_hosted"=>1,"definition"=>wp_json_encode($a)];
    if($wpdb->insert($t["runtime_bundle_assets"],$item)===false)throw new RuntimeException("LEGACY_ASSET_FAILED:".$wpdb->last_error);
  }
  $stored=["old"=>$wpdb->get_row($wpdb->prepare("SELECT * FROM {$t["runtime_bundles"]} WHERE id=%d",$id),ARRAY_A),"assets"=>$wpdb->get_results($wpdb->prepare("SELECT * FROM {$t["runtime_bundle_assets"]} WHERE runtime_bundle_id=%d ORDER BY asset_order",$id),ARRAY_A)];
  file_put_contents("/tmp/s01-r8-v6-old.json",wp_json_encode($stored));
  update_option("vf_s01_r8_owner_canary",["stay"=>"exact","source"=>"user"],false);
  echo "S01_R8_V6_LEGACY_SEALED_FIXTURE=PASS 1 row / ".count($stored["assets"])." assets\n";
'
wp plugin activate vf-tool-m3u8
wp eval '
  global $wpdb;
  $t=vf_tools_m3u8_v6_table_names();
  $old=json_decode(file_get_contents("/tmp/s01-r8-v6-old.json"),true);
  $id=(int)$old["old"]["id"];
  $now=["old"=>$wpdb->get_row($wpdb->prepare("SELECT * FROM {$t["runtime_bundles"]} WHERE id=%d",$id),ARRAY_A),"assets"=>$wpdb->get_results($wpdb->prepare("SELECT * FROM {$t["runtime_bundle_assets"]} WHERE runtime_bundle_id=%d ORDER BY asset_order",$id),ARRAY_A)];
  if($old!==$now)throw new RuntimeException("LEGACY_SEALED_MUTATED");
  if(get_option("vf_s01_r8_owner_canary")!==["stay"=>"exact","source"=>"user"])throw new RuntimeException("OWNER_CANARY_MUTATED");
  $bundle=vf_tools_m3u8_runtime_bundle();
  $manifest=vf_tools_m3u8_provider_manifest();
  if($bundle["version"]!=="1.25.1"||$manifest["version"]!=="1.25.1")throw new RuntimeException("NEW_IDENTITY_NOT_LOADED");
  if(!hash_equals($bundle["content_hash"],vf_tools_m3u8_contract_hash($bundle)))throw new RuntimeException("RUNTIME_HASH_INVALID");
  if(!hash_equals($manifest["content_hash"],vf_tools_m3u8_contract_hash($manifest)))throw new RuntimeException("PROVIDER_HASH_INVALID");
  $check=vf_tools_m3u8_validate_runtime_bundle_contract($bundle,true);
  if(empty($check["ok"]))throw new RuntimeException("RUNTIME_ASSET_SEAL_INVALID:".implode(",",$check["errors"]??[]));
  $bad=$bundle;$bad["assets"][0]["sha256"]=str_repeat("0",64);
  if(!empty(vf_tools_m3u8_validate_runtime_bundle_contract($bad,true)["ok"]))throw new RuntimeException("MISMATCH_NOT_REJECTED");
  $svc=vf_tools_m3u8_v6_runtime_service();
  $seed=$svc->seedBundled();
  if(empty($seed["ok"]))throw new RuntimeException("NEW_RUNTIME_SEED_FAILED:".implode(",",$seed["errors"]??[]));
  $new=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$t["runtime_bundles"]} WHERE provider_key=%s AND version=%s","vf.m3u8","1.25.1"),ARRAY_A);
  if(!$new||$new["content_hash"]!==$bundle["content_hash"]||$new["lifecycle_state"]!=="SEALED")throw new RuntimeException("NEW_SEALED_ROW_NOT_FOUND");
  $count=(int)$wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$t["runtime_bundle_assets"]} WHERE runtime_bundle_id=%d",$new["id"]));
  if($count!==14)throw new RuntimeException("NEW_SEALED_ASSETS_WRONG:".$count);
  $after=["old"=>$wpdb->get_row($wpdb->prepare("SELECT * FROM {$t["runtime_bundles"]} WHERE id=%d",$id),ARRAY_A),"assets"=>$wpdb->get_results($wpdb->prepare("SELECT * FROM {$t["runtime_bundle_assets"]} WHERE runtime_bundle_id=%d ORDER BY asset_order",$id),ARRAY_A)];
  if($after!==$old)throw new RuntimeException("LEGACY_SEALED_MUTATED_AFTER_SEED");
  echo "S01_R8_V6_PHP_NATIVE_SEAL=PASS\n";
  echo "S01_R8_V6_NEGATIVE_ASSET_HASH=PASS\n";
  echo "S01_R8_V6_NEW_SEALED_DB=PASS 1.25.1 14/14\n";
  echo "S01_R8_V6_OLD_SEALED_DB_IMMUTABLE=PASS 1.25.0 14/14\n";
  echo "S01_R8_V6_OWNER_CANARY=PASS\n";
'
