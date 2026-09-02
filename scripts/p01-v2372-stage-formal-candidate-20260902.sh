#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT_BRANCH=release/v2372-formal-candidate-20260902
MAIN=2d429e08131311063fa9edf01b167d6617035fe2
HOTFIX=a63bba083dc6f2bde8c7692392afebb093b370a4
SOURCE=0838e47ec49bb961131da81b0b314ebf77f1e126
SCHEMA=2026082901

cd product
test "$(git rev-parse HEAD)" = "$HOTFIX"
test "$(git rev-parse HEAD^)" = "$MAIN"
test "$(cat VERSION)" = 2.37.1
test "$(cat src/VERSION.txt)" = 2.37.1
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

printf '2.37.2\n' > VERSION
printf '2.37.2\n' > src/VERSION.txt
python3 - <<'PY'
from pathlib import Path
import json, copy

p=Path('src/app/bootstrap.php')
s=p.read_text(encoding='utf-8')
old="define('VF_VERSION', '2.37.1');"
new="define('VF_VERSION', '2.37.2');"
if old not in s: raise SystemExit('bootstrap version anchor missing')
p.write_text(s.replace(old,new,1),encoding='utf-8')

p=Path('CHANGELOG.md')
s=p.read_text(encoding='utf-8')
head="""## V2.37.2 · IYF Mobile Cover Fallback Hotfix Candidate · 2026-09-02

- 修复爱一帆 `mview.iyf.tv/play/<ID>` 移动播放链接无法自动取得影视封面的问题。
- 根因已通过真实同 ID 对照确认：`mview.iyf.tv` 返回约 2.7 KB 的 JS 壳且 `og:image=0`；同 ID 的 `www.iyf.tv/play/<ID>` 返回约 11.8 KB 页面且 `og:image=1`、含 `static.iyf.tv` 海报。
- 保存的网址保持原样；仅封面抓取时把爱一帆移动播放页临时映射到同 ID 桌面播放页，失败时仍回退原地址，不迁移、不重写用户数据。
- 浏览器封面失败重试 key revision 从 `v2` 升至 `v3`，避免 V2.37.1 已记录的失败缓存阻止升级后立即重新补图。
- IYF same-token Diagnostic R2 `33596050361` PASS；Focused Hotfix Gate `33596187097` PASS。
- Schema 保持 `2026082901`，无 Migration；目标 Atomic 严格为 `V2.37.1 → V2.37.2`。

"""
if not s.startswith('## V2.37.2 '): p.write_text(head+s,encoding='utf-8')

p=Path('VF_PROJECT.json')
d=json.loads(p.read_text(encoding='utf-8'))
# Owner screenshot proves runtime/footer V2.37.1; closure is intentionally deferred because this compatibility bug was observed immediately after upgrade.
d['status']='V2.37.1 OWNER PRODUCTION OBSERVED / V2.37.2 HOTFIX RELEASE CANDIDATE'
d['production_version']='2.37.1'
d['working_version']='2.37.2'
d['target_release_version']='2.37.2'
d['current_phase']='V2.37.2 IYF MOBILE COVER FALLBACK HOTFIX / FORMAL RELEASE CANDIDATE'
d['candidate_version']='2.37.2'
d['candidate_schema_version']='2026082901'
d['candidate_state']='V2.37.2 FORMAL RELEASE CANDIDATE / NOT PUBLISHED'
d['formal_release_state']='V2.37.2 FORMAL GATES IN PROGRESS / NOT PUBLISHED'
d['current_authority']='Owner Production V2.37.1 OBSERVED / Published Latest V2.37.1 / V2.37.2 Hotfix Candidate'
d['next_action']='Run V2.37.2 Candidate Readiness, Formal Bind, Formal Artifact and Strict Fresh. Do not publish before gates PASS; Owner Production write remains NO.'
# Promote the already-published 2.37.1 object to observed production truth without claiming closure PASS.
pub=copy.deepcopy(d.get('published_release',{}))
if pub.get('version')!='2.37.1': raise SystemExit('published_release 2.37.1 missing')
pub['release_state']='PUBLISHED / OWNER INSTALLED OBSERVED / PRODUCTION CLOSURE DEFERRED BY IYF MVIEW BUG'
pub['owner_production_runtime']='2.37.1'
pub['owner_production_schema']='2026082901'
pub['production_closure']='DEFERRED / SUPERSEDED BY V2.37.2 HOTFIX'
pub['owner_version_readback']='Watch page footer V2.37.1 observed by Owner; cover compatibility regression discovered before closure.'
pub['owner_online_state']='V2.37.1 RUNNING / V2.37.2 HOTFIX IN PREPARATION'
d['production_release']=pub

d['current_change']={
  'change_id':'P01-V2372-IYF-MVIEW-COVER-FALLBACK-20260902',
  'type':'PATCH HOTFIX / IYF MOBILE COVER FALLBACK',
  'production_base':MAIN if False else '2d429e08131311063fa9edf01b167d6617035fe2',
  'hotfix_candidate':'a63bba083dc6f2bde8c7692392afebb093b370a4',
  'same_token_diagnostic_r1':33595996317,
  'same_token_diagnostic_r1_classification':'HARNESS_ONLY_SHELL_QUOTING',
  'same_token_diagnostic_r2':33596050361,
  'hotfix_gate':33596187097,
  'schema_change':False,
  'migration':None,
  'version_change':True,
  'release_authorized_by_owner':True,
  'main_write':False,
  'production_write':False,
  'runner_main_write':False,
  'release_completed':False
}
d['v2_37_2_release_candidate']={
  'source_version':'2.37.1',
  'target_version':'2.37.2',
  'schema_version':'2026082901',
  'production_base':'2d429e08131311063fa9edf01b167d6617035fe2',
  'published_source':'0838e47ec49bb961131da81b0b314ebf77f1e126',
  'hotfix_candidate':'a63bba083dc6f2bde8c7692392afebb093b370a4',
  'runtime_hotfix_files':['src/app/ResourceCoverCache.php','src/assets/workspace.js'],
  'same_token_diagnostic':33596050361,
  'hotfix_gate':33596187097,
  'schema_change':False,
  'migration':None,
  'assistant_production_write':False,
  'state':'STAGE CANDIDATE / NOT PUBLISHED'
}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

