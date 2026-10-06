#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-v8-${GITHUB_RUN_ID}"; DB="$NET-db"; WP="$NET-wp"
cleanup(){ docker rm -f "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; [[ -n "${MOCK_PID:-}" ]] && kill "$MOCK_PID" || true; }
trap cleanup EXIT
ASSET="vf-tools-theme_V${TARGET_VERSION}.zip"
export MOCK_PORT=18881 MOCK_ASSET="$PWD/proof/$ASSET" MOCK_STATE="$PWD/mock-state.json" MOCK_LOG="$PWD/mock.log" MOCK_HOST=vf-update.test
echo '{"mode":"normal"}' > "$MOCK_STATE"
python3 - <<'PY'
import pathlib,os
s=pathlib.Path('target/tests/wp-update/mock-github-server.py').read_text()
s=s.replace('1.35.8',os.environ['SOURCE_VERSION']).replace('1.35.9',os.environ['TARGET_VERSION'])
s=s.replace('VF_Tools_Theme_V'+os.environ['TARGET_VERSION']+'_UPDATE.zip','vf-tools-theme_V'+os.environ['TARGET_VERSION']+'.zip')
s=s.replace("if not self.auth_ok(): return", "if not self.auth_ok(): return\n        if p.path=='/repos/llhzx2018/core-updates': self.send_json({'private':True}); return")
pathlib.Path('/tmp/v8-mock.py').write_text(s)
PY
python3 /tmp/v8-mock.py >/tmp/v8-mock-stdout 2>&1 & MOCK_PID=$!
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60); do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break; sleep 2; done
docker run -d --name "$WP" --network "$NET" --add-host vf-update.test:host-gateway -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90); do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break; sleep 2; done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
# Expose the same real Apache origin inside the container for WordPress loopback HTTP.
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf; sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf; apachectl graceful' >/dev/null
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e TARGET_VERSION="$TARGET_VERSION" -e SOURCE_VERSION="$SOURCE_VERSION" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli core install --url=http://127.0.0.1:18880 --title='Synthetic VF Update' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli option update blogdescription 'Synthetic Runner tagline, preserved across native upgrade' >/dev/null
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set VF_WP_UPDATE_GITHUB_API_BASE http://vf-update.test:18881 >/dev/null
docker cp "previous/vf-tools-theme_V${TARGET_VERSION}.zip" "$WP:/var/www/html/previous.zip"
cli theme install /var/www/html/previous.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
cli option update vf_private_update_credential_v1 runner-private-token >/dev/null
cli eval 'set_theme_mod("vf_v8_preservation_sentinel", "keep-me");' >/dev/null
cli eval 'wp_set_current_user(1);vf_theme_bootstrap_require_many(["theme-options-runtime.php","theme-options.php","services/brand-design-service.php","services/navigation-service.php"]);$s=theme_navigation_readback();$n=$s["navigation"];foreach(array_keys(vf_theme_navigation_menu_field_map()) as $i=>$field){$id=wp_create_nav_menu("Synthetic ".$field);if(is_wp_error($id)){throw new Exception("seed menu failed");}wp_update_nav_menu_item($id,0,["menu-item-title"=>"Synthetic link ".$i,"menu-item-url"=>home_url("/"),"menu-item-status"=>"publish"]);$n[$field]=(int)$id;}$r=theme_navigation_save($n,$s["revision"],1,$s["navigation"]);if(empty($r["ok"])){throw new Exception("seed navigation failed: ".wp_json_encode(["code"=>$r["failureCode"]??"unknown","error_fields"=>array_keys($r["errors"]??[]),"failed_checks"=>array_keys(array_filter($r["runtimeVerification"]["checks"]??[],fn($c)=>empty($c["ok"])))]));}update_option("vf_nav_seed_fingerprint",hash("sha256",wp_json_encode(theme_navigation_readback()["navigation"])));' >/dev/null
cli eval 'wp_set_current_user(1);vf_theme_bootstrap_require_many(["services/renderer-config-service.php"]);$d=vf_tools_theme_renderer_defaults();update_option(vf_tools_theme_renderer_option_key(),$d,false);update_option("vf_render_seed_fingerprint",hash("sha256",wp_json_encode($d)));' >/dev/null
cli eval 'wp_set_current_user(1);vf_theme_bootstrap_require_many(require get_template_directory()."/inc/bootstrap/manifests/admin-tabs/seo.php");$s=theme_seo_readback();$result=theme_seo_save($s["seo"],$s["revision"],1);if(empty($result["ok"])){throw new Exception("seed SEO: ".wp_json_encode($result));}update_option("vf_seo_seed_fingerprint",vf_theme_seo_payload_hash(theme_seo_readback()["seo"]));' >/dev/null
node lane/baseline-probe.js
