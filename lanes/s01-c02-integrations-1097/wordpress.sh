#!/usr/bin/env bash
set -Eeuo pipefail
: "${PRODUCT_DIR:?}"
wpPath="$(mktemp -d /tmp/s01-c02-integration-wp-XXXXXX)"
trap 'rm -rf "$wpPath"' EXIT
curl -fsSLo /tmp/wp-cli-integration.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
wp(){ php /tmp/wp-cli-integration.phar --allow-root --path="$wpPath" "$@"; }
wp core download --version=7.0.2 --force >/dev/null
wp config create --dbname=integrations_db --dbuser=vf --dbpass=vf --dbhost=127.0.0.1 --skip-check >/dev/null
wp config set FS_METHOD direct --type=constant >/dev/null
wp core install --url=http://127.0.0.1:18097 --title='Integrations Isolated' --admin_user=admin --admin_password='fixture-only-admin' --admin_email=synthetic@example.invalid --skip-email >/dev/null
python3 "$PRODUCT_DIR/.github/release/build-ops-package.py" --source "$PRODUCT_DIR" --output /tmp/vf-ops-integrations-candidate.zip > /tmp/integrations-package.json
wp plugin install /tmp/vf-ops-integrations-candidate.zip --activate >/dev/null
wp eval '
wp_set_current_user(1);
if(!function_exists("vf_ops_save_integrations"))throw new RuntimeException("Missing native integration service");
$before=ops_integrations_readback();$rev=(int)$before["revision"];$hash=(string)($before["configHash"]??"");
$base=["gscProperty"=>"sc-domain:example.com","gscAuthMode"=>"oauth","gscCredentialSecret"=>["clientId"=>"fixture-123.apps.googleusercontent.com","clientSecret"=>"synthetic-not-real"],"indexNowKey"=>"syntheticIndexNow123456789","analyticsMeasurementId"=>"","gscSyncSchedule"=>"daily","analyticsEnabled"=>false,"consentMode"=>"region_aware"];
$save=vf_ops_save_integrations($base,$rev,$hash);
if(($save["code"]??"")!=="INTEGRATIONS_SAVED")throw new RuntimeException("Initial save failed: ".($save["code"]??""));
$first=ops_integrations_readback();
if(!vf_ops_integrations_config_integrity_v121486($first)||$first["revision"]!==$rev+1)throw new RuntimeException("Initial hash/revision invalid");
if(!str_contains($first["gscCredentialSecret"],"") || $first["gscCredentialSecret"]==="synthetic-not-real")throw new RuntimeException("Credential not encrypted");
if($first["indexNowKey"]==="syntheticIndexNow123456789")throw new RuntimeException("IndexNow plaintext persisted");
$masked=ops_integrations_readback_masked();
if(isset($masked["gscCredentialSecret"])||isset($masked["indexNowKey"])||strpos(json_encode($masked),"synthetic-not-real")!==false)throw new RuntimeException("Secret escaped masked response");
echo "INTEGRATIONS_NATIVE_ENCRYPTED_SAVE_REDACTION_PASS\\n";
$next=$base;$next["gscProperty"]="sc-domain:second.example.com";$next["gscCredentialSecret"]=[];$next["indexNowKey"]="";
$changed=vf_ops_save_integrations($next,$first["revision"],$first["configHash"]);
if(($changed["code"]??"")!=="INTEGRATIONS_SAVED")throw new RuntimeException("Existing GSC edit failed: ".($changed["code"]??""));
$second=ops_integrations_readback();
if($second["gscCredentialSecret"]!==$first["gscCredentialSecret"]||$second["indexNowKey"]!==$first["indexNowKey"]||$second["gscProperty"]!=="sc-domain:second.example.com")throw new RuntimeException("Changed property dropped encrypted credentials");
echo "INTEGRATIONS_EXISTING_CONNECTED_EDIT_PRESERVE_PASS\\n";
$bad=$next;$bad["analyticsEnabled"]=true;$bad["analyticsMeasurementId"]="not-GA4";
$invalid=vf_ops_save_integrations($bad,$second["revision"],$second["configHash"]);
if(($invalid["code"]??"")!=="VALIDATION_FAILED")throw new RuntimeException("Invalid GA4 accepted");
$stale=vf_ops_save_integrations($next,$first["revision"],$first["configHash"]);
if(($stale["code"]??"")!=="REVISION_CONFLICT")throw new RuntimeException("Stale revision accepted");
$hashConflict=vf_ops_save_integrations($next,$second["revision"],str_repeat("a",64));
if(($hashConflict["code"]??"")!=="CONFIG_HASH_CONFLICT")throw new RuntimeException("Wrong config hash accepted");
if(ops_integrations_readback()["configHash"]!==$second["configHash"])throw new RuntimeException("Failed writes mutated config");
echo "INTEGRATIONS_NATIVE_INVALID_GA4_REVISION_HASH_FAIL_CLOSED_PASS\\n";
$valid=$next;$valid["analyticsEnabled"]=true;$valid["analyticsMeasurementId"]="G-ABCD1234";$valid["consentMode"]="explicit_required";
$after=vf_ops_save_integrations($valid,$second["revision"],$second["configHash"]);
if(($after["code"]??"")!=="INTEGRATIONS_SAVED"||empty(ops_integrations_readback()["analyticsEnabled"]))throw new RuntimeException("Valid GA4 save failed");
echo "INTEGRATIONS_NATIVE_GA4_AND_CONSENT_SAVE_PASS\\n";
' | tee /tmp/integrations-native-receipt.txt
