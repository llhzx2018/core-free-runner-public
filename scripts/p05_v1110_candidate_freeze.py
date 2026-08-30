#!/usr/bin/env python3
import json
from pathlib import Path

p=Path('VF_PROJECT.json')
d=json.loads(p.read_text(encoding='utf-8'))
d.update({
    'status':'V1.1.10_RELEASE_CANDIDATE / FINAL_EXACT_SOURCE_GATE_PENDING / PRODUCTION_NOT_DEPLOYED',
    'version':'1.1.10','target_version':'1.1.10','working_version':'1.1.10',
    'formal_release':'v1.1.9','formal_release_state':'RELEASED_CURRENT_REAL_USER_FAIL',
    'runtime_recovery_candidate':'V1.1.10_RUNTIME_POINTER_INSTALL_FIX',
    'runtime_recovery_release':'PENDING_FINAL_EXACT_SOURCE_GATE',
    'production_runtime_acceptance':'V1.1.9_REAL_USER_FAIL_V1.1.10_NOT_DEPLOYED',
    'production_deployment':'NOT_DEPLOYED','production_write':0,
    'working_branch':'fix/p05-runtime-pointer-v1110-20260830',
    'owner_real_use_review':'V1.1.9_REAL_FAIL_V1.1.10_REAL_ENDPOINT_NOT_PROVEN',
    'owner_real_use_pass':'NOT_PROVEN_FOR_V1.1.10',
    'release_authorization':'PENDING_V1.1.10_FINAL_EXACT_SOURCE_GATE',
    'product_failure':'V1.1.9_FIRST_REQUEST_MARKER_CREATION_PLUS_HOME_ENV_STORAGE_DISCOVERY_COULD_REBIND_OLD_STATE',
    'next_action':'RUN FINAL V1.1.10 EXACT SOURCE FULL GATE; RELEASE ONLY AFTER PASS',
    'deployment_readiness':'V1.1.10_CANDIDATE_MACHINE_GATE_PENDING',
    'runtime_evidence':'docs/evidence/V1.1.10_RUNTIME_POINTER_INSTALL_MECHANISM_20260830.md'
})
d.setdefault('authority',{})['browser_first_install']='docs/authority/BROWSER_FIRST_INSTALL_MAIN_CURRENT.md'
d['authority']['release_candidate']='docs/authority/RELEASE_V1.1.10_CANDIDATE.md'
d['v1_1_10_runtime_pointer_install_fix']={
    'state':'RELEASE_CANDIDATE','install_identity_authority':'WEBROOT_RUNTIME_POINTER',
    'runtime_pointer':'VF_INSTALL_INSTANCE.json','pointer_created':'AFTER_SUCCESSFUL_SETUP_ONLY',
    'fresh_rule':'POINTER_ABSENT_MEANS_NEW_INSTALL','private_state_isolation':'POINTER_BOUND_RANDOM_SIBLING',
    'runtime_config':'../.vfseo-data-<instance_id>/config/runtime.env',
    'runtime_data':'../.vfseo-data-<instance_id>/data','setup_lock':'../.vfseo-data-<instance_id>/config/setup.lock.json',
    'backup_data':'../.vfseo-data-<instance_id>/backups','fresh_install_uses_home':False,
    'fresh_install_uses_environment_storage_paths':False,'fresh_install_database_heuristics':False,
    'legacy_in_place_compatibility':True,'mechanism_source':'34c7e03bd18283e27aa58e0ef138486fec15a901',
    'mechanism_gate_run':33316433128,'mechanism_gate_job':99270632195,'mechanism_gate':'PASS',
    'formal_staging_immutable_during_tests':'PASS','dirty_state_full_delete_reinstall':'PASS',
    'old_private_data_preserved_not_adopted':'PASS','chrome_e2e':'PASS','production_state':'NOT_DEPLOYED'
}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

