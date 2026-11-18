"""Current P07 M01/M02/M04 module targets: exact official ZIP, source and rollback.

Former synthetic-function harness exercised removed direct installers. This
suite instead runs the public Owner-confirmed route and pinned atomic module
on isolated temp roots, retaining the historical bootstrap identity guard.
"""
from pathlib import Path
import os
import unittest
from unittest.mock import patch

from test_p07_five_official_owner_route import FiveModuleOwnerRoute, route

ROOT=Path(__file__).resolve().parents[1]
TOOLBOX=ROOT/"installers/p07-toolbox.sh"


class P07ModuleTargetUpgradeGate(FiveModuleOwnerRoute):
    def test_old_bootstrap_builds_are_still_explicitly_pinned(self):
        source=TOOLBOX.read_text()
        self.assertIn('M01_BOOTSTRAP_BUILD="0.1.0-rc13"',source)
        self.assertIn('VPS_AUDIT_BOOTSTRAP_BUILD="2.1.0-rc7-field"',source)
        self.assertIn('M04_BOOTSTRAP_BUILD="0.1.0-rc83"',source)
        self.assertIn('M01_PREVIOUS_BUILD="0.1.0-ux2"',source)
        self.assertIn('VPS_AUDIT_PREVIOUS_BUILD="2.1.1-ux2"',source)
        self.assertIn('M04_PREVIOUS_BUILD="0.1.0-ux4"',source)
        self.assertIn('VF_NODE_EXPECTED="0.1.0-ux3"',source)
        self.assertIn('VPS_AUDIT_BUILD_EXPECTED="2.1.1-ux3"',source)
        self.assertIn('M04_BUILD_EXPECTED="0.1.0-ux5"',source)

    def test_unknown_legacy_module_versions_fail_closed_without_fetch(self):
        for module,legacy in (
            ("P07-M01","0.1.0-rc13"),
            ("P07-M02","2.1.0-rc7-field"),
            ("P07-M04","0.1.0-rc83"),
        ):
            with self.subTest(module=module):
                config=route.MODULES[module]
                home=self.modules / config["slot"]
                unknown=home/"releases"/legacy
                unknown.mkdir(parents=True)
                (home/"current").symlink_to("releases/"+legacy)
                before=self.before()
                with self.assertRaisesRegex(route.Blocked,"已验证升级范围"):
                    self.invoke(module)
                self.assertEqual(os.readlink(home/"current"),"releases/"+legacy)
                self.assertEqual(self.before(),before)

if __name__=="__main__":unittest.main()
