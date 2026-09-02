#!/usr/bin/env bash
set -Eeuo pipefail
PRODUCT_BRANCH=release/v2375-formal-candidate-20260902
MAIN=58ed50f2d56afc04cfff467075fc7025306afeb5
HOTFIX=f88b6f2994b2afc83713440f2409f1dfc78990d5
SOURCE=4532e6443805cefe141efc1f70f1689e532450b9
SCHEMA=2026082901
FOCUSED_GATE=33609124506
LEGACY_REPLAY=33608249098
EDGE_DIAG=33608705736

cd product
test "$(git rev-parse HEAD)" = "$HOTFIX"
test "$(git rev-parse HEAD^)" = "$MAIN"
test "$(cat VERSION)" = 2.37.4
test "$(cat src/VERSION.txt)" = 2.37.4
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

printf '2.37.5\n' > VERSION
printf '2.37.5\n' > src/VERSION.txt
python3 - <<'PY'
from pathlib import Path
import json, copy

p=Path('src/app/bootstrap.php'); s=p.read_text(encoding='utf-8')
old="define('VF_VERSION', '2.37.4');"; new="define('VF_VERSION', '2.37.5');"
assert s.count(old)==1
p.write_text(s.replace(old,new,1),encoding='utf-8')

p=Path('CHANGELOG.md'); s=p.read_text(encoding='utf-8')
head="""## V2.37.5 · Cover Failure Diagnostics & Manual Retry Candidate · 2026-09-02

- Owner 已真实运行 V2.37.4，但真实 IYF 历史卡片仍停留字母占位，因此 V2.37.4 Production Closure 继续 DEFERRED。
- 精确回放历史“天真遇到现实”原 URL `https://www.iyf.tv/play/MRcWYmJRueF`：V2.37.4 Runner 连续 12/12 自动封面成功；Cloudflare 两个 IPv4 页面节点与两个静态图片节点均返回 200，说明继续猜图片格式/CDN edge 已无证据价值。
- V2.37.5 不再盲改远端抓取策略：管理员影视卡片缺封面时新增明确“重新抓封面”动作，并把后端真实失败原因持久显示在对应卡片；显式手动重试不受一小时 localStorage 失败阻断。
- 自动失败也会显示具体错误；浏览器 retry revision 从 `v5` 升为 `v6`，升级后旧失败立即重新进入真实请求链。
- Focused Candidate Gate `33609124506` PASS，精确仅修改 `FunctionalWorkspaceShell.php`、`workspace.js`、`surface-workspace.css`。
- Schema 保持 `2026082901`，无 Migration；目标 Atomic 严格为 `V2.37.4 → V2.37.5`。

"""
if not s.startswith('## V2.37.5 '): p.write_text(head+s,encoding='utf-8')

p=Path('VF_PROJECT.json'); d=json.loads(p.read_text(encoding='utf-8'))
pub=copy.deepcopy(d.get('published_release',{}))
assert pub.get('version')=='2.37.4', pub.get('version')
prod=copy.deepcopy(pub)
prod['release_state']='PUBLISHED / OWNER INSTALLED OBSERVED / PRODUCTION CLOSURE DEFERRED BY REAL IYF COVER FAILURE'
prod['owner_production_runtime']='2.37.4'; prod['owner_production_schema']='2026082901'
prod['production_closure']='DEFERRED / SUPERSEDED BY V2.37.5 COVER FAILURE DIAGNOSTICS HOTFIX'
prod['owner_version_readback']='Owner screenshots show V2.37.4 running; real IYF cards still show letter placeholders.'
prod['owner_online_state']='V2.37.4 RUNNING / IYF COVER FAILURE STILL OBSERVED'
d['production_release']=prod

