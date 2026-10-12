#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p proof
wpPath="$(mktemp -d /tmp/s01-c02-governance-wp-XXXXXX)"
cleanup(){ rm -rf "$wpPath" /tmp/vf-ops-audit-wp-cli.phar /tmp/vf-ops-audit-official.zip; }
trap cleanup EXIT
curl -fsSLo /tmp/vf-ops-audit-wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
wp(){ php /tmp/vf-ops-audit-wp-cli.phar --allow-root --path="$wpPath" "$@"; }
wp core download --version=7.0.2 --force >/dev/null
wp config create --dbname=ops_test --dbuser=ops --dbpass=ops --dbhost=127.0.0.1:3306 --skip-check >/dev/null
wp config set FS_METHOD direct --type=constant >/dev/null
wp core install --url=http://127.0.0.1:18097 --title='Ops Governance Isolated' --admin_user=admin --admin_password='synthetic-only-2026' --admin_email=test@example.invalid --skip-email >/dev/null
GH_TOKEN="$VF_PRIVATE_READ_TOKEN" gh release download v1.21.1096 --repo llhzx2018/vf-tools-ops --pattern vf-tools-ops_V1.21.1096.zip --output /tmp/vf-ops-audit-official.zip
digest="$(GH_TOKEN="$VF_PRIVATE_READ_TOKEN" gh api repos/llhzx2018/vf-tools-ops/releases/tags/v1.21.1096 --jq '.assets[] | select(.name=="vf-tools-ops_V1.21.1096.zip") | .digest')"
test "sha256:$(sha256sum /tmp/vf-ops-audit-official.zip | awk '{print $1}')" = "$digest"
wp plugin install /tmp/vf-ops-audit-official.zip --activate >/dev/null
wp eval 'if(VF_OPS_VERSION!=="1.21.1096")throw new RuntimeException("Wrong version"); do_action("admin_init");echo "OPS_GOVERNANCE_ISOLATED_VERSION_PASS\\n";' | tee proof/identity.txt
wp eval '
$c=ops_plugins_readback();$oldRev=(int)$c["revision"];$oldHash=(string)$c["configHash"];
$raw=["allowedCombination"=>$c["allowedCombination"],"updatePolicy"=>$c["updatePolicy"],"auditRetentionDays"=>(int)$c["auditRetentionDays"]];
$noChange=vf_ops_save_plugin_policy($raw,$oldRev,$oldHash);
if(($noChange["code"]??"")!=="NO_CHANGES")throw new RuntimeException("No-op must not advance revision: ".($noChange["code"]??""));
$bad=$raw;$bad["auditRetentionDays"]=1;
$invalid=vf_ops_save_plugin_policy($bad,$oldRev,$oldHash);
if(($invalid["code"]??"")!=="VALIDATION_FAILED")throw new RuntimeException("Bad form policy accepted: ".($invalid["code"]??""));
$raw["auditRetentionDays"]=((int)$raw["auditRetentionDays"]===180?181:180);
$saved=vf_ops_save_plugin_policy($raw,$oldRev,$oldHash);
if(($saved["code"]??"")!=="POLICY_SAVED")throw new RuntimeException("Real policy commit not persisted: ".($saved["code"]??""));
$new=ops_plugins_readback();
if((int)$new["revision"]!==$oldRev+1 || $new["configHash"]===$oldHash)throw new RuntimeException("Policy readback identity did not change");
$stale=vf_ops_save_plugin_policy($raw,$oldRev,$oldHash);
if(($stale["code"]??"")!=="REVISION_CONFLICT")throw new RuntimeException("Stale policy commit not rejected");
if(!vf_ops_plugins_config_integrity_v121488($new))throw new RuntimeException("Saved revision integrity failed");
echo "OPS_GOVERNANCE_POLICY_NOOP_VALIDATION_COMMIT_AND_STALE_REFUSAL_PASS\\n";
' | tee proof/policy.txt
wp eval '
if(!function_exists("vf_ops_refresh_plugin_inventory")||!function_exists("vf_ops_run_plugin_dependency_audit"))throw new RuntimeException("Native governance entry absent");
$c=ops_plugins_readback();$rev=(int)($c["revision"]??0);$hash=(string)($c["configHash"]??"");
if($rev<1||strlen($hash)!==64)throw new RuntimeException("Governance revision/hash invalid");
$denied=vf_ops_run_plugin_dependency_audit($rev+1,$hash);
if(($denied["code"]??"")!=="REVISION_CONFLICT")throw new RuntimeException("Expected stale revision refusal");
$in=vf_ops_refresh_plugin_inventory($rev,$hash);
if(empty($in["ok"])||($in["code"]??"")!=="INVENTORY_REFRESHED")throw new RuntimeException("Inventory not written: ".($in["code"]??""));
$e=(array)($in["evidence"]??[]);
if(empty($e["inventoryHash"])||empty($e["rows"]))throw new RuntimeException("No verifiable inventory");
echo "OPS_GOVERNANCE_INVENTORY_WRITE_PASS\\n";
' | tee proof/inventory.txt
# Source traversal runs in the isolated WP installation only. Force a
# real 3000+ file resumable scan; Production and the product repo are untouched.
mkdir -p "$wpPath/wp-content/themes/vf-audit-synthetic"
for file in $(seq -w 1 3400); do
  printf '<?php /* isolated scanner coverage fixture %s */\\n' "$file" > "$wpPath/wp-content/themes/vf-audit-synthetic/fixture-$file.php"
