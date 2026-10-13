#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C target rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C target rev-parse HEAD^{tree})" = "$TARGET_TREE"
test "$(tr -d '[:space:]' < target/VERSION)" = "$TARGET_VERSION"
gh api "repos/llhzx2018/core-updates/contents/projects/S01-C03.json?ref=$CHANNEL_SHA" -H 'Accept: application/vnd.github.raw+json' > /tmp/m3-channel.json
gh api "repos/llhzx2018/core-updates/contents/projects/S01-C03.json?ref=main" -H 'Accept: application/vnd.github.raw+json' > /tmp/m3-channel-main.json
cmp /tmp/m3-channel-main.json /tmp/m3-channel.json
python3 - <<'PY'
import json,os,pathlib
a=json.loads(pathlib.Path('/tmp/m3-channel.json').read_text());b=json.loads(pathlib.Path('target/projects/S01-C03.json').read_text())
assert a==b and a['target_version']==os.environ['M3_VERSION'] and a['asset_sha256']==os.environ['M3_ASSET_SHA']
assert os.environ['M3_SOURCE_VERSION'] in a['from_versions'] and os.environ['M3_LEGACY_SOURCE_VERSION'] in a['from_versions']
PY
gh release download "v$THEME_VERSION" --repo llhzx2018/vf-tools-theme --pattern "vf-tools-theme_V$THEME_VERSION.zip" --output /tmp/theme-host.zip
gh release download "v$M3_SOURCE_VERSION" --repo llhzx2018/vf-tools-m3u8 --pattern "vf-tools-m3u8_V$M3_SOURCE_VERSION.zip" --output /tmp/m3-source.zip
gh release download "v$M3_LEGACY_SOURCE_VERSION" --repo llhzx2018/vf-tools-m3u8 --pattern "vf-tools-m3u8_V$M3_LEGACY_SOURCE_VERSION.zip" --output /tmp/m3-legacy.zip
python3 - <<'PY'
import pathlib,json,hashlib,zipfile,os
for p,size,digest in [('/tmp/theme-host.zip','THEME_BYTES','THEME_ASSET_SHA'),('/tmp/m3-source.zip','M3_SOURCE_BYTES','M3_SOURCE_SHA256'),('/tmp/m3-legacy.zip','M3_LEGACY_BYTES','M3_LEGACY_SHA256')]:
 data=pathlib.Path(p).read_bytes()
 assert len(data)==int(os.environ[size]) and hashlib.sha256(data).hexdigest()==os.environ[digest]
 with zipfile.ZipFile(p) as z:assert z.testzip() is None
PY
NET="vf-m3-native-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1&&break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php&&curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null&&break;sleep 2;done
curl -fsSLo /tmp/wp-native.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/wp-native.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic M3U8 native discovery' --admin_user=admin --admin_password='Synthetic-Only-Native-87!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp /tmp/theme-host.zip "$WP:/tmp/theme-host.zip"
docker cp /tmp/m3-source.zip "$WP:/tmp/m3-source.zip"
docker cp /tmp/m3-legacy.zip "$WP:/tmp/m3-legacy.zip"
docker cp /tmp/m3-channel.json "$WP:/tmp/channel.json"
docker cp historic-m3/lanes/s01-c03-embed78-20261010/discovery.php "$WP:/tmp/native-m3.php"
cli theme install /tmp/theme-host.zip --activate >/dev/null
cli plugin install /tmp/m3-source.zip --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_SOURCE_VERSION"
docker exec --user www-data -e VF_PRIVATE_READ_TOKEN -e SOURCE_VERSION="$M3_SOURCE_VERSION" -e TARGET_VERSION="$M3_VERSION" -e TARGET_SHA="$M3_SHA" -e TARGET_TREE="$M3_TREE" -e CHANNEL_SHA="$CHANNEL_SHA" "$WP" php /usr/local/bin/wp eval-file /tmp/native-m3.php --path=/var/www/html > proof/native-m3-current.json
cli plugin install /tmp/m3-legacy.zip --force --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_LEGACY_SOURCE_VERSION"
docker exec --user www-data -e VF_PRIVATE_READ_TOKEN -e SOURCE_VERSION="$M3_LEGACY_SOURCE_VERSION" -e TARGET_VERSION="$M3_VERSION" -e TARGET_SHA="$M3_SHA" -e TARGET_TREE="$M3_TREE" -e CHANNEL_SHA="$CHANNEL_SHA" "$WP" php /usr/local/bin/wp eval-file /tmp/native-m3.php --path=/var/www/html > proof/native-m3-legacy.json
python3 - <<'PY'
import json,os,pathlib
checks={}
for name,source in [('current','M3_SOURCE_VERSION'),('legacy','M3_LEGACY_SOURCE_VERSION')]:
 r=json.loads((pathlib.Path('proof')/('native-m3-'+name+'.json')).read_text())
 assert r['status']=='PASS' and r['native_discovery']=='UPDATE_AVAILABLE' and r['missing_credential']=='FAIL_CLOSED_PRESERVED'
 assert r['source_version']==os.environ[source] and r['target_version']==os.environ['M3_VERSION'] and r['asset_sha256']==os.environ['M3_ASSET_SHA']
 assert r['channel_sha']==os.environ['CHANNEL_SHA'] and r['production']=='NOT_EXECUTED'
 checks[r['source_version']]={k:r[k] for k in ['status','source_version','target_version','native_discovery','asset_bytes','asset_sha256','missing_credential']}
p={'status':'PASS','channel_sha':os.environ['CHANNEL_SHA'],'component':'S01-C03','source_coverage':list(checks),'checks':checks,'production':'NOT_EXECUTED','owner_production_install':'PENDING_MANUAL'}
pathlib.Path('proof/FINAL_DISCOVERY.json').write_text(json.dumps(p,indent=2));print('PUBLIC_SAFE_NATIVE_DISCOVERY',json.dumps(p))
PY

