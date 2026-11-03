#!/usr/bin/env python3
"""Disposable-only P01 candidate repair with journal crash recovery.
Uses existing public V2 Atomic engine; does NOT publish or modify stable builder."""
import argparse,base64,hashlib,importlib.util,json,pathlib,re,sys
ap=argparse.ArgumentParser()
ap.add_argument('--source-root',required=True)
ap.add_argument('--maintenance-repair',required=True)
ap.add_argument('--out',required=True)
a=ap.parse_args()
source=pathlib.Path(a.source_root).resolve()
repair=pathlib.Path(a.maintenance_repair).resolve()
out=pathlib.Path(a.out).resolve()
assert str(source).startswith('/tmp/p01-ia6-atomic-')
assert str(repair).startswith('/tmp/p01-ia6-atomic-')
assert str(out).startswith('/tmp/p01-ia6-atomic-')
assert (source/'VERSION.txt').read_text().strip()=='2.47.491'
text=repair.read_text()
def const(name):
 m=re.search(r"private const "+name+r"='([^']*)';",text)
 assert m,name
 return json.loads(base64.b64decode(m.group(1)))
src_manifest=const('SOURCE_MANIFEST')
target_manifest=const('TARGET_MANIFEST')
target_payload=const('PAYLOAD')
assert len(src_manifest)>100 and len(target_manifest)>100
def hashdata(b):return hashlib.sha256(b).hexdigest()
source_data={}
for rel,digest in src_manifest.items():
 p=source/rel
 assert not p.is_symlink() and p.is_file() and hashdata(p.read_bytes())==digest,rel
 source_data[rel]=p.read_bytes()
target_data={}
for rel,b64 in target_payload.items():
 value=base64.b64decode(b64,validate=True)
 if rel in target_manifest: assert hashdata(value)==target_manifest[rel]
 target_data[rel]=value
assert all(k in target_data for k in target_manifest)
spec=importlib.util.spec_from_file_location('p01_v2',pathlib.Path(__file__).with_name('p01-build-release-v2.py'))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
generated=mod.build_repair(source_data,target_data,'')
for name,old,new in [
 ('SOURCE_VERSION','2.21.14','2.47.491'),
 ('TARGET_VERSION','2.21.15','2.47.492'),
 ('TARGET_SCHEMA','2026080902','2026102201'),
]:
 pattern="public const "+name+"='"+old+"';"
 assert generated.count(pattern)==1,name
 generated=generated.replace(pattern,"public const "+name+"='"+new+"';")
def set_private(name,value):
 global generated
 pattern=r"(private const "+re.escape(name)+r"=)'[^']*';"
 b64=base64.b64encode(json.dumps(value,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()).decode()
 generated,n=re.subn(pattern,lambda m:m.group(1)+"'"+b64+"';",generated,count=1)
 assert n==1,name
set_private('TARGET_MANIFEST',target_manifest)
set_private('SOURCE_ALTERNATES',{})
assert 'VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY' in generated
assert 'recoverInterrupted' in generated and 'journalPath' in generated
out.mkdir(parents=True,exist_ok=True)
dest=out/'repair-v2.47.492.php'
dest.write_text(generated)
print('P01_IA6_TEST_ONLY_JOURNALED_REPAIR_BUILD=PASS')
