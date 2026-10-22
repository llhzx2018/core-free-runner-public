from pathlib import Path
s=Path('lane/native.sh').read_text().replace('provider/vf-tools-m3u8_V1.25.91.zip','provider/vf-tools-m3u8_V1.25.94.zip')
installer='cli plugin install polylang --version=3.8.10 --activate >/dev/null'
assert s.count(installer)==1
s=s.replace(installer,'for attempt in 1 2 3; do '+installer+' && break; test "$attempt" -lt 3 || exit 1; sleep 3; done')
assert s.count('node lane/warm-admin.cjs')==1
s=s.replace('node lane/warm-admin.cjs','true')
marker='if [ "'+'$'+'{VF_REVIEW_ONLY_STATE:-0}" = "1" ];then'
assert s.count(marker)==1
s=s.split(marker)[0]+'''
docker cp provider/vf-tools-theme_V1.35.165.zip "$WP:/tmp/theme165.zip"
docker cp provider/vf-tools-theme_V1.35.166.zip "$WP:/tmp/theme166.zip"
version_check(){
  test "$(cli theme get vf-tools-theme --field=version)" = "$1"
  test "$(cli plugin get vf-tool-m3u8 --field=version)" = 1.25.94
  echo "NATIVE_VERSION_PASS=$1"
}
version_check 1.35.166
cli theme install /tmp/theme165.zip --force >/dev/null
version_check 1.35.165
cli eval-file /tmp/snapshot.php > proof/lifecycle-before.json
cli theme install /tmp/theme166.zip --force >/dev/null
version_check 1.35.166
cli eval-file /tmp/snapshot.php > proof/lifecycle-after-upgrade.json
cmp proof/lifecycle-before.json proof/lifecycle-after-upgrade.json
cli theme install /tmp/theme165.zip --force >/dev/null
version_check 1.35.165
cli theme install /tmp/theme166.zip --force >/dev/null
version_check 1.35.166
cli theme install /tmp/theme166.zip --force >/dev/null
version_check 1.35.166
cli eval-file /tmp/snapshot.php > proof/lifecycle-after-repeat.json
cmp proof/lifecycle-before.json proof/lifecycle-after-repeat.json
echo NATIVE_UPGRADE_ROLLBACK_REPEAT_DATA_PRESERVATION_PASS
NODE_PATH="$PWD/node_modules" node lane/render166-browser.cjs
cli eval-file /tmp/snapshot.php > proof/lifecycle-after-browser.json
python3 - <<'PYDATA'
import json
from pathlib import Path
a=json.loads(Path('proof/lifecycle-before.json').read_text())
b=json.loads(Path('proof/lifecycle-after-browser.json').read_text())
changed=[k for k in a['sections'] if a['sections'][k]!=b['sections'][k]]
assert set(changed)<={'vf_theme_renderer'},changed
print('NATIVE_RENDERER_ONLY_WRITE_SCOPE_PASS',changed)
PYDATA
'''
Path('lane/native-render166.sh').write_text(s)
