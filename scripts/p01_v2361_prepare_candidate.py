from pathlib import Path
import json

OLD='2.36.0'
NEW='2.36.1'
BASE='8cce764a455031d6c8cc20ec1c6fd79477f6ff28'
PRODUCT_MERGE='2b60b27c1e5cb53f841e9e7f0c8e521bacba1030'
RUNTIME_TREE='9788bdf228f3bd7e140a89f7881ce1b01c43f154'

root=Path('.')

# VERSION authorities
for rel in ['VERSION','src/VERSION.txt']:
    p=root/rel
    txt=p.read_text()
    if txt.strip()!=OLD:
        raise SystemExit(f'{rel} expected {OLD}, got {txt!r}')
    p.write_text(NEW+'\n')

# Runtime constant
p=root/'src/app/bootstrap.php'
txt=p.read_text()
old=f"define('VF_VERSION', '{OLD}');"
new=f"define('VF_VERSION', '{NEW}');"
if txt.count(old)!=1:
    raise SystemExit('bootstrap version fence failed')
p.write_text(txt.replace(old,new,1))

# CHANGELOG
p=root/'CHANGELOG.md'
txt=p.read_text()
marker='## V2.36.1 · Patch Release Candidate · 2026-09-01'
if marker in txt:
    raise SystemExit('duplicate V2.36.1 changelog marker')
section=f'''{marker}\n\n- 撤销 V2.36.0 中不符合 VF Start 原有产品模型的“管理员视角 / 公开视角 / 查看公开版 / 返回管理”双视角设计。\n- 恢复单一前台登录模型：未登录仅公开内容；已登录仍在同一前台直接显示公开 + 私人内容，并提供 `☷ 资源管理` 与 `⚙ 系统设置` 管理入口。\n- `public_view` / `preview_return` 不再承担产品视角切换，不再产生第二套前台状态。\n- 390 / 1440 Fresh Runtime 已验证匿名公开可见、私人隔离、登录后公开+私人、管理入口可达、旧视角参数失效；SQLite integrity / FK PASS。\n- Product 修复 PR #166 已合并；Authority PR #167 已收口。Formal Product Gate `33471511064` = PASS，Artifact `9786687777`。\n- Schema 保持 `2026082901`，无 Migration；本补丁不引入其他产品功能。\n- Candidate 版本推进为 `2.36.1`；当前仍未修改 `main` / Tag / GitHub Release / core-updates / Owner Production。\n\n'''
p.write_text(section+txt)

# Project authority metadata
p=root/'VF_PROJECT.json'
data=json.loads(p.read_text())
if data.get('production_version')!='2.36.0':
    raise SystemExit('production_version drift')
if data.get('schema_version')!='2026082901':
    raise SystemExit('schema drift')

data['status']='V2.36.0 PRODUCTION CLOSURE PASS / V2.36.1 PATCH RELEASE CANDIDATE PREPARATION'
data['working_version']=NEW
data['target_release_version']=NEW
data['current_phase']='V2.36.1 FORMAL PATCH RELEASE GATE / CANDIDATE PREPARATION'
data['candidate_version']=NEW
data['candidate_schema_version']='2026082901'
data['candidate_state']='V2.36.1 VERSIONED PATCH CANDIDATE / FORMAL RELEASE GATE STARTED / NOT RELEASED'
data['formal_release_state']='V2.36.0 PUBLISHED / PRODUCTION CLOSURE PASS'
data['develop_state']='V2.36.1 PATCH CANDIDATE PREPARATION / SINGLE-SYSTEM AUTH MODEL RESTORED / NOT RELEASED'
data['current_authority']='Owner Production V2.36.0 Closure PASS / Published Latest V2.36.0 / develop single-system auth correction PR #166 + Authority PR #167 / Formal Product Gate 33471511064 PASS'
data['next_action']='Run V2.36.1 Patch Candidate Readiness and Formal Artifact Gates against the exact versioned candidate. Do not promote main, publish Tag/Release, mutate core-updates or write Owner Production unless subsequent gates pass.'
data['v2_36_1_release_candidate']={
    'base_develop': BASE,
    'product_fix_merge': PRODUCT_MERGE,
    'runtime_product_tree': RUNTIME_TREE,
    'version': NEW,
    'production_version': '2.36.0',
    'schema_version': '2026082901',
    'schema_change': False,
    'migration': None,
    'scope': 'PATCH / RESTORE SINGLE-SYSTEM LOGIN MODEL ONLY',
    'product_pr': 166,
    'authority_pr': 167,
    'product_gate': 33471511064,
    'product_artifact': 9786687777,
    'product_artifact_sha256': 'c5d59b936a2bff252b7d2d021b2183c692d5c10f0d82be89a8c2cacd0d556a54',
    'state': 'VERSIONED PATCH CANDIDATE PREPARATION / NOT RELEASED',
    'main_write': False,
    'production_write': False
}
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
