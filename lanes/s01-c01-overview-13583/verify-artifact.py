import hashlib, json, pathlib, sys, zipfile

archive = pathlib.Path(sys.argv[1])
metadata = json.loads(pathlib.Path(sys.argv[2]).read_text())
destination = pathlib.Path(sys.argv[3])
data = archive.read_bytes()
assert len(data) == metadata['size_in_bytes']
assert 'sha256:' + hashlib.sha256(data).hexdigest() == metadata['digest']
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for item in z.infolist():
        path = pathlib.PurePosixPath(item.filename)
        assert not path.is_absolute() and '..' not in path.parts
        assert not (item.external_attr >> 16) & 0o170000 == 0o120000
        assert item.is_dir() or path.suffix in {'.json', '.png'}
    z.extractall(destination)
print(json.dumps({'artifact_id': metadata['id'], 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'crc_and_safe_paths': 'PASS', 'files': sorted(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file())}))
