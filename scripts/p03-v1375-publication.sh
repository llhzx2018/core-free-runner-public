#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo P03_V1375_PUBLICATION_ERROR_LINE=$LINENO' ERR
: "${GH_TOKEN:?}"
REPO='llhzx2018/vf-forge'
TAG='v1.37.5'
SOURCE='f2865c97f80bd8052dd47d76ef08c626c044e669'
SOURCE_TREE='08775c0afa9732027898ceedfc33fd7f2019ae1f'
MERGED_MAIN='fdacc51c5ee652144490cfd963f57d2198dceb65'
FORMAL_RUN=33160320928
FORMAL_JOB=98812936218
ARTIFACT='P03-V1.37.5-HUMAN-BASELINE-FORMAL-RELEASE-SET'
WORK="$RUNNER_TEMP/p03-v1375-publication"
rm -rf "$WORK"; mkdir -p "$WORK/release" "$WORK/evidence"

printf '\n== Publication source fences ==\n'
test "$(gh api repos/$REPO/branches/main --jq .commit.sha)" = "$MERGED_MAIN"
test "$(gh api repos/$REPO/git/commits/$MERGED_MAIN --jq .tree.sha)" = "$SOURCE_TREE"
test "$(gh api repos/$REPO/git/commits/$SOURCE --jq .tree.sha)" = "$SOURCE_TREE"
gh api repos/llhzx2018/core-free-runner-public/actions/runs/$FORMAL_RUN | jq -e '.status=="completed" and .conclusion=="success"' >/dev/null
if gh api "repos/$REPO/git/ref/tags/$TAG" >/dev/null 2>&1; then echo 'v1.37.5 tag already exists before publication'; exit 1; fi
if gh api "repos/$REPO/releases/tags/$TAG" >/dev/null 2>&1; then echo 'v1.37.5 release already exists before publication'; exit 1; fi
echo P03_V1375_PUBLICATION_SOURCE_FENCE=PASS

printf '\n== Download exact PASS artifact ==\n'
gh run download "$FORMAL_RUN" -R llhzx2018/core-free-runner-public -n "$ARTIFACT" -D "$WORK/formal"
test -f "$WORK/formal/VF_Forge_V1.37.5_Atomic_Upgrade.zip"
test -f "$WORK/formal/VF_Forge_V1.37.5_FULL.zip"
test -f "$WORK/formal/P03_V1.37.5_RELEASE_MANIFEST.json"
test -f "$WORK/formal/RELEASE_SHA256SUMS.txt"
(cd "$WORK/formal" && sha256sum -c RELEASE_SHA256SUMS.txt)
python3 - "$WORK/formal/P03_V1.37.5_RELEASE_MANIFEST.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['schema']=='vf-p03-release/1' and m['project_id']=='P03'
assert m['version']=='1.37.5' and m['source_version']=='1.37.4' and m['schema_version']==30
assert m['candidate_source_sha']=='f2865c97f80bd8052dd47d76ef08c626c044e669'
assert m['production_changed'] is False
PY
cp "$WORK/formal/VF_Forge_V1.37.5_Atomic_Upgrade.zip" "$WORK/release/VF_Forge_V1.37.5_UPDATE.zip"
cp "$WORK/formal/VF_Forge_V1.37.5_FULL.zip" "$WORK/release/VF_Forge_V1.37.5_FULL.zip"
test "$(sha256sum "$WORK/formal/VF_Forge_V1.37.5_Atomic_Upgrade.zip"|awk '{print $1}')" = "$(sha256sum "$WORK/release/VF_Forge_V1.37.5_UPDATE.zip"|awk '{print $1}')"
(cd "$WORK/release" && sha256sum VF_Forge_V1.37.5_UPDATE.zip VF_Forge_V1.37.5_FULL.zip > RELEASE_SHA256SUMS.txt && sha256sum -c RELEASE_SHA256SUMS.txt)
echo P03_V1375_PUBLICATION_ARTIFACT_FENCE=PASS

printf '\n== Exact tag and GitHub Release ==\n'
gh api --method POST "repos/$REPO/git/refs" -f ref="refs/tags/$TAG" -f sha="$SOURCE" >/dev/null
test "$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq .object.sha)" = "$SOURCE"
cat >"$WORK/release-notes.md" <<'EOF'
# P03 · VF Forge V1.37.5

Common Product Baseline V2 后台可见化与人类可读化发布。

