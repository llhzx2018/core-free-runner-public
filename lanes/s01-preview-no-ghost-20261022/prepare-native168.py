from pathlib import Path
s=Path('lane/native.sh').read_text()
s=s.replace('provider/vf-tools-m3u8_V1.25.91.zip','provider/vf-tools-m3u8_V1.25.94.zip')
installer='cli plugin install polylang --version=3.8.10 --activate >/dev/null'
assert s.count(installer)==1
s=s.replace(installer,'for i in 1 2 3; do '+installer+' && break; test "$i" -lt 3 || exit 1; sleep 3; done')
s=s.replace('node lane/warm-admin.cjs','true')
marker='if [ "'+'$'+'{VF_REVIEW_ONLY_STATE:-0}" = "1" ];then'
assert s.count(marker)==1
s=s.split(marker)[0]+'''
docker cp provider/vf-tools-theme_V1.35.167.zip "$WP:/tmp/old167.zip"
docker cp provider/vf-tools-theme_V1.35.168.zip "$WP:/tmp/new168.zip"
check_version(){
 test "$(cli theme get vf-tools-theme --field=version)" = "$1"
 test "$(cli plugin get vf-tool-m3u8 --field=version)" = 1.25.94
 echo "NATIVE_THEME168_VERSION_PASS=$1"
}
check_version 1.35.168
cli theme install /tmp/old167.zip --force >/dev/null
check_version 1.35.167
cli eval-file /tmp/snapshot.php > proof/old-state.json
cli theme install /tmp/new168.zip --force >/dev/null
check_version 1.35.168
cli eval-file /tmp/snapshot.php > proof/upgraded-state.json
cmp proof/old-state.json proof/upgraded-state.json
cli theme install /tmp/old167.zip --force >/dev/null
check_version 1.35.167
cli theme install /tmp/new168.zip --force >/dev/null
check_version 1.35.168
cli theme install /tmp/new168.zip --force >/dev/null
check_version 1.35.168
cli eval-file /tmp/snapshot.php > proof/repeated-state.json
cmp proof/old-state.json proof/repeated-state.json
echo "NATIVE_167_TO_168_ROLLBACK_REPEAT_PROTECTED_DATA_PASS"
'''
Path('lane/native-preview168.sh').write_text(s)