done
echo 'OPS_GOVERNANCE_LARGE_SOURCE_FIXTURE=3400' | tee proof/scan-fixture.txt
for step in $(seq 1 35); do
  out="$(wp eval '
$c=ops_plugins_readback();
$r=vf_ops_run_plugin_dependency_audit((int)$c["revision"],(string)$c["configHash"]);
echo "AUDIT_STEP_RESULT=".wp_json_encode(["ok"=>$r["ok"]??false,"status"=>$r["status"]??"UNKNOWN","code"=>$r["code"]??"UNKNOWN","filesScanned"=>$r["filesScanned"]??0,"cursor"=>$r["cursor"]??0,"totalFiles"=>$r["totalFiles"]??0,"deletionAuthorized"=>$r["deletionAuthorized"]??false],JSON_UNESCAPED_SLASHES)."\\n";
')" 
  printf '%s\n' "$out" | tee -a proof/audit-steps.txt
  case "$out" in
    *'"code":"DEPENDENCY_AUDIT_COMPLETE"'*) break;;
    *'"code":"DEPENDENCY_SCAN_IN_PROGRESS"'*) continue;;
    *) echo 'OPS_GOVERNANCE_AUDIT_BROKEN' >&2;exit 6;;
  esac
  if test "$step" = 35; then echo 'OPS_GOVERNANCE_SCAN_STEP_LIMIT' >&2;exit 7;fi
done
wp eval '
$c=ops_plugins_readback();
$a=vf_ops_plugins_dependency_audit_state_v121464();
if(!vf_ops_plugins_dependency_verify_v121488($a,$c))throw new RuntimeException("Evidence readback invalid");
if(empty($a["sourceScanComplete"])||($a["sourceTotalFiles"]??0)<3400||($a["filesScanned"]??-1)!==$a["sourceTotalFiles"])throw new RuntimeException("No complete source coverage");
$auth=vf_ops_plugins_deletion_authorization_state_v121465();
if(!empty($auth["authorized"]))throw new RuntimeException("Never grant deletion during read-only audit");
$r=vf_ops_run_plugin_dependency_audit((int)$c["revision"]+1,(string)$c["configHash"]);
if(($r["code"]??"")!=="REVISION_CONFLICT")throw new RuntimeException("Dependency revision gate bypass");
$p=vf_ops_plugins_page_model_v121464();
if(!is_array($p["audit"]??null)||empty($p["dependencyAudit"]["auditHash"]))throw new RuntimeException("Evidence page missing saved log or hash");
echo "OPS_GOVERNANCE_FULL_AUDIT_EVIDENCE_AND_NO_DELETION_PASS ".(int)$a["filesScanned"]."\\n";
' | tee proof/final.txt