- 设置中心正式提供：系统信息 / 系统基线 / 在线升级 / 备份与恢复 / 运行健康五个统一维护入口。
- 系统基线以中文管理员结论、“你需要关注”和分组规则为主；原始 Runtime 机器证据仅保留在折叠技术详情中。
- CommonBaseline Runtime Resolver 不变，不建立第二套 Truth Store。
- V1.37.4 → V1.37.5 Atomic Success PASS；Source + SQLite Failure Rollback PASS。
- Fresh Install / Schema 30 / Backup-Restore / Project Intelligence / MCP E2E / Browser Responsive E2E 全部真实通过。
- Common Baseline V2：DRIFT=0 / UNKNOWN=0；既有受控 Exception/N_A 保持可追踪。
- Schema 30 不变，Migration NONE。
- Production 不由发布动作自动修改，需 Owner 在 VF Forge 后台执行在线升级后另行收口。

Formal Gate: Run 33160320928 / Job 98812936218 = PASS.
EOF
gh release create "$TAG" \
  "$WORK/release/VF_Forge_V1.37.5_UPDATE.zip" \
  "$WORK/release/VF_Forge_V1.37.5_FULL.zip" \
  "$WORK/release/RELEASE_SHA256SUMS.txt" \
  -R "$REPO" --title 'P03 · VF Forge V1.37.5' --notes-file "$WORK/release-notes.md" --verify-tag

REL="$WORK/release.json"; gh api "repos/$REPO/releases/tags/$TAG" > "$REL"
RELEASE_ID=$(jq -r .id "$REL"); RELEASED_AT=$(jq -r .published_at "$REL")
UPDATE_NAME='VF_Forge_V1.37.5_UPDATE.zip'
UPDATE_ID=$(jq -r --arg n "$UPDATE_NAME" '.assets[]|select(.name==$n)|.id' "$REL")
UPDATE_BYTES=$(stat -c%s "$WORK/release/$UPDATE_NAME")
UPDATE_SHA=$(sha256sum "$WORK/release/$UPDATE_NAME"|awk '{print $1}')
FULL_BYTES=$(stat -c%s "$WORK/release/VF_Forge_V1.37.5_FULL.zip")
FULL_SHA=$(sha256sum "$WORK/release/VF_Forge_V1.37.5_FULL.zip"|awk '{print $1}')
test "$(jq -r '.draft' "$REL")" = false
test "$(jq -r '.prerelease' "$REL")" = false
test "$(jq '.assets|length' "$REL")" -eq 3
python3 - "$REL" "$UPDATE_NAME" "$UPDATE_SHA" "$FULL_SHA" <<'PY'
import json,sys
r=json.load(open(sys.argv[1],encoding='utf-8')); un,us,fs=sys.argv[2:]
a={x['name']:x for x in r['assets']}
assert a[un]['digest']=='sha256:'+us
assert a['VF_Forge_V1.37.5_FULL.zip']['digest']=='sha256:'+fs
assert 'RELEASE_SHA256SUMS.txt' in a
PY
cat > "$WORK/evidence/P03-V1.37.5-PUBLICATION.json" <<EOF
{
  "schema":"vf-public-runner-result/v1",
  "project_id":"P03",
  "gate":"V1.37.5_FORMAL_RELEASE_PUBLICATION",
  "status":"SUCCESS",
  "pass":true,
  "version":"1.37.5",
  "source_version":"1.37.4",
  "candidate_source_sha":"$SOURCE",
  "candidate_source_tree":"$SOURCE_TREE",
  "product_main_merge_sha":"$MERGED_MAIN",
  "schema_version":"30",
  "formal_gate":{"run_id":$FORMAL_RUN,"job_id":$FORMAL_JOB,"artifact_name":"$ARTIFACT","status":"PASS"},
  "tag":"$TAG",
  "release_id":$RELEASE_ID,
  "released_at":"$RELEASED_AT",
  "assets":{"update":{"id":$UPDATE_ID,"name":"$UPDATE_NAME","bytes":$UPDATE_BYTES,"sha256":"$UPDATE_SHA"},"full":{"bytes":$FULL_BYTES,"sha256":"$FULL_SHA"}},
  "core_updates":{"status":"PENDING_SEPARATE_GATE"},
  "production":{"changed_by_publication":false,"status":"UPGRADE_REQUIRED"}
}
EOF
python3 -m json.tool "$WORK/evidence/P03-V1.37.5-PUBLICATION.json" >/dev/null
echo P03_V1375_GITHUB_RELEASE=PASS
echo "P03_RELEASE_ID=$RELEASE_ID"
echo "P03_RELEASED_AT=$RELEASED_AT"
echo "P03_UPDATE_ID=$UPDATE_ID"
echo "P03_UPDATE_BYTES=$UPDATE_BYTES"
echo "P03_UPDATE_SHA256=$UPDATE_SHA"
echo "P03_FULL_BYTES=$FULL_BYTES"
echo "P03_FULL_SHA256=$FULL_SHA"
echo RELEASE=YES
echo PRODUCTION=NO
