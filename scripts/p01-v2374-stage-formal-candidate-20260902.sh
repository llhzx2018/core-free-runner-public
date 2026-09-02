#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT_BRANCH=release/v2374-formal-candidate-20260902
MAIN=740610e6529dbc0997af3112d83c0aa95bd8d0ac
HOTFIX=84230316c9a0d64371f65eb461460a1cf1cc40e8
SOURCE=cec95e310771feb6813a51c7ee3340884295ee38
SCHEMA=2026082901
HOTFIX_GATE=33603844441
HOTFIX_R1=33603764352

cd product
test "$(git rev-parse HEAD)" = "$HOTFIX"
test "$(git rev-parse HEAD^)" = "$MAIN"
test "$(cat VERSION)" = 2.37.3
test "$(cat src/VERSION.txt)" = 2.37.3
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

printf '2.37.4\n' > VERSION
printf '2.37.4\n' > src/VERSION.txt
python3 - <<'PY'
from pathlib import Path
import json, copy

p=Path('src/app/bootstrap.php')
s=p.read_text(encoding='utf-8')
old="define('VF_VERSION', '2.37.3');"; new="define('VF_VERSION', '2.37.4');"
assert s.count(old)==1
p.write_text(s.replace(old,new,1),encoding='utf-8')

p=Path('CHANGELOG.md'); s=p.read_text(encoding='utf-8')
head="""## V2.37.4 · IYF Cover Content-Negotiation Hotfix Candidate · 2026-09-02

- Owner 已真实升级至 V2.37.3，但影视页仍有 IYF 资源停留在字母占位，因此 V2.37.3 Production Closure 不标记 PASS。
- 代码审计发现 V2.37.3 的远程图片请求主动声明接受 `image/avif`，但安全验证器只接受 PNG/JPG/WebP/GIF；CDN 可按 Accept 改变实际返回格式，形成请求能力与验证能力不一致。
- V2.37.4 不放宽 AVIF 文件处理，而是移除 AVIF 声明，仅协商验证器已安全支持的 WebP/PNG/JPEG/GIF；手动封面上传规则不变。
- 浏览器失败重试 revision 从 `v4` 升至 `v5`，升级后清除 V2.37.3 的一小时失败阻断。
- Focused Gate R1 `33603764352` 为测试脚本重复 require 的 Harness-only；R2 `33603844441` PASS，三条真实 IYF URL 首刷 `3/3`，CDN 实际均返回/保存为 WebP，验证了内容协商会改变真实 MIME。
- Schema 保持 `2026082901`，无 Migration；目标 Atomic 严格为 `V2.37.3 → V2.37.4`。

"""
if not s.startswith('## V2.37.4 '): p.write_text(head+s,encoding='utf-8')

p=Path('VF_PROJECT.json'); d=json.loads(p.read_text(encoding='utf-8'))
pub=copy.deepcopy(d.get('published_release',{}))
assert pub.get('version')=='2.37.3', pub.get('version')
prod=copy.deepcopy(pub)
prod['release_state']='PUBLISHED / OWNER INSTALLED OBSERVED / PRODUCTION CLOSURE DEFERRED BY REAL IYF COVER FAILURE'
prod['owner_production_runtime']='2.37.3'; prod['owner_production_schema']='2026082901'
prod['production_closure']='DEFERRED / SUPERSEDED BY V2.37.4 CONTENT-NEGOTIATION HOTFIX'
prod['owner_version_readback']='Owner update screenshot shows Current V2.37.3 / Latest V2.37.3 / 2.37.2→2.37.3 success; real IYF cards still show letter placeholders.'
prod['owner_online_state']='V2.37.3 RUNNING / IYF COVER FAILURE STILL OBSERVED'
d['production_release']=prod

