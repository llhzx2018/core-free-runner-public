#!/usr/bin/env bash
set -Eeuo pipefail
NETWORK="vf-s01-pll-$GITHUB_RUN_ID"
DB="$NETWORK-db"
WP="$NETWORK-wp"
cleanup(){
 docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true
 docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$NETWORK" >/dev/null
docker run -d --name "$DB" --network "$NETWORK" \
 -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress \
 -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for _ in $(seq 1 60); do
 if docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1;then break;fi
 sleep 2
done
docker run -d --name "$WP" --network "$NETWORK" -p 18883:80 \
 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress \
 -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb \
 wordpress:7.1.2-php8.3-apache >/dev/null
for _ in $(seq 1 90); do
 if docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18883/wp-admin/install.php >/dev/null;then break;fi
 sleep 2
done
curl -fsSLo /tmp/s01-pll-wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/s01-pll-wp-cli.phar "$WP:/usr/local/bin/wp"
docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli core install --url=http://127.0.0.1:18883 --title='S01 Synthetic Polylang Guard' \
 --admin_user=admin --admin_password='S01-Synthetic-Guard-Only!' \
 --admin_email=runner@example.invalid --skip-email >/dev/null
cli plugin install polylang --activate >/dev/null
cli plugin install seo-by-rank-math --activate >/dev/null
cli eval 'update_option("rank_math_modules",array_values(array_unique(array_merge((array)get_option("rank_math_modules",[]),["redirections"])))); \\RankMath\\Installer::create_tables(["redirections"]);' >/dev/null
# Isolated container-resolvable URL is required for a genuine HTTP 301 readback
# from within WordPress; no Production hostname or account is ever accessed.
cli option update home "http://$WP" >/dev/null
cli option update siteurl "http://$WP" >/dev/null
cli rewrite structure '/%postname%/' >/dev/null
docker cp target/includes/multilingual-slug-cleaner/service-actions-parts/01-common.php "$WP:/tmp/01-common.php"
docker cp target/includes/multilingual-slug-cleaner/service-actions-parts/02-scan.php "$WP:/tmp/02-scan.php"
docker cp target/includes/multilingual-slug-cleaner/service-actions-parts/03-repair-helpers.php "$WP:/tmp/03-repair-helpers.php"
docker cp runner/lanes/s01-c02-polylang-archive-guard/fixture.php "$WP:/tmp/fixture.php"
cli eval-file /tmp/fixture.php > /tmp/s01-pll-integration.log
docker cp runner/lanes/s01-c02-polylang-archive-guard/rank-math-fixture.php "$WP:/tmp/rank-math-fixture.php"
cli eval-file /tmp/rank-math-fixture.php > /tmp/s01-rankmath.log
cat /tmp/s01-rankmath.log
grep -q S01_C02_RANK_MATH_NATIVE_301_PASS /tmp/s01-rankmath.log
grep -q S01_C02_RANK_MATH_ISOLATED_ROLLBACK_PASS /tmp/s01-rankmath.log
cat /tmp/s01-pll-integration.log
grep -q S01_C02_POLYLANG_WORDPRESS_PASS /tmp/s01-pll-integration.log
grep -q S01_C02_POLYLANG_LINK_REHEARSAL_PASS /tmp/s01-pll-integration.log
grep -q S01_C02_POLYLANG_LINK_ROLLBACK_PASS /tmp/s01-pll-integration.log
grep -q S01_C02_POLYLANG_RECIPROCAL_RELATION_PASS /tmp/s01-pll-integration.log
grep -q S01_C02_POLYLANG_NAIVE_RELATION_BLOCK_PASS /tmp/s01-pll-integration.log
grep -q S01_C02_NO_301_NO_ARCHIVE_PASS /tmp/s01-pll-integration.log
grep -q S01_C02_MISSING_SOURCE_GUARD_PASS /tmp/s01-pll-integration.log
grep -q S01_C02_REAL_HTTP_301_ARCHIVE_PASS /tmp/s01-pll-integration.log
mkdir -p proof
python3 - <<'PY'
import json,os,pathlib
p={'status':'PASS','scope':'live WordPress + MariaDB + official Polylang (free) translation membership','candidate_sha':os.environ['PRODUCT_SHA'],'production':'NOT_EXECUTED','rehearsal':'Polylang relink rollback and failclosed non-301 archive checked','limitations':'Polylang Pro license and Production Rank Math/CF configuration not tested; official free Rank Math engine verified in isolated environment'}
pathlib.Path('proof/WORDPRESS.json').write_text(json.dumps(p,indent=2))
print('S01_C02_WORDPRESS_ISOLATED_PASS',json.dumps(p))
PY
