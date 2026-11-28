"""Actual atomic file installation proof in a fresh disposable directory.

Official UX3 archive is downloaded and SHA256 checked. UX4 uses the exact
candidate script and existing canonical package format. The original
installer executes its real root guard, ZIP unpack, runtime identity check
and pointer swaps. No production paths, benchmark, or system services.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
URL="https://github.com/llhzx2018/core-free-runner-public/releases/download/p07-all-ux-v0.1.0-20261118/P07-M02-2.1.1-ux3.zip"
OLD_SHA="88da5b8219fb7e04d606eb3de998d872747cb05153bdd93c7351b46f957164b4"
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def check(cond,why):
    if not cond:raise AssertionError(why)
def rejected(call):
    try:call()
    except Exception:return
    raise AssertionError("unsafe operation was accepted")

def main():
    check(os.geteuid()==0,"real installer root guard required")
    for path in ("/opt/vfops-modules","/opt/vf-server-ops","/home/clp","/etc/cloudpanel"):
        check(not os.path.lexists(path),"existing host installation; refuse")
    candidate=load(ROOT/"installers/p07-m02-ux4-atomic.py","m02_dev")
    old_engine=load(ROOT/"installers/p07-three-ux-atomic.py","m02_old")
    builder=load(ROOT/"scripts/build_p07_ux_three_release_candidates.py","m02_zip_builder")
    check(candidate.blob(candidate.ENGINE.read_bytes())==candidate.ENGINE_BLOB,"original engine changed")
    with tempfile.TemporaryDirectory(prefix="p07-m02-real-atomic-") as tmp:
        root=Path(tmp); base=root/"slots";base.mkdir()
        archive=root/"official-ux3.zip"
        req=urllib.request.Request(URL,headers={"User-Agent":"P07-M02-atomic-proof"})
        with urllib.request.urlopen(req,timeout=30) as response:
            data=response.read(8*1024*1024+1)
        check(len(data)<=8*1024*1024 and candidate.sha(data)==OLD_SHA,"official ZIP mismatch")
        archive.write_bytes(data)
        script=(ROOT/"experiments/p07-vps-audit-v21-ux4.sh").read_bytes()
        files={candidate.ENTRY:script,"VERSION":(candidate.NEW+"\n").encode()}
        files[candidate.META]=candidate.manifest(candidate.NEW,script)
        candidate.check_payload(candidate.NEW,files)
        target_zip=root/"ux4-dev.zip"
        digest=builder.output_zip(target_zip,candidate.MODULE,files)
        siblings={}
        for name in ("m01","m03","m04","m05"):
            sibling=base/name;sibling.mkdir()
            (sibling/"VERSION").write_text(name+"\n")
            (sibling/"current").symlink_to("retained")
            siblings[name]=(sibling/"VERSION").read_bytes()
        def untouched():
            for name,content in siblings.items():
                sibling=base/name
                check(set(p.name for p in sibling.iterdir())=={"VERSION","current"},"sibling file changed")
                check((sibling/"VERSION").read_bytes()==content and os.readlink(sibling/"current")=="retained","sibling identity changed")
        old_engine.BASE=base
        check(old_engine.install(candidate.MODULE,archive,OLD_SHA)==candidate.OLD,"official old install")
        engine=candidate.engine_for(base)
        home=base/"m02";old=home/"releases"/candidate.OLD
        candidate.verify_saved(old,candidate.OLD,candidate.MODULE)
        def current(version):
            check(os.readlink(home/"current")=="releases/"+version,"wrong current pointer")
            entry=home/"current"/candidate.ENTRY
            out=subprocess.check_output(["bash",str(entry),"--build-id"],text=True,timeout=10)
            check(out.strip()==version,"wrong executable identity")
            untouched()
        current(candidate.OLD)
        rejected(lambda:engine.install(candidate.MODULE,target_zip,"0"*64))
        current(candidate.OLD)
        # A re-sealed ZIP still cannot admit a different script identity.
        bad=dict(files);bad[candidate.ENTRY]+=b"\n# modified runtime\n"
        bad[candidate.META]=candidate.manifest(candidate.NEW,bad[candidate.ENTRY])
        bad_zip=root/"modified.zip";bad_sha=builder.output_zip(bad_zip,candidate.MODULE,bad)
        rejected(lambda:engine.install(candidate.MODULE,bad_zip,bad_sha))
        current(candidate.OLD)
        switch=engine.switching
        def fail_switch(*args):raise OSError("synthetic pre-swap failure")
        engine.switching=fail_switch
        rejected(lambda:engine.install(candidate.MODULE,target_zip,digest))
        current(candidate.OLD)
        engine.switching=switch
        check(engine.install(candidate.MODULE,target_zip,digest)==candidate.NEW,"upgrade")
        current(candidate.NEW)
        check(engine.install(candidate.MODULE,target_zip,digest)==candidate.NEW,"idempotent")
        current(candidate.NEW)
        rejected(lambda:candidate.rollback(engine,candidate.OLD,"WRONG"))
        current(candidate.NEW)
        # A self-consistent but changed historical manifest is rejected.
        orig={p.name:p.read_bytes() for p in old.iterdir()}
        changed=orig[candidate.ENTRY]+b"\n# altered old runtime\n"
        (old/candidate.ENTRY).write_bytes(changed)
        (old/candidate.META).write_bytes(candidate.manifest(candidate.OLD,changed))
        rejected(lambda:candidate.rollback(engine,candidate.OLD,candidate.MODULE+":"+candidate.OLD))
        current(candidate.NEW)
        for name,content in orig.items():(old/name).write_bytes(content)
        check(candidate.rollback(engine,candidate.OLD,candidate.MODULE+":"+candidate.OLD)==candidate.OLD,"rollback")
        current(candidate.OLD)
        check(engine.install(candidate.MODULE,target_zip,digest)==candidate.NEW,"reupgrade")
        current(candidate.NEW)
        check(not list(home.glob(".stage-*")) and not list(home.glob(".switch-*")),"temporary residue")
        # Separate clean install of UX4 through the same real engine.
        fresh=root/"fresh";fresh.mkdir()
        check(candidate.engine_for(fresh).install(candidate.MODULE,target_zip,digest)==candidate.NEW,"fresh install")
        check(os.readlink(fresh/"m02/current")=="releases/"+candidate.NEW,"fresh identity")
        check(set(p.name for p in fresh.iterdir())=={"m02"},"fresh installed siblings")
        print("M02_OFFICIAL_UX3_TO_EXACT_UX4_REAL_ATOMIC=PASS")
        print("M02_BAD_ARCHIVE_RESEALED_OLD_AND_FAILED_SWITCH=PASS")
        print("M02_ROLLBACK_REUPGRADE_FRESH_INSTALL_FOUR_SIBLINGS=PASS")
        print("M02_FULL_AUDIT=NOT_RUN")

if __name__=="__main__":main()
