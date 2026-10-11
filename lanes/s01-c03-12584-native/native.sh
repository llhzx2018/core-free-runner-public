#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p proof
test "$(git -C channel rev-parse HEAD)" = "$CHANNEL_SHA"
test "$(git -C product rev-parse HEAD)" = "$PRODUCT_SHA"
test "$(git -C product rev-parse HEAD^{tree})" = "$PRODUCT_TREE"
test "$(cat product/VERSION)" = "$TARGET_VERSION"
gh api "repos/llhzx2018/core-updates/contents/projects/S01-C03.json?ref=main" -H 'Accept: application/vnd.github.raw+json' > /tmp/channel-12584.json
cmp /tmp/channel-12584.json channel/projects/S01-C03.json
gh release download "v$SOURCE_VERSION" --repo llhzx2018/vf-tools-m3u8 --pattern "vf-tools-m3u8_V$SOURCE_VERSION.zip" --output /tmp/source-12583.zip
gh release download "v$TARGET_VERSION" --repo llhzx2018/vf-tools-m3u8 --pattern "vf-tools-m3u8_V$TARGET_VERSION.zip" --output /tmp/target-12584.zip
python3 - <<'PY'
import json,os,pathlib,hashlib,zipfile
m=json.loads(pathlib.Path('/tmp/channel-12584.json').read_text())
s=pathlib.Path('/tmp/source-12583.zip').read_bytes()
t=pathlib.Path('/tmp/target-12584.zip').read_bytes()
assert m['component_id']=='S01-C03' and m['target_version']==os.environ['TARGET_VERSION']
assert m['release_tag']=='v'+os.environ['TARGET_VERSION'] and m['asset_bytes']==len(t)==3573888
assert m['asset_sha256']==hashlib.sha256(t).hexdigest()==os.environ['ASSET_SHA']
assert m['runtime_fingerprint']==os.environ['PRODUCT_FP'] and m['runtime_files']==568
assert m['released_at']=='2026-10-11T11:30:07Z'
assert os.environ['SOURCE_VERSION'] in m['from_versions']
assert len(s)==3573699 and hashlib.sha256(s).hexdigest()=='86c577a92b00e4dac32ffe1f9e0e45d3cf0171748666d41891a57e4e648464ed'
for p in ['/tmp/source-12583.zip','/tmp/target-12584.zip']:
 with zipfile.ZipFile(p) as z: assert z.testzip() is None and 'vf-tool-m3u8/vf-tool-m3u8.php' in z.namelist()
