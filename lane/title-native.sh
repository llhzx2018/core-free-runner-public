#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(pwd)"
TASK_ROOT="$RUNNER_TEMP/s01-title-update"
WP="$TASK_ROOT/wordpress"
mkdir -p "$WP" evidence
export VF_EVIDENCE_DIR="$ROOT/evidence"
curl -fsSL https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar -o "$TASK_ROOT/wp"
chmod +x "$TASK_ROOT/wp"
wp(){ php "$TASK_ROOT/wp" --path="$WP" "$@"; }
wp core download --version=7.0.2 --force >/dev/null
wp config create --dbname=vf_title --dbuser=vf --dbpass=vf-fixture-db --dbhost=127.0.0.1:3306 --skip-check >/dev/null
wp config set WP_HOME http://127.0.0.1:18092 >/dev/null
wp config set WP_SITEURL http://127.0.0.1:18092 >/dev/null
wp core install --url=http://127.0.0.1:18092 --title='Synthetic title regression' --admin_user=admin --admin_password='Synthetic-Title-Fixture-Only!' --admin_email=fixture@example.invalid --skip-email >/dev/null
wp plugin install "$ROOT/baseline.zip" --activate >/dev/null
wp eval 'do_action("admin_init");if(VF_OPS_VERSION!==getenv("BASE_VERSION"))throw new RuntimeException("BASE_VERSION");$r=VF_Ops_Runtime_Authority_V1::verify(VF_OPS_VERSION,WP_PLUGIN_DIR."/vf-ops/");if(is_wp_error($r))throw new RuntimeException($r->get_error_code());update_option("vf_ops_title_fixture",["preserve"=>"yes"],false);$h=vf_tools_ops_v6_secret_put("TITLE_FIXTURE","synthetic-value","title-test");update_option("vf_ops_title_fixture_handle",$h,false);echo "BASELINE_INSTALL_RUNTIME=PASS\n";'
wp eval '$r=vf_ops_wp_update_manual_check_v1();if(($r["status"]??"")!=="UPDATE_AVAILABLE")throw new RuntimeException(wp_json_encode($r));echo "NATIVE_DISCOVERY=PASS\n";'
wp eval '$r=vf_ops_wp_update_execute_v1();if(empty($r["ok"]))throw new RuntimeException(wp_json_encode($r));echo "PLUGIN_UPGRADER=PASS\n";'
wp eval 'require_once ABSPATH."wp-admin/includes/plugin.php";if(VF_OPS_VERSION!==getenv("TARGET_VERSION")||!is_plugin_active("vf-ops/vf-ops.php"))throw new RuntimeException("TARGET_RUNTIME");if(is_wp_error(VF_Ops_Runtime_Authority_V1::verify(VF_OPS_VERSION,WP_PLUGIN_DIR."/vf-ops/")))throw new RuntimeException("TARGET_FINGERPRINT");if(get_option("vf_ops_title_fixture")!==["preserve"=>"yes"])throw new RuntimeException("STATE_CHANGED");$h=get_option("vf_ops_title_fixture_handle");if(vf_tools_ops_v6_secret_resolve($h,"TITLE_FIXTURE")!=="synthetic-value")throw new RuntimeException("SECRET_CHANGED");echo "UPGRADE_POST_READBACK_STATE_SECRET=PASS\n";'
php -S 127.0.0.1:18092 -t "$WP" > "$TASK_ROOT/wp-server.log" 2>&1 &
WP_PID=$!
trap 'kill "$WP_PID" 2>/dev/null || true' EXIT
for i in $(seq 1 30);do if curl -fsS http://127.0.0.1:18092/wp-login.php >/dev/null;then break;fi;sleep 1;done
BROWSER_EXIT=0
node lane/title-native-browser.js || BROWSER_EXIT=$?
wp eval '$r=VF_Ops_Update_Recovery_V1::restore_source();if(is_wp_error($r))throw new RuntimeException($r->get_error_code());echo "SOURCE_ROLLBACK=PASS\n";'
wp eval 'require_once ABSPATH."wp-admin/includes/plugin.php";if(VF_OPS_VERSION!==getenv("BASE_VERSION")||!is_plugin_active("vf-ops/vf-ops.php"))throw new RuntimeException("ROLLBACK_VERSION_ACTIVE");if(is_wp_error(VF_Ops_Runtime_Authority_V1::verify(VF_OPS_VERSION,WP_PLUGIN_DIR."/vf-ops/")))throw new RuntimeException("ROLLBACK_FINGERPRINT");if(get_option("vf_ops_title_fixture")!==["preserve"=>"yes"])throw new RuntimeException("ROLLBACK_STATE");echo "ROLLBACK_POST_READBACK=PASS\n";'
test "$BROWSER_EXIT" = 0
echo EXACT_NATIVE_UPGRADE_ROLLBACK=PASS
