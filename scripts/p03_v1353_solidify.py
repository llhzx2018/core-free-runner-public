#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, subprocess, tempfile

root=Path('.')
version='1.35.3'
branch='work/p03-v1.35.3-post-seal-health-ui'
engineering_head='4452f7caa8c6914bfb89c13cbd6f86478d0fd92e'
engineering_run='31940219353'

(root/'VERSION').write_text(version+'\n', encoding='utf-8')

p=root/'src/app/bootstrap.php'
s=p.read_text(encoding='utf-8')
old="define('VFAB_VERSION', '1.35.2');"
new="define('VFAB_VERSION', '1.35.3');"
assert old in s and new not in s
p.write_text(s.replace(old,new,1), encoding='utf-8')

p=root/'scripts/build_atomic.py'
s=p.read_text(encoding='utf-8')
assert "TARGET_VERSION='1.35.2'" in s
assert "ALLOWED_SOURCES=['1.35.1']" in s
# First advance every target identity from 1.35.2 to 1.35.3, then advance the
# source compatibility boundary independently from 1.35.1 to 1.35.2.
s=s.replace('1.35.2','1.35.3')
s=s.replace("ALLOWED_SOURCES=['1.35.1']","ALLOWED_SOURCES=['1.35.2']",1)
p.write_text(s, encoding='utf-8')

p=root/'CHANGELOG.md'
s=p.read_text(encoding='utf-8')
marker='## V1.35.3 · Post-Seal Health + Reference-Driven UA/UI Candidate'
if marker not in s:
    section=f'''\n{marker}\n\n- Production baseline remains V1.35.2 / Schema 29; this candidate does not modify Schema or Migration.\n- Full product health review completed against current Git truth; engineering verification Run `{engineering_run}` PASS.\n- Reference Prototype: PRIMARY = JFrog Artifactory; secondary = Sonatype Nexus, Notion Search, Dropbox Version History.\n- Rebuilt daily navigation as `工作台 / 项目 / 资产 / 取用入口 / 搜索`, while keeping governance in `需要确认 / 设置`.\n- Added isolated `forge-ui.css` / `forge-ui.js` workspace layer: context Drawer for read-only details, Modal for writes, table overflow containment, long-name handling, accessibility semantics, reduced motion, and 390–1920 responsive contracts.\n- Added read-only cross-object semantic consistency audit for Project Slot, Artifact Family, Snapshot, Release, Recipe and frozen SHA/bytes relationships.\n- Repaired stale Runtime Source Manifest / source-integrity contract: current engineering runtime is 37 files (35 production files + 2 new UI modules).\n- Product Failure: NONE. Project Block: NONE.\n- Release / Tag / core-updates / Production Upgrade: NOT EXECUTED.\n\n'''
    first=s.find('\n## ')
    s=(s[:first]+section+s[first:]) if first>=0 else (s+section)
    p.write_text(s,encoding='utf-8')

p=root/'docs/authority/RPD.md'
s=p.read_text(encoding='utf-8')
s=s.replace('**当前 Production：** V1.35.1 / Schema 29','**当前 Production：** V1.35.2 / Schema 29',1)
s=s.replace('V1.35.0 完成了产品模型纠偏；当前 Production 已推进到 V1.35.1 / Schema 29。V1.35.1 属于维护型 Release，没有重新定义上述产品边界，也没有业务功能模型或 Schema 方向变化。',
            'V1.35.0 完成了产品模型纠偏；当前 Production 已推进到 V1.35.2 / Schema 29。V1.35.1 与 V1.35.2 均未重新定义上述产品边界；V1.35.2 完成统一在线更新接入。当前 V1.35.3 属于 Post-Seal 健康审计、BUG 清零与 Reference-Driven UA/UI 重构，继续继承本 RPD，不扩大产品边界。',1)
