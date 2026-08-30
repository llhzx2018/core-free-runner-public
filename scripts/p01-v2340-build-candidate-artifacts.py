#!/usr/bin/env python3
from pathlib import Path
import hashlib, importlib.util, json

ROOT = Path.cwd()
VERSION = '2.34.0'
SOURCE_VERSION = '2.33.0'
SCHEMA = '2026082901'
CANDIDATE = '8cd4b78ec27ced5657888a692a32bad1cc953fcd'
CANDIDATE_TREE = '67ece5c16135e43acbfe6be8d1dad96e3d541900'
PRODUCT = '25dd705582a6f2c0c06a3f52c32c780c2268b5fa'
PRODUCT_TREE = 'd44882648a101e314ba66a66eb8b7f72ec67b283'
RUNTIME_TREE = 'f3eeb66fbce3949ef50483ac4c5a821edbd15d35'
SOURCE = '8c819c8bfd055d16b3ac367cef15f723431d9a42'
SOURCE_TREE = 'db5a6e2b6a852e6925727b974fb7130359e3cdf8'
SOURCE_RUNTIME_TREE = 'febc1b01a5b59963bc974cdc6455cfa824c0adc3'


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
    'app/FunctionalWorkspace.php',
    'app/SurfaceShell.php',
    'app/bootstrap.php',
    'assets/surface-home.js',
    'assets/workspace-create-bundle.js',
    'assets/workspace-primary-open.js',
    'assets/workspace-rebaseline.js',
    'assets/workspace.js',
    'cli/surface-verify.php',
    'workspace-action.php',
])
if changed != expected_delta:
    raise SystemExit('unexpected V2.34 runtime delta: ' + json.dumps(changed, ensure_ascii=False))
if added != ['assets/workspace-primary-open.js']:
    raise SystemExit('unexpected V2.34 added runtime files: ' + json.dumps(added))
if removed:
    raise SystemExit('unexpected V2.34 removed runtime files: ' + json.dumps(removed))

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
        'asset_name': 'VF_Start_V2.34.0_UPDATE.zip',
        'supported_from': [SOURCE_VERSION], 'backup_required': True,
        'rollback_supported': True, 'schema_migration_atomic': False,
    },
    'ux_v234': {
        'global_search_efficiency': True,
        'cross_page_bulk_selection': True,
        'bulk_privacy_convergence': True,
        'bulk_tag_management': True,
        'favorite_recent_efficiency': True,
        'recent_time_windows': True,
        'midwidth_category_search': True,
        'mobile_search_reachability': True,
    },
}
manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
full = dict(target_delivery)
full['release-manifest.json'] = manifest_bytes
atomic = dict(target)
atomic['release-manifest.json'] = manifest_bytes
repair = v2.build_repair(source, atomic, sha(target['app/UpdateManager.php']))
old = "public const SOURCE_VERSION='2.21.14';\n    public const TARGET_VERSION='2.21.15';\n    public const TARGET_SCHEMA='2026080902';"
new = "public const SOURCE_VERSION='2.33.0';\n    public const TARGET_VERSION='2.34.0';\n    public const TARGET_SCHEMA='2026082901';"
if repair.count(old) != 1:
    raise SystemExit('repair constant anchor mismatch')
repair = repair.replace(old, new, 1)

out = Path('/tmp/p01-v2340-candidate-artifacts')
out.mkdir(parents=True, exist_ok=True)
repair_path = out / 'repair-v2.34.0.php'
repair_path.write_text(repair, encoding='utf-8', newline='\n')
base.deterministic_zip(out / 'VF-Start-V2.34.0-FULL.zip', full)
base.deterministic_zip(out / 'VF_Start_V2.34.0_UPDATE.zip', {repair_path.name: repair_path.read_bytes()})
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
(out / 'P01-V2.34.0-CANDIDATE-GATE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
artifacts = [p for p in sorted(out.iterdir()) if p.is_file()]
(out / 'SHA256SUMS.txt').write_text(''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in artifacts), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
