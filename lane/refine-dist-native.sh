#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(pwd)"
TASK_ROOT="$RUNNER_TEMP/s01-keyword-1036-distribution"
WP="$TASK_ROOT/wordpress"
mkdir -p "$WP" evidence

curl -fsSL https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar -o "$TASK_ROOT/wp"
chmod +x "$TASK_ROOT/wp"
wp(){ php "$TASK_ROOT/wp" --path="$WP" "$@"; }

wp core download --version=7.0.2 --force >/dev/null
wp config create --dbname=vf_refine --dbuser=vf --dbpass=vf-fixture-db --dbhost=127.0.0.1:3306 --skip-check >/dev/null
wp core install --url=http://127.0.0.1:18096 --title='Keyword Distribution Fixture' --admin_user=admin --admin_password='Fixture-Keyword-Distribution-Only!' --admin_email=fixture@example.invalid --skip-email >/dev/null

wp plugin install "$ROOT/baseline.zip" --activate >/dev/null
wp eval 'do_action("admin_init");if(VF_OPS_VERSION!==getenv("BASE_VERSION"))throw new RuntimeException("BASE_VERSION");$r=VF_Ops_Runtime_Authority_V1::verify(VF_OPS_VERSION,WP_PLUGIN_DIR."/vf-ops/");if(is_wp_error($r))throw new RuntimeException($r->get_error_code());update_option("vf_ops_keyword_distribution_fixture",["preserve"=>"yes"],false);echo "BASELINE_INSTALL_RUNTIME=PASS\n";'

wp eval '$r=vf_ops_wp_update_manual_check_v1();if(($r["status"]??"")!=="UPDATE_AVAILABLE")throw new RuntimeException(wp_json_encode($r));if(($r["manifest"]["target_version"]??"")!==getenv("TARGET_VERSION"))throw new RuntimeException("DISCOVERY_TARGET_MISMATCH");echo "NATIVE_DISCOVERY=PASS\n";'
wp eval '$r=vf_ops_wp_update_execute_v1();if(empty($r["ok"]))throw new RuntimeException(wp_json_encode($r));echo "PLUGIN_UPGRADER=PASS\n";'
wp eval 'require_once ABSPATH."wp-admin/includes/plugin.php";if(VF_OPS_VERSION!==getenv("TARGET_VERSION")||!is_plugin_active("vf-ops/vf-ops.php"))throw new RuntimeException("TARGET_RUNTIME");if(is_wp_error(VF_Ops_Runtime_Authority_V1::verify(VF_OPS_VERSION,WP_PLUGIN_DIR."/vf-ops/")))throw new RuntimeException("TARGET_FINGERPRINT");if(get_option("vf_ops_keyword_distribution_fixture")!==["preserve"=>"yes"])throw new RuntimeException("STATE_CHANGED");echo "UPGRADE_POST_READBACK_STATE=PASS\n";'

wp eval '$r=VF_Ops_Update_Recovery_V1::restore_source();if(is_wp_error($r))throw new RuntimeException($r->get_error_code());echo "SOURCE_ROLLBACK=PASS\n";'
wp eval 'require_once ABSPATH."wp-admin/includes/plugin.php";if(VF_OPS_VERSION!==getenv("BASE_VERSION")||!is_plugin_active("vf-ops/vf-ops.php"))throw new RuntimeException("ROLLBACK_VERSION_ACTIVE");if(is_wp_error(VF_Ops_Runtime_Authority_V1::verify(VF_OPS_VERSION,WP_PLUGIN_DIR."/vf-ops/")))throw new RuntimeException("ROLLBACK_FINGERPRINT");if(get_option("vf_ops_keyword_distribution_fixture")!==["preserve"=>"yes"])throw new RuntimeException("ROLLBACK_STATE");echo "ROLLBACK_POST_READBACK=PASS\n";'
echo EXACT_PUBLISHED_NATIVE_UPGRADE_ROLLBACK=PASS
