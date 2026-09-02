#!/usr/bin/env bash
set -Eeuo pipefail

PRODUCT_REPO=llhzx2018/vf-start
PRODUCT_BRANCH=release/v2371-formal-candidate-20260902
MAIN=fe0aaef44b163c4b899d802e73faa69d06b0f285
HOTFIX=0fdf3746d1b218b0781bac44bd3079ef5582e044
DEVELOP=6442c4b40a029ff359539d4adb509260c1ecf496
SCHEMA=2026082901

cd product
test "$(git rev-parse HEAD)" = "$HOTFIX"
test "$(git rev-parse HEAD^)" = "$MAIN"
test "$(git rev-parse origin/main)" = "$MAIN"
test "$(git rev-parse origin/develop)" = "$DEVELOP"
test "$(cat VERSION)" = 2.37.0
test "$(cat src/VERSION.txt)" = 2.37.0
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$MAIN":database)"

printf '2.37.1\n' > VERSION
printf '2.37.1\n' > src/VERSION.txt
python3 - <<'PY'
from pathlib import Path
import json

p=Path('src/app/bootstrap.php')
s=p.read_text(encoding='utf-8')
old="define('VF_VERSION', '2.37.0');"
new="define('VF_VERSION', '2.37.1');"
if old not in s: raise SystemExit('bootstrap version anchor missing')
p.write_text(s.replace(old,new,1),encoding='utf-8')

p=Path('CHANGELOG.md')
s=p.read_text(encoding='utf-8')
head="""## V2.37.1 · Watch Cover Hydration Hotfix Candidate · 2026-09-02

- 修复影视资源大量显示单字占位而无法自动补海报的问题：封面提取器在 OpenGraph 之外新增 JSON-LD、`data-original`、`data-src`、`data-lazy-src`、`data-url` 与普通 `<img>` 候选。
- 继续保持 `og:image` 最高优先级，并对 poster/cover/thumb/pic/vod/video/lazy 语义加权；logo/avatar/二维码/banner/advert/icon 降权，避免把站点装饰图当海报。
- 升级浏览器端失败重试 key revision，使 V2.37.0 已写入的 1 小时失败缓存不会阻止新提取器上线后立即重新补图。
- Hotfix Gate R2 `33591609518` PASS；真实 `xiaoheimi.cc` 海报抓取与图片下载 PASS。
- 四个 Owner 主要影视源真实诊断 PASS：`www.iyf.tv` 桌面播放页、`www.xiaobaotv.com`、`xiaoheimi.cc`、`xiaoyakankan.com` 均可从各自静态详情/播放页提取并下载有效封面；`mview.iyf.tv` 纯 JS 壳没有静态海报元数据，保留为已知边界。
- Schema 保持 `2026082901`，无 Migration；目标 Atomic 严格为 `V2.37.0 → V2.37.1`。

"""
if not s.startswith('## V2.37.1 '): p.write_text(head+s,encoding='utf-8')

p=Path('VF_PROJECT.json')
d=json.loads(p.read_text(encoding='utf-8'))
d['status']='V2.37.0 OWNER PRODUCTION / V2.37.1 HOTFIX RELEASE CANDIDATE'
d['working_version']='2.37.1'
d['target_release_version']='2.37.1'
d['current_phase']='V2.37.1 WATCH COVER HYDRATION HOTFIX / FORMAL RELEASE CANDIDATE'
d['candidate_version']='2.37.1'
d['candidate_schema_version']='2026082901'
d['candidate_state']='V2.37.1 FORMAL RELEASE CANDIDATE / NOT PUBLISHED'
d['formal_release_state']='V2.37.1 FORMAL GATES IN PROGRESS / NOT PUBLISHED'
d['current_authority']='Owner Production V2.37.0 / Published Latest V2.37.0 / V2.37.1 Hotfix Candidate'
d['next_action']='Run V2.37.1 Candidate Readiness, Formal Bind, Formal Artifact and Strict Fresh. Do not publish before gates PASS; Owner Production write remains NO.'
d['current_change']={
  'change_id':'P01-V2371-WATCH-COVER-HYDRATION-HOTFIX-20260902',
  'type':'PATCH HOTFIX / WATCH COVER HYDRATION',
  'production_base':'fe0aaef44b163c4b899d802e73faa69d06b0f285',
  'hotfix_candidate':'0fdf3746d1b218b0781bac44bd3079ef5582e044',
  'hotfix_gate_r1':33591472844,
  'hotfix_gate_r1_classification':'HARNESS_ONLY_WORKFLOW_CONFIG',
  'hotfix_gate_r2':33591609518,
  'four_site_diagnostic':33592368667,
  'detail_level_diagnostic':33592546995,
  'schema_change':False,
  'migration':None,
  'version_change':True,
  'release_authorized_by_owner':True,
  'main_write':False,
  'production_write':False,
  'runner_main_write':False,
  'release_completed':False
}
d['v2_37_1_release_candidate']={
  'source_version':'2.37.0',
  'target_version':'2.37.1',
  'schema_version':'2026082901',
  'production_base':'fe0aaef44b163c4b899d802e73faa69d06b0f285',
  'hotfix_candidate':'0fdf3746d1b218b0781bac44bd3079ef5582e044',
  'runtime_hotfix_files':['src/app/ResourceCoverCache.php','src/assets/workspace.js'],
  'hotfix_gate':33591609518,
  'four_site_diagnostic':33592368667,
  'detail_level_diagnostic':33592546995,
  'schema_change':False,
  'migration':None,
  'assistant_production_write':False,
  'state':'STAGE CANDIDATE / NOT PUBLISHED'
}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