d['status']='V2.37.3 OWNER PRODUCTION OBSERVED / V2.37.4 HOTFIX RELEASE CANDIDATE'
d['production_version']='2.37.3'; d['working_version']='2.37.4'; d['target_release_version']='2.37.4'
d['current_phase']='V2.37.4 IYF COVER CONTENT-NEGOTIATION HOTFIX / FORMAL RELEASE CANDIDATE'
d['candidate_version']='2.37.4'; d['candidate_schema_version']='2026082901'
d['candidate_state']='V2.37.4 FORMAL RELEASE CANDIDATE / NOT PUBLISHED'
d['formal_release_state']='V2.37.4 FORMAL GATES IN PROGRESS / NOT PUBLISHED'
d['current_authority']='Owner Production V2.37.3 OBSERVED / Published Latest V2.37.3 / V2.37.4 Hotfix Candidate'
d['next_action']='Run V2.37.4 Candidate Readiness, Formal Bind, Formal Artifact and Strict Fresh. Publish only after PASS. Production Closure remains pending real Owner IYF cover verification.'
d['current_change']={
 'change_id':'P01-V2374-IYF-CONTENT-NEGOTIATION-20260902','type':'PATCH HOTFIX / IYF COVER CONTENT NEGOTIATION',
 'production_base':'740610e6529dbc0997af3112d83c0aa95bd8d0ac','hotfix_candidate':'84230316c9a0d64371f65eb461460a1cf1cc40e8',
 'hotfix_gate_r1':33603764352,'hotfix_gate_r1_classification':'HARNESS_ONLY_DUPLICATE_RESOURCE_ASSET_STORE_REQUIRE',
 'hotfix_gate':33603844441,'hotfix_gate_result':'PASS / REAL IYF FIRST ATTEMPT 3 OF 3 / CDN NEGOTIATED WEBP 3 OF 3',
 'runtime_hotfix_files':['src/app/ResourceCoverCache.php','src/assets/workspace.js'],
 'avif_advertised':False,'supported_remote_formats':['image/webp','image/png','image/jpeg','image/gif'],'retry_revision':'v5',
 'schema_change':False,'migration':None,'version_change':True,'release_authorized_by_owner':True,
 'main_write':False,'production_write':False,'runner_main_write':False,'release_completed':False
}
d['v2_37_4_release_candidate']={
 'source_version':'2.37.3','target_version':'2.37.4','schema_version':'2026082901',
 'production_base':'740610e6529dbc0997af3112d83c0aa95bd8d0ac','published_source':'cec95e310771feb6813a51c7ee3340884295ee38',
 'hotfix_candidate':'84230316c9a0d64371f65eb461460a1cf1cc40e8','runtime_hotfix_files':['src/app/ResourceCoverCache.php','src/assets/workspace.js'],
 'hotfix_gate_r1':33603764352,'hotfix_gate':33603844441,'real_iyf_first_attempt':'3/3 PASS','cdn_negotiated_mime':'image/webp 3/3',
 'avif_advertised':False,'manual_upload_policy':'UNCHANGED / WEBP JPG PNG','schema_change':False,'migration':None,'assistant_production_write':False,
 'state':'STAGE CANDIDATE / NOT PUBLISHED'
}
d['authority']['current_formal_release_evidence']='docs/evidence/P01_V2.37.4_RELEASE_CANDIDATE_20260902.md'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

block="""<!-- P01_V2374_RELEASE_CANDIDATE -->
## V2.37.4 IYF Cover Content-Negotiation Hotfix Candidate · 2026-09-02

- Owner Production 已真实运行 `V2.37.3`，更新页 Current/Latest 均为 V2.37.3，但真实影视页仍有 IYF 卡片显示字母占位，因此 V2.37.3 Closure **DEFERRED**。
- V2.37.3 远程封面请求声明接受 AVIF，但后端安全验证器并不接受 AVIF；CDN 会按 Accept 协商真实格式，形成能力不一致。
- Candidate `84230316c9a0d64371f65eb461460a1cf1cc40e8` 仅改 2 个 runtime 文件：不再声明 AVIF，只请求 WebP/PNG/JPEG/GIF；浏览器失败缓存 revision `v4 → v5`。
- Gate R1 `33603764352` Harness-only；R2 `33603844441` PASS，真实 IYF 首刷 `3/3`，三条均协商为 WebP 并成功落盘。
- Schema `2026082901` 不变，无 Migration；目标严格单跳 `V2.37.3 → V2.37.4`；Assistant Production Write = NO。

"""
for name in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
    q=Path(name); t=q.read_text(encoding='utf-8')
    if '<!-- P01_V2374_RELEASE_CANDIDATE -->' not in t:
        lines=t.splitlines(True); q.write_text(lines[0]+'\n'+block+''.join(lines[1:]),encoding='utf-8')

