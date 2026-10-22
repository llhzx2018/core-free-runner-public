from pathlib import Path
s=Path('lane/native.sh').read_text().replace('provider/vf-tools-m3u8_V1.25.91.zip','provider/vf-tools-m3u8_V1.25.94.zip')
old='cli plugin install polylang --version=3.8.10 --activate >/dev/null'
assert s.count(old)==1
s=s.replace(old,'for attempt in 1 2 3; do '+old+' && break; test "$attempt" -lt 3 || exit 1; sleep 3; done')
s=s.replace('node lane/warm-admin.cjs','true')
marker='if [ "'+'$'+'{VF_REVIEW_ONLY_STATE:-0}" = "1" ];then'
assert s.count(marker)==1
s=s.split(marker)[0]+'''
docker cp provider/vf-tools-theme_V1.35.165.zip "$WP:/tmp/old165.zip"
docker cp provider/vf-tools-theme_V1.35.166.zip "$WP:/tmp/old166.zip"
docker cp provider/vf-tools-theme_V1.35.167.zip "$WP:/tmp/new167.zip"
version_check(){
  test "$(cli theme get vf-tools-theme --field=version)" = "$1"
  test "$(cli plugin get vf-tool-m3u8 --field=version)" = 1.25.94
  echo "NATIVE_THEME_VERSION_PASS=$1"
}
version_check 1.35.167
cli theme install /tmp/old165.zip --force >/dev/null
version_check 1.35.165
cli eval-file /tmp/snapshot.php > proof/data165-before.json
cli theme install /tmp/new167.zip --force >/dev/null
version_check 1.35.167
cli eval-file /tmp/snapshot.php > proof/data165-after.json
cmp proof/data165-before.json proof/data165-after.json
echo NATIVE_165_TO_167_PROTECTED_DATA_PASS
cli theme install /tmp/old166.zip --force >/dev/null
version_check 1.35.166
cli eval-file /tmp/snapshot.php > proof/data166-before.json
cli theme install /tmp/new167.zip --force >/dev/null
version_check 1.35.167
cli eval-file /tmp/snapshot.php > proof/data166-after.json
cmp proof/data166-before.json proof/data166-after.json
cli theme install /tmp/old166.zip --force >/dev/null
version_check 1.35.166
cli theme install /tmp/new167.zip --force >/dev/null
version_check 1.35.167
cli theme install /tmp/new167.zip --force >/dev/null
version_check 1.35.167
cli eval-file /tmp/snapshot.php > proof/data-repeat.json
cmp proof/data166-before.json proof/data-repeat.json
echo NATIVE_166_TO_167_ROLLBACK_REPEAT_PROTECTED_DATA_PASS
cli eval 'require_once get_theme_file_path("inc/services/technical-seo-service.php"); update_option(vf_theme_seo_option_key(),vf_theme_seo_defaults(),false); $a=theme_seo_readback(); if(!$a["stored"] || strlen($a["revision"])!==64) exit(82); echo "NATIVE_SEO_STORED_PASS";' > proof/seo-storage.txt
grep -q NATIVE_SEO_STORED_PASS proof/seo-storage.txt
cli eval-file /tmp/snapshot.php > proof/readonly-before.json
NODE_PATH="$PWD/node_modules" node lane/seo167-browser.cjs
cli eval-file /tmp/snapshot.php > proof/readonly-after.json
python3 - <<'PYREAD'
import json
from pathlib import Path
a=json.loads(Path('proof/readonly-before.json').read_text())
b=json.loads(Path('proof/readonly-after.json').read_text())
changed=[k for k in a['sections'] if a['sections'][k]!=b['sections'][k]]
print('READONLY_WORDPRESS_BOOTSTRAP_CHANGED_SECTIONS',changed)
allowed={'vf_theme_brand','vf_theme_tokens','vf_theme_navigation'}
assert set(changed)<=allowed,changed
assert all(not a['option_presence'][k] and b['option_presence'][k] for k in changed),changed
print('NATIVE_SEO_READONLY_PROTECTED_DATA_PASS')
PYREAD
echo NATIVE_SEO_READONLY_DATA_IDENTICAL_PASS
'''
Path('lane/native-seo167.sh').write_text(s)
