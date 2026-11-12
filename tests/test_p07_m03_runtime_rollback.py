"""P07-M03 网站与数据: standalone previous-runtime restore in disposable fixture.

This is NOT a website/database restore and never touches Owner CP2.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"installers/p07-m03-restore-previous.sh"


class M03Rollback(unittest.TestCase):
    @unittest.skipUnless(os.getenv("P07_M03_NATIVE_TEST")=="1","ephemeral runner only")
    def test_previous_runtime_swap_and_failure_protection(self):
        self.assertEqual(os.geteuid(),0)
        self.assertEqual(os.getenv("GITHUB_ACTIONS"),"true")
        with tempfile.TemporaryDirectory(prefix="p07-m03-rollback-") as temp:
            base=Path(temp)
            current=base/"current"
            previous=base/"previous"
            link=base/"vfops"
            lock=base/"m03.lock"
            other={key:base/key for key in ("m01","m02","m04","m05")}
            for folder in other.values():
                folder.mkdir()
                (folder/"OWNER").write_text("UNCHANGED\n")
            def create_runtime(home:Path, build:str):
                (home/"lib").mkdir(parents=True)
                (home/"bin").mkdir()
                (home/"BUILD_ID").write_text(build+"\n")
                script=(
                    "#!/usr/bin/env bash\n"
                    'root="$(cd "$(dirname "$0")/.." && pwd)"\n'
                    'case "$1" in\n'
                    '  --version) echo "VF Server Ops 0.1.0" ;;\n'
                    '  --build-id) cat "$root/BUILD_ID" ;;\n'
                    '  *) exit 13 ;;\n'
                    'esac\n'
                )
                (home/"bin/vfops-user").write_text(script)
                (home/"bin/vfops-user").chmod(0o755)
                for i in range(53):
                    (home/f"lib/source{i:02d}.py").write_text(f"fixture {i}\n")
                files=sorted([*home.glob("lib/*.py"),home/"BUILD_ID",
                              home/"bin/vfops-user"])
                rows=[]
                for p in files:
                    raw=p.read_bytes()
                    h=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
                    rows.append(h+"  "+p.relative_to(home).as_posix())
                (home/".runtime-manifest.gitblob").write_text("\n".join(rows)+"\n")
            create_runtime(current,"0.1.0-release115")
            create_runtime(previous,"0.1.0-release114")
            link.symlink_to(current/"bin/vfops-user")
            custom=base/"m03-rollback-test.sh"
            source=SOURCE.read_text(encoding="utf-8")
            for before,after in (
                ("M03_ROOT='/opt/vf-server-ops'","M03_ROOT='"+str(current)+"'"),
                ("M03_PREVIOUS='/opt/vf-server-ops.previous'","M03_PREVIOUS='"+str(previous)+"'"),
                ("M03_ENTRY='/usr/local/bin/vfops'","M03_ENTRY='"+str(link)+"'"),
                ("M03_LOCK='/opt/vf-server-ops.rollback.lock'","M03_LOCK='"+str(lock)+"'"),
            ):
                self.assertEqual(source.count(before),1,before)
                source=source.replace(before,after)
            custom.write_text(source)
            def invoke(build,confirm):
                return subprocess.run(["bash",str(custom),"restore-previous",build,confirm],
                                      capture_output=True,text=True,timeout=15)
            def state():
                return {key:(folder/"OWNER").read_bytes() for key,folder in other.items()}
            siblings=state()
            denied=invoke("0.1.0-release114","P07-M03:incorrect")
            self.assertEqual(denied.returncode,13,denied.stderr)
            self.assertEqual((current/"BUILD_ID").read_text().strip(),"0.1.0-release115")
            t=previous/"lib/source00.py"
            content=t.read_bytes()
            t.write_bytes(b"broken")
            denied=invoke("0.1.0-release114","P07-M03:0.1.0-release114")
            self.assertEqual(denied.returncode,13,denied.stderr)
            self.assertEqual((current/"BUILD_ID").read_text().strip(),"0.1.0-release115")
            t.write_bytes(content)
            ok=invoke("0.1.0-release114","P07-M03:0.1.0-release114")
            self.assertEqual(ok.returncode,0,ok.stderr)
            self.assertEqual((current/"BUILD_ID").read_text().strip(),"0.1.0-release114")
            self.assertEqual((previous/"BUILD_ID").read_text().strip(),"0.1.0-release115")
            self.assertEqual(state(),siblings)
            back=invoke("0.1.0-release115","P07-M03:0.1.0-release115")
            self.assertEqual(back.returncode,0,back.stderr)
            self.assertEqual((current/"BUILD_ID").read_text().strip(),"0.1.0-release115")
            self.assertEqual(state(),siblings)
            print("P07_M03_PREVIOUS_RUNTIME_SWAP_AND_REVERSE=PASS_SYNTHETIC",flush=True)
            print("P07_M03_SIBLING_MODULES_UNCHANGED=PASS_SYNTHETIC",flush=True)


if __name__=="__main__":
    unittest.main()
