#!/usr/bin/env python3
from pathlib import Path
import hashlib, importlib.util, json

ROOT = Path.cwd()
VERSION = '2.33.0'
SOURCE_VERSION = '2.32.0'
SCHEMA = '2026082901'
CANDIDATE = 'da430cf426915a11198cfb9c6aa5335da391402f'
CANDIDATE_TREE = '064b40e984c26a6d13b29e020415259a8e192a6a'
PRODUCT = 'faf853ab897c9e9b080dd365ab54df7698a8428c'
PRODUCT_TREE = 'f81d776da1fa92d04acd31ccbe6444cb1d9f0d43'
RUNTIME_TREE = 'febc1b01a5b59963bc974cdc6455cfa824c0adc3'
SOURCE = '120a42667fce7357fdaef03b64cb7ea41392040d'
SOURCE_TREE = 'd0fa7c87ebefef083712ec0b7707a6c4273943f2'
SOURCE_RUNTIME_TREE = 'f348cb314623906acc851cb79d75b1c8f6637aff'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit('cannot load ' + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base = load('base', ROOT / 'proven/scripts/p01-build-release.py')
v2 = load('v2', ROOT / 'proven/scripts/p01-build-release-v2.py')
sha = lambda b: hashlib.sha256(b).hexdigest()
gate_only = {'.gitignore', 'CHANGELOG.md', 'DEPLOY-HERE.txt', 'FULL-PACKAGE-NOTES.txt', 'README.md', 'UPGRADE-V2.txt', 'robots.txt'}

def runtime(files):
    return {k: v for k, v in files.items() if k != 'release-manifest.json' and k not in gate_only and k != 'VF-Start-Browser-Extension.zip'}

target_delivery = base.collect(ROOT / 'candidate/src')
source_delivery = base.collect(ROOT / 'production/src')
if target_delivery.get('VERSION.txt', b'').strip() != VERSION.encode():
    raise SystemExit('candidate version mismatch')
if source_delivery.get('VERSION.txt', b'').strip() != SOURCE_VERSION.encode():
    raise SystemExit('source version mismatch')

target = runtime(target_delivery)
source = runtime(source_delivery)
changed = sorted(k for k in target if k not in source or sha(target[k]) != sha(source[k]))
added = sorted(set(target) - set(source))
removed = sorted(set(source) - set(target))
expected_delta = sorted([
    'VERSION.txt',
    'app/FunctionalHome.php',
    'app/LinkHealth.php',
    'app/bootstrap.php',
    'assets/health.js',
    'health.php',
])
if changed != expected_delta:
    raise SystemExit('unexpected V2.33 runtime delta: ' + json.dumps(changed))
if added:
    raise SystemExit('unexpected V2.33 added runtime files: ' + json.dumps(added))
if removed:
    raise SystemExit('unexpected V2.33 removed runtime files: ' + json.dumps(removed))

manifest = {
    'project': 'VF Start', 'project_id': 'P01', 'project_slug': 'vf-start', 'component_id': 'APP',
    'version': VERSION, 'source_version': SOURCE_VERSION,
    'schema_version': SCHEMA, 'source_schema_version': SCHEMA,
    'release_type': 'candidate', 'stage': 'CANDIDATE_READINESS_GATE',
    'deployable': False, 'release_authorized': False,
    'candidate_source_commit': CANDIDATE, 'candidate_source_tree': CANDIDATE_TREE,
    'product_source_commit': PRODUCT, 'product_source_tree': PRODUCT_TREE,
    'runtime_source_tree': RUNTIME_TREE,
    'production_source_commit': SOURCE, 'production_source_tree': SOURCE_TREE,
    'production_runtime_tree': SOURCE_RUNTIME_TREE,
    'schema_change': False, 'schema_migrations': [],
    'runtime_data_included': False, 'seed_user_business_data_included': False,
    'runtime_hashed_file_count': len(target),
    'runtime_files': {k: sha(v) for k, v in sorted(target.items())},
    'atomic_runtime_boundary': {
        'source_version': SOURCE_VERSION, 'target_version': VERSION,
        'source_schema': SCHEMA, 'target_schema': SCHEMA,
        'source_app_gate_count': len(source), 'target_app_gate_count': len(target),
        'added_files': added, 'removed_files': removed, 'runtime_delta': changed,
    },
    'update': {
        'project_id': 'P01', 'component_id': 'APP',
        'publication': 'CANDIDATE_GATE_ONLY_NOT_PUBLISHED',
        'asset_name': 'VF_Start_V2.33.0_UPDATE.zip',
        'supported_from': [SOURCE_VERSION], 'backup_required': True,
        'rollback_supported': True, 'schema_migration_atomic': False,
    },
    'ux_v233': {
        'health_triage_rebaseline': True,
        'legacy_raw_problems_compatibility': True,
        'home_needs_action_excludes_restricted': True,
        'restricted_manual_confirmation': True,
        'ignored_excluded_from_review': True,
        'open_url_action': True,
    },
}
manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
full = dict(target_delivery)
full['release-manifest.json'] = manifest_bytes
atomic = dict(target)
atomic['release-manifest.json'] = manifest_bytes
repair = v2.build_repair(source, atomic, sha(target['app/UpdateManager.php']))
old = "public const SOURCE_VERSION='2.21.14';\n    public const TARGET_VERSION='2.21.15';\n    public const TARGET_SCHEMA='2026080902';"
new = "public const SOURCE_VERSION='2.32.0';\n    public const TARGET_VERSION='2.33.0';\n    public const TARGET_SCHEMA='2026082901';"
if repair.count(old) != 1:
    raise SystemExit('repair constant anchor mismatch')
repair = repair.replace(old, new, 1)

out = Path('/tmp/p01-v2330-candidate-artifacts')
out.mkdir(parents=True, exist_ok=True)
repair_path = out / 'repair-v2.33.0.php'
repair_path.write_text(repair, encoding='utf-8', newline='\n')
base.deterministic_zip(out / 'VF-Start-V2.33.0-FULL.zip', full)
base.deterministic_zip(out / 'VF_Start_V2.33.0_UPDATE.zip', {repair_path.name: repair_path.read_bytes()})
result = {
    'project_id': 'P01', 'version': VERSION, 'source_version': SOURCE_VERSION,
    'candidate_source': CANDIDATE, 'candidate_tree': CANDIDATE_TREE,
    'product_source': PRODUCT, 'product_tree': PRODUCT_TREE,
    'runtime_tree': RUNTIME_TREE,
    'source_commit': SOURCE, 'source_tree': SOURCE_TREE,
    'source_runtime_tree': SOURCE_RUNTIME_TREE,
    'source_schema': SCHEMA, 'schema': SCHEMA, 'schema_change': False,
    'runtime_source_files': len(source), 'runtime_target_files': len(target),
    'runtime_added': added, 'runtime_removed': removed,
    'runtime_delta': changed, 'runtime_delta_count': len(changed),
    'atomic_update': True, 'atomic_schema_migration': False,
    'release_published': False, 'owner_production_write': False,
    'status': 'CANDIDATE_ARTIFACT_BUILD_PASS',
}
(out / 'P01-V2.33.0-CANDIDATE-GATE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
artifacts = [p for p in sorted(out.iterdir()) if p.is_file()]
(out / 'SHA256SUMS.txt').write_text(''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in artifacts), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
