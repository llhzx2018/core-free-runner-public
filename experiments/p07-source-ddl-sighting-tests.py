"""P07 synthetic DDL sighting test, never touches live MySQL."""
import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("schema_sighting",HERE/"p07-source-ddl-sighting.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/"dump.sql.gz"

    def write(self, data):
        with gzip.open(self.p,"wb") as handle:handle.write(data)

    def test_non_utf8_dml_does_not_hide_valid_tables(self):
        self.write(
            b"SET NAMES utf8mb4;\nCREATE TABLE \x60accounts\x60(id INT);\n"
            b"INSERT INTO \x60accounts\x60 VALUES ('"+bytes([255])+b"');\n"
            b"CREATE TABLE \x60history\x60(\n id INT PRIMARY KEY\n);\n"
        )
        result=m.inspect_source_schema_candidates(self.p)
        self.assertEqual(result["recognized_schema_candidates"],2)
        self.assertEqual(result["invalid_utf8_ddl_candidates"],0)
        self.assertFalse(result["dml_content_verified"])
        self.assertEqual(result["verification"],"NOT_A_PASS_GATE")
        self.assertFalse(result["migration_resume_allowed"])
        self.assertFalse(result["cutover_allowed"])

    def test_invalid_ddl_not_reported_as_recognized(self):
        self.write(b"CREATE TABLE \x60t\x60(v VARCHAR(9) COMMENT '"+bytes([254])+b"');\n")
        result=m.inspect_source_schema_candidates(self.p)
        self.assertEqual(result["recognized_schema_candidates"],0)
        self.assertEqual(result["invalid_utf8_ddl_candidates"],1)

    def test_empty_file_has_no_verified_tables(self):
        self.write(b"-- header only\n")
        x=m.inspect_source_schema_candidates(self.p)
        self.assertEqual(x["schema_candidates"],0)
        self.assertEqual(x["verification"],"NOT_A_PASS_GATE")

    def test_oversized_ddl_fails_closed(self):
        self.write(b"CREATE TABLE t("+b"x"*128+b"\n"+b"y"*(m.MAX_DDL+1)+b");\n")
        with self.assertRaises(m.UnsafeOrUnverifiedExport) as ex:
            m.inspect_source_schema_candidates(self.p)
        self.assertEqual(str(ex.exception),"DDL_STATEMENT_TOO_LARGE")

    def test_incomplete_ddl_fails_closed(self):
        self.write(b"CREATE TABLE t(id INT\n")
        with self.assertRaises(m.UnsafeOrUnverifiedExport) as ex:
            m.inspect_source_schema_candidates(self.p)
        self.assertEqual(str(ex.exception),"DDL_STATEMENT_INCOMPLETE")

    def test_single_byte_mutation_does_not_claim_data_parity(self):
        self.write(b"CREATE TABLE t(x INT);\nINSERT INTO t VALUES('a');\n")
        x=m.inspect_source_schema_candidates(self.p)
        self.write(b"CREATE TABLE t(x INT);\nINSERT INTO t VALUES('b');\n")
        y=m.inspect_source_schema_candidates(self.p)
        self.assertEqual(x["recognized_schema_candidates"],y["recognized_schema_candidates"])
        self.assertFalse(x["dml_content_verified"])
        self.assertFalse(y["dml_content_verified"])

    def test_corrupt_gzip_rejected(self):
        self.write(b"CREATE TABLE t(x INT);\n")
        self.p.write_bytes(self.p.read_bytes()[:-5])
        with self.assertRaises(m.UnsafeOrUnverifiedExport):
            m.inspect_source_schema_candidates(self.p)

    def test_small_byte_cap_rejected(self):
        self.write(b"CREATE TABLE t(x INT);\n")
        with self.assertRaises(m.UnsafeOrUnverifiedExport) as ex:
            m.inspect_source_schema_candidates(self.p,max_bytes=5)
        self.assertEqual(str(ex.exception),"DECOMPRESSED_LIMIT_EXCEEDED")

    def test_unsafe_symlink_and_world_writable_rejected(self):
        self.write(b"CREATE TABLE t(x INT);\n")
        link=Path(self.tmp.name)/"link.sql.gz"
        link.symlink_to(self.p)
        with self.assertRaises(m.UnsafeOrUnverifiedExport):
            m.inspect_source_schema_candidates(link)
        self.p.chmod(0o666)
        with self.assertRaises(m.UnsafeOrUnverifiedExport):
            m.inspect_source_schema_candidates(self.p)

    def test_duplicate_candidates_rejected(self):
        self.write(b"CREATE TABLE t(x INT);\nCREATE TABLE t(x VARCHAR(3));\n")
        with self.assertRaises(m.UnsafeOrUnverifiedExport) as ex:
            m.inspect_source_schema_candidates(self.p)
        self.assertEqual(str(ex.exception),"DUPLICATE_TABLE_CANDIDATE")

if __name__=="__main__":unittest.main()
