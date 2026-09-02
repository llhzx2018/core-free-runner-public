#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT_BRANCH=release/v2373-formal-candidate-20260902
MAIN=6f09d59e3ecc0ed54b9a3ae6e3fc6ba22b109ea1
HOTFIX=80ccbdf77b7e708cd17b3d9d7fcbaed71426cc51
SOURCE=1f5a16796511620760a45cb81b3c8019b91e505b
SCHEMA=2026082901
HOTFIX_GATE=33600058990
DIAG_R2=33599532987

cd product
test "$(git rev-parse HEAD)" = "$HOTFIX"
test "$(git rev-parse HEAD^)" = "$MAIN"
test "$(cat VERSION)" = 2.37.2
test "$(cat src/VERSION.txt)" = 2.37.2
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

printf '2.37.3\n' > VERSION
printf '2.37.3\n' > src/VERSION.txt
python3 - <<'PY'
from pathlib import Path
import json, copy

p=Path('src/app/bootstrap.php')
s=p.read_text(encoding='utf-8')
old="define('VF_VERSION', '2.37.2');"
new="define('VF_VERSION', '2.37.3');"
if s.count(old)!=1: raise SystemExit('bootstrap version anchor mismatch')
p.write_text(s.replace(old,new,1),encoding='utf-8')

p=Path('CHANGELOG.md')
s=p.read_text(encoding='utf-8')
head="""## V2.37.3 · IYF GIF Auto-cover Hotfix Candidate · 2026-09-02

- 修复 V2.37.2 已能定位爱一帆海报 URL，但真实自动封面链路仍可能因海报实际返回 `image/gif` 而被验证器拒绝的问题。
- 真实 E2E 诊断 R2 `33599532987` 已复现：三条独立 IYF 资源第一次仅 `1/3` 成功，`mview` 连续两次失败；失败统一为“自动封面仅接受 PNG、JPG、WebP”。
- 自动远程封面验证器新增 GIF87a/GIF89a 魔数识别与 `image/gif` 白名单；仍保留 2 MB、有效图片、尺寸边界等安全校验。
- 手动上传规则保持 WebP/JPG/PNG，不因本 Hotfix 放宽。
- 浏览器失败重试 revision 从 `v3` 升至 `v4`，升级后旧的一小时失败缓存立即失效并重新补图。
- Focused Hotfix Gate R3 `33600058990`：三条 IYF 第一次 `refreshOne()` 保存 `3/3 PASS`，`resource-cover.php` 实际输出 `3/3 PASS`。
- Schema 保持 `2026082901`，无 Migration；目标 Atomic 严格为 `V2.37.2 → V2.37.3`。

"""
if not s.startswith('## V2.37.3 '):
    p.write_text(head+s,encoding='utf-8')

p=Path('VF_PROJECT.json')
d=json.loads(p.read_text(encoding='utf-8'))
pub=copy.deepcopy(d.get('published_release',{}))
if pub.get('version')!='2.37.2': raise SystemExit('published_release V2.37.2 missing')
pub['release_state']='PUBLISHED / OWNER INSTALLED OBSERVED / PRODUCTION CLOSURE DEFERRED BY IYF GIF VALIDATION BUG'
pub['owner_production_runtime']='2.37.2'
pub['owner_production_schema']='2026082901'
pub['production_closure']='DEFERRED / SUPERSEDED BY V2.37.3 HOTFIX'
pub['owner_version_readback']='Owner update page screenshot shows Current V2.37.2 / Latest V2.37.2 / 2.37.1→2.37.2 success; IYF covers still absent.'
pub['owner_online_state']='V2.37.2 RUNNING / V2.37.3 HOTFIX IN PREPARATION'
d['production_release']=pub