docs={
'docs/authority/BROWSER_FIRST_INSTALL_MAIN_CURRENT.md':'''# P05 · VF SEO · Browser-first Install Current Authority\n\nCandidate: `v1.1.10`\n\n`VF_INSTALL_INSTANCE.json` is the only current Webroot installation authority. Pointer absent means fresh install. Opening `/` or `/setup` never creates it. The runtime must not inspect historical SQLite, setup locks, login history, business rows, HOME/POSIX-home state, `VF_ENV_FILE`, `VF_SQLITE_PATH`, or `VF_BACKUP_DIR` to guess installation state.\n\nNormal install: pristine FULL → `/setup` → create owner → initialize/self-test SQLite → atomically write pointer LAST → enter application. No SSH/CLI/manual `.env`/manual migration/private-data cleanup is required.\n\nA successful new install binds one random sibling private root:\n\n```text\n../.vfseo-data-<instance_id>/config/runtime.env\n../.vfseo-data-<instance_id>/config/setup.lock.json\n../.vfseo-data-<instance_id>/data/vf-seo.sqlite3\n../.vfseo-data-<instance_id>/backups/\n```\n\nDeleting the complete Webroot removes the pointer. Re-extracting pristine FULL is fresh; historical private data is preserved but not auto-adopted. Existing in-place historical Webroots retain compatibility only for their own existing pointer/marker.\n\nFormal FULL excludes pointer/marker files, SQLite/DB/WAL/SHM, runtime.env, setup.lock, `.vfseo-data-*`, backups and runtime test artifacts. Browser/Chrome tests run on isolated copies and formal staging must remain byte-identical.\n\nMechanism: `34c7e03bd18283e27aa58e0ef138486fec15a901` / Run `33316433128` / Job `99270632195` / PASS / Production write `0`.\n''',
'docs/handoff/CURRENT_STATE.md':'''# P05 · VF SEO · Current State\n\n```text\nCurrent Formal Release: v1.1.9\nReal-user verdict v1.1.9: FAIL for fresh-reinstall issue\nWorking Candidate: v1.1.10\nMechanism Gate: 33316433128 · PASS\nProduction: NOT_DEPLOYED\nProduction Write: 0\nSchema: VF-SEO-SCHEMA@1 / 1\n```\n\nv1.1.10 uses pointer-last installation: pointer absent means fresh, historical private storage cannot be discovered/adopted, and the pointer is committed only after owner/database setup and final self-test.\n\nNext: freeze complete candidate SHA → final Exact Source FULL/dirty-state/Chrome/staging-immutability gate → only after PASS promote and publish pristine `VF_SEO_V1.1.10_FULL.zip`. Production remains untouched.\n''',
'php/README.md':'''# P05 · VF SEO · PHP Runtime\n\nPHP 8.2+ / PDO_SQLite is the normal CloudPanel runtime. Browser installation requires no SSH, CLI, PM2, manual `.env`, migration, or private-data cleanup.\n\nNo `VF_INSTALL_INSTANCE.json` → `/setup` → owner → SQLite init/self-test → write pointer last. The pointer binds `../.vfseo-data-<instance_id>/` containing config/runtime.env, config/setup.lock.json, data/vf-seo.sqlite3 and backups/. Fresh installs do not use HOME/POSIX-home discovery or storage-path environment overrides. Full Webroot deletion therefore returns pristine FULL to `/setup` while historical private data remains untouched and unadopted. Runtime/private files and tests never ship in formal FULL.\n''',
'docs/evidence/V1.1.10_RUNTIME_POINTER_INSTALL_MECHANISM_20260830.md':'''# V1.1.10 Runtime Pointer Install Mechanism Evidence\n\n```text\nMechanism Source: 34c7e03bd18283e27aa58e0ef138486fec15a901\nPublic Runner Run: 33316433128\nJob: 99270632195\nResult: PASS\nRelease Write: 0\nProduction Write: 0\n```\n\nThe gate retained old SQLite, old admin/login success history, real project data, HOME state and poisoned storage environment variables, then deleted the complete Webroot and re-extracted the same formal FULL staging. PASS proved: pointer absent before setup; GET does not create pointer; fresh Webroot does not adopt historical storage; successful setup creates a new random sibling private root and writes pointer last; old SQLite SHA stays unchanged; Browser smoke and real Chrome E2E pass; formal staging is byte-identical before/after runtime tests; runtime/private state is excluded from the package.\n\nFormal v1.1.10 still requires a final gate on the complete Candidate Exact Source.\n''',
'docs/authority/RELEASE_V1.1.10_CANDIDATE.md':'''# P05 · VF SEO · v1.1.10 Release Candidate Authority\n\nState: `FINAL_EXACT_SOURCE_GATE_PENDING`\n\nv1.1.10 replaces fresh-install heuristics with the P01/P02-style Webroot runtime pointer model. Release is allowed only after one complete candidate SHA passes version/authority consistency, lint/typecheck/PHP syntax, formal FULL package gate, pointer-last browser setup, dirty historical-state full-delete reinstall, poisoned HOME/storage-env isolation, real Chrome E2E, formal staging immutability, and pristine post-test rebuild. Production writes remain zero. Previous formal release `v1.1.9` retains historical machine evidence but its real-user fresh-reinstall verdict is FAIL.\n'''
}
for path,body in docs.items():
    q=Path(path); q.parent.mkdir(parents=True,exist_ok=True); q.write_text(body,encoding='utf-8')

c=Path('CHANGELOG.md'); s=c.read_text(encoding='utf-8'); marker='## 1.1.10 · Runtime Pointer Install Model'
if marker not in s:
    h='# 变更记录\n\n'; assert s.startswith(h)
    e='''## 1.1.10 · Runtime Pointer Install Model（Candidate · 2026-08-30）\n\n- 对齐 P01/P02/P03/P04：不再通过 HOME、SQLite、setup lock、LOGIN_SUCCESS 或业务数据推断安装状态。\n- `VF_INSTALL_INSTANCE.json` 成为唯一 Webroot Runtime Pointer；pointer 不存在即新安装。\n- 首次 GET 不创建 pointer；只有管理员、SQLite 与最终自检成功后才原子写入。\n- 新实例绑定 `../.vfseo-data-<instance_id>/`，fresh install 不依赖 HOME/POSIX-home 或存储路径环境变量。\n- 全删 Webroot 再解压 pristine FULL 必须回到 `/setup`；旧 private data 保留但不采用。\n- Browser/Chrome 测试在隔离副本执行，formal staging 前后逐文件 SHA-256 必须一致。\n- Mechanism `34c7e03bd18283e27aa58e0ef138486fec15a901` / Runner `33316433128` / Job `99270632195` = PASS。\n- 仍为 Candidate；完整 Exact Source Gate PASS 后才允许 Release。Production 继续 NOT_DEPLOYED。\n\n'''
    c.write_text(h+e+s[len(h):],encoding='utf-8')
