#!/usr/bin/env bash
set -Eeuo pipefail
test "$(git -C baseline rev-parse HEAD)" = "fbe049dc18eb18eab21e9d8c3cededfe55b783e7"
test "$(git -C candidate rev-parse HEAD)" = "3ab0992fb4788b8b9d15d0e338040189b6fcdd8f"
test "$(git -C theme rev-parse HEAD)" = "d44b6b148bcdf67c3908ff95678ea3528c1bb265"
test "$(git -C ops rev-parse HEAD)" = "3f22e61339f7c76eea2c4524885819b10ee59057"
echo S01_R8_ZIP_SOURCE_IDENTITIES=PASS

OUT=/tmp/s01-r8-zip-fixture
WP=/tmp/s01-r8-upgrade-wp
mkdir -p "$OUT" "$WP"
python3 - "$OUT" <<'PY'
import hashlib,json,pathlib,re,shutil,sys,zipfile
out=pathlib.Path(sys.argv[1])
base=pathlib.Path('baseline/src')
candidate=pathlib.Path('candidate/src')
tmp=out/'candidate-version-only-fixture'
shutil.copytree(candidate,tmp,dirs_exist_ok=True)
php=tmp/'vf-tool-m3u8.php'
s=php.read_text()
a,n=re.subn(r'(?m)^ \* Version: 1\.25\.99$', ' * Version: 99.99.999',s)
assert n==1,'Version header must be 1.25.99'
a,n=re.subn(r"define\('VF_TOOL_M3U8_VERSION', '1\.25\.99'\)", "define('VF_TOOL_M3U8_VERSION', '99.99.999')",a)
assert n==1,'version constant must match'
php.write_text(a)
mf=tmp/'plugin-manifest.json'
d=json.loads(mf.read_text())
assert d['version']=='1.25.99'
d['version']='99.99.999'
mf.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
for name,src in [('baseline.zip',base),('candidate-version-only-fixture.zip',tmp)]:
    with zipfile.ZipFile(out/name,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in src.rglob('*') if p.is_file()):
            rel=path.relative_to(src).as_posix()
            if rel.startswith(('tests/','docs/','evidence/','.git/','.github/')):continue
            if rel=='PACKAGE_PROFILE.json':continue
            z.write(path,'vf-tool-m3u8/'+rel)
    with zipfile.ZipFile(out/name) as z:
        assert z.testzip() is None
        assert 'vf-tool-m3u8/vf-tool-m3u8.php' in z.namelist()
        assert 'vf-tool-m3u8/public/dist/converter.js' in z.namelist()
    print('S01_R8_ZIP_'+name+'=PASS sha256='+hashlib.sha256((out/name).read_bytes()).hexdigest())
for path in sorted(p for p in candidate.rglob('*') if p.is_file()):
    rel=path.relative_to(candidate)
    if str(rel) in {'vf-tool-m3u8.php','plugin-manifest.json'}:continue
    assert path.read_bytes()==(tmp/rel).read_bytes(),f'unexpected fixture overlay: {rel}'
print('S01_R8_EXACT_CANDIDATE_EXCEPT_SYNTHETIC_VERSION=PASS')
PY

curl -fsSLo /tmp/s01-r8-wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
wp(){ php /tmp/s01-r8-wp-cli.phar "$@" --path="$WP"; }
wp core download --skip-content --quiet
wp config create --dbname=wordpress --dbuser=wordpress --dbpass=synthetic-wp --dbhost=127.0.0.1:3306 --skip-check
wp core install --url=http://127.0.0.1:18882 --title=S01-Upgrade-Fixture --admin_user=synthetic --admin_password=synthetic-only-password --admin_email=synthetic@example.invalid --skip-email
mkdir -p "$WP/wp-content/themes/vf-tools-theme" "$WP/wp-content/plugins/vf-tools-ops"
cp -a theme/src/. "$WP/wp-content/themes/vf-tools-theme/"
cp -a ops/. "$WP/wp-content/plugins/vf-tools-ops/"
wp theme activate vf-tools-theme
wp plugin activate vf-tools-ops/vf-ops.php
wp plugin install "$OUT/baseline.zip" --activate
test "$(wp plugin get vf-tool-m3u8 --field=version)" = "1.25.99"
wp plugin is-active vf-tool-m3u8
echo S01_R8_VERSIONED_BASELINE_INSTALL=PASS