d['status']='V2.37.2 OWNER PRODUCTION OBSERVED / V2.37.3 HOTFIX RELEASE CANDIDATE'
d['production_version']='2.37.2'
d['working_version']='2.37.3'
d['target_release_version']='2.37.3'
d['current_phase']='V2.37.3 IYF GIF AUTO-COVER HOTFIX / FORMAL RELEASE CANDIDATE'
d['candidate_version']='2.37.3'
d['candidate_schema_version']='2026082901'
d['candidate_state']='V2.37.3 FORMAL RELEASE CANDIDATE / NOT PUBLISHED'
d['formal_release_state']='V2.37.3 FORMAL GATES IN PROGRESS / NOT PUBLISHED'
d['current_authority']='Owner Production V2.37.2 OBSERVED / Published Latest V2.37.2 / V2.37.3 Hotfix Candidate'
d['next_action']='Run V2.37.3 Candidate Readiness with true IYF first-attempt E2E, then Formal Bind, Formal Artifact and Strict Fresh. Do not publish before PASS; Owner Production write remains NO.'
d['current_change']={
  'change_id':'P01-V2373-IYF-GIF-AUTO-COVER-20260902',
  'type':'PATCH HOTFIX / IYF GIF AUTO COVER',
  'production_base':'6f09d59e3ecc0ed54b9a3ae6e3fc6ba22b109ea1',
  'hotfix_candidate':'80ccbdf77b7e708cd17b3d9d7fcbaed71426cc51',
  'diagnostic_r1':33599355573,
  'diagnostic_r1_classification':'PARTIAL / LINK-ID HARNESS BUG BUT GIF REJECTION OBSERVED',
  'diagnostic_r2':33599532987,
  'diagnostic_r2_result':'FAIL REPRODUCED / FIRST ATTEMPT 1 OF 3',
  'hotfix_gate_r1':33599708702,
  'hotfix_gate_r1_classification':'HARNESS_ONLY_WORKFLOW_YAML_PARSE',
  'hotfix_gate_r2':33599902477,
  'hotfix_gate_r2_classification':'HARNESS_ONLY_PRIVATE_STORAGE_PATH_ASSERTION / PRODUCT E2E 3 OF 3 BEFORE ASSERTION',
  'hotfix_gate':33600058990,
  'hotfix_gate_result':'PASS / FIRST ATTEMPT 3 OF 3 / RESOURCE COVER SERVE 3 OF 3',
  'schema_change':False,
  'migration':None,
  'version_change':True,
  'release_authorized_by_owner':True,
  'main_write':False,
  'production_write':False,
  'runner_main_write':False,
  'release_completed':False
}
d['v2_37_3_release_candidate']={
  'source_version':'2.37.2','target_version':'2.37.3','schema_version':'2026082901',
  'production_base':'6f09d59e3ecc0ed54b9a3ae6e3fc6ba22b109ea1',
  'published_source':'1f5a16796511620760a45cb81b3c8019b91e505b',
  'hotfix_candidate':'80ccbdf77b7e708cd17b3d9d7fcbaed71426cc51',
  'runtime_hotfix_files':['src/app/ResourceCoverCache.php','src/assets/workspace.js'],
  'diagnostic_r2':33599532987,'hotfix_gate':33600058990,
  'first_attempt_e2e':'3/3 PASS','resource_cover_serve':'3/3 PASS',
  'manual_upload_policy':'UNCHANGED / WEBP JPG PNG',
  'schema_change':False,'migration':None,'assistant_production_write':False,
  'state':'STAGE CANDIDATE / NOT PUBLISHED'
}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

block="""<!-- P01_V2373_RELEASE_CANDIDATE -->
## V2.37.3 IYF GIF Auto-cover Hotfix Candidate · 2026-09-02

- Owner 已实测升级到 `V2.37.2`，更新页显示 Current/Latest 均为 V2.37.2，但 IYF 封面仍未加载，因此 V2.37.2 Production Closure **不标记 PASS**。
- 根因 E2E 已确认：IYF `og:image`/海报 URL 实际为 `.gif`，CDN 有时返回 WebP、有时返回 GIF；V2.37.2 自动封面验证器只允许 PNG/JPG/WebP，导致真实链路不稳定并触发一小时失败缓存。
- Diagnostic R2 `33599532987`：三条独立 IYF 首次刷新仅 `1/3`；Hotfix Gate R3 `33600058990`：首次保存 `3/3 PASS`，`resource-cover.php` 输出 `3/3 PASS`。
- Product Hotfix `80ccbdf77b7e708cd17b3d9d7fcbaed71426cc51`：仅 `ResourceCoverCache.php` + `workspace.js`；自动远程封面安全支持 GIF，失败重试 revision `v4`。
- 手动上传仍只允许 WebP/JPG/PNG；用户保存 URL 不改写；Schema `2026082901` 不变，无 Migration。
- 目标严格单跳：`V2.37.2 → V2.37.3`。

"""
for name in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
    q=Path(name); t=q.read_text(encoding='utf-8')
    if '<!-- P01_V2373_RELEASE_CANDIDATE -->' not in t:
        lines=t.splitlines(True)
        q.write_text(lines[0]+'\n'+block+''.join(lines[1:]),encoding='utf-8')

