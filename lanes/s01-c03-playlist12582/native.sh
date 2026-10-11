#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p proof pkg/vf-tool-m3u8
cp -a candidate/src/. pkg/vf-tool-m3u8/
(cd pkg && zip -qr /tmp/vf-m3u8-12582.zip vf-tool-m3u8)
GH_TOKEN="$VF_PRIVATE_READ_TOKEN" gh release download v1.35.108 --repo llhzx2018/vf-tools-theme --pattern vf-tools-theme_V1.35.108.zip --output /tmp/theme108.zip
NET="s01-playlist-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1&&break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php&&curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null&&break;sleep 2;done
curl -fsSLo /tmp/s01-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/s01-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='S01 Playlist 12582 Isolated' --admin_user=admin --admin_password='Synthetic-Only-Playlist-81!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp /tmp/theme108.zip "$WP:/tmp/theme108.zip"
docker cp /tmp/vf-m3u8-12582.zip "$WP:/tmp/candidate.zip"
cli theme install /tmp/theme108.zip --activate >/dev/null
cli plugin install /tmp/candidate.zip --activate >/dev/null
cli rewrite structure '/%postname%/' --hard >/dev/null
cli eval 'if(!get_page_by_path("m3u8-playlist-checker")){wp_insert_post(["post_type"=>"page","post_status"=>"publish","post_name"=>"m3u8-playlist-checker","post_title"=>"Playlist Checker","post_content"=>"[vf_m3u8_playlist_checker]"]);}else{$p=get_page_by_path("m3u8-playlist-checker");wp_update_post(["ID"=>$p->ID,"post_content"=>"[vf_m3u8_playlist_checker]","post_status"=>"publish"]);}if(!shortcode_exists("vf_m3u8_playlist_checker"))throw new Exception("shortcode missing");echo wp_json_encode(["theme"=>wp_get_theme()->get("Version"),"provider"=>VF_TOOL_M3U8_VERSION,"page"=>get_page_by_path("m3u8-playlist-checker")->ID]);' > proof/wp-install.json
test "$(cli theme get vf-tools-theme --field=version)" = "1.35.108"
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "1.25.82"
curl -fsS http://127.0.0.1:18880/m3u8-playlist-checker/ > /tmp/playlist.html
grep -Fq 'data-vf-module="playlist-checker"' /tmp/playlist.html
node lane/browser.cjs
python3 - <<'PY'
import json,pathlib
proof=json.loads(pathlib.Path('proof/playlist-browser.json').read_text())
assert proof['status']=='PASS' and len(proof['checks'])>=20 and all(x['pass'] for x in proof['checks'])
pathlib.Path('proof/wp-final.json').write_text(json.dumps({'status':'PASS','wordpress':'7.1.2','mariadb':'11.8.8','theme':'1.35.108','m3u8':'1.25.82','browser_check_count':len(proof['checks']),'production':'NOT_EXECUTED'},indent=2))
print('S01_PLAYLIST_12582_WORDPRESS_PASS',len(proof['checks']))
PY
