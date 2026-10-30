#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01-design-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break;sleep 2;done
curl -fsSLo /tmp/wp-cli-review.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/wp-cli-review.phar "$WP:/usr/local/bin/wp"
docker exec "$WP" sh -c 'echo "Listen 18880" >> /etc/apache2/ports.conf;sed -i "s/<VirtualHost \*:80>/<VirtualHost *:80 *:18880>/" /etc/apache2/sites-enabled/000-default.conf;echo "opcache.enable=0" > /usr/local/etc/php/conf.d/review.ini;apachectl graceful' >/dev/null
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic Frontend Review' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker exec "$WP" mkdir -p /var/www/html/wp-content/themes/vf-tools-theme /var/www/html/wp-content/mu-plugins
docker cp target/src/. "$WP:/var/www/html/wp-content/themes/vf-tools-theme/"
docker cp provider/vf-tools-m3u8_V1.25.94.zip "$WP:/tmp/provider.zip"
cli plugin install /tmp/provider.zip --activate >/dev/null
docker cp lane/fixture.php "$WP:/var/www/html/wp-content/mu-plugins/progress-fixture.php"
docker exec "$WP" chown -R www-data:www-data /var/www/html/wp-content/themes/vf-tools-theme
cli theme activate vf-tools-theme >/dev/null
cli plugin install polylang --version=3.8.10 --activate >/dev/null
docker cp lane/languages.php "$WP:/tmp/languages.php";cli eval-file /tmp/languages.php >/dev/null
docker cp lane/wp-check.php "$WP:/tmp/wp-check.php";cli eval-file /tmp/wp-check.php > proof/wordpress.json
cli rewrite structure '/%postname%/' --hard >/dev/null
docker cp lane/mount-seed.php "$WP:/tmp/mount-seed.php";cli eval-file /tmp/mount-seed.php > proof/mounts.json
docker cp lane/seed.php "$WP:/tmp/seed.php";cli eval-file /tmp/seed.php > proof/seed.json
cli plugin install seo-by-rank-math --activate >/dev/null
# Equivalent to Rank Math's supported Skip Registration action; synthetic site only.
cli option update rank_math_registration_skip 1 >/dev/null
docker exec "$WP" sh -c 'cat > /var/www/html/wp-content/mu-plugins/seo-observe.php <<'\''PHP'\''
<?php
add_action("wp_head",static function(){global $wp_filter; $id=get_queried_object_id(); $d=["id"=>$id,"lang"=>function_exists("pll_get_post_language")?pll_get_post_language($id):"","singular"=>is_singular(),"is404"=>is_404(),"rank_math_defined"=>defined("RANK_MATH_VERSION"),"rank_math_class"=>class_exists("RankMath"),"meta"=>get_post_meta($id,"rank_math_description",true),"static_context"=>$GLOBALS["vf_toolsite_static_route_context"]??"missing","cached_existing"=>function_exists("vf_toolsite_static_route_existing_post")?(int)(vf_toolsite_static_route_existing_post("m3u8-encryption-detector")->ID??0):-1,"cached_virtual"=>function_exists("vf_toolsite_static_route_virtual_post")?(int)(vf_toolsite_static_route_virtual_post("m3u8-encryption-detector")->ID??0):-1,"request_lang"=>function_exists("vf_toolsite_multilingual_request_language_code")?vf_toolsite_multilingual_request_language_code():"missing","resolver_exists"=>function_exists("vf_theme_public_route_contract_find_exact_published_post_id_for_route_language"),"resolver_en"=>function_exists("vf_theme_public_route_contract_find_exact_published_post_id_for_route_language")?vf_theme_public_route_contract_find_exact_published_post_id_for_route_language("m3u8-encryption-detector","en"):-1,"resolver_zh"=>function_exists("vf_theme_public_route_contract_find_exact_published_post_id_for_route_language")?vf_theme_public_route_contract_find_exact_published_post_id_for_route_language("m3u8-encryption-detector","zh"):-1,"head_priorities"=>array_keys($wp_filter["wp_head"]->callbacks??[])]; echo "<meta name=\"fixture-observation\" content=\"".esc_attr(wp_json_encode($d))."\">";},1);
foreach([-1,11] as $priority){add_action("wp",static function()use($priority){$GLOBALS["fixture_wp_phases"][$priority]=["id"=>get_queried_object_id(),"sitemap"=>get_query_var("sitemap"),"customize"=>is_customize_preview(),"frontend_loaded"=>did_action("rank_math/frontend/loaded"),"has_integration"=>has_action("wp")];},$priority);}
add_filter("rank_math/frontend/description",static function($value){$GLOBALS["fixture_rank_description"]=$value;return $value;},PHP_INT_MAX);
add_action("wp_head",static function(){ $p=function_exists("vf_tools_theme_projection_current_seo")?vf_tools_theme_projection_current_seo():[]; $buf=ob_get_contents();global $wp_filter; $d=["wp_phases"=>$GLOBALS["fixture_wp_phases"]??[],"wp_head_one"=>array_keys($wp_filter["wp_head"]->callbacks[1]??[]),"rm_head_priorities"=>array_keys($wp_filter["rank_math/head"]->callbacks??[]),"rm_head_calls"=>did_action("rank_math/head"),"description_filter_called"=>array_key_exists("fixture_rank_description",$GLOBALS),"description_filter_value"=>$GLOBALS["fixture_rank_description"]??null,"raw_description_word"=>is_string($buf)&&strpos($buf,"description")!==false,"projection_managed"=>$p["managed"]??null,"projection_ok"=>$p["ok"]??null,"theme_owned"=>function_exists("vf_theme_seo_is_theme_owned_route")?vf_theme_seo_is_theme_owned_route():null];$q=chr(34);echo "<meta name=".$q."fixture-seo-observe".$q." content=".$q.esc_attr(wp_json_encode($d)).$q.">";},PHP_INT_MAX-1);
PHP'
docker cp control/lanes/s01-encryption-browser/seo-seed.php "$WP:/tmp/seo-seed.php";cli eval-file /tmp/seo-seed.php > proof/seo-seed.json
docker cp lane/extra-seed.php "$WP:/tmp/extra-seed.php";cli eval-file /tmp/extra-seed.php > proof/cases.json
docker cp lane/snapshot.php "$WP:/tmp/snapshot.php"
# Warm only public read-only boot paths before protected-state comparison.
curl -fsS http://127.0.0.1:18880/ >/dev/null
curl -fsS http://127.0.0.1:18880/m3u8-encryption-detector/ >/dev/null
cli eval-file /tmp/snapshot.php > proof/bootstrap-before.json
node lane/warm-admin.cjs
cli eval-file /tmp/snapshot.php > proof/bootstrap-after.json
python3 - <<'PYBOOT'
import json,pathlib
r=pathlib.Path('proof');a=json.loads((r/'bootstrap-before.json').read_text());b=json.loads((r/'bootstrap-after.json').read_text());changed=[k for k in a['sections']if a['sections'][k]!=b['sections'][k]]
assert set(changed)<= {'vf_theme_brand','vf_theme_tokens','vf_theme_navigation'}
assert all(not a['option_presence'][k]and b['option_presence'][k]for k in changed)
(r/'bootstrap.json').write_text(json.dumps({'status':'PASS','created_missing_options':changed,'existing_protected_records':'BYTE_IDENTICAL','scope':'fresh isolated installation initialization before review baseline'}))
PYBOOT
cli eval-file /tmp/snapshot.php > proof/state-before.sha256
node control/lanes/s01-encryption-browser/seo-check.cjs
cli eval-file /tmp/snapshot.php > proof/state-after.sha256
cmp proof/state-before.sha256 proof/state-after.sha256
echo ENCRYPTION_DATA_PROTECTION_PASS
# Only modify the synthetic English fixture after protected-state proof.
fixture_en_id=$(python3 -c 'import json; print(int(json.load(open("proof/seo-seed.json"))["pair"]["en"]))')
cli post update "$fixture_en_id" --post_status=draft >/dev/null
SEO_MISSING_EN=1 node control/lanes/s01-encryption-browser/seo-check.cjs