Path('docs/evidence/P01_V2.37.3_RELEASE_CANDIDATE_20260902.md').write_text("""# P01 · VF Start · V2.37.3 Release Candidate Evidence

- Owner Production Observed: `V2.37.2` / Schema `2026082901`.
- Owner Evidence: update page Current V2.37.2 / Latest V2.37.2 / V2.37.1→V2.37.2 success; IYF covers still absent.
- Published V2.37.2 Formal Source: `1f5a16796511620760a45cb81b3c8019b91e505b`.
- Hotfix Candidate: `80ccbdf77b7e708cd17b3d9d7fcbaed71426cc51`.
- Diagnostic R2: `33599532987` / FAIL REPRODUCED / first attempt 1/3, eventual 2/3.
- Hotfix Gate R1: `33599708702` / HARNESS ONLY / invalid workflow YAML.
- Hotfix Gate R2: `33599902477` / HARNESS ONLY persistence-path assertion; product calls already 3/3 success.
- Hotfix Gate R3: `33600058990` / PASS / first attempt persist 3/3 / resource-cover serve 3/3.
- Runtime change: automatic remote cover accepts validated GIF87a/GIF89a; browser retry revision v3→v4.
- Manual upload: unchanged, WebP/JPG/PNG only.
- Target: `V2.37.3`; Schema `2026082901`; Migration NONE; Owner Production Write NO.
""",encoding='utf-8')
PY

python3 -m json.tool VF_PROJECT.json >/dev/null
php -l src/app/ResourceCoverCache.php
php -l src/app/bootstrap.php
node --check src/assets/workspace.js
git diff --check

test "$(cat VERSION)" = 2.37.3
test "$(cat src/VERSION.txt)" = 2.37.3
grep -Fx "define('VF_VERSION', '2.37.3');" src/app/bootstrap.php >/dev/null
grep -F "'image/gif'=>'gif'" src/app/ResourceCoverCache.php >/dev/null
grep -F 'vf-cover-retry:v4:' src/assets/workspace.js >/dev/null
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

mapfile -t changed < <(git status --porcelain | sed -E 's/^.. //' | sort)
printf '%s\n' "${changed[@]}" | tee /tmp/p01-v2373-stage-files.txt
expected=$(cat <<'EOF'
CHANGELOG.md
VERSION
VF_PROJECT.json
docs/authority/CURRENT.md
docs/evidence/P01_V2.37.3_RELEASE_CANDIDATE_20260902.md
docs/handoff/CURRENT_STATE.md
src/VERSION.txt
src/app/bootstrap.php
EOF
)
test "$(printf '%s\n' "${changed[@]}")" = "$expected"

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add CHANGELOG.md VERSION VF_PROJECT.json docs/authority/CURRENT.md docs/evidence/P01_V2.37.3_RELEASE_CANDIDATE_20260902.md docs/handoff/CURRENT_STATE.md src/VERSION.txt src/app/bootstrap.php
git commit -m 'release: stage V2.37.3 iyf gif cover hotfix'
git push origin HEAD:$PRODUCT_BRANCH

CANDIDATE=$(git rev-parse HEAD)
TREE=$(git rev-parse HEAD^{tree})
RUNTIME=$(git rev-parse HEAD:src)
printf 'P01_V2373_STAGE=PASS\nOWNER_PRODUCTION_OBSERVED=2.37.2\nPUBLISHED_SOURCE=%s\nHOTFIX=%s\nHOTFIX_GATE=%s\nCANDIDATE=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' "$SOURCE" "$HOTFIX" "$HOTFIX_GATE" "$CANDIDATE" "$TREE" "$RUNTIME" "$SCHEMA" | tee /tmp/p01-v2373-stage-verdict.txt
