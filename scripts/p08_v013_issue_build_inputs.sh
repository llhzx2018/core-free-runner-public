#!/usr/bin/env bash
# P08 v013 source-exact official package preparation; no release/channel writes.
set -Eeuo pipefail
test "$GITHUB_ACTIONS" = true
test "$P08_ISOLATED_INSTALL_TEST" = YES
test "$(id -u)" != 0
test "$(git -C target rev-parse HEAD)" = 8b385fecd132a02ac79f5b67e670783e98997c3e
test "$(git -C target rev-parse HEAD^{tree})" = 32b8722fbfaff3e988e69693510be0c1e6df8bba
test "$(git -C old rev-parse HEAD)" = dac7bc1d5410c077f32e522eb5740537f618ef9d
test "$(git -C gov rev-parse HEAD)" = 74c4090c93cea7ef6a55c7b17d39515e7ca8710c
test "$(cat target/VERSION)" = 0.1.13
grep -Fq '| skill-release | V3.20 |' gov/CURRENT.md
grep -q '## RP-07U' target/docs/authority/ACCEPTANCE_MATRIX.md
test -z "$(git -C target status --porcelain --untracked-files=all)"
tmp="$RUNNER_TEMP/p08-v013-immutable-issue"
site="$RUNNER_TEMP/p08-r129-real-issued-r131-r155-sqlite-issue"
test ! -e "$tmp" && test ! -e "$site"
mkdir -m 700 "$tmp" "$site"
set +x
while read -r id file expected; do
 curl -fsSL --retry 2 --max-time 100 -H "Authorization: Bearer $READ_TOKEN" \
  -H 'Accept: application/octet-stream' -H 'X-GitHub-Api-Version: 2022-11-28' \
  "https://api.github.com/repos/llhzx2018/vf-adops/releases/assets/$id" \
  -o "$tmp/$file"
 test "$(sha256sum "$tmp/$file" | cut -d' ' -f1)" = "$expected"
done <<'ASSETS'
763106581 v019-full.zip 91a37e0116066bf0df32341cc0708b8b52eaaa998ea556a920b72ff3863a9232
763937408 v010-update.zip 3a9ceae0d6b928bc6871b8db900be421728be24c4500dc1c661463917ba4a827
766931637 v012-update.zip 9a80f880a9cfbd22efce35383ee933766100e936fc6f99f89272237dd4e0ab56
ASSETS
unset READ_TOKEN
echo P08_V013_PREVIOUS_ISSUED_ASSET_BYTES=VERIFIED
unzip -q "$tmp/v019-full.zip" -d "$site"
mkdir -p "$site/tests/compatibility"
cp old/tests/test_install_sqlite_e2e.php "$site/tests/"
cp old/tests/compatibility/r101_complete_schema.php "$site/tests/compatibility/"
php "$site/tests/test_install_sqlite_e2e.php"
test "$(readlink "$site/current")" = releases/b77c7e8563d93255f5f4a60bb8c5736a994d8151
token="$site/storage/app/private/adops/upgrade/github-read-token"
test -f "$token" && test ! -L "$token" && test "$(stat -c %a "$token")" = 600
test "$(cat "$token")" = "github_pat_$(printf 's%.0s' {1..42})"
rm -- "$token"
python3 - "$tmp/v019-to-v010.php" <<'PY'
from pathlib import Path
import sys
s=Path('old/tests/compatibility/r154_clean_full_to_two_native_atomic_cycles.php').read_text()
items=[
("'0.1.5':($phase==='recover'?'0.1.7':'0.1.6')","'0.1.9':($phase==='recover'?'0.1.10':'0.1.9')",1),
("trim((string)file_get_contents($site.'/current/VERSION'))!=='0.1.6'","trim((string)file_get_contents($site.'/current/VERSION'))!=='0.1.10'",1),
("'target_version'=>'0.1.7'","'target_version'=>'0.1.10'",1),
("str_repeat('1',40)","'ef78dcb21117c822e2756360280f2418f794704f'",1),
("str_repeat('2',40)","'ef78dcb21117c822e2756360280f2418f794704f'",4)]
for a,b,n in items:
 assert s.count(a)==n,(a,s.count(a))
 s=s.replace(a,b)
