"""Synthetic worker tests, including row multiset order and bytes; no DB connections."""
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

FILE=Path(__file__).with_name("p07-www3-content-worker.py")
spec=importlib.util.spec_from_file_location("p07_worker",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class FakeProc:
    def __init__(self,values):
        self.stdout=io.BytesIO(values)
        self.returncode=0
        self.done=False
    def wait(self,timeout):
        self.done=True
        return 0
    def poll(self):
        return self.returncode if self.done else None
    def kill(self):
        self.done=True

class Tests(unittest.TestCase):
    def test_schema_order_is_python_not_sql_collation(self):
        def sql(args,query,timeout=60):
            if "FROM information_schema.TABLES" in query:return "wp_z\nwp_A"
            return "wp_z\tz\nwp_z\ta\nwp_A\tid"
        with mock.patch.object(m,"sql_read",side_effect=sql):
            tables,cols=m.schema(["mariadb"],"scratch")
            self.assertEqual(tables,["wp_A","wp_z"])
            self.assertEqual(cols["wp_z"],["a","z"])

    def test_null_text_and_binary_values_are_safe_hex(self):
        a=[b"0\tN\tVFF\n",b"0\tV00\tN\n",b"0\tV00\tN\n"]
        b=list(reversed(a))
        cols={"wp_a":["c1","c2"]}
        def evaluate(lines):
            with mock.patch.object(m.shutil,"which",
                side_effect=lambda n:{"mariadb":"/usr/bin/mariadb","timeout":"/usr/bin/timeout"}.get(n)), \
                 mock.patch.object(m.subprocess,"Popen",return_value=FakeProc(b"".join(lines))):
                result,total=m.fingerprint(["--defaults-extra-file=/root/unused"],
                                            "p07scratch-abcdef123456",["wp_a"],cols)
                self.assertEqual(total,3)
                self.assertEqual(next(iter(result.values()))[0],3)
                return result
        self.assertEqual(evaluate(a),evaluate(b))

    def test_payload_is_null_distinct_and_no_sql_literal_disclosure(self):
        def evaluate(row):
            with mock.patch.object(m.shutil,"which",
                side_effect=lambda n:{"mariadb":"/usr/bin/mariadb","timeout":"/usr/bin/timeout"}.get(n)), \
                 mock.patch.object(m.subprocess,"Popen",return_value=FakeProc(row)):
                result,_=m.fingerprint(["--defaults-extra-file=/root/unused"],
                                      "p07scratch-abcdef123456",["wp_a"],{"wp_a":["c1"]})
                return result
        self.assertNotEqual(evaluate(b"0\tN\n"),evaluate(b"0\tV\n"))
        self.assertNotEqual(evaluate(b"0\tV00\n"),evaluate(b"0\tV0000\n"))

    def test_single_cell_change_changes_only_that_column_digest(self):
        def examine(payload):
            with mock.patch.object(m.shutil,"which",
                side_effect=lambda name:{"mariadb":"/usr/bin/mariadb",
                                        "timeout":"/usr/bin/timeout"}.get(name)), \
                 mock.patch.object(m.subprocess,"Popen",
                    return_value=FakeProc(payload)):
                data,count=m.fingerprint(["--defaults-extra-file=/root/notused"],
                    "p07scratch-abcdef123456",["wp_a"],{"wp_a":["c1","c2"]})
                self.assertEqual(count,1)
                return next(iter(data.values()))
        before=examine(b"0\tV41\tV42\n")
        after=examine(b"0\tV41\tV43\n")
        self.assertNotEqual(before[1],after[1])
        self.assertEqual(before[2],after[2])
        self.assertEqual(len(before[3]),2)
        differing=sum(before[3][k]!=after[3][k] for k in before[3])
        self.assertEqual(differing,1)

    def test_nonhex_payload_fails_closed_without_printing_value(self):
        with mock.patch.object(m.shutil,"which",
            side_effect=lambda n:{"mariadb":"/usr/bin/mariadb","timeout":"/usr/bin/timeout"}.get(n)), \
             mock.patch.object(m.subprocess,"Popen",
                 return_value=FakeProc(b"0\tVPLAINTEXT\n")):
            with self.assertRaises(SystemExit) as ctx:
                m.fingerprint(["--defaults-extra-file=/root/unused"],
                              "p07scratch-abcdef123456",["wp_a"],{"wp_a":["c1"]})
            self.assertEqual(ctx.exception.code,13)

    def test_static_byte_identity_and_transaction_read_only(self):
        source=FILE.read_text()
        self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY",source)
        self.assertIn("HEX(CAST(",source)
        self.assertIn("ROW_CAP=1000000",source)
        self.assertIn("tempfile.TemporaryDirectory(prefix=",source)
        self.assertNotIn("DROP DATABASE",source)
        self.assertNotIn("CREATE DATABASE",source)
        self.assertNotIn("INSERT INTO",source)

if __name__=="__main__":
    unittest.main()
