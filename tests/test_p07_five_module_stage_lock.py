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
    # Every Toolbox bootstrap build must match its OWN immutable module
    # candidate. Never silently route M05's candidate2 as old candidate1.
    pin_names={
        "P07-M01":"VF_NODE_EXPECTED",
        "P07-M02":"VPS_AUDIT_BUILD_EXPECTED",
        "P07-M03":"VF_SERVER_OPS_BUILD_EXPECTED",
        "P07-M04":"M04_BUILD_EXPECTED",
        "P07-M05":"M05_BUILD_EXPECTED",
    }
    for candidate in modules:
        key=pin_names[candidate["id"]]
        prefix=key+'="'
        matches=[line[len(prefix):-1] for line in toolbox.splitlines()
                 if line.startswith(prefix) and line.endswith('"')]
        if matches!=[candidate["build"]]:
            raise ValueError("candidate build drift for "+candidate["id"])
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
            # Lock BOTH hops of the installer; a mutable main download can
            # otherwise fetch a file whose blob differs from the expected pin.
            if m.get("package_identity_algorithm")!="GIT_BLOB_SHA1":
                raise ValueError("M03 must pin its runtime manifest")
            for field in ("installer_source_ref","installer_blob",
                          "final_installer_source_ref","final_installer_blob"):
                identity=m.get(field)
                if not isinstance(identity,str) or not re.fullmatch(r"[0-9a-f]{40}",identity):
                    raise ValueError("M03 immutable installer chain: "+field)
            for field in ("installer_source_ref","installer_blob"):
                if m[field] not in toolbox:
                    raise ValueError("M03 immutable Toolbox source mismatch: "+field)
            final=(ROOT/"installers/p07.sh").read_text(encoding="utf-8")
            if (m["final_installer_source_ref"] not in final or
                m["final_installer_blob"] not in final):
                raise ValueError("M03 nested final installer mismatch")
            # A self-edited manifest must never authorize arbitrary root CLI
            # execution; the selected stable M03 build is an exact locked source.
            m03_guard=toolbox.split("m03_verified_current() {",1)[1].split("\n}\n",1)[0]
            pin='VF_SERVER_OPS_MANIFEST_BLOB="'+m["package_identity_digest"]+'"'
            if pin not in toolbox:
                raise ValueError("M03 stable manifest pin absent")
            gate_order=[
                '[[ "$installed" == "$VF_SERVER_OPS_BUILD_EXPECTED" ]] || return 1',
                '[[ "$(p07_git_blob_sha1 "$root/.runtime-manifest.gitblob" 2>/dev/null || true)" == "$VF_SERVER_OPS_MANIFEST_BLOB" ]] || return 1',
                'done < "$root/.runtime-manifest.gitblob"',
                '[[ "$count" -ge 50 ]] || return 1',
                '[[ -v seen[$entry_rel] ]] || return 1',
                'NO_COLOR=1 vfops --build-id',
                'NO_COLOR=1 vfops --version',
            ]
            indices=[m03_guard.find(token) for token in gate_order]
            if any(i<0 for i in indices) or indices!=sorted(indices) or len(set(indices))!=len(indices):
                raise ValueError("M03 may execute before exact pinned integrity check")
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
            offline=m.get("offline_owner_trial")
            if not isinstance(offline,dict):
                raise ValueError("private M05 offline artifact missing")
            if (offline.get("format")!="ONE_BASH_FILE_EMBEDDED_SHA256_ZIP"
                    or offline.get("distribution")!="PRIVATE_OWNER_TRIAL_ONLY"
                    or offline.get("public_package_url") is not None
                    or offline.get("offline_no_git_token") is not True
                    or offline.get("cloudpanel_bootstrap_manual_confirmation_required") is not True
                    or offline.get("installed_on_owner_server") is not False
                    or offline.get("cloudpanel_real_fresh_vm")!="NOT_RUN"
                    or offline.get("one_file_verified_on_disposable_host") is not True):
                raise ValueError("private Owner Trial cannot become Release or VPS PASS")
            if not re.fullmatch(r"[a-f0-9]{64}",offline.get("sha256","")):
                raise ValueError("private offline executable SHA256 missing")
            if not re.fullmatch(r"[a-f0-9]{40}",offline.get("private_git_commit","")):
                raise ValueError("private offline Git commit missing")
            if not re.fullmatch(r"[a-f0-9]{40}",offline.get("private_git_blob_sha1","")):
                raise ValueError("private offline Git blob missing")
            if (offline.get("private_repository")!="llhzx2018/vf-server-ops"
                    or offline.get("file")!="owner-trial/P07-M05-0.1.0-m05-candidate2-OFFLINE.run"
                    or not isinstance(offline.get("bytes"),int)
                    or offline["bytes"] < 500000 or offline["bytes"] >= 1024*1024):
                raise ValueError("private trial materialization identity drift")
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

    def test_m03_installer_chain_cannot_revert_to_unpinned_main(self):
        altered=copy.deepcopy(self.stage)
        m03=next(m for m in altered["modules"] if m["id"]=="P07-M03")
        m03["installer_source_ref"]="main"
        with self.assertRaises(ValueError): verify(altered,self.toolbox)
        m03["installer_source_ref"]=self.stage["modules"][2]["installer_source_ref"]
        m03["final_installer_blob"]="0"*40
        with self.assertRaises(ValueError): verify(altered,self.toolbox)

    def test_private_offline_one_file_cannot_be_mislabeled_public_or_real_cloudpanel(self):
        for key,value in (
            ("distribution","PUBLIC_RELEASE"),
            ("cloudpanel_real_fresh_vm","PASS"),
            ("installed_on_owner_server",True),
            ("public_package_url","https://example.invalid/owner-trial.run"),
            ("sha256","0"*40),
            ("offline_no_git_token",False),
        ):
            with self.subTest(key=key):
                altered=copy.deepcopy(self.stage)
                offline=next(x for x in altered["modules"] if x["id"]=="P07-M05")["offline_owner_trial"]
                offline[key]=value
                with self.assertRaises(ValueError): verify(altered,self.toolbox)

    def test_all_five_module_builds_fail_closed_on_drift(self):
        self.assertTrue(verify(self.stage,self.toolbox))
        for module,key in (
            ("P07-M01","VF_NODE_EXPECTED"),
            ("P07-M02","VPS_AUDIT_BUILD_EXPECTED"),
            ("P07-M03","VF_SERVER_OPS_BUILD_EXPECTED"),
            ("P07-M04","M04_BUILD_EXPECTED"),
            ("P07-M05","M05_BUILD_EXPECTED"),
        ):
            with self.subTest(module=module):
                changed=self.toolbox.replace(key+'="',key+'="bad-',1)
                with self.assertRaisesRegex(ValueError,"candidate build drift"):
                    verify(self.stage,changed)
        stale=copy.deepcopy(self.stage)
        stale["modules"][4]["build"]="0.1.0-m05-candidate1"
        with self.assertRaisesRegex(ValueError,"candidate build drift"):
            verify(stale,self.toolbox)

    def test_toolbox_help_has_independent_m05_without_stale_m03_label(self):
        self.assertIn("5. 新服务器初始化        系统更新/CloudPanel/数据库选择",self.toolbox)
        self.assertIn("系统更新/CloudPanel/数据库选择",self.toolbox)
        self.assertIn("--modules) modules_status_readonly",self.toolbox)
        self.assertIn("P07-M05 新服务器初始化",self.toolbox)

    def test_m03_never_runs_unverified_or_foreign_current_runtime(self):
        self.assertTrue(verify(self.stage,self.toolbox))
        # Release-115 must be checked against immutable bytes, not only a
        # self-maintained local SHA list. Four other module pins are untouched.
        for needle in (
            '[[ "$installed" == "$VF_SERVER_OPS_BUILD_EXPECTED" ]] || return 1',
            '[[ "$(p07_git_blob_sha1 "$root/.runtime-manifest.gitblob" 2>/dev/null || true)" == "$VF_SERVER_OPS_MANIFEST_BLOB" ]] || return 1',
            '[[ -v seen[$entry_rel] ]] || return 1',
        ):
            with self.subTest(missing=needle):
                bad=self.toolbox.replace(needle,"# removed proof",1)
                with self.assertRaisesRegex(ValueError,"M03 may execute before exact pinned integrity check"):
                    verify(self.stage,bad)
        # The manifest pin is tied to the exact current stable module stage.
        bad=self.toolbox.replace('VF_SERVER_OPS_MANIFEST_BLOB="4acbaca22aac0da681b34376e2cc86d876593181"',
                                 'VF_SERVER_OPS_MANIFEST_BLOB="0000000000000000000000000000000000000000"',1)
        with self.assertRaisesRegex(ValueError,"M03 stable manifest pin absent"):
            verify(self.stage,bad)


if __name__=="__main__":
    unittest.main()
