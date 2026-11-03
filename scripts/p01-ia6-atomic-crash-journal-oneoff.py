#!/usr/bin/env python3
"""Disposable exact-repair Atomic journal crash-state fixture; no Production."""
import base64, datetime, json, pathlib, re, shutil, sqlite3, subprocess, sys
site=pathlib.Path(sys.argv[1]).resolve()
repair=pathlib.Path(sys.argv[2]).resolve()
assert str(site).startswith("/tmp/p01-ia6-atomic-")
assert site.is_dir() and repair.is_file()
assert (site/"VERSION.txt").read_text().strip()=="2.47.491"
code=repair.read_text()
def payload(name):
    m=re.search(r"private const "+re.escape(name)+r"='([^']*)';",code)
    assert m, name
    return json.loads(base64.b64decode(m.group(1)))
source=payload("SOURCE_MANIFEST")
target=payload("TARGET_MANIFEST")
removed=payload("REMOVED")
assert len(source)>100 and len(target)>100
assert all(re.fullmatch("[0-9a-f]{64}",x) for x in source.values())
runtime=subprocess.check_output(["php","-r",
 "echo json_encode(include $argv[1],JSON_THROW_ON_ERROR);",str(site/"app/.runtime.php")],
 text=True)
p=json.loads(runtime)
datadir=pathlib.Path(p["data_dir"]).resolve()
db=pathlib.Path(p["db_file"]).resolve()
config=pathlib.Path(p["config_file"]).resolve()
assert datadir.is_dir() and str(datadir).startswith(str(site)+"/")
assert db.is_file() and config.is_file()
updates=datadir/"updates"
updates.mkdir(mode=0o750,exist_ok=True)
stage=updates/".atomic-2.47.492-synthetic-crash-journal"
assert not stage.exists()
stage.mkdir(mode=0o700)
all_files=sorted(set(target)|set(removed))
meta={}
for name in all_files:
    rel=pathlib.PurePosixPath(name)
    assert str(rel)==name and ".." not in rel.parts and not name.startswith("/")
    frompath=site/name
    assert not frompath.is_symlink()
    exists=frompath.is_file()
    meta[name]=exists
    if exists:
        dest=stage/"source"/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(frompath,dest)
(stage/"source-meta.json").write_text(json.dumps(meta,sort_keys=True))
shutil.copy2(config,stage/"config.bin")
with sqlite3.connect(str(db)) as opened:
    with sqlite3.connect(str(stage/"database.sqlite")) as snapshot:
        opened.backup(snapshot)
assert (stage/"database.sqlite").stat().st_size>0
version=site/"VERSION.txt"
assert "VERSION.txt" in meta and meta["VERSION.txt"]
version.write_text("2.47.492\n")
assert version.read_text().strip()=="2.47.492"
journal=updates/"p01-atomic-transaction.json"
assert not journal.exists()
journal.write_text(json.dumps({
 "target_version":"2.47.492",
 "source_version":"2.47.491",
 "stage":str(stage),
 "phase":"source_applied",
 "created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()
})+"\n")
assert journal.is_file() and stage.is_dir()
print("P01_IA6_ATOMIC_SYNTHETIC_INTERRUPTED_JOURNAL_CREATED=PASS")
