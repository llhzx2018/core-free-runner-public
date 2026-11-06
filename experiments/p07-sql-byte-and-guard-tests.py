"""Synthetic-only data integrity / dynamic-guard proofs for P07 blockers."""
import gzip
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "dist/p07/0.1.0/overlay/lib"
sys.path.insert(0, str(LIB))
import verify
import sql_diff_evidence

spec = importlib.util.spec_from_file_location(
    "raw_bytes", HERE / "p07-sql-raw-byte-advisory.py"
)
byte = importlib.util.module_from_spec(spec)
spec.loader.exec_module(byte)


class ByteExactEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p07-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.a = Path(self.temp.name) / "src.sql.gz"
        self.b = Path(self.temp.name) / "dst.sql.gz"

    def write(self, a, b):
        for path, data in ((self.a, a), (self.b, b)):
            with gzip.open(path, "wb") as handle:
                handle.write(data)

    def test_invalid_utf8_identical_bytes_are_advisory_not_pass(self):
        data = (b"SET NAMES utf8mb4;\n"
                b"CREATE TABLE t(id INT PRIMARY KEY, val BLOB);\n"
                b"INSERT INTO t VALUES (1,'" + bytes([255,254]) + b"');\n")
        self.write(data, data)
        result = byte.compare_sql_bytes(self.a, self.b)
        self.assertEqual(result["comparison"], "EXACT_UNCOMPRESSED_SQL_BYTES_NOT_VERIFIED")
        self.assertEqual(result["verification"], "NOT_A_PASS_GATE")
        self.assertFalse(result["target_restore_verified"])
        self.assertFalse(result["source_export_provenance_verified"])
        self.assertFalse(result["cutover_allowed"])

    def test_single_literal_byte_change_fails_even_if_row_count_equal(self):
        old = b"CREATE TABLE t(id INT);\nINSERT INTO t VALUES ('" + bytes([255]) + b"');\n"
        new = b"CREATE TABLE t(id INT);\nINSERT INTO t VALUES ('" + bytes([254]) + b"');\n"
        self.write(old, new)
        self.assertEqual(byte.compare_sql_bytes(self.a, self.b)["comparison"],
                         "UNCOMPRESSED_SQL_BYTES_DIFFER")

    def test_single_schema_byte_change_fails(self):
        self.write(b"CREATE TABLE t(id INT);\n", b"CREATE TABLE t(id BIGINT);\n")
        self.assertEqual(byte.compare_sql_bytes(self.a, self.b)["comparison"],
                         "UNCOMPRESSED_SQL_BYTES_DIFFER")

    def test_guard_mutation_is_not_normalized_away(self):
        self.write(b"/*!50000 SET @x=IF(@flag,'SELECT 1','SELECT 0') */;\n",
                   b"/*!50000 SET @x=IF(@flag,'SELECT 0','SELECT 0') */;\n")
        self.assertEqual(byte.compare_sql_bytes(self.a, self.b)["comparison"],
                         "UNCOMPRESSED_SQL_BYTES_DIFFER")

    def test_truncated_gzip_fails_closed(self):
        self.write(b"CREATE TABLE a(id INT);\n", b"CREATE TABLE a(id INT);\n")
        self.b.write_bytes(self.b.read_bytes()[:-6])
        with self.assertRaises(byte.EvidenceUnavailable) as err:
            byte.compare_sql_bytes(self.a, self.b)
        self.assertEqual(str(err.exception), "GZIP_STREAM_INVALID")

    def test_cap_fails_closed(self):
        self.write(b"x"*100, b"x"*100)
        with self.assertRaises(byte.EvidenceUnavailable) as err:
            byte.compare_sql_bytes(self.a, self.b, max_bytes=99)
        self.assertEqual(str(err.exception), "SCAN_LIMIT_EXCEEDED")

    def test_symlink_and_world_write_refused(self):
        self.write(b"x", b"x")
        link = Path(self.temp.name) / "link.sql.gz"
        link.symlink_to(self.a)
        with self.assertRaises(byte.EvidenceUnavailable):
            byte.compare_sql_bytes(link, self.b)
        self.a.chmod(0o666)
        with self.assertRaises(byte.EvidenceUnavailable):
            byte.compare_sql_bytes(self.a, self.b)


class GuardSafety(unittest.TestCase):
    def test_allow_only_fixed_narrow_session_or_read_branches(self):
        self.assertTrue(verify._cross_engine_safe_dynamic_branch("'SET SQL_MODE = 0'"))
        self.assertTrue(verify._cross_engine_safe_dynamic_branch("'SELECT 1'"))
        for unsafe in (
            "'SET GLOBAL SQL_MODE=0'",
            "'SET PERSIST SQL_MODE=0'",
            "'SELECT * FROM mysql.user'",
            "'SELECT 1; DROP TABLE users'",
            "'UPDATE t SET value=1'",
            "'SET @a=1;SET @b=2'",
        ):
            with self.subTest(unsafe=unsafe):
                self.assertFalse(verify._cross_engine_safe_dynamic_branch(unsafe))

    def test_three_unproven_dynamic_branches_remain_blocked(self):
        sample = (
            "/*!50000 SET @stmt_a = IF(@present,'SET GLOBAL SQL_MODE=0','SELECT 1') */;\n"
            "/*!50000 SET @stmt_b = IF(@present,'SET @v=1;SELECT 1','SELECT 1') */;\n"
            "/*!50000 SET @stmt_c = IF(@present,'SELECT * FROM mysql.user','SELECT 1') */;\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"source.sql.gz"
            with gzip.open(p, "wb") as stream:
                stream.write(sample.encode("utf-8"))
            result = sql_diff_evidence.dynamic_guard_syntax_counts(p)
        self.assertEqual(result["recognized_unsafe"], 3)
        self.assertEqual(result["unsafe_yes_branches"], 3)
        self.assertEqual(result["unsafe_no_branches"], 0)

    def test_no_automatic_data_write_or_cutover_paths(self):
        source = (HERE / "p07-sql-raw-byte-advisory.py").read_text()
        for prohibited in (
            "target_create_database_local", "prepare_migration(",
            "resume_prepare_migration(", "cutover_migration(",
            "source_freeze(", "import_database("
        ):
            self.assertNotIn(prohibited, source)

if __name__=="__main__":
    unittest.main()