if '## 当前 V1.35.3 产品边界' not in s:
    s += '\n\n## 当前 V1.35.3 产品边界\n\nV1.35.3 只优化资产取回效率、项目上下文呈现、UA/UI 信息架构与长期数据一致性审计；不得把 VF Forge 扩展为通用网盘、多人协作 SaaS、企业知识库或 GitHub 替代品。\n'
p.write_text(s,encoding='utf-8')

p=root/'docs/authority/SSOT.md'
s=p.read_text(encoding='utf-8')
s=s.replace('**状态：** `CURRENT / GIT-GOVERNED / STABLE OPERATIONS / FINAL ONLINE PASS`','**状态：** `CURRENT / GIT-GOVERNED / POST-SEAL CANDIDATE`',1)
s=s.replace('**Working：** NONE','**Working：** V1.35.3',1)
s=s.replace('**Candidate：** NONE','**Candidate：** V1.35.3 / EXACT REVERIFY PENDING',1)
s=s.replace('**当前阶段：** `PRODUCTION V1.35.2 CLOSED / STABLE OPERATIONS`','**当前阶段：** `V1.35.3 POST-SEAL CANDIDATE VERIFICATION`',1)
if '## 0. V1.35.3 Post-Seal 当前施工合同' not in s:
    insert=f'''\n## 0. V1.35.3 Post-Seal 当前施工合同\n\n- Production Truth：V1.35.2 / Schema 29 / main；保持不动。\n- Working / Candidate：V1.35.3 / Schema 29 / `{branch}`。\n- Engineering Baseline：`{engineering_head}`。\n- Engineering Regression：core-free-runner-public Run `{engineering_run}` / PASS。\n- Scope：Post-Seal 全系统健康审计、BUG 清零、成熟产品基准研究、Reference-Driven UA/UI 大重构、跨对象语义一致性审计。\n- Schema / Migration：NONE / 29 → 29。\n- Release / Tag / core-updates / Production Upgrade / main Promotion：NOT AUTHORIZED / NOT EXECUTED。\n\n'''
    pos=s.find('\n## 1.')
    assert pos>=0
    s=s[:pos]+insert+s[pos:]
p.write_text(s,encoding='utf-8')

p=root/'docs/authority/ACCEPTANCE_MATRIX.md'
s=p.read_text(encoding='utf-8')
s=s.replace('**状态：** `CURRENT / SEALED / FINAL ONLINE PASS`','**状态：** `CURRENT / V1.35.3 CANDIDATE VERIFICATION`',1)
s=s.replace('**Working：** NONE','**Working：** V1.35.3',1)
s=s.replace('**Candidate：** NONE','**Candidate：** V1.35.3 / EXACT REVERIFY PENDING',1)
s=s.replace('**Lifecycle：** `STABLE_OPERATIONS`','**Lifecycle：** `POST_SEAL_CANDIDATE`',1)
if '## V1.35.3 Post-Seal Candidate Gate' not in s:
    gate=f'''\n## V1.35.3 Post-Seal Candidate Gate\n\n| 验收项 | 证据 | 结果 |\n|---|---|---|\n| Current Truth Readback | main = develop = c074678f… / Production V1.35.2 / Schema 29 | PASS |\n| Engineering Product Head | `{engineering_head}` | PASS |\n| Engineering Regression | core-free-runner-public Run `{engineering_run}` | PASS |\n| Schema / Migration | 29 → 29 / no database migration diff | PASS |\n| Runtime Source Manifest Contract | 37 / 37 exact files at engineering head | PASS |\n| Cross-object Semantic Consistency | Project / Slot / Family / Snapshot / Release / Recipe frozen relationships | PASS / 0 finding |\n| Browser E2E | Playwright Chromium | PASS |\n| Responsive | 390 / 480 / 640 / 768 / 1024 / 1280 / 1440 / 1920 | PASS |\n| UA/UI Gate | Reference-driven workspace + Drawer/Modal contract | PASS |\n| Exact V1.35.3 Candidate Reverification | final candidate commit | PENDING |\n| Formal Artifact Gate | FULL / UPDATE(Atomic) / SHA / Integrity / Upgrade fixture | PENDING |\n| Release / Production | 本轮停止线之外 | NOT EXECUTED |\n\n'''
    pos=s.find('\n| 验收项')
    assert pos>=0
    s=s[:pos]+gate+s[pos:]