Path(sys.argv[1]).write_text(s)
PY
php -l "$tmp/v019-to-v010.php"
P08_R154_NATIVE=YES php "$tmp/v019-to-v010.php" first "$site" \
 b77c7e8563d93255f5f4a60bb8c5736a994d8151 "$tmp/v010-update.zip"
test "$(readlink "$site/current")" = releases/ef78dcb21117c822e2756360280f2418f794704f
test "$(sha256sum "$site/current/FULL_MANIFEST.json" | cut -d' ' -f1)" = \
 efebfefde3115864dba71c2e56fedae2f7ada8ad4064010473d716b689f67fe9
printf 'P08_SYNTHETIC_ONLY\n' > "$site/storage/app/private/adops/r202-media-proof.bin"
chmod 0600 "$site/storage/app/private/adops/r202-media-proof.bin"
P08_R205_CHAINED=YES php old/tests/compatibility/r205_chained_atomic_apply.php \
 "$site" ef78dcb21117c822e2756360280f2418f794704f \
 efebfefde3115864dba71c2e56fedae2f7ada8ad4064010473d716b689f67fe9 \
 "$tmp/v012-update.zip" dac7bc1d5410c077f32e522eb5740537f618ef9d 0.1.12
test "$(readlink "$site/current")" = releases/dac7bc1d5410c077f32e522eb5740537f618ef9d
installed="$(sha256sum "$site/current/FULL_MANIFEST.json" | cut -d' ' -f1)"
test "$installed" = 607b3a02a20021c0747d42440497b7e9e3e0fe39040869f475ba22f9f19437e9
test "$installed" != 4df28b7a9dcfbaf4c0bec18009955fe1b0c7764ccfe94f4257ae2ca0dc3794cc
echo P08_V013_PREVIOUS_AUTHENTIC_607B_SOURCE=VERIFIED

npm ci --prefix target --ignore-scripts --no-fund --no-audit
npm run typecheck --prefix target
npm run build --prefix target
npm run test:unit --prefix target
composer --working-dir=target install --no-dev --no-scripts --prefer-dist --no-interaction --no-progress --optimize-autoloader
php target/tests/test_owner_next_release_gateway.php
php target/tests/test_owner_future_atomic_status.php
python3 -B target/scripts/check_stack_contract.py --phase full --root target
(
 cd target
 git diff --exit-code && git diff --cached --exit-code
 for f in $(git ls-files --others --exclude-standard); do
  case "$f" in
    bootstrap/cache/packages.php|bootstrap/cache/services.php) test -f "$f" && ! test -L "$f" && rm -- "$f" ;;
    *) echo P08_V013_UNEXPECTED_SOURCE_GENERATION; exit 24 ;;
  esac
 done
 test -z "$(git status --porcelain --untracked-files=all)"
)
for part in first second; do
 python3 -B target/scripts/build_full.py \
  --source "$GITHUB_WORKSPACE/target" --output "$tmp/full-$part.zip" \
  --version 0.1.13 --source-sha 8b385fecd132a02ac79f5b67e670783e98997c3e \
  --governance-root "$GITHUB_WORKSPACE/gov"
 python3 -B target/scripts/build_atomic.py \
  --source "$GITHUB_WORKSPACE/target" --output "$tmp/update-$part.zip" \
  --source-version 0.1.12 --source-sha dac7bc1d5410c077f32e522eb5740537f618ef9d \
  --source-full-manifest-sha256 "$installed" \
  --previous-full-manifest "$site/current/FULL_MANIFEST.json" \
  --target-version 0.1.13 --target-sha 8b385fecd132a02ac79f5b67e670783e98997c3e
done
cmp "$tmp/full-first.zip" "$tmp/full-second.zip"
cmp "$tmp/update-first.zip" "$tmp/update-second.zip"
test "$(sha256sum "$tmp/full-first.zip" | cut -d' ' -f1)" = \
 f8075f065d1413c984f80ef7531242cfc894bf272e90f6d89282074f6617c1ec
