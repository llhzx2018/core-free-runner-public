"""P07-M01 网络代理节点（V2Ray）: standalone management package, not live node installation."""
from pathlib import Path
import hashlib
import os
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
MANAGER=ROOT/"installers/p07-vf-node-independent-rc13.sh"
PKG=ROOT/"packages/p07-network-node/0.1.0-rc13"

class M01IndependentManager(unittest.TestCase):
    def test_verified_exact_10_item_manifest(self):
        m=(PKG/"MANIFEST.sha256").read_bytes()
        self.assertEqual(hashlib.sha256(m).hexdigest(),"1ca3dc95a5cc6e5aa35c9b7ead415d3b6ea6c6eb9e8307a76310d146ab53c47f")
        pairs=[]
        for line in m.decode().strip().splitlines():
            match=re.fullmatch(r"([a-f0-9]{64})  ([a-zA-Z0-9_./-]+)",line)
            self.assertIsNotNone(match)
            digest,name=match.groups()
            self.assertNotIn("..",Path(name).parts)
            self.assertEqual(hashlib.sha256((PKG/name).read_bytes()).hexdigest(),digest)
            pairs.append(name)
        self.assertEqual(len(pairs),10)
        self.assertEqual(len(set(pairs)),10)

    def test_manager_only_no_daemon_or_other_module_installer(self):
        s=MANAGER.read_text()
        self.assertIn("P07-M01 网络代理节点（V2Ray）",s)
        self.assertIn("MODULE_ROOT='/opt/vfops-modules/m01'",s)
        self.assertIn("SOURCE_COMMIT='07fdedf8e79f4ea15213c3653f63d5876e4f7552'",s)
        for forbidden in (
            "ensure_server_ops_current","ensure_system_care_current",
            "/opt/vf-server-ops","/opt/vf-system-care",
            "systemctl start","systemctl restart","/etc/systemd/system",
            "/opt/vf-network-node","/usr/local/bin/vf-node",
        ):
            self.assertNotIn(forbidden,s)
        self.assertIn("mv -Tf",s)
        self.assertIn("MANIFEST_SHA256=",s)

    def test_own_manager_version_without_existing_node(self):
        p=subprocess.run(["bash",str(PKG/"vf-node.sh"),"--version"],
                         capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("0.1.0-rc13",p.stdout)

    def test_syntax_and_help_do_not_install(self):
        p=subprocess.run(["bash","-n",str(MANAGER)],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        p=subprocess.run(["bash",str(MANAGER),"--version"],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("P07-M01 网络代理节点（V2Ray）",p.stdout)

    def test_unexpected_action_is_fail_closed(self):
        p=subprocess.run(["bash",str(MANAGER),"uninstall"],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,13)
        self.assertIn("管理器独立安装已阻断",p.stderr)

    @unittest.skipUnless(os.getenv("P07_M01_DISPOSABLE_RUNNER")=="1","GitHub disposable runner only")
    def test_native_install_no_other_modules_and_idempotent(self):
        self.assertEqual(os.geteuid(),0)
        root=Path("/opt/vfops-modules")
        m01=root/"m01"
        self.assertFalse(m01.exists() or m01.is_symlink(),"pre-existing module, refusing")
        sentinels={}
        for n in ("m02","m03","m04","m05"):
            d=root/n
            self.assertFalse(d.exists() or d.is_symlink(),"pre-existing foreign module, refusing")
            d.mkdir(parents=True,exist_ok=False)
            sentinel=d/"BUILD_ID"
            sentinel.write_text(n+"-UNCHANGED")
            sentinels[n]=sentinel
        before={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sentinels.items()}
        try:
            for _ in range(2):
                p=subprocess.run(["bash",str(MANAGER),"install"],capture_output=True,text=True,timeout=180)
                self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(os.readlink(m01/"current"),"releases/0.1.0-rc13")
            entry=m01/"current/vf-node.sh"
            v=subprocess.run(["bash",str(entry),"--version"],capture_output=True,text=True,timeout=15)
            self.assertEqual(v.returncode,0,v.stderr)
            self.assertIn("0.1.0-rc13",v.stdout)
            self.assertEqual(before,{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sentinels.items()})
            with (m01/"releases/0.1.0-rc13/status.sh").open("ab") as h:
                h.write(b"\n# synthetically corrupted\n")
            failed=subprocess.run(["bash",str(MANAGER),"install"],capture_output=True,text=True,timeout=30)
            self.assertEqual(failed.returncode,13)
            self.assertEqual(os.readlink(m01/"current"),"releases/0.1.0-rc13")
            self.assertEqual(before,{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sentinels.items()})
        finally:
            for d in [m01,*[root/n for n in sentinels]]:
                subprocess.run(["rm","-rf","--",str(d)],timeout=20,check=True)

if __name__=="__main__":
    unittest.main()
