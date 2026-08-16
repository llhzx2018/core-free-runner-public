#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = '2.21.17'
SOURCE_VERSION = '2.21.16'
SCHEMA = '2026080902'
CANDIDATE_COMMIT = '89f55e9a772904ebe03537ec54c2891e13a52c80'
CANDIDATE_TREE = '184738a87e5bdf9a4d2cd912933f6a935dcc9038'
PRODUCTION_COMMIT = '4c908ae6a32ed0855751bbe809c8b204d957aba1'
REGRESSION_RUN = 31936680515
FORMAL_GATE_RUN = 31937010308
GATE_ONLY_FILES = {
    '.gitignore', 'CHANGELOG.md', 'DEPLOY-HERE.txt', 'FULL-PACKAGE-NOTES.txt',
    'README.md', 'UPGRADE-V2.txt', 'robots.txt',
}
LEGACY_EXTENSION_ZIP = 'VF-Start-Browser-Extension.zip'
EXPECTED_RUNTIME_DELTA = {
    'VERSION.txt',
    'app/AdminShell.php',
    'app/SecurityManager.php',
    'app/bootstrap.php',
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_module('p01_base_formal_22117', HERE / 'p01-build-release.py')
v2 = load_module('p01_v2_formal_22117', HERE / 'p01-build-release-v2.py')


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime_boundary(files: dict[str, bytes]) -> dict[str, bytes]:
    return {
        k: v for k, v in files.items()
        if k != 'release-manifest.json'
        and k not in GATE_ONLY_FILES
        and k != LEGACY_EXTENSION_ZIP
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--production', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--candidate-commit', required=True)
    ap.add_argument('--candidate-tree', required=True)
    ap.add_argument('--production-commit', required=True)
    args = ap.parse_args()

    if args.candidate_commit != CANDIDATE_COMMIT:
        raise SystemExit('candidate commit mismatch')
    if args.candidate_tree != CANDIDATE_TREE:
        raise SystemExit('candidate tree mismatch')
    if args.production_commit != PRODUCTION_COMMIT:
        raise SystemExit('production commit mismatch')

    cand = Path(args.candidate).resolve()
    prod = Path(args.production).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    target_delivery = base.collect(cand)
    source_delivery = base.collect(prod)
    if target_delivery.get('VERSION.txt', b'').strip() != VERSION.encode():
        raise SystemExit('candidate VERSION.txt mismatch')
    if source_delivery.get('VERSION.txt', b'').strip() != SOURCE_VERSION.encode():
        raise SystemExit('production VERSION.txt mismatch')

    target_runtime = runtime_boundary(target_delivery)
    source_runtime = runtime_boundary(source_delivery)
    if set(target_runtime) != set(source_runtime):
        added = sorted(set(target_runtime) - set(source_runtime))
        removed = sorted(set(source_runtime) - set(target_runtime))
        raise SystemExit(f'formal runtime shape drift added={added} removed={removed}')

    changed = {
        k for k in target_runtime
        if sha256_bytes(target_runtime[k]) != sha256_bytes(source_runtime[k])
    }
    if changed != EXPECTED_RUNTIME_DELTA:
        raise SystemExit(f'unexpected runtime delta: {sorted(changed)}')

    ext = json.loads(target_delivery['browser-extension/manifest.json'].decode('utf-8'))
    if str(ext.get('version')) != '1.6.4':
        raise SystemExit('browser extension version drift')

    old_manifest = json.loads(target_delivery.get('release-manifest.json', b'{}').decode('utf-8'))
    release_manifest = dict(old_manifest)
    release_manifest.update({
        'project': 'VF Start',
        'project_id': 'P01',
        'project_slug': 'vf-start',
        'version': VERSION,
        'source_version': SOURCE_VERSION,
        'release_type': 'formal-release',
        'stage': 'FORMAL_RELEASE',
        'deployable': True,
        'release_authorized': True,
        'source_commit': CANDIDATE_COMMIT,
        'source_tree': CANDIDATE_TREE,
        'production_source_commit': PRODUCTION_COMMIT,
        'schema_version': SCHEMA,
        'schema_change': False,
        'schema_migrations': [],
        'runtime_data_included': False,
        'seed_user_business_data_included': False,
        'runtime_hashed_file_count': len(target_runtime),
        'runtime_files': {k: sha256_bytes(v) for k, v in sorted(target_runtime.items())},
        'candidate_verification': {
            'status': 'PASS',
            'regression_run_id': REGRESSION_RUN,
            'formal_artifact_gate_run_id': FORMAL_GATE_RUN,
        },
        'atomic_runtime_boundary': {
            'source_version': SOURCE_VERSION,
            'target_version': VERSION,
            'source_app_gate_count': len(source_runtime),
            'target_app_gate_count': len(target_runtime),
            'gate_only_files_excluded': sorted(GATE_ONLY_FILES),
            'legacy_extension_zip_excluded': LEGACY_EXTENSION_ZIP,
            'runtime_shape_changed': False,
            'runtime_delta': sorted(changed),
        },
        'browser_extension': {
            'version': '1.6.4',
            'release_unit': 'INDEPENDENT',
            'released_this_round': False,
            'mechanical_version_bump': False,
        },
        'update': {
            'project_id': 'P01',
            'component_id': 'APP',
            'manifest_truth': 'llhzx2018/core-updates/projects/P01.json',
            'release_truth': 'GitHub Release',
            'asset_name': f'VF_Start_V{VERSION}_UPDATE.zip',
            'supported_from': [SOURCE_VERSION],
            'backup_required': True,
            'rollback_supported': True,
        },
    })
    release_bytes = (json.dumps(release_manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

    target_delivery_with_manifest = dict(target_delivery)
    target_delivery_with_manifest['release-manifest.json'] = release_bytes
    atomic_target = dict(target_runtime)
    atomic_target['release-manifest.json'] = release_bytes

    repair = v2.build_repair(
        source_runtime,
        atomic_target,
        sha256_bytes(target_runtime['app/UpdateManager.php']),
    )
    old_source = "public const SOURCE_VERSION='2.21.14';"
    old_target = "public const TARGET_VERSION='2.21.15';"
    new_source = f"public const SOURCE_VERSION='{SOURCE_VERSION}';"
    new_target = f"public const TARGET_VERSION='{VERSION}';"
    if repair.count(old_source) != 1 or repair.count(old_target) != 1:
        raise SystemExit('atomic version template anchor mismatch')
    repair = repair.replace(old_source, new_source, 1).replace(old_target, new_target, 1)

    repair_name = f'repair-v{VERSION}.php'
    repair_path = out / repair_name
    repair_path.write_text(repair, encoding='utf-8', newline='\n')
    base.deterministic_zip(out / f'VF_Start_V{VERSION}_FULL.zip', target_delivery_with_manifest)
    base.deterministic_zip(out / f'VF_Start_V{VERSION}_SOURCE.zip', target_delivery_with_manifest)
    rb = repair_path.read_bytes()
    base.deterministic_zip(out / f'VF_Start_V{VERSION}_ATOMIC.zip', {repair_name: rb})
    base.deterministic_zip(out / f'VF_Start_V{VERSION}_UPDATE.zip', {repair_name: rb})

    notes = (
        f'# VF Start V{VERSION} 正式发布\n\n'
        f'- Production 基线：V{SOURCE_VERSION}\n'
        f'- Release：V{VERSION}\n'
        f'- Candidate Product Commit：{CANDIDATE_COMMIT}\n'
        f'- Candidate Product Tree：{CANDIDATE_TREE}\n'
        f'- Schema：{SCHEMA}（不变）\n'
        '- Browser Helper：1.6.4（不变）\n'
        '- Candidate Regression：PASS\n'
        '- Formal Artifact Gate：PASS\n'
        '- Production Upgrade：本次发布阶段不执行\n'
    )
    (out / f'VF_Start_V{VERSION}_RELEASE_NOTES.md').write_text(notes, encoding='utf-8')

    formal = {
        'project_id': 'P01',
        'component_id': 'APP',
        'version': VERSION,
        'source_version': SOURCE_VERSION,
        'candidate_commit': CANDIDATE_COMMIT,
        'candidate_tree': CANDIDATE_TREE,
        'production_commit': PRODUCTION_COMMIT,
        'schema': SCHEMA,
        'release_authorized': True,
        'candidate_verification': 'PASS',
        'regression_run_id': REGRESSION_RUN,
        'formal_artifact_gate': 'PASS',
        'formal_artifact_gate_run_id': FORMAL_GATE_RUN,
        'runtime_source_files': len(source_runtime),
        'runtime_target_files': len(target_runtime),
        'runtime_delta': sorted(changed),
        'browser_extension': '1.6.4 / UNCHANGED',
        'production_upgrade': 'NOT EXECUTED',
    }
    (out / f'VF_Start_V{VERSION}_RELEASE_MANIFEST.json').write_text(
        json.dumps(formal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )

    artifacts = [p for p in sorted(out.iterdir()) if p.is_file() and p.name != 'SHA256SUMS.txt']
    (out / 'SHA256SUMS.txt').write_text(
        ''.join(f'{base.sha256_file(p)}  {p.name}\n' for p in artifacts), encoding='utf-8'
    )

    print(json.dumps({
        'version': VERSION,
        'source_version': SOURCE_VERSION,
        'candidate_commit': CANDIDATE_COMMIT,
        'candidate_tree': CANDIDATE_TREE,
        'production_commit': PRODUCTION_COMMIT,
        'runtime_source_files': len(source_runtime),
        'runtime_target_files': len(target_runtime),
        'runtime_delta': sorted(changed),
        'release_authorized': True,
        'status': 'BUILD_PASS',
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