test "$(sha256sum "$tmp/update-first.zip" | cut -d' ' -f1)" = \
 6982a7b44873ac825e6c252b309d8f11a9ade67e67f5b8b6467538a46ef71b2a
mv "$tmp/full-first.zip" "$tmp/VF_AdOps_V0.1.13_FULL.zip"
mv "$tmp/update-first.zip" "$tmp/VF_AdOps_V0.1.13_UPDATE.zip"
rm "$tmp/full-second.zip" "$tmp/update-second.zip"
unzip -tqq "$tmp/VF_AdOps_V0.1.13_FULL.zip"
unzip -tqq "$tmp/VF_AdOps_V0.1.13_UPDATE.zip"
test -z "$(git -C target status --porcelain --untracked-files=all)"
echo P08_V013_OFFICIAL_INPUTS_DOUBLE_BUILT_FINAL_MAIN=PASS
cat > "$tmp/RELEASE_NOTES.md" <<'NOTES'
# VF AdOps v0.1.13 — 一键升级安全状态修复

本版修复历史升级任务归档、后台读取状态异常和系统更新页同步。管理员主动检查更新，再点击一次“一键安全升级”启动旧版 PHP 后台的原生备份、验证和 Atomic 切换，页面打开不会自动检查、下载或执行更新。

**本次 Atomic 仅允许已经真实验证的 v0.1.12 旧版来源：** 官方 v0.1.9 FULL → v0.1.10 Atomic → v0.1.12 Atomic，源 SHA dac7bc1d5410c077f32e522eb5740537f618ef9d，当前 FULL_MANIFEST SHA256 必须为 607b3a02a20021c0747d42440497b7e9e3e0fe39040869f475ba22f9f19437e9。全新 v0.1.12 FULL 的 4df28b... 清单以及其它未知来源**不受本次 Atomic 更新频道支持**；不准绕过身份检查，不使用 FULL 覆盖现有网站。

源代码、三数据库、旧版真实来源、独立备份与回滚/SIGKILL、HTTPS Chromium、13 域安全门禁已按 P08 RP-07U 和 GOV-DOC Mode U 验证。本人 Preview/Real Use 后置，仍需 Owner 手工升级后验收。Production、CloudPanel、SSL、DNS 和数据库不自动修改。
NOTES
python3 - "$tmp" <<'PY'
from pathlib import Path
import hashlib,json,sys
p=Path(sys.argv[1])
h=lambda n:hashlib.sha256((p/n).read_bytes()).hexdigest()
full="VF_AdOps_V0.1.13_FULL.zip";update="VF_AdOps_V0.1.13_UPDATE.zip"
prov=dict(project_id="P08",repository="llhzx2018/vf-adops",
 source_version="0.1.12",source_sha="dac7bc1d5410c077f32e522eb5740537f618ef9d",
 source_full_manifest_sha256="607b3a02a20021c0747d42440497b7e9e3e0fe39040869f475ba22f9f19437e9",
 target_version="0.1.13",target_sha="8b385fecd132a02ac79f5b67e670783e98997c3e",
 target_tree_sha="32b8722fbfaff3e988e69693510be0c1e6df8bba",
 governance_sha="74c4090c93cea7ef6a55c7b17d39515e7ca8710c",
 full_sha256=h(full),atomic_sha256=h(update),schema_changes=False,data_included=False,
 schema_from="1.1",schema_to="1.1",backup_required=True,
 rollback_supported=True,production_auto_apply=False,
 native_three_db_gate_run_id=44666251399,
 owner_preview="POST_RELEASE_REQUIRED_NOT_PASS",
 owner_real_use="POST_OWNER_MANUAL_PRODUCTION_REQUIRED_NOT_PASS")
(p/"RELEASE_PROVENANCE.json").write_text(json.dumps(prov,sort_keys=True,indent=2)+"\n")
names=[full,update,"RELEASE_PROVENANCE.json","RELEASE_NOTES.md"]
(p/"SHA256SUMS").write_text("".join(h(n)+"  "+n+"\n" for n in names))
print("P08_V013_OFFICIAL_PROVENANCE_AND_SHA256SUMS=PASS")
PY