d['status']='V2.37.4 OWNER PRODUCTION OBSERVED / V2.37.5 HOTFIX RELEASE CANDIDATE'
d['production_version']='2.37.4'; d['working_version']='2.37.5'; d['target_release_version']='2.37.5'
d['current_phase']='V2.37.5 COVER FAILURE DIAGNOSTICS + MANUAL RETRY / FORMAL RELEASE CANDIDATE'
d['candidate_version']='2.37.5'; d['candidate_schema_version']='2026082901'
d['candidate_state']='V2.37.5 FORMAL RELEASE CANDIDATE / NOT PUBLISHED'
d['formal_release_state']='V2.37.5 FORMAL GATES IN PROGRESS / NOT PUBLISHED'
d['current_authority']='Owner Production V2.37.4 OBSERVED / Published Latest V2.37.4 / V2.37.5 Hotfix Candidate'
d['next_action']='Run V2.37.5 Candidate Readiness, Formal Bind, Formal Artifact and Strict Fresh. Publish only after PASS; then use real Owner Production error text to diagnose IYF without further blind fixes.'
d['current_change']={
 'change_id':'P01-V2375-COVER-FAILURE-DIAGNOSTICS-20260902','type':'PATCH HOTFIX / COVER FAILURE DIAGNOSTICS + MANUAL RETRY',
 'production_base':'58ed50f2d56afc04cfff467075fc7025306afeb5','hotfix_candidate':'f88b6f2994b2afc83713440f2409f1dfc78990d5',
 'focused_gate':33609124506,'focused_gate_result':'PASS / 3 FILES / VERSION UNCHANGED',
 'legacy_exact_replay':33608249098,'legacy_exact_replay_result':'12/12 PASS',
 'edge_diagnostic':33608705736,'edge_diagnostic_result':'PASS / BOTH WWW IPv4 200 + OG / BOTH STATIC IPv4 200 WEBP',
 'runtime_hotfix_files':['src/app/FunctionalWorkspaceShell.php','src/assets/workspace.js','src/assets/surface-workspace.css'],
 'retry_revision':'v6','manual_retry_bypasses_browser_backoff':True,'persistent_admin_error_surface':True,
 'schema_change':False,'migration':None,'version_change':True,'release_authorized_by_owner':True,
 'main_write':False,'production_write':False,'runner_main_write':False,'release_completed':False
}
d['v2_37_5_release_candidate']={
 'source_version':'2.37.4','target_version':'2.37.5','schema_version':'2026082901',
 'production_base':'58ed50f2d56afc04cfff467075fc7025306afeb5','published_source':'4532e6443805cefe141efc1f70f1689e532450b9',
 'hotfix_candidate':'f88b6f2994b2afc83713440f2409f1dfc78990d5',
 'runtime_hotfix_files':['src/app/FunctionalWorkspaceShell.php','src/assets/workspace.js','src/assets/surface-workspace.css'],
 'focused_gate':33609124506,'legacy_exact_replay':33608249098,'edge_diagnostic':33608705736,
 'retry_revision':'v6','schema_change':False,'migration':None,'assistant_production_write':False,
 'state':'STAGE CANDIDATE / NOT PUBLISHED'
}
d.setdefault('authority',{})['current_formal_release_evidence']='docs/evidence/P01_V2.37.5_RELEASE_CANDIDATE_20260902.md'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

block="""<!-- P01_V2375_RELEASE_CANDIDATE -->
## V2.37.5 Cover Failure Diagnostics & Manual Retry Candidate · 2026-09-02

- Owner Production 已真实运行 `V2.37.4`，但真实 IYF 历史卡片仍显示字母占位，因此 V2.37.4 Closure **DEFERRED**。
- 历史精确 URL `https://www.iyf.tv/play/MRcWYmJRueF` 在当前 V2.37.4 Runner 连续 `12/12` 成功；Cloudflare 两个 IPv4 页面/静态节点均成功，继续猜格式或 edge 不再作为修复依据。
- Candidate `f88b6f2994b2afc83713440f2409f1dfc78990d5` 精确改 3 个 runtime 文件：管理员缺封面卡片显示手动重试，自动/手动失败显示后端真实错误，手动重试绕过浏览器 backoff，retry revision `v5→v6`。
- Focused Gate `33609124506` PASS；Schema `2026082901` 不变，无 Migration；目标严格单跳 `V2.37.4 → V2.37.5`；Assistant Production Write = NO。

"""
for name in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
    q=Path(name); t=q.read_text(encoding='utf-8')
    if '<!-- P01_V2375_RELEASE_CANDIDATE -->' not in t:
        lines=t.splitlines(True); q.write_text(lines[0]+'\n'+block+''.join(lines[1:]),encoding='utf-8')

