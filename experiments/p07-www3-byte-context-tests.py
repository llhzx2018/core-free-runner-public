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


class TempExportLifecycle(unittest.TestCase):
    def test_classifier_runs_inside_temporary_export_scope(self):
        calls = [n for n in ast.walk(tree) if isinstance(n,ast.Call)
                 and isinstance(n.func,ast.Name)
                 and n.func.id=="classify_invalid_utf8_context"]
        scopes = [n for n in ast.walk(tree) if isinstance(n,ast.With)
                  and any(isinstance(c.context_expr,ast.Call)
                          and isinstance(c.context_expr.func,ast.Attribute)
                          and c.context_expr.func.attr=="TemporaryDirectory"
                          for c in n.items)]
        self.assertEqual(len(calls),1)
        self.assertEqual(len(scopes),1)
        self.assertTrue(any(n is calls[0] for n in ast.walk(scopes[0])))

    def test_synthetic_export_cleanup_and_invalid_dml(self):
        import contextlib,io,shutil,sys,types
        from unittest import mock
        fixture=b"SET NAMES utf8mb4;\nCREATE TABLE t(id INT);\nINSERT INTO t VALUES('"+bytes([255])+b"');\n"
        with tempfile.TemporaryDirectory() as tmp:
            anchor='root=Path("/var/lib/vf-server-ops/pull-source")/mid/"data"'
            self.assertIn(anchor,remote)
            script=remote.replace(anchor, "root=Path("+repr(tmp)+")")
            cloud=types.ModuleType("cloudpanel")
            cloud.CloudPanelError=RuntimeError
            def export(name,output,*,clpctl):
                self.assertEqual(name,"fixture")
                with gzip.open(output,"wb") as h:h.write(fixture)
            cloud.export_database=export
            inventory=types.ModuleType("inventory")
            inventory.build_manifest=lambda _:{"sites":[{"domain":"www3.m3u8.one","mysql_databases":["fixture"]}]}
            lib=Path(__file__).resolve().parents[1]/"dist/p07/0.1.0/overlay/lib"
            if str(lib) not in sys.path:sys.path.insert(0,str(lib))
            import sql_diff_evidence as evidence
            buf=io.StringIO()
            with mock.patch.dict(sys.modules,{"cloudpanel":cloud,"inventory":inventory,
                                              "sql_diff_evidence":evidence}),\
                 mock.patch.object(sys,"argv",["-c","www3.m3u8.one","fixture","fake"]),\
                 mock.patch.object(shutil,"which",return_value=None),\
                 contextlib.redirect_stdout(buf):
                exec(compile(script,"<synthetic>","exec"),{"__name__":"__main__"})
            self.assertIn("PARSER_RESULT=SQL_DIAGNOSTIC_INPUT_UNAVAILABLE",buf.getvalue())
            self.assertIn("UTF8_CONTEXT_SCAN_COMPLETE=TRUE",buf.getvalue())
            self.assertIn("INVALID_UTF8_CHUNKS_DML=1",buf.getvalue())
            self.assertIn("SOURCE_BUSINESS_DB_WRITES=NO",buf.getvalue())
            self.assertEqual(list(Path(tmp).iterdir()),[])


if __name__=="__main__":unittest.main()
