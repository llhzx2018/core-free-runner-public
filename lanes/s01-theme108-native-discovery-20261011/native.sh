#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C target rev-parse HEAD)" = "$TARGET_SHA"
test "$(git -C target rev-parse HEAD^{tree})" = "$TARGET_TREE"
# Allow unrelated component manifests to advance; enforce exact live S01-C01/C03 bytes below.
LIVE_CHANNEL_SHA="$(gh api repos/llhzx2018/core-updates/git/ref/heads/main --jq .object.sha)"
test -n "$LIVE_CHANNEL_SHA"
for comp in theme m3;do
 if [ "$comp" = theme ];then repo=llhzx2018/vf-tools-theme;ver="$THEME_SOURCE_VERSION";name="vf-tools-theme_V$ver.zip"
 else repo=llhzx2018/vf-tools-m3u8;ver="$M3_SOURCE_VERSION";name="vf-tools-m3u8_V$ver.zip";fi
 gh release download "v$ver" --repo "$repo" --pattern "$name" --output "/tmp/$comp-source.zip"
done
gh api "repos/llhzx2018/core-updates/contents/projects/S01-C01.json?ref=$CHANNEL_SHA" -H 'Accept: application/vnd.github.raw+json' > /tmp/theme-channel.json
gh api "repos/llhzx2018/core-updates/contents/projects/S01-C03.json?ref=$CHANNEL_SHA" -H 'Accept: application/vnd.github.raw+json' > /tmp/m3-channel.json
gh api "repos/llhzx2018/core-updates/contents/projects/S01-C01.json?ref=main" -H 'Accept: application/vnd.github.raw+json' > /tmp/theme-channel-main.json
gh api "repos/llhzx2018/core-updates/contents/projects/S01-C03.json?ref=main" -H 'Accept: application/vnd.github.raw+json' > /tmp/m3-channel-main.json
cmp /tmp/theme-channel-main.json /tmp/theme-channel.json
cmp /tmp/m3-channel-main.json /tmp/m3-channel.json
python3 - <<'PY'
import pathlib,json,os
for c,p,ver,digest in [('theme','S01-C01','THEME_VERSION','THEME_ASSET_SHA'),('m3','S01-C03','M3_VERSION','M3_ASSET_SHA')]:
 r=json.loads(pathlib.Path('/tmp/'+c+'-channel.json').read_text())
 v=json.loads((pathlib.Path('target/projects')/(p+'.json')).read_text())
 assert r==v and r['target_version']==os.environ[ver] and r['asset_sha256']==os.environ[digest]
PY

