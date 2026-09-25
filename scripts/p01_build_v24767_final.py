#!/usr/bin/env python3
from __future__ import annotations
import base64, hashlib, json, re, zipfile
from pathlib import Path

ROOT=Path.cwd()
CAND=ROOT/"candidate"/"src"
BASE=Path("/tmp/p01-rel66/full")
OLD_REPAIR=Path("/tmp/p01-rel66/update/repair-v2.47.66.php")
OUT=Path("/tmp/p01-v24767-artifacts")
VERSION="2.47.67"
SOURCE_VERSION="2.47.66"
SCHEMA="2026090401"
SOURCE_SHA="f025db78457ea6521c67d146130825e8a132f517"
SOURCE_TREE="868bbdcb618e28422655ac5e9c28342fbce60c55"

def sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def decode_const(text:str,name:str):
    m=re.search(r"private const "+re.escape(name)+r"='([^']*)';",text)
    if not m:
        raise SystemExit(f"missing template constant {name}")
    return json.loads(base64.b64decode(m.group(1)).decode())

def replace_const(text:str,name:str,obj)->str:
    enc=base64.b64encode(json.dumps(obj,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()).decode()
    pattern=r"(private const "+re.escape(name)+r"=)'[^']*';"
    out,n=re.subn(pattern,lambda m:m.group(1)+"'"+enc+"';",text,count=1)
    if n!=1:
        raise SystemExit(f"cannot replace {name}")
    return out

def collect(root:Path)->dict[str,bytes]:
    out={}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[p.relative_to(root).as_posix()]=p.read_bytes()
    return out

def zip_deterministic(path:Path, files:dict[str,bytes]):
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in sorted(files):
            info=zipfile.ZipInfo(rel,(2026,9,24,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o644 & 0xFFFF)<<16
            z.writestr(info,files[rel])

OUT.mkdir(parents=True,exist_ok=True)
old=OLD_REPAIR.read_text(encoding="utf-8")
old_target=decode_const(old,"TARGET_MANIFEST")

baseline_all=collect(BASE)
candidate_all=collect(CAND)

missing_baseline=sorted(k for k in old_target if k not in baseline_all)
if missing_baseline:
    raise SystemExit("baseline FULL misses prior target manifest files: "+",".join(missing_baseline[:10]))
for rel,expected in old_target.items():
    if sha(baseline_all[rel])!=expected:
        raise SystemExit("baseline FULL bytes do not match prior Atomic target: "+rel)

package_only=set(baseline_all)-set(old_target)
source_files={k:baseline_all[k] for k in sorted(old_target)}
target_files={k:v for k,v in candidate_all.items() if k not in package_only}

formal=json.loads(baseline_all["release-manifest.json"].decode())
formal["version"]=VERSION
formal["source_version"]=SOURCE_VERSION
formal["schema_version"]=SCHEMA
formal["source_commit"]=SOURCE_SHA
formal["source_tree"]=SOURCE_TREE
formal["stage"]="FINAL_CANDIDATE_BYTES"
formal["release_scope"]="p01-v24767-final-release"
formal["schema_change"]=False
formal["schema_migrations"]=[]
formal["runtime_data_included"]=False
formal["seed_user_business_data_included"]=False
target_files["release-manifest.json"]=(json.dumps(formal,ensure_ascii=False,indent=2)+"\n").encode()

source_manifest={k:sha(v) for k,v in sorted(source_files.items())}
target_manifest={k:sha(v) for k,v in sorted(target_files.items())}
payload={k:base64.b64encode(v).decode() for k,v in sorted(target_files.items())}
removed=sorted(set(source_manifest)-set(target_manifest))
alternates={}

repair=old
for a,b in [
    ("public const SOURCE_VERSION='2.47.65';",f"public const SOURCE_VERSION='{SOURCE_VERSION}';"),
    ("public const TARGET_VERSION='2.47.66';",f"public const TARGET_VERSION='{VERSION}';"),
    ("public const TARGET_SCHEMA='2026090401';",f"public const TARGET_SCHEMA='{SCHEMA}';"),
]:
    if repair.count(a)!=1:
        raise SystemExit("template identity replacement failed: "+a)
    repair=repair.replace(a,b,1)
for name,obj in [
    ("SOURCE_MANIFEST",source_manifest),
    ("TARGET_MANIFEST",target_manifest),
    ("PAYLOAD",payload),
    ("REMOVED",removed),
    ("SOURCE_ALTERNATES",alternates),
]:
    repair=replace_const(repair,name,obj)

repair_name=f"repair-v{VERSION}.php"
repair_bytes=repair.encode()

full_files=dict(candidate_all)
full_files["release-manifest.json"]=target_files["release-manifest.json"]
full_files["FULL-PACKAGE-NOTES.txt"]=(f"""VF Start V{VERSION} FINAL FULL

FULL = 干净首次安装包。
不包含真实用户网址、分类、PRIVATE 数据、运行 SQLite、备份、日志、Session、Token、私钥、repair/staging 或测试数据。
已有 V{SOURCE_VERSION} 运行站点请使用正式 Atomic UPDATE，禁止使用 FULL 直接覆盖。
""").encode()

full_name=f"VF-Start-V{VERSION}-FULL.zip"
update_name=f"VF_Start_V{VERSION}_UPDATE.zip"
zip_deterministic(OUT/full_name,full_files)
zip_deterministic(OUT/update_name,{repair_name:repair_bytes})

for name in [full_name,update_name]:
    h=sha((OUT/name).read_bytes())
    (OUT/(name+".sha256")).write_text(f"{h}  {name}\n",encoding="utf-8")

sums=[]
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name!="SHA256SUMS.txt":
        sums.append(f"{sha(p.read_bytes())}  {p.name}\n")
(OUT/"SHA256SUMS.txt").write_text("".join(sums),encoding="utf-8")

receipt={
    "project_id":"P01",
    "version":VERSION,
    "source_version":SOURCE_VERSION,
    "source_sha":SOURCE_SHA,
    "source_tree":SOURCE_TREE,
    "schema":SCHEMA,
    "baseline_atomic_target_files":len(old_target),
    "target_atomic_files":len(target_manifest),
    "removed_files":removed,
    "full_entries":len(full_files),
    "full_name":full_name,
    "full_bytes":(OUT/full_name).stat().st_size,
    "full_sha256":sha((OUT/full_name).read_bytes()),
    "update_name":update_name,
    "update_bytes":(OUT/update_name).stat().st_size,
    "update_sha256":sha((OUT/update_name).read_bytes()),
}
(OUT/"P01_V24767_ARTIFACT_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt,ensure_ascii=False,indent=2))
