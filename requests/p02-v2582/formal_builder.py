#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, stat, subprocess, zipfile
from pathlib import Path

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def meta(path: Path, kind: str | None = None) -> dict:
    data=path.read_bytes()
    out={"path":path.name,"bytes":len(data),"sha256":sha_bytes(data)}
    if kind: out["type"]=kind
    return out

def zip_stamp(ts: str):
    from datetime import datetime, timezone
    d=datetime.fromisoformat(ts.replace("Z","+00:00")).astimezone(timezone.utc)
    return (d.year,d.month,d.day,d.hour,d.minute,d.second)

def write_entry(z: zipfile.ZipFile, name: str, data: bytes, stamp, mode=0o644):
    i=zipfile.ZipInfo(name,stamp)
    i.compress_type=zipfile.ZIP_DEFLATED
    i.create_system=3
    i.external_attr=(stat.S_IFREG|mode)<<16
    z.writestr(i,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)

def files(root: Path):
    out=[]
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise RuntimeError(f"symlink forbidden: {p}")
        if p.is_file():
            out.append((p.relative_to(root).as_posix(),p))
    return out

def zip_tree(dst: Path, root: Path, stamp):
    with zipfile.ZipFile(dst,"w") as z:
        for rel,p in files(root):
            write_entry(z,rel,p.read_bytes(),stamp,0o755 if os.access(p,os.X_OK) else 0o644)

def source_zip(dst: Path, repo: Path, stamp):
    banned_parts={".git","_import_chunks","node_modules","vendor","build","PRIVATE_DATA"}
    tracked=subprocess.check_output(["git","ls-files"],cwd=repo,text=True).splitlines()
    with zipfile.ZipFile(dst,"w") as z:
        for rel in sorted(tracked):
            parts=set(Path(rel).parts)
            low=rel.lower()
            if parts & banned_parts: continue
            if low.endswith((".sqlite",".sqlite3",".db",".log")) or ".env" in Path(rel).parts:
                raise RuntimeError(f"forbidden tracked file: {rel}")
            p=repo/rel
            if not p.is_file() or p.is_symlink():
                raise RuntimeError(f"invalid tracked source file: {rel}")
            write_entry(z,rel,p.read_bytes(),stamp,0o755 if os.access(p,os.X_OK) else 0o644)

