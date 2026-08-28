#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE='867e3387b8efb70398287d05fd3652540efa77c8'
CANDIDATE_TREE='5985dab8ee071c881fd1e425864ed363e3bdc905'
SOURCE_COMMIT='6e7d30e6ea0c8f5f70076a69b0d1e6fb9be620b2'
VERSION='2.24.0'
SOURCE_VERSION='2.23.0'
SCHEMA='2026082801'
SOURCE_SCHEMA='2026082801'
RELEASE_EXACT_GATE='33155682269'
OUT='/tmp/p01-v2240-artifacts'
BUILD_OUT='/tmp/p01-v222-artifacts'

ROOT="${GITHUB_WORKSPACE:-$(pwd)}"
cd "$ROOT"
test "$(git -C candidate rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C candidate rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C production rev-parse HEAD)" = "$SOURCE_COMMIT"
test "$(tr -d '\r\n' < candidate/VERSION)" = "$VERSION"
test "$(tr -d '\r\n' < production/VERSION)" = "$SOURCE_VERSION"
find candidate/src -type f -name '*.php' -print0 | xargs -0 -r -n1 php -l >/dev/null
find candidate/src -type f -name '*.js' -print0 | xargs -0 -r -n1 node --check >/dev/null
php candidate/tests/unit/system_baseline_human_ui_contract.php

echo 'P01_V2240_SOURCE_FENCE=PASS'
rm -rf oldrunner proven "$OUT" "$BUILD_OUT" /tmp/p01-v2240-builder.py
git clone -q --depth 1 --branch task/p01-v222-multi-surface-gate-20260828 https://github.com/llhzx2018/core-free-runner-public.git oldrunner
git clone -q --depth 1 --branch agent/p01-22121-formal-artifact-gate-20260819 https://github.com/llhzx2018/core-free-runner-public.git proven
cp oldrunner/scripts/p01-build-v222-schema-release.py /tmp/p01-v2240-builder.py
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/p01-v2240-builder.py')
s=p.read_text(encoding='utf-8')
pairs=[
("VERSION='2.22.0'; SOURCE_VERSION='2.21.25'; SCHEMA='2026082801'; SOURCE_SCHEMA='2026080902'","VERSION='2.24.0'; SOURCE_VERSION='2.23.0'; SCHEMA='2026082801'; SOURCE_SCHEMA='2026082801'"),
("CANDIDATE='2c159b4b7ecfc03e79eff2e6103f7e2c768ded08'","CANDIDATE='867e3387b8efb70398287d05fd3652540efa77c8'"),
("CANDIDATE_TREE='9116fe6cfc24d9a5a0a7070fb6af3f31bb079392'","CANDIDATE_TREE='5985dab8ee071c881fd1e425864ed363e3bdc905'"),
("SOURCE='6bc09cd152210183972dcb3f2c361eb65a4cadab'","SOURCE='6e7d30e6ea0c8f5f70076a69b0d1e6fb9be620b2'"),
("'schema_change':True,'schema_migrations':['2026082801_v222_multi_surface.php']","'schema_change':False,'schema_migrations':[]"),
("public const SOURCE_VERSION='2.21.25';\\n    public const TARGET_VERSION='2.22.0';\\n    public const SOURCE_SCHEMA='2026080902';\\n    public const TARGET_SCHEMA='2026082801';","public const SOURCE_VERSION='2.23.0';\\n    public const TARGET_VERSION='2.24.0';\\n    public const SOURCE_SCHEMA='2026082801';\\n    public const TARGET_SCHEMA='2026082801';"),
("public const SOURCE_SCHEMA='2026080902';","public const SOURCE_SCHEMA='2026082801';"),
("'schema_migration':'2026082801_v222_multi_surface.php'","'schema_migration':None"),
("P01-V2.22.0-ARTIFACT-GATE.json","P01-V2.24.0-ARTIFACT-GATE.json")
]
for old,new in pairs:
    n=s.count(old)
    if n < 1:
        raise SystemExit('missing builder anchor: '+old[:100])
    s=s.replace(old,new)
