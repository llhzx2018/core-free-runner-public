#!/usr/bin/env bash
set -Eeuo pipefail
trap 'printf "NATIVE_FAILURE line=%s\n" "$LINENO" >&2' ERR
NET="s01-player95-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60); do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break; sleep 2; done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90); do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break; sleep 2; done
curl -fsSLo /tmp/wp-cli-player95.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/wp-cli-player95.phar "$WP:/usr/local/bin/wp"
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Player Check' --admin_user=admin --admin_password='Synthetic-Only-Player-95!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp provider/vf-tools-m3u8_V1.25.94.zip "$WP:/tmp/old.zip"
docker cp provider/vf-tools-m3u8_V1.25.95.zip "$WP:/tmp/new.zip"
echo STEP_FRESH_INSTALL
cli plugin install /tmp/new.zip --activate
echo STEP_FRESH_VERSION
test "$(cli plugin get vf-tool-m3u8 --field=version)" = '1.25.95'
echo STEP_INTEGRITY_ORIGINAL
cli eval 'require_once WP_PLUGIN_DIR."/vf-tool-m3u8/includes/settings-engine.php"; if (!function_exists("vf_tool_m3u8_hls_js_url")) { WP_CLI::error("ENGINE_FUNCTION_MISSING"); } if (!vf_tool_m3u8_hls_js_url([])) { WP_CLI::error("LOCAL_HLS_UNAVAILABLE"); }'
echo STEP_INTEGRITY_TAMPER
docker exec "$WP" cp /var/www/html/wp-content/plugins/vf-tool-m3u8/public/vendor/hls.js/hls.min.js /tmp/hls-good.js
docker exec "$WP" sh -c 'printf tampered > /var/www/html/wp-content/plugins/vf-tool-m3u8/public/vendor/hls.js/hls.min.js'
cli eval 'require_once WP_PLUGIN_DIR."/vf-tool-m3u8/includes/settings-engine.php"; if (vf_tool_m3u8_hls_js_url([]) !== "") { exit(1); }' >/dev/null
docker exec "$WP" cp /tmp/hls-good.js /var/www/html/wp-content/plugins/vf-tool-m3u8/public/vendor/hls.js/hls.min.js
cli eval 'require_once WP_PLUGIN_DIR."/vf-tool-m3u8/includes/settings-engine.php"; if (!vf_tool_m3u8_hls_js_url([])) { exit(1); }' >/dev/null
echo STEP_INSTALL_PREDECESSOR
cli plugin install /tmp/old.zip --force --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = '1.25.94'
cli option add vf_player95_protected '{"playlist":"synthetic","favorite":true}' --format=json >/dev/null
PID=$(cli post create --post_type=page --post_status=publish --post_title='Player fixture' --post_name=player-test --post_content='[vf_m3u8_player]' --porcelain)
cli post meta add "$PID" _vf_player95_protected 'synthetic-owned-meta' >/dev/null
snapshot(){ cli eval 'foreach (["vf_m3u8_settings","vf_m3u8_settings_revisions","vf_m3u8_settings_audit","vf_tool_m3u8_settings"] as $key) { echo $key."=".hash("sha256",serialize(get_option($key)))."\n"; }' | sha256sum | cut -d' ' -f1; printf '%s\n' "$(cli option get vf_player95_protected --format=json)" "$(cli post get "$PID" --field=post_content)" "$(cli post meta get "$PID" _vf_player95_protected)" | sha256sum | cut -d' ' -f1; }
echo STEP_SNAPSHOT
snapshot > proof/state-before.sha256
cli plugin install /tmp/new.zip --force --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = '1.25.95'
echo STEP_BROWSER
PLAYER_FIXTURE_ID="$PID" node control/lanes/s01-player95-20261028/browser.cjs
echo STEP_INSTALL_PREDECESSOR
cli plugin install /tmp/old.zip --force --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = '1.25.94'
snapshot > proof/state-rollback.sha256;cmp proof/state-before.sha256 proof/state-rollback.sha256
cli plugin install /tmp/new.zip --force --activate >/dev/null
cli plugin install /tmp/new.zip --force --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = '1.25.95'
snapshot > proof/state-after.sha256;cmp proof/state-before.sha256 proof/state-after.sha256
cli eval '$r=VF_M3U8_Runtime_Authority_V1::snapshot(WP_PLUGIN_DIR."/vf-tool-m3u8"); if (is_wp_error($r)) { WP_CLI::error($r->get_error_message()); } unset($r["files"]); echo wp_json_encode($r);' > proof/runtime-authority.json
echo '{"status":"PASS","clean_install":"1.25.95","sequence":["1.25.94","1.25.95","1.25.94","1.25.95","1.25.95"],"tampered_hls":"REJECTED","synthetic_option_content_meta":"BYTE_IDENTICAL","production":"UNTOUCHED"}' > proof/native-lifecycle.json
