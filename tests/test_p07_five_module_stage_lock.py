"""P07 five-module independent-stage lock: version & scope without hidden release."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/"dist/p07/candidates/five-modules-stage-20261112.json"
TOOLBOX=ROOT/"installers/p07-toolbox.sh"
NAMES={
 "P07-M01":"网络代理节点（V2Ray）",
 "P07-M02":"服务器性能检测（VPS 验机）",
 "P07-M03":"网站与数据",
 "P07-M04":"服务器维护与安全",
 "P07-M05":"新服务器初始化",
}
ROOTS={
 "P07-M01":"/opt/vfops-modules/m01",
 "P07-M02":"/opt/vfops-modules/m02",
 "P07-M03":"/opt/vf-server-ops",
 "P07-M04":"/opt/vfops-modules/m04",
 "P07-M05":"/opt/vfops-modules/m05",
}

def verify(stage,toolbox):
    if stage.get("schema")!="vf.p07.five-module-stage-lock.v1":
        raise ValueError("stage schema")
    if stage.get("status")!="DEV_READY_NOT_DISTRIBUTED":
        raise ValueError("stage prematurely released")
    if stage.get("formal_release_authorized") is not False:
        raise ValueError("formal release misrepresented")
    if stage.get("production_install_authorized") is not False:
        raise ValueError("production misrepresented")
    if stage.get("implicit_cross_module_installs_allowed") is not False:
        raise ValueError("cross module install enabled")
    modules=stage.get("modules")
    if not isinstance(modules,list) or len(modules)!=5:
        raise ValueError("five modules")
    if {m["id"] for m in modules}!=set(NAMES):
        raise ValueError("unique five module IDs")
    if {m["install_root"] for m in modules}!=set(ROOTS.values()):
        raise ValueError("module root collision or drift")
    for m in modules:
        ident=m["id"]
        if m.get("name")!=NAMES[ident]:
            raise ValueError("Chinese name drift: "+ident)
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}",m.get("build","")):
            raise ValueError("invalid build identity: "+ident)
        data=m.get("package_identity_digest")
        algorithm=m.get("package_identity_algorithm")
        if algorithm=="NONE":
            if data is not None:
                raise ValueError("M03 no package sha tracked")
        elif algorithm=="GIT_BLOB_SHA1":
            if not isinstance(data,str) or not re.fullmatch(r"[a-f0-9]{40}",data):
                raise ValueError("invalid git blob")
        elif algorithm in ("SHA256_MANIFEST","SHA256_EXECUTABLE","SHA256_ZIP"):
            if not isinstance(data,str) or not re.fullmatch(r"[a-f0-9]{64}",data):
                raise ValueError("invalid SHA256")
        else:
            raise ValueError("unknown identity algorithm")
        if ident in ("P07-M01","P07-M04","P07-M05"):
            if not re.fullmatch(r"[a-f0-9]{40}",m.get("installer_source_ref","")):
                raise ValueError("installer must use immutable commit")
            if not re.fullmatch(r"[a-f0-9]{40}",m.get("installer_blob","")):
                raise ValueError("installer blob must be exact")
            if m["installer_blob"] not in toolbox or m["installer_source_ref"] not in toolbox:
                raise ValueError("pinned installer not in selected Toolbox: "+ident)
        if ident=="P07-M02":
            if m["package_identity_digest"] not in toolbox:
                raise ValueError("M02 audit SHA missing from Toolbox")
        if ident=="P07-M03":
            if m.get("rollback_scope")!="M03_RUNTIME_ONLY_NO_SITE_OR_DATABASE_RESTORE":
                raise ValueError("M03 rollback contract must exclude business data")
            if m.get("previous_snapshot_protection")!="NEVER_OVERWRITE_OR_DELETE":
                raise ValueError("M03 rollback must preserve previous snapshot")
            for field in ("rollback_installer_source_ref","rollback_installer_blob"):
                value=m.get(field)
                if not isinstance(value,str) or not re.fullmatch(r"[a-f0-9]{40}",value):
                    raise ValueError("M03 rollback immutable blob/ref required")
                if value not in toolbox:
                    raise ValueError("M03 rollback installer absent from Toolbox")

        if ident=="P07-M05":
            if m.get("distribution")!="NOT_RELEASED" or m.get("public_package_url") is not None:
                raise ValueError("M05 package must remain unlisted before release")
            if m.get("package_source_sha")!=stage.get("product_source_sha"):
                raise ValueError("M05 candidate source drift")
            if m.get("package_identity_algorithm")!="SHA256_ZIP":
                raise ValueError("M05 ZIP identity")
            if not isinstance(m.get("package_file_count"),int) or m["package_file_count"]<20:
                raise ValueError("M05 file count")
            if 'M05_BUNDLE_URL=""' not in toolbox or 'M05_BUNDLE_SHA256=""' not in toolbox:
                raise ValueError("undeclared distribution")
    return True

class StageLock(unittest.TestCase):
    def setUp(self):
        self.stage=json.loads(STAGE.read_text(encoding="utf-8"))
        self.toolbox=TOOLBOX.read_text(encoding="utf-8")

    def test_stage_and_all_five_chinese_paths_are_immutable_and_unreleased(self):
        self.assertTrue(verify(self.stage,self.toolbox))
        self.assertEqual(len({m["install_root"] for m in self.stage["modules"]}),5)

    def test_unknown_or_duplicated_modules_are_denied(self):
        bad=copy.deepcopy(self.stage)
        bad["modules"][4]["id"]="P07-M01"
        with self.assertRaises(ValueError): verify(bad,self.toolbox)

    def test_cross_module_install_contract_cannot_be_disabled(self):
        bad=copy.deepcopy(self.stage)
        bad["implicit_cross_module_installs_allowed"]=True
        with self.assertRaises(ValueError): verify(bad,self.toolbox)

    def test_m05_claimed_public_distribution_is_denied(self):
        bad=copy.deepcopy(self.stage)
        bad["modules"][4]["distribution"]="RELEASED"
        with self.assertRaises(ValueError): verify(bad,self.toolbox)
        bad=copy.deepcopy(self.stage)
        bad["modules"][4]["public_package_url"]="https://example.invalid/zip"
        with self.assertRaises(ValueError): verify(bad,self.toolbox)

    def test_hash_identity_distinguishes_zip_manifest_and_git_blob(self):
        bad=copy.deepcopy(self.stage)
        bad["modules"][3]["package_identity_algorithm"]="SHA256_ZIP"
        with self.assertRaises(ValueError): verify(bad,self.toolbox)
        bad=copy.deepcopy(self.stage)
        bad["modules"][4]["package_identity_digest"]="0"*40
        with self.assertRaises(ValueError): verify(bad,self.toolbox)

    def test_toolbox_help_has_independent_m05_without_stale_m03_label(self):
        self.assertIn("5. 新服务器初始化        系统更新/CloudPanel/数据库选择",self.toolbox)
        self.assertIn("系统更新/CloudPanel/数据库选择",self.toolbox)
        self.assertIn("--modules) modules_status_readonly",self.toolbox)
        self.assertIn("P07-M05 新服务器初始化",self.toolbox)


if __name__=="__main__":
    unittest.main()