NET="vf-s01-native-$GITHUB_RUN_ID";DB="$NET-db";WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1&&break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php&&curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null&&break;sleep 2;done
curl -fsSLo /tmp/vf-s01-wpcli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/vf-s01-wpcli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='Synthetic S01 Native Discovery' --admin_user=admin --admin_password='Synthetic-Only-Discovery-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp /tmp/theme-source.zip "$WP:/tmp/theme-source.zip"
gh release download "v$THEME_LEGACY_SOURCE_VERSION" --repo llhzx2018/vf-tools-theme --pattern "vf-tools-theme_V$THEME_LEGACY_SOURCE_VERSION.zip" --output /tmp/theme-legacy106-source.zip
python3 - <<'PYLEGACY'
from pathlib import Path
import hashlib,zipfile
p=Path('/tmp/theme-legacy106-source.zip')
data=p.read_bytes()
assert len(data)==1790587 and hashlib.sha256(data).hexdigest()=='7514fc4134488d4aeb5e43ea5013f28374d282d24a906d70bb185fdcce3d18e8'
with zipfile.ZipFile(p) as z:assert z.testzip() is None
PYLEGACY
docker cp /tmp/theme-legacy106-source.zip "$WP:/tmp/theme-legacy106-source.zip"
docker cp /tmp/m3-source.zip "$WP:/tmp/m3-source.zip"
cli theme install /tmp/theme-source.zip --activate >/dev/null
cli plugin install /tmp/m3-source.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$THEME_SOURCE_VERSION"
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$M3_SOURCE_VERSION"
docker cp /tmp/theme-channel.json "$WP:/tmp/channel.json"
docker cp historic-theme/lanes/s01-c01-footer105-20261010/discovery.php "$WP:/tmp/native-theme.php"
docker exec --user www-data -e VF_PRIVATE_READ_TOKEN -e SOURCE_VERSION="$THEME_SOURCE_VERSION" -e TARGET_VERSION="$THEME_VERSION" -e TARGET_SHA="$THEME_SHA" -e TARGET_TREE="$THEME_TREE" -e CHANNEL_SHA="$CHANNEL_SHA" "$WP" php /usr/local/bin/wp eval-file /tmp/native-theme.php --path=/var/www/html > proof/native-theme107.json
cli theme install /tmp/theme-legacy106-source.zip --force --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$THEME_LEGACY_SOURCE_VERSION"
docker exec --user www-data -e VF_PRIVATE_READ_TOKEN -e SOURCE_VERSION="$THEME_LEGACY_SOURCE_VERSION" -e TARGET_VERSION="$THEME_VERSION" -e TARGET_SHA="$THEME_SHA" -e TARGET_TREE="$THEME_TREE" -e CHANNEL_SHA="$CHANNEL_SHA" "$WP" php /usr/local/bin/wp eval-file /tmp/native-theme.php --path=/var/www/html > proof/native-theme106.json
docker cp /tmp/m3-channel.json "$WP:/tmp/channel.json"
docker cp historic-m3/lanes/s01-c03-embed78-20261010/discovery.php "$WP:/tmp/native-m3.php"
docker exec --user www-data -e VF_PRIVATE_READ_TOKEN -e SOURCE_VERSION="$M3_SOURCE_VERSION" -e TARGET_VERSION="$M3_VERSION" -e TARGET_SHA="$M3_SHA" -e TARGET_TREE="$M3_TREE" -e CHANNEL_SHA="$CHANNEL_SHA" "$WP" php /usr/local/bin/wp eval-file /tmp/native-m3.php --path=/var/www/html > proof/native-m3.json
python3 - <<'PY'
import os,json,pathlib
receipts={}
for id,name,v,src,sha in [('S01-C01','theme107','THEME_VERSION','THEME_SOURCE_VERSION','THEME_ASSET_SHA'),('S01-C03','m3','M3_VERSION','M3_SOURCE_VERSION','M3_ASSET_SHA')]:
 r=json.loads((pathlib.Path('proof')/('native-'+name+'.json')).read_text())
 assert r['status']=='PASS' and r['native_discovery']=='UPDATE_AVAILABLE' and r['missing_credential']=='FAIL_CLOSED_PRESERVED'
 assert r['target_version']==os.environ[v] and r['source_version']==os.environ[src] and r['asset_sha256']==os.environ[sha] and r['channel_sha']==os.environ['CHANNEL_SHA']
 assert r['production']=='NOT_EXECUTED'
 receipts[id]={'status':r['status'],'source_version':r['source_version'],'target_version':r['target_version'],'native_discovery':r['native_discovery'],'asset_sha256':r['asset_sha256'],'missing_credential':r['missing_credential']}
legacy=json.loads((pathlib.Path('proof')/'native-theme106.json').read_text())
assert legacy['status']=='PASS' and legacy['source_version']==os.environ['THEME_LEGACY_SOURCE_VERSION']
assert legacy['target_version']==os.environ['THEME_VERSION'] and legacy['native_discovery']=='UPDATE_AVAILABLE'
assert legacy['asset_sha256']==os.environ['THEME_ASSET_SHA'] and legacy['missing_credential']=='FAIL_CLOSED_PRESERVED'
assert legacy['channel_sha']==os.environ['CHANNEL_SHA'] and legacy['production']=='NOT_EXECUTED'
receipts['S01-C01']['source_coverage']=[os.environ['THEME_LEGACY_SOURCE_VERSION'],os.environ['THEME_SOURCE_VERSION']]
p={'status':'PASS','channel_sha':os.environ['CHANNEL_SHA'],'component_checks':receipts,'production':'NOT_EXECUTED','owner_production_install':'PENDING_MANUAL'}
pathlib.Path('proof/FINAL_DISCOVERY.json').write_text(json.dumps(p,indent=2));print('PUBLIC_SAFE_NATIVE_DISCOVERY',json.dumps(p))
PY
