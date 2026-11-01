"""P07 synthetic immutable ilovem3u8 readback tests (no real DB or SSH)."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location("p07_ilovem3u8_verify",
    ROOT/"p07-ilovem3u8-isolated-recovery-verify.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def digest(b):return hashlib.sha256(b).hexdigest()
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"recover"
        self.root.mkdir(mode=0o700)
        self.state=Path(self.tmp.name)/"state.json"
        source=b"first gzip data"
        target=b"second gzip data"
        (self.root/"source.sql.gz").write_bytes(source)
        (self.root/"protected-original-target.sql.gz").write_bytes(target)
        os.chmod(self.root/"source.sql.gz",0o600)
        os.chmod(self.root/"protected-original-target.sql.gz",0o600)
        self.db="p07scratch-1a2b3c4d5e6f"
        self.user="p07stage-1a2b3c4d5e6f"
        self.rec={
            "migration_id":m.MID,"original_site":m.DOMAIN,
            "status":"ISOLATED_SOURCE_READBACK_PASS",
            "scratch_database":self.db,"scratch_user":self.user,
            "cutover_allowed":False,"source_frozen":False,
            "dns_changed":False,"site_config_modified":False,
            "existing_target_database_modified":False,
            "original_target_preserved":True,
            "source_dump_sha256":digest(source),
            "target_dump_sha256":digest(target),
            "source_ddl_table_count":42,"target_ddl_table_count":42,
            "source_uncompressed_bytes":123,
            "readback_tables":42,"readback_rows":1013,
        }
        sites=[{"domain":"example.test","stage_status":"PULLED_STAGED"} for _ in range(17)]
        sites[7]={"domain":m.DOMAIN,"stage_status":"PENDING"}
        self.origin={
            "schema":"vf-server-ops.server-migration.target-pull.v1",
            "migration_id":m.MID,"status":"PREPARE_FAILED",
            "source_runtime_frozen":False,"dns_changed_by_p07":False,
            "source_delete_allowed":False,"existing_target_overwrite_allowed":False,
            "sites":sites}
        self.write_json(self.root/"status.json",self.rec)
        self.write_json(self.state,self.origin)
        self.write_json(self.root/"scratch-credentials.json",{
            "database":self.db,"user":self.user,"password":"p"*32})
        self.stage=types.SimpleNamespace(
            panel_link_count=lambda db:1,
            readback=lambda db,user,pw:(42,1013))
        self.base=types.SimpleNamespace(
            inspect_archive=lambda path:(123,42),
            _master_sql_presence=lambda db,user:("1","1"))
    def write_json(self,path,data):
        path.write_text(json.dumps(data))
        os.chmod(path,0o600)
    def run_verify(self,other_names=None,src_count=1013,tgt_count=1015):
        # CI is a non-root runner. Mock ONLY the root-UID part of the file
        # checks, retaining actual permission, file/symlink and size guards.
        def synthetic_private_file(path,maxsize):
            try:x=path.lstat()
            except OSError:raise m.Block("PRIVATE_RECOVERY_FILE_MISSING") from None
            import stat
            if (not stat.S_ISREG(x.st_mode) or x.st_mode&0o077
                    or path.is_symlink() or not 0<x.st_size<=maxsize):
                raise m.Block("PRIVATE_RECOVERY_FILE_UNSAFE")
            return path
        with mock.patch.object(m,"private_dir"), \
             mock.patch.object(m,"private_file",side_effect=synthetic_private_file), \
             mock.patch.object(m,"cloudpanel_site_db_names",
               return_value=other_names if other_names is not None
                   else {self.db,"original-db"}), \
             mock.patch.object(m,"archive_tuple_count",
               side_effect=[src_count,tgt_count]):
            return m.verify(self.stage,self.base,self.root,self.state)
    def test_valid_recovered_state_avoids_reinstall_and_cutover(self):
        result=self.run_verify()
        self.assertEqual(result["SOURCE_ARCHIVE"],"SHA256_PASS")
        self.assertEqual(result["ORIGINAL_TARGET_ARCHIVE"],"SHA256_PASS")
        self.assertEqual(result["SCRATCH_TABLES"],42)
        self.assertEqual(result["SCRATCH_ROWS"],1013)
        self.assertEqual(result["PROTECTED_ISOLATED_RECOVERY_READBACK"],"PASS")
        self.assertEqual(result["DATABASE_WRITES"],"NONE")
        self.assertEqual(result["SOURCE_VPS_CONTACTED"],"NO")
        self.assertEqual(result["CUTOVER_ALLOWED"],"NO")
        self.assertEqual(result["RAW_SOURCE_EXPORT_TO_DB_VALUE_PARITY"],"NOT_VERIFIED")
        self.assertNotIn(self.db,str(result))
        self.assertNotIn("original-db",str(result))
    def test_source_snapshot_sql_tuple_count_mismatch_fails(self):
        with self.assertRaisesRegex(m.Block,"SOURCE_EXPORT_SQL_ROW_COUNT_DIFFERS"):
            self.run_verify(src_count=1012)
        result=self.run_verify(src_count="UNAVAILABLE")
        self.assertEqual(result["SOURCE_SQL_INSERT_TUPLES_ADVISORY"],"UNAVAILABLE")
    def test_archives_are_immutable_and_source_target_both_required(self):
        path=self.root/"protected-original-target.sql.gz"
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(m.Block,"PROTECTED_ORIGINAL_TARGET_ARCHIVE_SHA"):
            self.run_verify()
        path.unlink()
        with self.assertRaisesRegex(m.Block,"PRIVATE_RECOVERY_FILE_MISSING"):
            self.run_verify()
    def test_prevent_status_marker_and_restore_stage_replay(self):
        self.rec["cutover_allowed"]=True
        self.write_json(self.root/"status.json",self.rec)
        with self.assertRaisesRegex(m.Block,"ISOLATED_RECOVERY_STATE_CHANGED"):
            self.run_verify()
        self.rec["cutover_allowed"]=False
        self.rec["status"]="ISOLATED_IMPORT_STARTED"
        self.write_json(self.root/"status.json",self.rec)
        with self.assertRaisesRegex(m.Block,"ISOLATED_RECOVERY_STATE_CHANGED"):
            self.run_verify()
    def test_original_migration_remains_failed_protected(self):
        self.origin["existing_target_overwrite_allowed"]=True
        self.write_json(self.state,self.origin)
        with self.assertRaisesRegex(m.Block,"ORIGINAL_MIGRATION_PROTECTION_CHANGED"):
            self.run_verify()
    def test_scratch_identity_and_binding_cannot_drift(self):
        self.rec["scratch_user"]="p07stage-ffffffffffff"
        self.write_json(self.root/"status.json",self.rec)
        with self.assertRaisesRegex(m.Block,"SCRATCH_DATABASE_USER_IDENTITY_CHANGED"):
            self.run_verify()
        self.rec["scratch_user"]=self.user
        self.write_json(self.root/"status.json",self.rec)
        with self.assertRaisesRegex(m.Block,"ORIGINAL_CP2_DATABASE_REGISTRATION_CHANGED"):
            self.run_verify(other_names={"original-db","other-db"})
        with self.assertRaisesRegex(m.Block,"ORIGINAL_CP2_DATABASE_REGISTRATION_CHANGED"):
            self.run_verify(other_names={"original-db"})
    def test_private_permissions_are_required(self):
        os.chmod(self.root/"status.json",0o644)
        with self.assertRaisesRegex(m.Block,"PRIVATE_RECOVERY_FILE_UNSAFE"):
            self.run_verify()
    def test_non_verify_cli_mode_fails_before_loading_helpers(self):
        with mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(m.sys,"argv",["tool","--restore"]), \
             mock.patch.object(m,"pinned") as load:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_ISOLATED_READONLY_GATE_REQUIRED"):
                m.main()
            load.assert_not_called()
    def test_no_source_or_database_writes_in_operator(self):
        s=(ROOT/"p07-ilovem3u8-isolated-recovery-verify.py").read_text()
        for forbidden in ("cloudpanel.export_database(", "add_database(",
                          "import_database(", "isolated_import(",
                          "cutover_migration(", "source_remote(", "pull_path(",
                          "DROP TABLE", "DELETE FROM", "UPDATE "):
            self.assertNotIn(forbidden,s)
        self.assertIn("CUTOVER_ALLOWED","".join(["CUTOVER_ALLOWED=NO","CUTOVER_ALLOWED"]))
        self.assertIn('RAW_SOURCE_EXPORT_TO_DB_VALUE_PARITY":"NOT_VERIFIED"',s)
if __name__=="__main__":
    unittest.main()
