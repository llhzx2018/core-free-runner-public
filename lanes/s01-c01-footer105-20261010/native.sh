#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-v8-${GITHUB_RUN_ID}";DB="$NET-db";export WP="$NET-wp"
TASK_ROOT="$PWD"
cleanup(){ docker rm -fv "$WP" "$DB" "$NET-clean" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;apachectl graceful' >/dev/null
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e SOURCE_VERSION="$SOURCE_VERSION" -e TARGET_VERSION="$TARGET_VERSION" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Theme Integration' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp "provider/vf-tools-theme_V${SOURCE_VERSION}.zip" "$WP:/tmp/theme.zip"
cli theme install /tmp/theme.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"

cli config set DISABLE_WP_CRON true --raw >/dev/null
docker cp "provider/vf-tools-m3u8_V${PROVIDER_VERSION}.zip" "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$PROVIDER_VERSION"
docker cp lane/seed.php "$WP:/tmp/integration-seed.php"
cli eval-file /tmp/integration-seed.php > proof/seed.json
docker cp lane/provider.php "$WP:/tmp/provider.php"
cli eval-file /tmp/provider.php > proof/provider-baseline.json
node lane/browser.js baseline
cli eval 'foreach(["vf_theme_seo","vf_theme_layout","vf_theme_brand","vf_theme_navigation","vf_tool_m3u8_tool_product_config"] as $k)$s[$k]=get_option($k);set_theme_mod("round5_preservation","synthetic-keep");update_option("round5_preservation",hash("sha256",serialize($s)));' >/dev/null
docker cp "proof/vf-tools-theme_V${TARGET_VERSION}.zip" "$WP:/tmp/candidate.zip"
cli theme install /tmp/candidate.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
cli eval-file /tmp/provider.php > proof/provider-actual.json
cli eval 'foreach(["vf_theme_seo","vf_theme_layout","vf_theme_brand","vf_theme_navigation","vf_tool_m3u8_tool_product_config"] as $k)$s[$k]=get_option($k);if(hash("sha256",serialize($s))!==get_option("round5_preservation")||get_theme_mod("round5_preservation")!=="synthetic-keep")throw new Exception("upgrade lost canonical state");' >/dev/null

cli theme install /tmp/theme.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
cli eval-file /tmp/provider.php > proof/provider-rollback.json
node lane/browser.js rollback

cli eval 'foreach(["vf_theme_seo","vf_theme_layout","vf_theme_brand","vf_theme_navigation","vf_tool_m3u8_tool_product_config"] as $k)$s[$k]=get_option($k);if(hash("sha256",serialize($s))!==get_option("round5_preservation")||get_theme_mod("round5_preservation")!=="synthetic-keep")throw new Exception("rollback lost canonical state");' >/dev/null
cli theme install /tmp/candidate.zip --force >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"

cli eval 'foreach(["vf_theme_seo","vf_theme_layout","vf_theme_brand","vf_theme_navigation","vf_tool_m3u8_tool_product_config"] as $k)$s[$k]=get_option($k);if(hash("sha256",serialize($s))!==get_option("round5_preservation")||get_theme_mod("round5_preservation")!=="synthetic-keep")throw new Exception("reapply lost canonical state");' >/dev/null
cli theme install /tmp/candidate.zip --force >/dev/null
cli eval 'foreach(["vf_theme_seo","vf_theme_layout","vf_theme_brand","vf_theme_navigation","vf_tool_m3u8_tool_product_config"] as $k)$s[$k]=get_option($k);if(hash("sha256",serialize($s))!==get_option("round5_preservation")||get_theme_mod("round5_preservation")!=="synthetic-keep")throw new Exception("reapply lost canonical state");' >/dev/null
cli eval 'echo wp_json_encode(VF_Theme_Runtime_Authority_V1::snapshot(get_template_directory()));' > proof/installed-runtime.json
cli eval 'echo wp_json_encode(["status"=>"PASS","from"=>getenv("SOURCE_VERSION"),"to"=>getenv("TARGET_VERSION"),"upgrade"=>"PASS","rollback"=>"PASS","reapply"=>"PASS","canonical_data_preservation"=>"PASS","repeat_install"=>"PASS"]);' > proof/upgrade-rollback.json
node lane/browser.js
cli eval 'update_option("footer105_nav_before_variants",get_option("vf_theme_navigation"));$n=get_option("vf_theme_navigation");$n["footerColumns"]=4;update_option("vf_theme_navigation",$n);' >/dev/null
node lane/browser.js variant-four
cli eval '$n=get_option("vf_theme_navigation");$n["footerColumns"]=1;$n["shell"]["footer"]["variant"]="simple";update_option("vf_theme_navigation",$n);' >/dev/null
node lane/browser.js variant-simple
cli eval '$n=get_option("vf_theme_navigation");$n["footerColumns"]=3;$n["shell"]["footer"]["variant"]="columns";$n["shell"]["footer"]["mobileMode"]="accordion";update_option("vf_theme_navigation",$n);' >/dev/null
node lane/browser.js variant-accordion
cli eval 'update_option("vf_theme_navigation",get_option("footer105_nav_before_variants"));foreach(["vf_theme_seo","vf_theme_layout","vf_theme_brand","vf_theme_navigation","vf_tool_m3u8_tool_product_config"] as $k)$s[$k]=get_option($k);if(hash("sha256",serialize($s))!==get_option("round5_preservation"))throw new Exception("variant restore lost canonical state");' >/dev/null
cli eval-file /tmp/provider.php > proof/provider-reapply.json
cli eval 'echo wp_json_encode(["status"=>"PASS","wordpress"=>get_bloginfo("version"),"theme"=>wp_get_theme()->get("Version"),"provider"=>VF_TOOL_M3U8_VERSION]);' > proof/installed-versions.json
docker run -d --name "$NET-clean" --network "$NET" -p 18881:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb -e WORDPRESS_TABLE_PREFIX=clean_ wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$NET-clean" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18881/wp-admin/install.php >/dev/null && break;sleep 2;done
docker cp /tmp/wp-cli.phar "$NET-clean:/usr/local/bin/wp"
docker cp "proof/vf-tools-theme_V${TARGET_VERSION}.zip" "$NET-clean:/tmp/candidate.zip"
docker exec --user www-data "$NET-clean" php /usr/local/bin/wp core install --url=http://127.0.0.1:18881 --title='Synthetic Clean FULL' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email --path=/var/www/html >/dev/null
docker exec --user www-data "$NET-clean" php /usr/local/bin/wp theme install /tmp/candidate.zip --activate --path=/var/www/html >/dev/null
test "$(docker exec --user www-data "$NET-clean" php /usr/local/bin/wp theme get vf-tools-theme --field=version --path=/var/www/html)" = "$TARGET_VERSION"
curl -fsS http://127.0.0.1:18881/ >/tmp/clean-first.html
grep -q "vf-theme-version.*$TARGET_VERSION" /tmp/clean-first.html
node lane/clean-browser.js
python3 lane/final.py