block="""<!-- P01_V2371_RELEASE_CANDIDATE -->
## V2.37.1 Watch Cover Hydration Hotfix Candidate · 2026-09-02

- Owner Production / Published Latest 仍为 `V2.37.0`；本段仅为 **Release Candidate**，未写 Production。
- 根因：V2.37.0 自动封面提取器主要依赖 OpenGraph；大量影视模板把真实海报放在 `data-original` / `data-src` 等懒加载字段，导致 `cover_url` 为空并退回单字占位。
- Product Hotfix `0fdf3746d1b218b0781bac44bd3079ef5582e044`：只修改 `ResourceCoverCache.php` 与 `workspace.js`；Hotfix Gate R2 `33591609518` PASS。
- Owner 主要影视源真实验证：爱壹帆桌面播放页 / 小宝影院 / 小黑米 / 小鸭看看均成功提取并下载真实图片；诊断 `33592368667`、`33592546995` PASS。
- Schema `2026082901` 不变，无 Migration；目标升级路径严格 `V2.37.0 → V2.37.1`。
- Next：Candidate Readiness → Formal Bind → Formal Artifact → Strict Fresh；全部 PASS 后才允许 Tag / Release / core-updates。

> 以下 V2.37.0 Owner Production Closure 继续是当前 Production Truth，直到 Owner 完成 V2.37.1 在线更新并闭环。

"""
for name in ['docs/authority/CURRENT.md','docs/handoff/CURRENT_STATE.md']:
    q=Path(name); t=q.read_text(encoding='utf-8')
    if '<!-- P01_V2371_RELEASE_CANDIDATE -->' not in t:
        lines=t.splitlines(True)
        if not lines: raise SystemExit(name+' empty')
        q.write_text(lines[0]+'\n'+block+''.join(lines[1:]),encoding='utf-8')

p=Path('docs/evidence/P01_V2.37.1_RELEASE_CANDIDATE_20260902.md')
p.write_text("""# P01 · VF Start · V2.37.1 Release Candidate Evidence

- Date: 2026-09-02
- Production Base: `fe0aaef44b163c4b899d802e73faa69d06b0f285` / V2.37.0 Owner Production Closure
- Hotfix Candidate: `0fdf3746d1b218b0781bac44bd3079ef5582e044`
- Hotfix Files: `src/app/ResourceCoverCache.php`, `src/assets/workspace.js`
- Hotfix Gate R1: `33591472844` / HARNESS ONLY / workflow configuration / no product write
- Hotfix Gate R2: `33591609518` / PASS
- Four-site Diagnostic: `33592368667` / PASS
- Detail-level Diagnostic: `33592546995` / PASS
- Tested provider patterns: IYF desktop `og:image`; Xiaobao `og:image + data-original + JSON-LD`; Xiaoheimi `data-original`; Xiaoya `data-src`.
- Known boundary: `mview.iyf.tv` mobile JS shell exposes no static poster metadata; standard `www.iyf.tv/play/...` is supported.
- Target: V2.37.1, Schema `2026082901`, Migration NONE.
- Owner Production Write: NO.
""",encoding='utf-8')
PY

python3 -m json.tool VF_PROJECT.json >/dev/null
php -l src/app/ResourceCoverCache.php
php -l src/app/bootstrap.php
node --check src/assets/workspace.js
git diff --check

test "$(cat VERSION)" = 2.37.1
test "$(cat src/VERSION.txt)" = 2.37.1
grep -Fx "define('VF_VERSION', '2.37.1');" src/app/bootstrap.php >/dev/null
test "$(git rev-parse HEAD:database)" = "$(git rev-parse "$MAIN":database)"

mapfile -t changed < <(git status --porcelain | sed -E 's/^.. //' | sort)
printf '%s\n' "${changed[@]}" | tee /tmp/p01-v2371-stage-files.txt
expected=$(cat <<'EOF'
CHANGELOG.md
VERSION
VF_PROJECT.json
docs/authority/CURRENT.md
docs/evidence/P01_V2.37.1_RELEASE_CANDIDATE_20260902.md
docs/handoff/CURRENT_STATE.md
src/VERSION.txt
src/app/bootstrap.php
EOF
)
test "$(printf '%s\n' "${changed[@]}")" = "$expected"

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add CHANGELOG.md VERSION VF_PROJECT.json docs/authority/CURRENT.md docs/evidence/P01_V2.37.1_RELEASE_CANDIDATE_20260902.md docs/handoff/CURRENT_STATE.md src/VERSION.txt src/app/bootstrap.php
git commit -m 'release: stage V2.37.1 watch cover hotfix'
git push origin HEAD:$PRODUCT_BRANCH

CANDIDATE=$(git rev-parse HEAD)
TREE=$(git rev-parse HEAD^{tree})
RUNTIME=$(git rev-parse HEAD:src)
printf 'P01_V2371_STAGE=PASS\nPRODUCTION_BASE=%s\nHOTFIX=%s\nCANDIDATE=%s\nTREE=%s\nRUNTIME_TREE=%s\nSCHEMA=%s\nMIGRATION=NONE\nOWNER_PRODUCTION_WRITE=NO\n' "$MAIN" "$HOTFIX" "$CANDIDATE" "$TREE" "$RUNTIME" "$SCHEMA" | tee /tmp/p01-v2371-stage-verdict.txt
