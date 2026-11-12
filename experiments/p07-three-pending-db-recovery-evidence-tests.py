"""Synthetic-only three pending-site DB recovery boundary audits."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).parent
def load(name,alias):
    spec=importlib.util.spec_from_file_location(alias,HERE/name)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
m=load("p07-three-pending-db-recovery-evidence.py","pending_recovery_audit")
fx=load("p07-17-site-staged-local-evidence-tests.py","pending_fixture")

class Tests(unittest.TestCase):
    @staticmethod
    def local_fixture_private_file(path,limit=1048576):
        # CI runner has no root-owned temp files. Preserve mode and type rules
        # in these synthetic tests; a separate test checks the real root gate.
        try:meta=path.lstat()
        except FileNotFoundError:return "ABSENT",None
        if not (stat.S_ISREG(meta.st_mode) and
                meta.st_uid==os.getuid() and not meta.st_mode&0o077
                and 0<meta.st_size<=limit):
            raise m.Block("PRIVATE_EVIDENCE_KIND_OWNER_OR_PERMISSIONS_CHANGED")
        return "PRESENT",path
    def make(self,root,*,alter=None):
        states=fx.make_states()
        if alter:alter(states)
        scratch=root/"recovery-scratch-www3"
        scratch.mkdir()
        data=b"protected-original-database-dump"
        archive=scratch/"source.sql.gz"
        archive.write_bytes(data)
        archive.chmod(0o600)
        import hashlib
        record={
            "migration_id":m.WWW3,"original_site":"www3.m3u8.one",
            "status":"ISOLATED_IMPORT_COMPLETED_NOT_VERIFIED",
            "source_dump_sha256":hashlib.sha256(data).hexdigest(),
            "site_config_modified":False,
            "existing_target_database_modified":False,
            "dns_changed":False,"source_frozen":False,"cutover_allowed":False,
            "scratch_database":"PRIVATE_NAME_NO_OUTPUT",
            "password":"PRIVATE_PASSWORD_NO_OUTPUT"
        }
        status=scratch/"status.json"
        status.write_text(json.dumps(record))
        status.chmod(0o600)
        creds=scratch/"scratch-credentials.json"
        creds.write_text('{"password":"PRIVATE_SECRET_NO_OUTPUT"}')
        creds.chmod(0o600)
        backup=[]
        for i in range(3):
            p=root/("backup"+str(i)+".json")
            p.write_text('{"safe":"metadata"}')
            p.chmod(0o644)
            backup.append(p)
        return states,scratch,backup
    def invoke(self,alter=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            states,scratch,backup=self.make(root,alter=alter)
            out=io.StringIO()
            with mock.patch.object(m.base,"secure_state",
                     side_effect=lambda p:states[p.parent.name]), \
                 mock.patch.object(m.os,"geteuid",return_value=0), \
                 mock.patch.object(m,"WWW3_RECOVERY",scratch), \
                 mock.patch.object(m,"private_file",
                                   side_effect=self.local_fixture_private_file), \
                 mock.patch.object(m,"BACKUP_MANIFESTS",tuple(backup)), \
                 mock.patch.object(m,"backup_manifest_presence",return_value="PRESENT"), \
                 mock.patch.object(sys,"argv",[
                   "probe","--audit-three-pending-site-databases-readonly"]), \
                 contextlib.redirect_stdout(out):
                m.run()
            return out.getvalue()
    def test_realistic_3_pending_and_private_www3_archive_sha(self):
        data=self.invoke()
        self.assertEqual(sum(x.startswith("SITE=") for x in data.splitlines()),3)
        self.assertIn("PENDING_SITE_COUNT=3",data)
        self.assertIn("WWW3_SOURCE_PROTECTED_ARCHIVE=SHA256_PASS",data)
        self.assertIn("WWW3_SCRATCH_IMPORT_COMPLETED_RECORDED=YES",data)
        self.assertIn("ILOVEM3U8_PROTECTED_BACKUP_MANIFEST_1=PRESENT",data)
        self.assertIn("UNZIP_CONDITIONAL_SQL_RECOVERY=NOT_AUTHORIZED",data)
        self.assertIn("CUTOVER_ALLOWED=NO",data)
        for bad in ("PRIVATE_PASSWORD","PRIVATE_SECRET","PRIVATE_NAME","source.sql.gz"):
            self.assertNotIn(bad,data)
    def test_all_backup_records_optional_and_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(m.backup_manifest_presence(root/"absent"),"ABSENT")
            p=root/"world-writable"
            p.write_text("{}")
            p.chmod(0o666)
            self.assertEqual(m.backup_manifest_presence(p),
                             "UNSAFE_OR_UNVERIFIED")
    def test_archive_mismatch_fails_closed_reporting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/"source.sql.gz"
            archive.write_bytes(b"changed")
            archive.chmod(0o600)
            rec={"source_dump_sha256":"a"*64}
            with mock.patch.object(m,"private_file",
                                   side_effect=self.local_fixture_private_file):
                self.assertEqual(m.archive_proof(rec,archive),"SHA256_MISMATCH")
                archive.unlink()
                self.assertEqual(m.archive_proof(rec,archive),"ARCHIVE_ABSENT")
    def test_protected_scratch_mutation_blocks_before_reporting(self):
        def changed(states):
            states[m.base.JOBS[2][1]]["dns_changed_by_p07"]=True
        with self.assertRaisesRegex(m.Block,"MIGRATION_SAFETY_BOUNDARY_CHANGED"):
            self.invoke(changed)
    def test_pending_to_staged_wrongly_blocks(self):
        def changed(states):
            states[m.base.JOBS[2][1]]["sites"][-1]["stage_status"]="PULLED_STAGED"
        with self.assertRaisesRegex(m.Block,"17_SITE_STAGED_PENDING_SCOPE_CHANGED"):
            self.invoke(changed)
    def test_explicit_readonly_gate(self):
        with mock.patch.object(m.os,"geteuid",return_value=0), \
             mock.patch.object(sys,"argv",["tool","--restore"]), \
             mock.patch.object(m,"site_evidence") as check:
            with self.assertRaisesRegex(m.Block,"EXPLICIT_THREE_PENDING_DB_AUDIT_REQUIRED"):
                m.run()
            check.assert_not_called()
    def test_real_private_file_root_owner_gate_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"evidence"
            f.write_text("{}")
            f.chmod(0o600)
            if os.getuid()!=0:
                with self.assertRaisesRegex(
                    m.Block,"PRIVATE_EVIDENCE_KIND_OWNER_OR_PERMISSIONS_CHANGED"):
                    m.private_file(f)
            f.chmod(0o644)
            with self.assertRaisesRegex(
                m.Block,"PRIVATE_EVIDENCE_KIND_OWNER_OR_PERMISSIONS_CHANGED"):
                m.private_file(f)

    def test_no_server_writes_or_source_contact(self):
        txt=(HERE/"p07-three-pending-db-recovery-evidence.py").read_text()
        for token in ("subprocess.run(", "socket.create_connection(",
                      "shutil.copy", "os.replace(", "os.chown(", "os.chmod(",
                      "DROP DATABASE", "INSERT INTO", "UPDATE ", "DELETE ",
                      "ssh ", "rsync ", "curl "):
            self.assertNotIn(token,txt)
        self.assertIn("OLD_SERVER_CONTACTED=NO",txt)
        self.assertIn("MYSQL_CONNECTIONS_AND_WRITES=NONE",txt)
        self.assertIn("CUTOVER_ALLOWED=NO",txt)

if __name__=="__main__":
    unittest.main()
