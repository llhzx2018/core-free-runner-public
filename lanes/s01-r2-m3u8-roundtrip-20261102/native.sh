#!/usr/bin/env bash
set -Eeuo pipefail
NET="s01r2-$GITHUB_RUN_ID"
DB="$NET-db"
WP="$NET-wp"
WORK="$(mktemp -d)"
cleanup() {
  docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -rf "$WORK" /tmp/s01r2-wpcli.phar
}
trap cleanup EXIT

# Build two deterministic non-release packages; the baseline is exact main,
# the candidate is exact PR #177. They have the same VERSION by design.
mkdir -p "$WORK/base"
git -C target archive "$BASE_SHA:src" | tar -x -C "$WORK/base"
python3 control/lanes/s01-r2-m3u8-roundtrip-20261102/build.py   --baseline "$WORK/base" --candidate target/src --out "$WORK"

docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET"   -e MARIADB_ROOT_PASSWORD=syntheticroot   -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress   -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
READY=0
for i in $(seq 1 80); do
  if docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1; then READY=1; break; fi
  sleep 2
done
test "$READY" = 1

docker run -d --name "$WP" --network "$NET" -p 18884:80   -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress   -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb   wordpress:7.1.2-php8.3-apache >/dev/null
READY=0
for i in $(seq 1 95); do
  if docker exec "$WP" test -f /var/www/html/wp-settings.php     && curl -fsS http://127.0.0.1:18884/wp-admin/install.php >/dev/null; then READY=1; break; fi
  sleep 2
done
test "$READY" = 1

curl -fsSLo /tmp/s01r2-wpcli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/s01r2-wpcli.phar "$WP:/usr/local/bin/wp"
cli() { docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli core install --url=http://127.0.0.1:18884 --title='S01 R2 Synthetic Site'   --admin_user=admin --admin_password='Synthetic-Only-54'   --admin_email=runner@example.invalid --skip-email >/dev/null

docker cp "$WORK/baseline.zip" "$WP:/tmp/base.zip"
docker cp "$WORK/candidate.zip" "$WP:/tmp/candidate.zip"
docker cp control/lanes/s01-r2-m3u8-roundtrip-20261102/state.php "$WP:/tmp/r2-state.php"
cli plugin install /tmp/base.zip --activate >/dev/null
cli plugin is-active vf-tool-m3u8
cli option update vf_m3u8_fixture_user_setting 'synthetic-preserve-me' >/dev/null
cli eval-file /tmp/r2-state.php > "$WORK/before.json"
echo S01_R2_BASELINE_INSTALL=PASS

# Show ordinary whole-database backup includes BOTH migration metadata
# options, which the plugin-local update recovery excludes.
docker exec "$DB" sh -c 'mariadb-dump -uroot -psyntheticroot wordpress' > "$WORK/whole-site.sql"
docker exec "$DB" mariadb -uroot -psyntheticroot -e 'CREATE DATABASE wordpress_restore'
docker exec -i "$DB" mariadb -uroot -psyntheticroot wordpress_restore < "$WORK/whole-site.sql"
KEYS="'vf_m3u8_skin_seasonal_migration_evidence','vf_m3u8_skin_seasonal_migration_snapshot'"
for SCHEMA in wordpress wordpress_restore; do
  docker exec "$DB" mariadb -N -uroot -psyntheticroot -e     "SELECT option_name,SHA2(option_value,256) FROM ${SCHEMA}.wp_options WHERE option_name IN (${KEYS}) ORDER BY option_name"     > "$WORK/$SCHEMA.hashes"
done
test "$(wc -l < "$WORK/wordpress.hashes")" -eq 2
cmp "$WORK/wordpress.hashes" "$WORK/wordpress_restore.hashes"
echo S01_R2_WHOLE_SITE_DATABASE_BACKUP_RESTORE=PASS

# Source promotion + rollback + candidate reapplication using real WP-CLI
# plugin package installation. Same-version promotion is NOT a native WP
# update discovery protocol and is not misrepresented as one.
for phase in candidate base candidate; do
  cli plugin install "/tmp/$phase.zip" --force >/dev/null
  cli plugin is-active vf-tool-m3u8
  cli eval-file /tmp/r2-state.php > "$WORK/$phase-$(date +%s%N).json"
  echo "S01_R2_SOURCE_PROMOTION_$phase=PASS"
done

# Validate every stage's M3U8 canonical state and excluded migration options.
python3 - "$WORK" <<'PY'
import glob, json, pathlib, sys
p=pathlib.Path(sys.argv[1])
files=sorted(p.glob('*.json'))
first=json.loads((p/'before.json').read_text())
assert first['status']=='PASS'
rows=[json.loads(q.read_text()) for q in files if q.name != 'before.json']
assert len(rows)==3, (len(rows),[str(q.name) for q in files])
assert first['provider_table_count']==14, first
assert all(x['status']=='PASS' and x['protected_options']==first['protected_options'] and x['provider_state_sha256']==first['provider_state_sha256'] for x in rows)
print('S01_R2_FULL_PLUGIN_INSTALL_ROLLBACK_REAPPLY_BYTE_PARITY=PASS')
PY