p.write_text(s,encoding='utf-8',newline='\n')
PY
python3 /tmp/p01-v2240-builder.py | tee /tmp/p01-v2240-build.log
mkdir -p "$OUT"
for f in \
  "$BUILD_OUT/VF-Start-V2.24.0-FULL.zip" \
  "$BUILD_OUT/VF-Start-V2.24.0-UPDATE.zip" \
  "$BUILD_OUT/server-update-v2.24.0-repair.php" \
  "$BUILD_OUT/P01-V2.24.0-ARTIFACT-GATE.json"; do
  test -f "$f"; cp "$f" "$OUT/"
done
php -l "$OUT/server-update-v2.24.0-repair.php" >/dev/null
php "$OUT/server-update-v2.24.0-repair.php" --self-test | tee "$OUT/atomic-self-test.json"
jq -e '.ok==true and .global_barrier==true and .interruption_recovery==true' "$OUT/atomic-self-test.json" >/dev/null
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
src=Path('/tmp/p01-v2240-artifacts/server-update-v2.24.0-repair.php')
out=Path('/tmp/p01-v2240-artifacts/VF_Start_V2.24.0_UPDATE.zip')
info=ZipInfo('repair-v2.24.0.php',(1980,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;info.create_system=3;info.external_attr=(0o100640<<16)
with ZipFile(out,'w',compression=ZIP_DEFLATED,compresslevel=9) as z:z.writestr(info,src.read_bytes())
PY
unzip -t "$OUT/VF_Start_V2.24.0_UPDATE.zip" >/dev/null
test "$(unzip -Z1 "$OUT/VF_Start_V2.24.0_UPDATE.zip" | wc -l)" -eq 1
unzip -Z1 "$OUT/VF_Start_V2.24.0_UPDATE.zip" | grep -Fxq 'repair-v2.24.0.php'
cmp -s "$OUT/server-update-v2.24.0-repair.php" <(unzip -p "$OUT/VF_Start_V2.24.0_UPDATE.zip" repair-v2.24.0.php)

echo 'P01_V2240_BUILD_AND_ATOMIC_SELFTEST=PASS'

# Fresh FULL install.
FULL_ROOT=/tmp/p01-v2240-full
FULL_COOKIE=/tmp/p01-v2240-full.cookies
FULL_ADMIN=/tmp/p01-v2240-full-admin.cookies
rm -rf "$FULL_ROOT" "$FULL_COOKIE" "$FULL_ADMIN"
mkdir -p "$FULL_ROOT"
unzip -q "$OUT/VF-Start-V2.24.0-FULL.zip" -d "$FULL_ROOT"
test "$(tr -d '\r\n' < "$FULL_ROOT/VERSION.txt")" = "$VERSION"
php -S 127.0.0.1:18294 -t "$FULL_ROOT" >/tmp/p01-v2240-full.log 2>&1 & FULL_PID=$!
READY=0
for i in $(seq 1 30); do if curl -fsS http://127.0.0.1:18294/setup.php -o /tmp/p01-v2240-full-setup.html; then READY=1; break; fi; sleep 1; done
test "$READY" = 1
curl -fsS -c "$FULL_COOKIE" -b "$FULL_COOKIE" http://127.0.0.1:18294/setup.php -o /tmp/p01-v2240-full-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v2240-full-setup.html',encoding='utf-8').read();print(re.search(r'name="setup_csrf"\s+value="([^"]+)"',s).group(1))
PY
)
curl -fsS -c "$FULL_COOKIE" -b "$FULL_COOKIE" -X POST http://127.0.0.1:18294/setup.php --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=V2240 Full' --data-urlencode 'admin_password=P01V2240!Full' --data-urlencode 'admin_password_confirm=P01V2240!Full' >/tmp/p01-v2240-full-post.html
php "$FULL_ROOT/cli/verify.php" | grep -Fx 'VERIFY_PASS=YES'
php "$FULL_ROOT/cli/surface-verify.php" | tee /tmp/p01-v2240-full-surface.txt
grep -Fx 'MULTI_SURFACE_PASS=YES' /tmp/p01-v2240-full-surface.txt
grep -Fx "WORKING_SCHEMA=$SCHEMA" /tmp/p01-v2240-full-surface.txt
php "$FULL_ROOT/cli/baseline-verify.php" | tee /tmp/p01-v2240-full-base.txt
grep -Fx 'BASELINE_CORE_PASS=YES' /tmp/p01-v2240-full-base.txt
grep -Fx 'DRIFT_COUNT=0' /tmp/p01-v2240-full-base.txt
grep -Fx 'UNKNOWN_COUNT=0' /tmp/p01-v2240-full-base.txt
curl -fsS -c "$FULL_ADMIN" -b "$FULL_ADMIN" -H 'Content-Type: application/json' -X POST 'http://127.0.0.1:18294/api.php?action=login' --data '{"password":"P01V2240!Full"}' | jq -e '.ok==true' >/dev/null
curl -fsS -c "$FULL_ADMIN" -b "$FULL_ADMIN" http://127.0.0.1:18294/system-baseline.php -o /tmp/p01-v2240-full-baseline-ui.html
grep -Eq '系统关键规则正常|有项目需要你关注' /tmp/p01-v2240-full-baseline-ui.html
grep -F '你需要关注' /tmp/p01-v2240-full-baseline-ui.html >/dev/null
grep -F '技术详情（给开发 / 排障使用）' /tmp/p01-v2240-full-baseline-ui.html >/dev/null
grep -F '个人单管理员模式' /tmp/p01-v2240-full-baseline-ui.html >/dev/null
curl -fsS -c "$FULL_ADMIN" -b "$FULL_ADMIN" http://127.0.0.1:18294/surfaces.php | grep -F 'vf-app-sidebar' >/dev/null
curl -fsS -c "$FULL_ADMIN" -b "$FULL_ADMIN" http://127.0.0.1:18294/channels.php | grep -F 'vf-app-sidebar' >/dev/null
curl -fsS -c "$FULL_ADMIN" -b "$FULL_ADMIN" http://127.0.0.1:18294/watch.php | grep -F 'vf-app-sidebar' >/dev/null
kill "$FULL_PID" 2>/dev/null || true

echo 'P01_V2240_FULL_FRESH_INSTALL=PASS'

# Real V2.23.0 updater -> V2.24.0, with business-data preservation.
OWNER=/tmp/p01-v2240-owner
OWNER_COOKIE=/tmp/p01-v2240-owner.cookies
rm -rf "$OWNER" "$OWNER_COOKIE"
cp -a production/src "$OWNER"
php -S 127.0.0.1:18295 -t "$OWNER" >/tmp/p01-v2240-owner.log 2>&1 & OWNER_PID=$!
READY=0
for i in $(seq 1 30); do if curl -fsS http://127.0.0.1:18295/setup.php -o /tmp/p01-v2240-owner-setup.html; then READY=1; break; fi; sleep 1; done
test "$READY" = 1
curl -fsS -c "$OWNER_COOKIE" -b "$OWNER_COOKIE" http://127.0.0.1:18295/setup.php -o /tmp/p01-v2240-owner-setup.html
CSRF=$(python3 - <<'PY'
import re
s=open('/tmp/p01-v2240-owner-setup.html',encoding='utf-8').read();print(re.search(r'name="setup_csrf"\s+value="([^"]+)"',s).group(1))
PY
)
curl -fsS -c "$OWNER_COOKIE" -b "$OWNER_COOKIE" -X POST http://127.0.0.1:18295/setup.php --data-urlencode "setup_csrf=$CSRF" --data-urlencode 'site_title=V2240 Owner' --data-urlencode 'admin_password=P01V2240!Owner' --data-urlencode 'admin_password_confirm=P01V2240!Owner' >/tmp/p01-v2240-owner-post.html
kill "$OWNER_PID" 2>/dev/null || true
cat >/tmp/p01-v2240-seed.php <<'PHP'
<?php
require '/tmp/p01-v2240-owner/app/bootstrap.php';
$r=new VfRepository(vf_db());
$c=$r->createCategory(['name'=>'V2240 Sentinel','description'=>'keep','is_private'=>false]);
$l=$r->saveLink(null,['category_id'=>$c,'title'=>'V2240 Keep Link','url'=>'https://example.com/v2240-keep','description'=>'keep','is_private'=>false],'manual');
file_put_contents('/tmp/p01-v2240-link-id',(string)$l['id']);
PHP
php /tmp/p01-v2240-seed.php
LEGACY_SHA=$(sha256sum "$OUT/VF_Start_V2.24.0_UPDATE.zip" | awk '{print $1}')
LEGACY_BYTES=$(stat -c %s "$OUT/VF_Start_V2.24.0_UPDATE.zip")
cat > "$OUT/manifest.json" <<JSON
{"schema_version":"1.0","project_id":"P01","component_id":"APP","enabled":true,"target_version":"2.24.0","update_type":"ATOMIC","from_versions":["2.23.0"],"schema_from":"2026082801","schema_to":"2026082801","repository":"llhzx2018/vf-start","release_tag":"v2.24.0","asset_name":"VF_Start_V2.24.0_UPDATE.zip","asset_bytes":${LEGACY_BYTES},"asset_sha256":"${LEGACY_SHA}","release_id":378293470,"release_identity":"v2.24.0@867e3387b8efb70398287d05fd3652540efa77c8","backup_required":true,"rollback_supported":true,"released_at":"2026-08-28T08:00:00Z","minimum_php":"8.0.0"}
JSON
cat >/tmp/p01-v2240-update.php <<'PHP'
<?php
require '/tmp/p01-v2240-owner/app/bootstrap.php';
$m=json_decode(file_get_contents('/tmp/p01-v2240-artifacts/manifest.json'),true,512,JSON_THROW_ON_ERROR);
$asset='/tmp/p01-v2240-artifacts/VF_Start_V2.24.0_UPDATE.zip';
$u=new VfUpdateManager(vf_db(),[
  'manifest_fetcher'=>fn()=>$m,
  'asset_downloader'=>function(array $x,string $dest)use($asset){if(!copy($asset,$dest))throw new RuntimeException('copy failed');return ['size'=>filesize($dest)];},
  'backup_creator'=>fn(string $f,string $t)=>['backup_key'=>'v2240-'.$f.'-'.$t],
]);
$c=$u->check(true);
if(empty($c['ok'])||empty($c['can_update'])||($c['latest_version']??'')!=='2.24.0')throw new RuntimeException('check failed: '.json_encode($c,JSON_UNESCAPED_UNICODE));
$p=$u->prepare();
if(empty($p['ok'])||($p['from_version']??'')!=='2.23.0'||($p['to_version']??'')!=='2.24.0')throw new RuntimeException('prepare failed');
$i=$u->install((string)$p['operation_id']);
if(empty($i['ok'])||empty($i['updated'])||($i['to_version']??'')!=='2.24.0')throw new RuntimeException('install failed');
echo "P01_V2240_REAL_UPDATER_INSTALL=PASS\n";
PHP
php /tmp/p01-v2240-update.php

test "$(tr -d '\r\n' < "$OWNER/VERSION.txt")" = "$VERSION"
php "$OWNER/cli/verify.php" | grep -Fx 'VERIFY_PASS=YES'
php "$OWNER/cli/surface-verify.php" | tee /tmp/p01-v2240-owner-surface.txt
grep -Fx 'MULTI_SURFACE_PASS=YES' /tmp/p01-v2240-owner-surface.txt
grep -Fx "WORKING_SCHEMA=$SCHEMA" /tmp/p01-v2240-owner-surface.txt
php "$OWNER/cli/baseline-verify.php" | tee /tmp/p01-v2240-owner-base.txt
grep -Fx 'BASELINE_CORE_PASS=YES' /tmp/p01-v2240-owner-base.txt
grep -Fx 'DRIFT_COUNT=0' /tmp/p01-v2240-owner-base.txt
grep -Fx 'UNKNOWN_COUNT=0' /tmp/p01-v2240-owner-base.txt
cat >/tmp/p01-v2240-verify-sentinel.php <<'PHP'
<?php
require '/tmp/p01-v2240-owner/app/bootstrap.php';
$id=(int)file_get_contents('/tmp/p01-v2240-link-id');
$stmt=vf_db()->prepare("SELECT title,url FROM links WHERE id=? AND lifecycle_state='active'");$stmt->execute([$id]);$row=$stmt->fetch(PDO::FETCH_ASSOC);
if(!$row||$row['title']!=='V2240 Keep Link'||$row['url']!=='https://example.com/v2240-keep')throw new RuntimeException('sentinel missing');
if(strtolower((string)vf_db()->query('PRAGMA integrity_check')->fetchColumn())!=='ok')throw new RuntimeException('integrity');
if(count(vf_db()->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC))!==0)throw new RuntimeException('foreign key');
echo "P01_V2240_DATA_PRESERVATION=PASS\n";
PHP
php /tmp/p01-v2240-verify-sentinel.php