block="""<!-- P01_V2372_RELEASE_CANDIDATE -->
## V2.37.2 IYF Mobile Cover Fallback Hotfix Candidate · 2026-09-02

- Owner 实际页面已观察到运行 `V2.37.1`；V2.37.1 Production Closure 因爱一帆移动链接封面兼容缺口而**延后，不标记 PASS**。
- 同一播放 ID 实测：`mview.iyf.tv/play/...` 无静态 `og:image`，而 `www.iyf.tv/play/...` 有 `og:image` 与真实 `static.iyf.tv` 海报；Diagnostic R2 `33596050361` PASS。
- Product Hotfix `a63bba083dc6f2bde8c7692392afebb093b370a4`：仅 `ResourceCoverCache.php` + `workspace.js`；Focused Gate `33596187097` PASS。
- 用户保存 URL 不改写；只在封面抓取时对 `mview.iyf.tv/play/<ID>` 临时尝试同 ID 的 `www.iyf.tv/play/<ID>`。
- Schema `2026082901` 不变，无 Migration；目标升级路径严格 `V2.37.1 → V2.37.2`。
- Next：Candidate Readiness → Formal Bind → Formal Artifact → Strict Fresh；全部 PASS 后才允许 Tag / Release / core-updates。

"""
for name in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
    q=Path(name); t=q.read_text(encoding='utf-8')
    if '<!-- P01_V2372_RELEASE_CANDIDATE -->' not in t:
        lines=t.splitlines(True)
        q.write_text(lines[0]+'\n'+block+''.join(lines[1:]),encoding='utf-8')

p=Path('docs/evidence/P01_V2.37.2_RELEASE_CANDIDATE_20260902.md')
p.write_text("""# P01 · VF Start · V2.37.2 Release Candidate Evidence

- Date: 2026-09-02
- Owner Production Observed: `V2.37.1` via actual Watch page footer; Closure deferred after IYF compatibility bug observation.
- Published V2.37.1 Formal Source: `0838e47ec49bb961131da81b0b314ebf77f1e126`
- Main Authority Base: `2d429e08131311063fa9edf01b167d6617035fe2`
- Hotfix Candidate: `a63bba083dc6f2bde8c7692392afebb093b370a4`
- Hotfix Files: `src/app/ResourceCoverCache.php`, `src/assets/workspace.js`
- Same-token Diagnostic R1: `33595996317` / HARNESS ONLY / shell quoting
- Same-token Diagnostic R2: `33596050361` / PASS
- Focused Hotfix Gate: `33596187097` / PASS
- Proven behavior: `mview.iyf.tv/play/<ID>` static metadata empty; same ID at `www.iyf.tv/play/<ID>` exposes `og:image` and `static.iyf.tv` poster.
- Data behavior: stored URL unchanged; cover-fetch-only canonical fallback.
- Target: V2.37.2, Schema `2026082901`, Migration NONE.
- Owner Production Write: NO.
""",encoding='utf-8')
PY

python3 -m json.tool VF_PROJECT.json >/dev/null
php -l src/app/ResourceCoverCache.php
php -l src/app/bootstrap.php
node --check src/assets/workspace.js
git diff --check

test "$(cat VERSION)" = 2.37.2
test "$(cat src/VERSION.txt)" = 2.37.2
grep -Fx "define('VF_VERSION', '2.37.2');" src/app/bootstrap.php >/dev/null
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

mapfile -t changed < <(git status --porcelain | sed -E 's/^.. //' | sort)
printf '%s\n' "${changed[@]}" | tee /tmp/p01-v2372-stage-files.txt
expected=$(cat <<'EOF'
CHANGELOG.md
VERSION
VF_PROJECT.json
docs/authority/CURRENT.md
docs/evidence/P01_V2.37.2_RELEASE_CANDIDATE_20260902.md
docs/handoff/CURRENT_STATE.md
src/VERSION.txt
src/app/bootstrap.php
EOF
)
test "$(printf '%s\n' "${changed[@]}")" = "$expected"

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add CHANGELOG.md VERSION VF_PROJECT.json docs/authority/CURRENT.md docs/evidence/P01_V2.37.2_RELEASE_CANDIDATE_20260902.md docs/handoff/CURRENT_STATE.md src/VERSION.txt src/app/bootstrap.php
git commit -m 'release: stage V2.37.2 iyf mobile cover hotfix'
git push origin HEAD:$PRODUCT_BRANCH

CANDIDATE=$(git rev-parse HEAD)
TREE=$(git rev-parse HEAD^{tree})
RUNTIME=$(git rev-parse HEAD:src)
printf 'P01_V2372_STAGE=PASS\nOWNER_PRODUCTION_OBSERVED=2.37.1\nPUBLISHED_SOURCE=%s\nHOTFIX=%s\nCANDIDATE=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' "$SOURCE" "$HOTFIX" "$CANDIDATE" "$TREE" "$RUNTIME" "$SCHEMA" | tee /tmp/p01-v2372-stage-verdict.txt
