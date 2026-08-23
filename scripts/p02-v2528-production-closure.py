from __future__ import annotations

import json
import subprocess
from pathlib import Path

repo = Path('product')
path = repo / 'VF_PROJECT.json'
data = json.loads(path.read_text(encoding='utf-8'))

now = '2026-08-24T04:30:00+08:00'
product_commit = '7861999d99a8de385bdd73f7892477e197c4559c'
product_tree = 'b4723505f944626a2e96e4e2f3d3b68aaf5ad734'
release_id = 375316679
release_at = '2026-08-23T20:23:03Z'
update_sha = '767a52ae1693d80ff27597f67b3b24dd6a79bd495183bc65a2594885ff1dc3f5'
update_bytes = 345779
core_updates_commit = '4ef79dbb1380f37c32d7f9221ed694e1c3c792e0'

data['status'] = 'V2.5.28_PRODUCTION_VERIFIED_CLOSED'
data['lifecycle'] = 'STABLE'
data['schema_version'] = 2401
data['schema_migration'] = False
data['source_authority'] = 'GIT_PLUS_AUTHENTICATED_PRODUCTION_READBACK'
data['as_of'] = now

data['maintenance_trigger'] = {
    'type': 'OWNER_REPORTED_RUNTIME_UX_BUG',
    'scope_contract': 'SCRATCH_WORKSPACE_NAVIGATION_EXIT_AND_SAVE_BARRIER',
    'summary': 'Temporary workspace overlaid the main content surface, so navigation appeared inert. V2.5.28 makes navigation wait for durable scratch save, exits the workspace before navigation, prevents duplicate workspace instances, and closes autosave/open races.',
    'schema_change': False,
    'result': 'CLOSED_IN_V2.5.28'
}

data['production_truth'] = {
    'current_version': '2.5.28',
    'latest_version': '2.5.28',
    'current_schema': 2401,
    'evidence': 'OWNER_AUTHENTICATED_SYSTEM_UPDATE_SCREENSHOT_2026_08_24_0430',
    'evidence_observed_at': now,
    'update_status': 'UP_TO_DATE',
    'authenticated_admin_session': 'PASS',
    'application_shell': 'PASS',
    'system_update_page': 'PASS_CURRENT_EQUALS_LATEST_V2.5.28',
    'version_footer': 'PASS_V2.5.28',
    'upgrade_executor': 'OWNER',
    'production_write_by_agent': 'NO'
}

data['formal_product_source'] = {
    'version': '2.5.28',
    'source_commit': product_commit,
    'source_tree': product_tree,
    'source_manifest_runtime_files': 76,
    'source_exact': 'PASS',
    'schema': 2401,
    'migration': False,
    'tag': 'v2.5.28'
}

data['candidate_verification'] = {
    'result': 'PASS',
    'version': '2.5.28',
    'runner_repository': 'llhzx2018/core-free-runner-public',
    'run_id': 32663984746,
    'source_manifest': '76_OF_76_PASS',
    'repository_source_privacy_gates': 'PASS',
    'deterministic_release_set': 'PASS',
    'fresh_install': 'PASS',
    'existing_data_upgrade': '2.5.27 -> 2.5.28 / PASS',
    'automatic_backup_and_data_preservation': 'PASS',
    'scratch_navigation_exit_matrix': 'PASS',
    'scratch_autosave_before_navigation': 'PASS',
    'scratch_workspace_singleton': 'PASS',
    'save_barrier': 'PASS',
    'schema': 2401,
    'migration': False,
    'production_write': 'NO'
}

data['formal_release'] = {
    'result': 'PASS',
    'version': '2.5.28',
    'remote_readback_run_id': 32664352190,
    'remote_readback_job_id': 97255330288,
    'tag': 'v2.5.28',
    'release_id': release_id,
    'published_at': release_at,
    'product_identity': product_commit,
    'source_tree': product_tree,
    'deterministic_release_set': 'PASS',
    'fresh_install': 'PASS',
    'existing_data_upgrade': '2.5.27 -> 2.5.28 / PASS',
    'automatic_backup_and_data_preservation': 'PASS',
    'scratch_navigation_and_save_regressions': 'PASS',
    'remote_readback': 'PASS',
    'asset_count': 8,
    'update_asset': {
        'name': 'VF_Library_V2.5.28_UPDATE.zip',
        'bytes': update_bytes,
        'sha256': update_sha
    },
    'production_write': 'NO'
}