pathlib.Path('proof/channel.json').write_text(json.dumps({'status':'PASS','channel_sha':os.environ['CHANNEL_SHA'],'target_version':m['target_version'],'asset_sha256':m['asset_sha256'],'asset_bytes':len(t),'runtime_fingerprint':m['runtime_fingerprint'],'source_version':os.environ['SOURCE_VERSION'],'production':'NOT_EXECUTED'},indent=2))
print('S01_C03_CHANNEL_REMOTE_READBACK_PASS',m['target_version'],m['asset_sha256'])
PY
NET="s01-m3native-$GITHUB_RUN_ID"; DB="$NET-db"; WP="$NET-wp"
cleanup(){ docker rm -fv "$WP" "$DB" >/dev/null 2>&1 || true;docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60);do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1&&break;sleep 2;done
docker run -d --name "$WP" --network "$NET" -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90);do docker exec "$WP" test -f /var/www/html/wp-settings.php&&curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null&&break;sleep 2;done
curl -fsSLo /tmp/s01-wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/s01-wp-cli.phar "$WP:/usr/local/bin/wp"
docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli config set DISABLE_WP_CRON true --raw >/dev/null
cli core install --url=http://127.0.0.1:18880 --title='S01 Native 12584' --admin_user=admin --admin_password='S01-Synthetic-Native-81!' --admin_email=runner@example.invalid --skip-email >/dev/null
docker cp /tmp/source-12583.zip "$WP:/tmp/source.zip"
docker cp /tmp/target-12584.zip "$WP:/tmp/target.zip"
docker cp /tmp/channel-12584.json "$WP:/tmp/channel.json"
docker cp lane/discovery.php "$WP:/tmp/discovery.php"
cli plugin install /tmp/source.zip --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$SOURCE_VERSION"
docker exec --user www-data -e VF_PRIVATE_READ_TOKEN -e SOURCE_VERSION="$SOURCE_VERSION" -e TARGET_VERSION="$TARGET_VERSION" -e TARGET_SHA="$PRODUCT_SHA" -e TARGET_TREE="$PRODUCT_TREE" -e CHANNEL_SHA="$CHANNEL_SHA" "$WP" php /usr/local/bin/wp eval-file /tmp/discovery.php --path=/var/www/html > proof/native.json
python3 - <<'PY'
import json,os,pathlib
d=json.loads(pathlib.Path('proof/native.json').read_text())
assert d['status']=='PASS' and d['native_discovery']=='UPDATE_AVAILABLE'
assert d['missing_credential']=='FAIL_CLOSED_PRESERVED' and d['production']=='NOT_EXECUTED'
assert d['channel_sha']==os.environ['CHANNEL_SHA'] and d['source_version']==os.environ['SOURCE_VERSION']
assert d['target_version']==os.environ['TARGET_VERSION'] and d['source_sha']==os.environ['PRODUCT_SHA']
assert d['asset_sha256']==os.environ['ASSET_SHA']
print('S01_C03_WORDPRESS_NATIVE_DISCOVERY_PASS',d['source_version'],d['target_version'])
PY
# Seed a REAL pre-upgrade-version error into persistent history and component
# state; verify that the upgraded code will not rehydrate it as current truth.
cli eval 'VF_M3U8_Update_History_V1::attempt("SOURCE_VERSION_NOT_ALLOWED",["target_version"=>"1.25.83"]);update_option("vf_s01_c03_update_center_state_v1",["state"=>"SOURCE_VERSION_NOT_ALLOWED","current_version"=>"1.25.83","target_version"=>"1.25.83","checked_at"=>gmdate("c")],false);' >/dev/null
cli plugin install /tmp/target.zip --force --activate >/dev/null
test "$(cli plugin get vf-tool-m3u8 --field=version)" = "$TARGET_VERSION"
cat > /tmp/s01-c03-post-current.php <<'PHP'
<?php
if(VF_TOOL_M3U8_VERSION!==getenv('TARGET_VERSION'))throw new RuntimeException('installed target mismatch');
$pre=(new VF_M3U8_Update_Admin_V1())->register_component([])['S01-C03'];
if(!in_array($pre['state'],['NOT_CHECKED','UP_TO_DATE'],true))throw new RuntimeException('stale pre-upgrade state replayed: '.$pre['state']);
echo "M3U8_POST_UPGRADE_OLD_HISTORY_NOT_REPLAYED=PASS\\n";
VF_M3U8_Update_Source_V1::clear_cache();
$c=new VF_M3U8_Update_Client_V1(VF_TOOL_M3U8_VERSION);
$t=$c->inject_plugin_update((object)['response'=>[]]);
$history=VF_M3U8_Update_History_V1::status();
$a=(array)($history['attempts']??[]);
$last=end($a);
if(($last['state']??'')!=='UP_TO_DATE'||!empty($t->response[VF_M3U8_Update_Contract_V1::PLUGIN_BASENAME]))throw new RuntimeException('published target should be up-to-date without update offer, got '.($last['state']??'NONE'));
$post=(new VF_M3U8_Update_Admin_V1())->register_component([])['S01-C03'];
if($post['state']!=='UP_TO_DATE')throw new RuntimeException('current verified updater status not displayed: '.$post['state']);
echo "M3U8_POST_UPGRADE_FRESH_CURRENT_HISTORY_PASS\\n";
echo "M3U8_INSTALLED_12584_ALREADY_CURRENT_NO_FALSE_BLOCK_PASS\\n";
PHP
docker cp /tmp/s01-c03-post-current.php "$WP:/tmp/post-current.php"
docker exec --user www-data -e VF_PRIVATE_READ_TOKEN -e TARGET_VERSION="$TARGET_VERSION" "$WP" php /usr/local/bin/wp eval-file /tmp/post-current.php --path=/var/www/html | tee proof/post-current.txt

cli eval 'if(!shortcode_exists("vf_m3u8_playlist_checker"))throw new Exception("browser stream shortcode missing");echo wp_json_encode(["status"=>"PASS","component"=>VF_TOOL_M3U8_VERSION,"shortcode"=>"vf_m3u8_playlist_checker"]);' > proof/installed.json
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path('proof')
for n in ['channel','native','installed']:assert json.loads((p/(n+'.json')).read_text())['status']=='PASS'
final={'status':'PASS','component':'S01-C03','channel_sha':os.environ['CHANNEL_SHA'],'product_sha':os.environ['PRODUCT_SHA'],'target_version':os.environ['TARGET_VERSION'],'source_version':os.environ['SOURCE_VERSION'],'checks':['CHANNEL_REMOTE_READBACK','NATIVE_UPDATE_AVAILABLE','DOWNLOAD_SHA256_MATCH','NO_CREDENTIAL_FAIL_CLOSED','TARGET_PLUGIN_INSTALL','POST_TARGET_UP_TO_DATE','STALE_HISTORY_REJECTED','FRESH_CURRENT_STATUS','BROWSER_TEST_SHORTCODE'],'production':'NOT_EXECUTED','owner_manual_upgrade':'PENDING'}
(p/'FINAL_DISCOVERY.json').write_text(json.dumps(final,indent=2))
print('S01_C03_CHANNEL_AND_NATIVE_PASS',json.dumps(final))
PY
