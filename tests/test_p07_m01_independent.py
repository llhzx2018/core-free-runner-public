"""P07-M01 网络代理节点（V2Ray）: manager can upgrade without installing any V2Ray node or sibling module."""
from __future__ import annotations
from pathlib import Path
import re
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
ENTRY=ROOT / "installers/p07-vf-node-independent-rc13.sh"


class M01ManagerIsolation(unittest.TestCase):
    def test_exact_pinned_release_and_private_directory(self):
        body=ENTRY.read_text()
        self.assertIn("MODULE_ROOT='/opt/vfops-modules/m01'",body)
        self.assertIn("VERSION='0.1.0-rc13'",body)
        self.assertIn("SOURCE_COMMIT='07fdedf8e79f4ea15213c3653f63d5876e4f7552'",body)
        self.assertIn("MANIFEST_SHA256='1ca3dc95a5cc6e5aa35c9b7ead415d3b6ea6c6eb9e8307a76310d146ab53c47f'",body)
        self.assertIn("mv -Tf --",body)
        self.assertIn("verify_release",body)
        self.assertIn("flock -x",body)

    def test_never_calls_other_modules_or_node_installer(self):
        body=ENTRY.read_text()
        for fragment in ("ensure_server_ops_current","ensure_system_care_current",
                         "VPS_AUDIT_URL", "/opt/vf-server-ops",
                         "/opt/vf-system-care","/opt/vf-network-node",
                         "/usr/local/bin/vf-node", "systemctl", "vf-node.sh install"):
            self.assertNotIn(fragment,body)

    def test_installer_syntax_version_and_reject_wrong_operation(self):
        p=subprocess.run(["bash","-n",str(ENTRY)],capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)
        v=subprocess.run(["bash",str(ENTRY),"--version"],capture_output=True,text=True,timeout=15)
        self.assertEqual(v.returncode,0,v.stderr)
        self.assertIn("P07-M01 网络代理节点（V2Ray） 0.1.0-rc13",v.stdout)
        bad=subprocess.run(["bash",str(ENTRY),"install-node"],capture_output=True,text=True,timeout=15)
        self.assertEqual(bad.returncode,13)
        self.assertIn("其他模块不受影响",bad.stderr)


if __name__=="__main__":
    unittest.main()
