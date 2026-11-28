"""Actual independent module install/upgrade/rollback on a disposable root.

No V2Ray deployment, network listener, service mutation or host credentials.
"""
from __future__ import annotations
import importlib.util,os,subprocess,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def need(ok,reason):
    if not ok:raise AssertionError(reason)
def load():
    spec=importlib.util.spec_from_file_location("candidate",ROOT/"installers/p07-m01-ux4-atomic.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def rejected(call):
    try:call()
    except Exception:return
    raise AssertionError("unsafe operation accepted")
def main():
    need(os.geteuid()==0,"real root installer required")
    for p in ("/opt/vfops-modules","/opt/vf-server-ops","/home/clp","/etc/cloudpanel","/etc/vf-node","/etc/v2ray"):
        need(not os.path.lexists(p),"existing product host refused")
    c=load();builder,prior,files=c.payloads()
    with tempfile.TemporaryDirectory(prefix="p07-m01-atomic-") as tmp:
        root=Path(tmp);base=root/"slots";base.mkdir()
        old=root/"issued.zip"
        url="https://github.com/llhzx2018/core-free-runner-public/releases/download/p07-all-ux-v0.1.0-20261118/P07-M01-0.1.0-ux3.zip"
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"P07-M01-dev-proof"}),timeout=40) as r:
            data=r.read(8*1024*1024+1)
        need(len(data)<=8*1024*1024 and c.sha(data)==c.OLD_SHA,"issued archive identity")
        old.write_bytes(data)
        archive=root/"candidate.zip";digest=builder.output_zip(archive,c.MODULE,files)
        siblings={}
        for slot in ("m02","m03","m04","m05"):
            p=base/slot;p.mkdir();(p/"VERSION").write_text(slot+"\n");(p/"current").symlink_to("retained")
            siblings[slot]=(p/"VERSION").read_bytes()
        def untouched():
            for slot,data in siblings.items():
                p=base/slot
                need(set(x.name for x in p.iterdir())=={"VERSION","current"},"sibling files changed")
                need((p/"VERSION").read_bytes()==data and os.readlink(p/"current")=="retained","sibling changed")
        origin=c.load("old_engine",c.ENGINE);origin.BASE=base
        need(origin.install(c.MODULE,old,c.OLD_SHA)==c.OLD,"old install")
        engine=c.engine_for(base,prior,files);home=base/c.SLOT
        def check(version):
            need(os.readlink(home/"current")=="releases/"+version,"pointer mismatch")
            engine.verify_saved(home/"releases"/version,version,c.MODULE)
            out=subprocess.check_output(["bash",str(home/"current"/c.ENTRY),"--version"],text=True,timeout=15)
            need(out.strip()=="VF Network Node "+version,"runtime identity")
            untouched()
        check(c.OLD)
        rejected(lambda:c.install(engine,archive,"0"*64));check(c.OLD)
        bad=dict(files);bad[c.ENTRY]+=b"\n# changed\n";bad["MODULE_MANIFEST.json"]=c.manifest(c.NEW,bad)
        modified=root/"changed.zip";wrong=builder.output_zip(modified,c.MODULE,bad)
        rejected(lambda:c.install(engine,modified,wrong));check(c.OLD)
        switch=engine.switching
        def fail(*args):raise OSError("injected pre-pointer-swap failure")
        engine.switching=fail
        rejected(lambda:c.install(engine,archive,digest));check(c.OLD)
        engine.switching=switch
        need(c.install(engine,archive,digest)==c.NEW,"upgrade");check(c.NEW)
        rejected(lambda:c.rollback(engine,"WRONG"));check(c.NEW)
        need(c.rollback(engine,c.MODULE+":"+c.OLD)==c.OLD,"rollback");check(c.OLD)
        need(c.install(engine,archive,digest)==c.NEW,"reupgrade");check(c.NEW)
        need(not list(home.glob(".stage-*")) and not list(home.glob(".switch-*")),"staging residue")
        fresh=root/"fresh";fresh.mkdir()
        need(c.install(c.engine_for(fresh,prior,files),archive,digest)==c.NEW,"fresh install")
        need(set(p.name for p in fresh.iterdir())=={c.SLOT},"sibling fresh install")
        print("M01_EXACT_OFFICIAL_UPGRADE_ROLLBACK_FRESH=PASS")
        print("M01_TAMPER_REFUSAL_FAILED_SWITCH_FOUR_SIBLINGS=PASS")
        print("M01_REAL_PROXY_CONNECTION=NOT_RUN")
if __name__=="__main__":main()