p.write_text(s,encoding='utf-8')

handoff=f'''# CURRENT STATE · P03 VF Forge\n\n项目：P03 · VF Forge  \nRepository：`llhzx2018/vf-forge`  \nProduction：`V1.35.2 / Schema29 / DEPLOYED / RUNTIME VERIFIED / SOURCE EXACT / FINAL / DONE`  \nWorking：`V1.35.3`  \nCandidate：`V1.35.3 / EXACT REVERIFY PENDING`  \nLifecycle：`POST_SEAL_CANDIDATE`\n\n分支合同：\n\n- `main` = Production Truth；\n- `{branch}` = 本轮 scoped Working / Candidate Truth；\n- 禁止 Force Push。\n\nProduction Source：`V1.35.2 / 35 Runtime Files / SOURCE EXACT`  \nProduction Runtime Fingerprint：`61333e4c001edf97c4823bed8f6be553bafe43689a2d029b0d633ed991a52440`  \nEngineering Product Head：`{engineering_head}`  \nEngineering Regression：`core-free-runner-public / {engineering_run} / PASS`  \nCandidate Runtime Shape：`37 files`  \nSchema：`29 / NO MIGRATION`  \nProduct Failure：`NONE`  \nProject Block：`NONE`\n\n## NEXT_ACTION\n\n完成 V1.35.3 Candidate Identity 固化 → 对最终 Candidate Commit 执行 Exact Candidate Reverification → Formal Artifact Gate → STOP FOR MASTER。不得自行 Release、Tag、core-updates、Production Upgrade 或 main Promotion。\n'''
(root/'docs/handoff/CURRENT_STATE.md').write_text(handoff,encoding='utf-8')

p=root/'VF_PROJECT.json'
d=json.loads(p.read_text(encoding='utf-8'))
d['status']='ACTIVE / POST_SEAL_CANDIDATE'
d['working_version']=version
d['candidate_version']=version
d['working_branch']=branch
d['post_seal_iteration']={
    'version':version,
    'scope':['FULL PRODUCT HEALTH AUDIT','BUG ZEROING','REFERENCE-DRIVEN UA/UI LARGE REFACTOR','CROSS-OBJECT SEMANTIC CONSISTENCY'],
    'engineering_head':engineering_head,
    'engineering_regression_run':engineering_run,
    'engineering_regression':'PASS',
    'schema_change':False,
    'candidate_exact_reverification':'PENDING',
    'formal_artifact_gate':'PENDING',
    'release':'NOT EXECUTED',
    'production_upgrade':'NOT EXECUTED'
}
d['closure']['working']='V1.35.3'
d['closure']['candidate']='V1.35.3 / EXACT REVERIFY PENDING'
d['closure']['lifecycle']='POST_SEAL_CANDIDATE'
d['closure']['product_failure']='NONE'
d['closure']['project_block']='NONE'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

with tempfile.TemporaryDirectory() as td:
    subprocess.run(['python3','scripts/build_runtime.py',td],check=True,stdout=subprocess.DEVNULL)
    out=Path(td); rows=[]
    for item in sorted(x for x in out.rglob('*') if x.is_file()):
        rows.append(f"{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.relative_to(out).as_posix()}")
    assert len(rows)==37, len(rows)
    (root/'docs/decisions/SOURCE_MANIFEST.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')

print('CANDIDATE_IDENTITY_FILES_SOLIDIFIED=PASS')
print('RUNTIME_SOURCE_MANIFEST=37')