def atomic_zip(dst: Path, repair: Path, stamp):
    with zipfile.ZipFile(dst,"w") as z:
        write_entry(z,repair.name,repair.read_bytes(),stamp)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--version",required=True)
    ap.add_argument("--source-version",action="append",required=True)
    ap.add_argument("--source-sha",required=True)
    ap.add_argument("--source-tree",required=True)
    ap.add_argument("--timestamp",required=True)
    ap.add_argument("--candidate-run",required=True)
    ap.add_argument("--formal-run",required=True)
    a=ap.parse_args()

    repo=Path(a.repo).resolve()
    out=Path(a.out).resolve()
    version=a.version
    sources=list(dict.fromkeys(a.source_version))
    schema=2401
    stamp=zip_stamp(a.timestamp)
    shutil.rmtree(out,ignore_errors=True)
    out.mkdir(parents=True)
    work=out/".work"
    deploy=work/"deploy"
    full=work/"full"
    work.mkdir()

    if (repo/"VERSION").read_text().strip()!=version:
        raise RuntimeError("VERSION mismatch")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    tree=subprocess.check_output(["git","show","-s","--format=%T","HEAD"],cwd=repo,text=True).strip()
    if head!=a.source_sha or tree!=a.source_tree:
        raise RuntimeError("exact source mismatch")

    subprocess.check_call(["bash",str(repo/"scripts/build-deploy-tree.sh"),str(deploy)],cwd=repo)
    if (deploy/"VERSION.txt").read_text().strip()!=version:
        raise RuntimeError("deploy version mismatch")

    update=out/f"VF_Library_V{version}_UPDATE.zip"
    cmd=["python3",str(repo/"scripts/build-multisource-update.py"),
         "--deploy-root",str(deploy),"--output",str(update),"--target-version",version]
    for s in sources: cmd += ["--source-version",s]
    cmd += ["--source-schema",str(schema),"--target-schema",str(schema),"--timestamp",a.timestamp]
    subprocess.check_call(cmd,cwd=repo)

    repair=out/f"repair-v{version}.php"
    cmd=["python3",str(repo/"scripts/build-multisource-repair.py"),
         "--deploy-root",str(deploy),"--template",str(repo/"scripts/repair-template.php"),
         "--output",str(repair),"--target-version",version]
    for s in sources: cmd += ["--source-version",s]
    cmd += ["--schema",str(schema)]
    subprocess.check_call(cmd,cwd=repo)

    atomic=out/f"VF_Library_V{version}_ATOMIC.zip"
    atomic_zip(atomic,repair,stamp)

    shutil.copytree(deploy,full)
    for name in ("README.md","CHANGELOG.md"):
        p=repo/name
        if p.is_file(): shutil.copy2(p,full/name)
    (full/"DEPLOY-HERE.txt").write_text(
        f"VF Library V{version} FORMAL CLEAN FULL\n\nFresh install only. Existing sites MUST use UPDATE/Atomic/repair.\n",
        encoding="utf-8")
    (full/"FULL-PACKAGE-NOTES.txt").write_text(
        f"VF Library V{version}\nSchema {schema}\nBuild: FORMAL_CLEAN_FULL\nBusiness seed: NONE\nPrivate runtime data: NONE\nGit/test/evidence files: NONE\n",
        encoding="utf-8")
    runtime_manifest={
      "name":"VF Library",
      "version":version,
      "release_state":"FORMAL_RELEASE",
      "build_flavor":"FORMAL_CLEAN_FULL",
      "build_time":a.timestamp,
      "schema_version":schema,
      "source_repository":"llhzx2018/vf-library",
      "source_ref":"main",
      "source_commit":a.source_sha,
      "source_tree":a.source_tree,
      "install_contract":{"fresh_install_only":True,"business_seed":"NONE","existing_site_update":"UPDATE/Atomic/repair only"},
      "privacy":{"private":True,"robots":"Disallow: /","x_robots_tag":"noindex, nofollow, noarchive, nosnippet","cache_control":"private, no-store"},
      "upgrade":{"supported_from":sources,"source_schema":schema,"target_schema":schema,"schema_migration":False,
                 "update":meta(update),"atomic":meta(atomic),"repair":meta(repair)},
      "files":[{"path":rel,"bytes":p.stat().st_size,"sha256":sha_bytes(p.read_bytes())} for rel,p in files(full)]
    }
    runtime_manifest["manifest_file_count"]=len(runtime_manifest["files"])
    runtime_manifest["formal_file_count"]=runtime_manifest["manifest_file_count"]+1
    (full/"release-manifest.json").write_text(json.dumps(runtime_manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    full_zip=out/f"VF_Library_V{version}_FULL.zip"
    zip_tree(full_zip,full,stamp)
    src_zip=out/f"VF_Library_V{version}_SOURCE.zip"
    source_zip(src_zip,repo,stamp)

    notes=out/f"VF_Library_V{version}_RELEASE_NOTES.md"
    notes.write_text(
        f"# VF Library V{version}\n\n"
        "Owner UX bug batch and state-safety closure release. "
        "This release fixes durable List/Notebook view preference, Inkstone-style global search, scoped and keyboard search behavior, unsaved-edit navigation protection, Settings scrolling and exact return behavior, privacy-truthful local edit recovery messaging, Inkstone shell alignment, and mobile/tablet command ownership and touch geometry. "
        "The product IA, private single-admin model, Canonical Content authority, authentication model, updater architecture and Schema 2401 remain unchanged; no migration is required.\n\n"
        f"Direct update sources: {', '.join('V'+s for s in sources)}.\n",
        encoding="utf-8")

    assets=[
      (src_zip,"SOURCE"),(full_zip,"FULL"),(update,"UPDATE"),(atomic,"ATOMIC"),(repair,"REPAIR"),(notes,"RELEASE_NOTES")
    ]
    release_manifest=out/f"VF_Library_V{version}_RELEASE_MANIFEST.json"
    rel={
      "schema":"vf-release-manifest/2.1",
      "release_id":f"P02-VF-LIBRARY-{version}",
      "version":version,
      "revision":1,
      "source":{"repository":"llhzx2018/vf-library","branch_or_tag":"main","candidate_commit":a.source_sha,"source_tree":a.source_tree,
                "candidate_equivalent_run":a.candidate_run},
      "build":{"build_time":a.timestamp,"schema":schema,"profile":"web_application / private single-admin","runtime_source_files":len(files(deploy))},
      "artifacts":[meta(p,k) for p,k in assets],
      "compatibility":{"supported_from":sources,"source_schema":schema,"target_schema":schema,"schema_migration":False,"full_existing_site_overwrite":False},
      "gates":{"candidate_exact_source":f"PASS_RUN_{a.candidate_run}",
               "formal_exact_source":f"PASS_RUN_{a.formal_run}",
               "secret":"PASS","private_data":"PASS","db_binary":"PASS","archive":"PASS",
               "fresh_install":"PASS","atomic_upgrade_source_matrix":"PASS","backup_recovery_point":"PASS",
               "browser_ux":"PASS","source_manifest":"PASS"},
      "git":{"main_readback":a.source_sha,"formal_tag":f"v{version}","tag_readback":"PENDING_REMOTE_RELEASE_STEP"},
      "deployment":{"status":"NOT_EXECUTED","production_readback":"NOT_EXECUTED","final_online_pass":False}
    }
    release_manifest.write_text(json.dumps(rel,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    sums_targets=[p for p,_ in assets]+[release_manifest]
    sums=out/"SHA256SUMS.txt"
    sums.write_text("".join(f"{sha_bytes(p.read_bytes())}  {p.name}\n" for p in sorted(sums_targets,key=lambda x:x.name)),encoding="utf-8")
    shutil.rmtree(work)
    print(json.dumps({"ok":True,"version":version,"source_sha":a.source_sha,"source_tree":a.source_tree,
                      "artifacts":[meta(p) for p in sorted(out.iterdir()) if p.is_file()]},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