data['core_updates'] = {
    'result': 'PASS',
    'repository': 'llhzx2018/core-updates',
    'authority_commit': core_updates_commit,
    'project_file': 'projects/P02.json',
    'current_version': '2.5.27',
    'target_version': '2.5.28',
    'from_versions': ['2.5.27'],
    'schema_from': '2401',
    'schema_to': '2401',
    'release_id': release_id,
    'product_identity': product_commit,
    'asset_name': 'VF_Library_V2.5.28_UPDATE.zip',
    'asset_bytes': update_bytes,
    'asset_sha256': update_sha,
    'remote_readback': 'PASS'
}

data['production_readiness'] = {
    'result': 'PASS_OWNER_AUTHENTICATED_PRODUCTION_READBACK',
    'version': '2.5.28',
    'actual_source_before_upgrade': 'v2.5.27',
    'target_source': 'v2.5.28',
    'core_updates_authority': 'PASS',
    'remote_release_metadata': 'PASS',
    'remote_update_bytes_sha256_atomic_identity': 'PASS',
    'owner_upgrade': 'PASS',
    'authenticated_post_upgrade_readback': 'PASS',
    'current_equals_latest': True,
    'latest_version': '2.5.28',
    'schema': 2401,
    'production_write_by_agent': 'NO'
}

branch = data.get('branch_authority') or {}
branch.update({
    'main_version': '2.5.28',
    'main_state': 'V2.5.28_FORMAL_RELEASE_PRODUCTION_VERIFIED',
    'develop_version': '2.5.28',
    'develop_state': 'V2.5.28_WORKING_RELEASE_ALIGNED',
    'runtime_product_identity': product_commit,
    'formal_source_tree': product_tree,
    'formal_tag': 'v2.5.28',
    'branch_relation': 'LIVE_GIT_COMPARE_REQUIRED',
    'force_push': 'NO',
    'history_rewrite': 'NO'
})
data['branch_authority'] = branch

pb = data.get('protected_boundaries') or {}
pb.update({
    'v2_5_28_main_promotion': 'COMPLETED_NON_FORCE',
    'v2_5_28_formal_tag_release': 'COMPLETED_REMOTE_READBACK_PASS',
    'v2_5_28_core_updates_publication': 'COMPLETED_REMOTE_READBACK_PASS',
    'v2_5_28_production_upgrade': 'EXECUTED_BY_OWNER_AND_AUTHENTICATED_UI_READBACK_PASS',
    'automatic_production_write': 'DISABLED',
    'force_push': 'NO',
    'history_rewrite': 'NO'
})
data['protected_boundaries'] = pb

data['v2_5_28_closure'] = {
    'bug': 'TEMPORARY_WORKSPACE_OVERLAY_BLOCKED_VISIBLE_NAVIGATION',
    'fixes': [
        'SAVE_BEFORE_NAVIGATION_AND_EXIT_WORKSPACE',
        'SINGLE_WORKSPACE_OPEN_PROMISE_LOCK',
        'STALE_AUTO_RESTORE_GUARD',
        'DURABLE_SAVE_BARRIER_FOR_IN_FLIGHT_AUTOSAVE'
    ],
    'candidate_run': 32663984746,
    'formal_release_readback_run': 32664352190,
    'formal_release_readback_job': 97255330288,
    'release_id': release_id,
    'core_updates_commit': core_updates_commit,
    'owner_production_evidence': 'OWNER_AUTHENTICATED_SYSTEM_UPDATE_SCREENSHOT_2026_08_24_0430',
    'owner_production_observed_at': now,
    'result': 'PASS_CLOSED'
}

data['project_failure'] = 'NONE'
data['project_block'] = 'NONE'
data['current_phase'] = 'V2.5.28_FINAL_CLOSED'
data['next_gate'] = 'NORMAL_OPERATIONS'
data['after_owner_upgrade_sequence'] = []

path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'VF Public Runner'], check=True)
subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'vf-public-runner@users.noreply.github.com'], check=True)
subprocess.run(['git', '-C', str(repo), 'checkout', '-b', 'closure/v2.5.28-production-readback'], check=True)
subprocess.run(['git', '-C', str(repo), 'add', 'VF_PROJECT.json'], check=True)
subprocess.run(['git', '-C', str(repo), 'commit', '-m', 'authority(P02): close V2.5.28 production readback'], check=True)
subprocess.run(['git', '-C', str(repo), 'push', 'origin', 'HEAD:closure/v2.5.28-production-readback'], check=True)
print('P02_V2_5_28_PRODUCTION_CLOSURE_WRITE=PASS')
print('PRODUCTION_WRITE=NO')
