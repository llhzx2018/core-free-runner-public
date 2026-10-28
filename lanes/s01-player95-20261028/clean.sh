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
for attempt in 1 2 3; do cli plugin install polylang --version=3.8.10 --activate >/dev/null && break; test "$attempt" -lt 3 || exit 1; sleep 3; done
docker cp control/lanes/s01-player95-20261028/languages.php "$WP:/tmp/languages.php"
cli eval-file /tmp/languages.php >/dev/null
docker cp provider/vf-tools-m3u8_V1.25.95.zip "$WP:/tmp/new.zip"
cli plugin install /tmp/new.zip --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = '1.25.95'
cli eval '$r=get_option("vf_m3u8_first_run_last_result",[]); $s=get_option("vf_m3u8_first_run_state",[]); echo wp_json_encode(["status"=>$r["status"]??"UNKNOWN","code"=>$r["code"]??"UNKNOWN","issues"=>array_map(fn($i)=>$i["code"]??"unknown",$r["issues"]??[]),"version"=>$s["version"]??""]);' > proof/clean-activation.json
node control/lanes/s01-player95-20261028/clean.cjs
cli eval '$r=get_option("vf_m3u8_first_run_last_result",[]); if (($r["status"]??"")!=="PASS") { WP_CLI::error("FIRST_RUN_NOT_READY: ".($r["code"]??"unknown")); }' >/dev/null
echo '{"status":"PASS","admin_login":"PASS","admin_revisit":"PASS","activation_readiness":"PASS","production":"UNTOUCHED"}' > proof/clean-admin.json
