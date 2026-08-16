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


base = load_module('p01_base_maintenance', HERE / 'p01-build-release.py')
v2 = load_module('p01_v2_atomic_maintenance', HERE / 'p01-build-release-v2.py')


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
        raise SystemExit(f'maintenance runtime shape drift added={added} removed={removed}')

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
        'release_type': 'formal-artifact-candidate-gate',
        'stage': 'FORMAL_ARTIFACT_CANDIDATE_GATE',
        'deployable': True,
        'release_authorized': False,
        'source_commit': args.candidate_commit,
        'source_tree': args.candidate_tree,
        'production_source_commit': args.production_commit,
        'schema_version': SCHEMA,
        'schema_change': False,
        'schema_migrations': [],
        'runtime_data_included': False,
        'seed_user_business_data_included': False,
        'runtime_hashed_file_count': len(target_runtime),
        'runtime_files': {k: sha256_bytes(v) for k, v in sorted(target_runtime.items())},
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
        f'# VF Start V{VERSION} Formal Artifact Candidate Gate\n\n'
        f'- Source: V{SOURCE_VERSION}\n'
        f'- Candidate: V{VERSION}\n'
        '- Release: NOT AUTHORIZED\n'
        '- Production: UNCHANGED\n'
        '- Schema: UNCHANGED\n'
        '- Browser Helper: 1.6.4 / UNCHANGED\n'
    )
    (out / f'VF_Start_V{VERSION}_RELEASE_NOTES.md').write_text(notes, encoding='utf-8')

    formal = {
        'project_id': 'P01',
        'component_id': 'APP',
        'version': VERSION,
        'source_version': SOURCE_VERSION,
        'candidate_commit': args.candidate_commit,
        'candidate_tree': args.candidate_tree,
        'production_commit': args.production_commit,
        'schema': SCHEMA,
        'release_authorized': False,
        'runtime_source_files': len(source_runtime),
        'runtime_target_files': len(target_runtime),
        'runtime_delta': sorted(changed),
        'browser_extension': '1.6.4 / UNCHANGED',
        'artifact_gate': 'PENDING_EXECUTION',
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
        'candidate_commit': args.candidate_commit,
        'candidate_tree': args.candidate_tree,
        'production_commit': args.production_commit,
        'runtime_source_files': len(source_runtime),
        'runtime_target_files': len(target_runtime),
        'runtime_delta': sorted(changed),
        'status': 'BUILD_PASS',
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
