#!/usr/bin/env bash
set -Eeuo pipefail
: "${VF_RELEASE_WRITE_TOKEN:?VF_RELEASE_WRITE_TOKEN required}"

BRANCH='governance/p06-v0115-release-authority-closure-20260828'
BASE='a9300382d3a862fb599b8b928961ead38dee8f31'
ROOT="$RUNNER_TEMP/p06-v0115-authority"
rm -rf "$ROOT"

git clone "https://x-access-token:${VF_RELEASE_WRITE_TOKEN}@github.com/llhzx2018/vf-press.git" "$ROOT" >/dev/null 2>&1
git -C "$ROOT" checkout "$BRANCH" >/dev/null
test "$(git -C "$ROOT" rev-parse HEAD)" = "$BASE"
test "$(git -C "$ROOT" rev-parse origin/main)" = "$BASE"

python3 - "$ROOT/VF_PROJECT.json" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding='utf-8'))
assert d['project_id']=='P06'
assert d['version']=='0.1.15'
assert int(d['schema'])==3
prod=d.get('production_update_state',{})
assert prod.get('observed_runtime_version')=='0.1.12', prod
assert prod.get('observed_runtime_evidence')=='OWNER_DIRECT_READBACK_2026_08_24', prod
assert prod.get('agent_production_write')=='NOT_EXECUTED', prod

# Release truth: V0.1.15 is fully published/distributed; Production is still owner-controlled.
d['lifecycle']='RELEASE_CURRENT_PRODUCTION_PENDING_OWNER_UPDATE'
d['current_phase']='V0_1_15_RELEASE_CURRENT_PRODUCTION_PENDING_OWNER_UPDATE'
d['next_gate']='OWNER_AUTHENTICATED_PRODUCTION_UPDATE_TO_V0_1_15'

human=d.setdefault('human_ui_exposure_v0_1_15',{})
human['state']='RELEASED'
human['production_change']=False

rg=d.setdefault('release_gates',{})
rg['formal_release_v0_1_13']='PASS_REMOTE_ASSET_READBACK'
rg['formal_release_v0_1_14']='PASS_REMOTE_ASSET_READBACK'
rg['formal_release_v0_1_15']='PASS_REMOTE_ASSET_READBACK_RUN_33185141664'
rg['atomic_upgrade_v0_1_15']='PASS_MULTI_FROM_RUN_33185544041'
rg['distribution_manifest_v0_1_15']='PASS_RUN_33185676999'
rg['online_update_discovery_v0_1_15']='PASS_REAL_V0_1_12_SERVICE_RUN_33185971982'
rg['production_update_v0_1_15']='PENDING_OWNER_AUTHENTICATED_ACTION'

# Replace stale singular current release evidence with the current formal release line.
d['release_evidence']={
  'tag':'v0.1.15',
  'product_exact_source':'561e59a82f035e2622c4567710bec06a1c50dab3',
  'source_sha':'a9300382d3a862fb599b8b928961ead38dee8f31',
  'release_id':378572142,
  'runner_repository':'llhzx2018/core-free-runner-public',
  'formal_human_ui_run_id':33183662919,
  'atomic_release_gate_run_id':33184343643,
  'atomic_release_gate_job_id':98893338106,
  'publication_run_id':33185141664,
  'publication_job_id':98896079113,
  'multi_from_atomic_run_id':33185544041,
  'multi_from_atomic_job_id':98897479162,
  'distribution_manifest_run_id':33185676999,
  'distribution_manifest_job_id':98897935898,
  'v0_1_12_real_discovery_run_id':33185971982,
  'v0_1_12_real_discovery_job_id':98898946304,
  'release_url':'https://github.com/llhzx2018/vf-press/releases/tag/v0.1.15',
  'full_asset':'VF_Press_V0.1.15_FULL.zip',
  'full_asset_id':533972860,
  'full_bytes':271733,
  'full_sha256':'03702b4c0401f5777cfbe52702821f84a11a83e1ea2a06680b0ead3808820cd7',
  'update_asset':'VF_Press_V0.1.15_UPDATE.zip',
  'update_asset_id':533972862,
  'update_bytes':278578,
  'update_sha256':'152c44d18c55d9d022b8eabf71628d3faf9edc229a54badf1c9887fe8324e5fe',
  'core_updates_manifest_commit':'0e834d734a0a1ed6b2173feee3435eb8f6015d96',
  'supported_from_versions':['0.1.12','0.1.13','0.1.14'],
  'remote_readback':'PASS',
  'distribution_manifest':'PASS',
  'online_discovery':'PASS_REAL_V0_1_12_SERVICE',
  'production_write':'NOT_EXECUTED_OWNER_ACTION_REQUIRED'
}

# Preserve authenticated Production observation. Only move the target/allowed path forward.
prod['observed_runtime_version']='0.1.12'
prod['observed_runtime_evidence']='OWNER_DIRECT_READBACK_2026_08_24'
prod['observed_schema']='UNKNOWN'
prod['target_version']='0.1.15'
prod['update_type']='ATOMIC'
prod['schema_from']=3
prod['schema_to']=3
prod['supported_from_versions']=['0.1.12','0.1.13','0.1.14']
prod['production_update']='PENDING_OWNER_AUTHENTICATED_UPDATE_TO_V0_1_15'
prod['agent_production_write']='NOT_EXECUTED'
prod['release_available']='0.1.15'
prod['discovery_proof']='PASS_REAL_V0_1_12_ONLINE_UPDATE_SERVICE_RUN_33185971982'
d['production_update_state']=prod

with open(p,'w',encoding='utf-8',newline='\n') as f:
    json.dump(d,f,ensure_ascii=False,indent=2)
    f.write('\n')
PY

# Governance closure must be one-file only.
mapfile -t files < <(git -C "$ROOT" diff --name-only "$BASE" --)
test "${#files[@]}" = 1
test "${files[0]}" = 'VF_PROJECT.json'
python3 -m json.tool "$ROOT/VF_PROJECT.json" >/dev/null

git -C "$ROOT" config user.name 'VictorForge'
git -C "$ROOT" config user.email 'llhzx2018@gmail.com'
git -C "$ROOT" add VF_PROJECT.json
git -C "$ROOT" commit -m 'governance(P06): close V0.1.15 release authority' >/dev/null
HEAD="$(git -C "$ROOT" rev-parse HEAD)"
git -C "$ROOT" push origin "HEAD:$BRANCH" >/dev/null 2>&1

echo "P06_V0115_AUTHORITY_SOURCE=$HEAD"
echo P06_V0115_AUTHORITY_ONE_FILE=PASS
echo P06_V0115_AUTHORITY_PRODUCTION_PRESERVED=0.1.12
echo P06_V0115_AUTHORITY_BUILD=PASS
