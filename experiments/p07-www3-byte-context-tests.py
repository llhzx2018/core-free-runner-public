"""Synthetic byte-preserving advisory tests; no real SQL or server access."""
import ast
import gzip
import re
import tempfile
from pathlib import Path
import unittest

SCRIPT=Path(__file__).with_name("p07-www3-source-schema-advisory.py")
raw=ast.parse(SCRIPT.read_text())
remote=next(n.value.value for n in ast.walk(raw) if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=="REMOTE" for t in n.targets))
tree=ast.parse(remote)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
        and n.name=="classify_invalid_utf8_context")
namespace={"gzip":gzip,"re":re}
exec(compile(ast.Module(body=[fn],type_ignores=[]),"<synthetic_advisory>","exec"),namespace)
scan=namespace["classify_invalid_utf8_context"]

def run(data):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"sample.sql.gz"
        with gzip.open(path,"wb") as f:f.write(data)
        return scan(path)

class ByteContext(unittest.TestCase):
    def test_invalid_dml_uses_lossless_read_only_classification(self):
        data=b"/*!40101 SET NAMES latin1 */;\nCREATE TABLE t (v BLOB);\n"
        data+=b"INSERT INTO t VALUES ('"+bytes([255])+b"');\n"
        result,complete,charset=run(data)
        self.assertTrue(complete)
        self.assertEqual(charset,"LATIN1")
        self.assertGreater(result["DML"],0)
        self.assertEqual(result["DDL"],0)

    def test_invalid_ddl_is_never_called_safe(self):
        x=b"CREATE TABLE "+bytes([255])+b" (id INT);\n"
        result,complete,charset=run(x)
        self.assertTrue(complete)
        self.assertGreater(result["DDL"],0)
        self.assertEqual(charset,"NOT_FOUND")

    def test_valid_multibyte_split_across_one_megabyte_boundary(self):
        # Each readline is capped at 1 MiB. A valid UTF-8 codepoint split
        # across chunks must not be reported as malformed.
        length=(1024*1024)-len(b"INSERT INTO t VALUES ('")-1
        data=b"INSERT INTO t VALUES ('"+b"a"*length+"😄".encode()+b"');\n"
        result,complete,_=run(data)
        self.assertTrue(complete)
        self.assertEqual(sum(result.values()),0)

    def test_no_invalid_utf8(self):
        result,complete,_=run(b"SET NAMES utf8mb4;\nCREATE TABLE t(id INT);\n")
        self.assertTrue(complete)
        self.assertEqual(sum(result.values()),0)

if __name__=="__main__":unittest.main()