echo 'P01_V2240_REAL_V230_TO_V2240_UPGRADE=PASS'

FULL_SHA=$(sha256sum "$OUT/VF-Start-V2.24.0-FULL.zip"|awk '{print $1}')
UPDATE_SHA=$(sha256sum "$OUT/VF-Start-V2.24.0-UPDATE.zip"|awk '{print $1}')
REPAIR_SHA=$(sha256sum "$OUT/server-update-v2.24.0-repair.php"|awk '{print $1}')
cat > "$OUT/P01-V2.24.0-RELEASE-GATE.json" <<JSON
{"project_id":"P01","version":"2.24.0","source_version":"2.23.0","candidate":"$CANDIDATE","candidate_tree":"$CANDIDATE_TREE","schema":"$SCHEMA","schema_change":false,"release_exact_source_gate":$RELEASE_EXACT_GATE,"full_sha256":"$FULL_SHA","update_sha256":"$UPDATE_SHA","legacy_sha256":"$LEGACY_SHA","legacy_bytes":$LEGACY_BYTES,"legacy_inner":"repair-v2.24.0.php","online_upgrade":"PASS","owner_readable_system_baseline":"PASS","common_baseline":"PASS","status":"PASS"}
JSON
printf '%s  %s\n' \
  "$FULL_SHA" 'VF-Start-V2.24.0-FULL.zip' \
  "$UPDATE_SHA" 'VF-Start-V2.24.0-UPDATE.zip' \
  "$LEGACY_SHA" 'VF_Start_V2.24.0_UPDATE.zip' \
  "$REPAIR_SHA" 'server-update-v2.24.0-repair.php' > "$OUT/SHA256SUMS.txt"

jq -e '.status=="PASS" and .version=="2.24.0" and .source_version=="2.23.0" and .schema_change==false and .online_upgrade=="PASS" and .owner_readable_system_baseline=="PASS"' "$OUT/P01-V2.24.0-RELEASE-GATE.json" >/dev/null
cd "$OUT"
sha256sum -c SHA256SUMS.txt

echo "P01_V2240_LEGACY_SHA=$LEGACY_SHA"
echo "P01_V2240_LEGACY_BYTES=$LEGACY_BYTES"
echo 'P01_V2240_FORMAL_ARTIFACT_MACHINE=PASS'
echo 'PRODUCTION=NO'
