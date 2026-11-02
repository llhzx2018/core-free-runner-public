#!/usr/bin/env python3
"""Build two isolated, non-release WordPress packages from exact Git source trees."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import argparse
import hashlib
import json

ROOT_FILES = {'vf-tool-m3u8.php', 'uninstall.php', 'plugin-manifest.json', 'tool-settings.schema.json'}
RUNTIME_DIRS = {'admin', 'config', 'includes', 'public', 'templates', 'tools'}
EXCLUDED = {'.git', '.github', 'tests', 'test', 'docs', 'doc', 'private', 'evidence', 'tmp', 'logs', 'log', 'cache'}

def allowed(relative):
    path = Path(relative)
    parts = path.parts
    if any(p.lower() in EXCLUDED for p in parts): return False
    if any(p.lower().endswith(('.log', '.zip', '.db', '.sqlite', '.sql', '.tar', '.gz')) for p in parts): return False
    return parts[0] in RUNTIME_DIRS if len(parts) > 1 else relative in ROOT_FILES

def create(root, output):
    paths = sorted((p for p in root.rglob('*') if p.is_file() and allowed(p.relative_to(root).as_posix())), key=lambda p: p.relative_to(root).as_posix())
    assert len(paths) > 300, f'package unexpectedly small: {len(paths)}'
    assert any(p.name == 'vf-tool-m3u8.php' for p in paths)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as z:
        for p in paths:
            entry = ZipInfo('vf-tool-m3u8/' + p.relative_to(root).as_posix(), date_time=(1980,1,1,0,0,0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, p.read_bytes())
    return {'files':len(paths), 'size':output.stat().st_size, 'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    a = create(args.baseline, args.out / 'baseline.zip')
    b = create(args.candidate, args.out / 'candidate.zip')
    assert a['files'] == b['files'], 'unexpected package file-count delta'
    print(json.dumps({'source_package':a,'candidate_package':b,'status':'PASS'},sort_keys=True))