Path('docs/evidence/P01_V2.37.4_RELEASE_CANDIDATE_20260902.md').write_text("""# P01 · VF Start · V2.37.4 Release Candidate Evidence

- Owner Production Observed: `V2.37.3` / Schema `2026082901`.
- Owner Evidence: Current V2.37.3 / Latest V2.37.3 / V2.37.2→V2.37.3 success; real IYF cards still show letter placeholders.
- Published V2.37.3 Formal Source: `cec95e310771feb6813a51c7ee3340884295ee38`.
- Hotfix Candidate: `84230316c9a0d64371f65eb461460a1cf1cc40e8`.
- Hotfix Gate R1: `33603764352` / HARNESS ONLY / duplicate ResourceAssetStore require before E2E.
- Hotfix Gate R2: `33603844441` / PASS / real IYF first attempt 3/3; all three CDN responses stored as `image/webp` despite `.gif` source URLs.
- Runtime change: remove `image/avif` from Accept negotiation; retain WebP/PNG/JPEG/GIF; browser retry revision `v4→v5`.
- Security boundary: validator remains PNG/JPG/WebP/GIF; manual upload remains WebP/JPG/PNG; no AVIF parser/storage support added.
- Target: `V2.37.4`; Schema `2026082901`; Migration NONE; Owner Production Write NO.
""",encoding='utf-8')
PY

python3 -m json.tool VF_PROJECT.json >/dev/null
php -l src/app/ResourceCoverCache.php
php -l src/app/bootstrap.php
node --check src/assets/workspace.js
git diff --check

test "$(cat VERSION)" = 2.37.4
test "$(cat src/VERSION.txt)" = 2.37.4
grep -Fx "define('VF_VERSION', '2.37.4');" src/app/bootstrap.php >/dev/null
grep -F 'image/webp,image/png,image/jpeg,image/gif,image/*;q=0.8,*/*;q=0.1' src/app/ResourceCoverCache.php >/dev/null
! grep -F 'image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.1' src/app/ResourceCoverCache.php >/dev/null
grep -F "'image/gif'=>'gif'" src/app/ResourceCoverCache.php >/dev/null
grep -F 'vf-cover-retry:v5:' src/assets/workspace.js >/dev/null
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

mapfile -t changed < <(git status --porcelain | sed -E 's/^.. //' | sort)
printf '%s\n' "${changed[@]}" | tee /tmp/p01-v2374-stage-files.txt
expected=$(cat <<'EOF'
CHANGELOG.md
VERSION
VF_PROJECT.json
docs/authority/CURRENT.md
docs/evidence/P01_V2.37.4_RELEASE_CANDIDATE_20260902.md
docs/handoff/CURRENT_STATE.md
src/VERSION.txt
src/app/bootstrap.php
EOF
)
test "$(printf '%s\n' "${changed[@]}")" = "$expected"

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add CHANGELOG.md VERSION VF_PROJECT.json docs/authority/CURRENT.md docs/evidence/P01_V2.37.4_RELEASE_CANDIDATE_20260902.md docs/handoff/CURRENT_STATE.md src/VERSION.txt src/app/bootstrap.php
git commit -m 'release: stage V2.37.4 iyf content-negotiation hotfix'
git push origin HEAD:$PRODUCT_BRANCH
CANDIDATE=$(git rev-parse HEAD); TREE=$(git rev-parse HEAD^{tree}); RUNTIME=$(git rev-parse HEAD:src)
printf 'P01_V2374_STAGE=PASS\nOWNER_PRODUCTION_OBSERVED=2.37.3\nPUBLISHED_SOURCE=%s\nHOTFIX=%s\nHOTFIX_GATE=%s\nCANDIDATE=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' "$SOURCE" "$HOTFIX" "$HOTFIX_GATE" "$CANDIDATE" "$TREE" "$RUNTIME" "$SCHEMA" | tee /tmp/p01-v2374-stage-verdict.txt
