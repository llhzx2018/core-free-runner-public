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
if(empty($a["sourceScanComplete"])||empty($a["sourceTotalFiles"])||($a["filesScanned"]??-1)!==$a["sourceTotalFiles"])throw new RuntimeException("No complete source coverage");
$auth=vf_ops_plugins_deletion_authorization_state_v121465();
if(!empty($auth["authorized"]))throw new RuntimeException("Never grant deletion during read-only audit");
$r=vf_ops_run_plugin_dependency_audit((int)$c["revision"]+1,(string)$c["configHash"]);
if(($r["code"]??"")!=="REVISION_CONFLICT")throw new RuntimeException("Dependency revision gate bypass");
$p=vf_ops_plugins_page_model_v121464();
if(!is_array($p["audit"]??null)||empty($p["dependencyAudit"]["auditHash"]))throw new RuntimeException("Evidence page missing saved log or hash");
echo "OPS_GOVERNANCE_FULL_AUDIT_EVIDENCE_AND_NO_DELETION_PASS ".(int)$a["filesScanned"]."\\n";
' | tee proof/final.txt