Path('docs/evidence/P01_V2.37.5_RELEASE_CANDIDATE_20260902.md').write_text("""# P01 · VF Start · V2.37.5 Release Candidate Evidence

- Owner Production Observed: `V2.37.4` / Schema `2026082901`; real IYF cards still show letter placeholders.
- Published V2.37.4 Formal Source: `4532e6443805cefe141efc1f70f1689e532450b9`.
- Exact historical record: `天真遇到现实` / `https://www.iyf.tv/play/MRcWYmJRueF`.
- Legacy exact replay `33608249098`: current V2.37.4 `refreshOne(force=true)` 12/12 PASS; saved WebP 420x600.
- Cloudflare edge diagnostic `33608705736`: both `www.iyf.tv` IPv4 edges HTTP 200 + OG image; both `static.iyf.tv` IPv4 edges HTTP 200 + WebP 132946 bytes; exact historical replay remained 12/12 PASS.
- Focused candidate `f88b6f2994b2afc83713440f2409f1dfc78990d5`, Gate `33609124506` PASS.
- Runtime change: persistent admin cover-error text, explicit manual retry bypassing browser backoff, retry revision `v6`; no remote-fetch policy change.
- Target: `V2.37.5`; Schema `2026082901`; Migration NONE; Owner Production Write NO.
""",encoding='utf-8')
PY

python3 -m json.tool VF_PROJECT.json >/dev/null
php -l src/app/FunctionalWorkspaceShell.php
php -l src/app/bootstrap.php
node --check src/assets/workspace.js
git diff --check

test "$(cat VERSION)" = 2.37.5
test "$(cat src/VERSION.txt)" = 2.37.5
grep -Fx "define('VF_VERSION', '2.37.5');" src/app/bootstrap.php >/dev/null
grep -F 'data-cover-refresh-id' src/app/FunctionalWorkspaceShell.php >/dev/null
grep -F 'data-cover-diagnostic' src/app/FunctionalWorkspaceShell.php >/dev/null
grep -F 'vf-cover-retry:v6:${id}' src/assets/workspace.js >/dev/null
grep -F 'const refreshCoverBatch=async(batch,manual=false)' src/assets/workspace.js >/dev/null
grep -F '.vf-cover-diagnostic[hidden]{display:none}' src/assets/surface-workspace.css >/dev/null
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$SOURCE":database)"

mapfile -t changed < <(git status --porcelain | sed -E 's/^.. //' | sort)
printf '%s\n' "${changed[@]}" | tee /tmp/p01-v2375-stage-files.txt
expected=$(cat <<'EOF'
CHANGELOG.md
VERSION
VF_PROJECT.json
docs/authority/CURRENT.md
docs/evidence/P01_V2.37.5_RELEASE_CANDIDATE_20260902.md
docs/handoff/CURRENT_STATE.md
src/VERSION.txt
src/app/bootstrap.php
EOF
)
test "$(printf '%s\n' "${changed[@]}")" = "$expected"

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add CHANGELOG.md VERSION VF_PROJECT.json docs/authority/CURRENT.md docs/evidence/P01_V2.37.5_RELEASE_CANDIDATE_20260902.md docs/handoff/CURRENT_STATE.md src/VERSION.txt src/app/bootstrap.php
git commit -m 'release: stage V2.37.5 cover diagnostics hotfix'
git push origin HEAD:$PRODUCT_BRANCH
CANDIDATE=$(git rev-parse HEAD); TREE=$(git rev-parse HEAD^{tree}); RUNTIME=$(git rev-parse HEAD:src)
printf 'P01_V2375_STAGE=PASS\nOWNER_PRODUCTION_OBSERVED=2.37.4\nPUBLISHED_SOURCE=%s\nHOTFIX=%s\nFOCUSED_GATE=%s\nCANDIDATE=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' "$SOURCE" "$HOTFIX" "$FOCUSED_GATE" "$CANDIDATE" "$TREE" "$RUNTIME" "$SCHEMA" | tee /tmp/p01-v2375-stage-verdict.txt