wp eval 'update_option("vf_r8_owner_canary",["safe"=>"retain","owner"=>"user","at"=>"fixture-only"],false);$id=wp_insert_post(["post_type"=>"page","post_status"=>"publish","post_name"=>"r8-owner-page","post_title"=>"Owner page","post_content"=>"Owner content do not overwrite"]);if(is_wp_error($id)||!$id)throw new Exception("OWNER_POST_CREATE_FAILED");update_post_meta($id,"_vf_owner_canary","retain-owner-post");$keys=["vf_r8_owner_canary","vf_m3u8_mounts","vf_m3u8_settings","vf_m3u8_copy","vf_m3u8_skin_seasonal_migration_snapshot"]; $out=[];foreach($keys as $key){$out[$key]=serialize(get_option($key,"__MISSING__"));} $out["_owner_page"]=["id"=>$id,"post"=>serialize(get_post($id)),"meta"=>serialize(get_post_meta($id))];file_put_contents("/tmp/s01-r8-before.json",json_encode($out));echo "S01_OWNER_FIXTURE_CREATED=PASS\n";'
verify_owner(){
wp eval '$baseline=json_decode(file_get_contents("/tmp/s01-r8-before.json"),true);foreach($baseline as $key=>$value){if($key==="_owner_page"){if(serialize(get_post($value["id"]))!==$value["post"] || serialize(get_post_meta($value["id"]))!==$value["meta"])throw new Exception("OWNER_POST_CHANGED");}elseif(serialize(get_option($key,"__MISSING__"))!==$value)throw new Exception("OWNER_OPTION_CHANGED:".$key);}echo "S01_R8_OWNER_DATA_READBACK=PASS\n";'
}
check_payload(){
local source="$1"
for file in public/dist/converter.js public/dist/playlist-checker.js public/dist/player.js public/dist/downloader.js includes/skin-seasonal.php includes/v510-copy.php;do
  cmp "$source/$file" "$WP/wp-content/plugins/vf-tool-m3u8/$file"
done
wp plugin is-active vf-tool-m3u8
verify_owner
echo "S01_R8_PLUGIN_PACKAGE_BYTES_AND_OWNER_STATE=PASS"
}

wp plugin install "$OUT/candidate-version-only-fixture.zip" --force
test "$(wp plugin get vf-tool-m3u8 --field=version)" = "99.99.999"
check_payload "$OUT/candidate-version-only-fixture"
echo S01_R8_WP_PLUGIN_UPGRADER_VERSIONED_FIXTURE=PASS

wp plugin install "$OUT/baseline.zip" --force
test "$(wp plugin get vf-tool-m3u8 --field=version)" = "1.25.99"
check_payload "baseline/src"
echo S01_R8_WP_PLUGIN_UPGRADER_ROLLBACK=PASS

wp plugin install "$OUT/candidate-version-only-fixture.zip" --force
test "$(wp plugin get vf-tool-m3u8 --field=version)" = "99.99.999"
check_payload "$OUT/candidate-version-only-fixture"
echo S01_R8_WP_PLUGIN_UPGRADER_REUPGRADE=PASS

wp eval '$required=["vf_m3u8_converter_lite","vf_m3u8_playlist_checker","vf_m3u8_backup_restore"];foreach($required as $shortcode){if(!shortcode_exists($shortcode))throw new Exception("MISSING_SHORTCODE:".$shortcode);} echo "S01_R8_POST_UPGRADE_SHORTCODES=PASS\n";'
echo "S01_R8_SYNTHETIC_VERSION_ONLY_NOT_OFFICIAL_RELEASE=YES"
