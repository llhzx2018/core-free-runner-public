"""P07 SQL column metadata synthetic diagnosis: never a resume or cutover gate."""
from __future__ import annotations
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"lib"))
import migration_sql_column_evidence as v

def col(default="a", normalized=None, *, overrides=None):
    data={field:["a"*64,"a"*64] for field in v.FIELDS}
    data["COLUMN_DEFAULT"]=[
        default*64,(normalized if normalized is not None else default)*64
    ]
    if overrides:
        for key,value in overrides.items():data[key]=value
    return data

class SQLMetadataEvidenceTests(unittest.TestCase):
    def test_expresses_cross_engine_presentation_only_without_granting_pass(self):
        name="0"*64
        a={name:col("a","b")};b={name:col("c","b")}
        original=copy.deepcopy((a,b))
        result=v.compare(a,b,expected_column_count=1)
        self.assertEqual(result["properties"]["COLUMN_DEFAULT"],{
            "raw_changed":1,"after_narrow_presentation_normalization":0,
            "presentation_candidates":1,
        })
        self.assertEqual(result["unresolved_normalized_property_differences"],0)
        for key in ("normalization_grants_schema_equivalence",
                    "dynamic_ddl_semantics_verified",
                    "original_export_snapshot_matched",
                    "source_target_data_parity_verified","cutover_allowed",
                    "database_writes_performed","state_writes_performed"):
            self.assertIs(result[key],False)
        self.assertEqual((a,b),original)

    def test_changed_nullable_never_filtered_by_numeric_display_rule(self):
        name="0"*64
        a={name:col(overrides={"IS_NULLABLE":["a"*64,"a"*64]})}
        b={name:col(overrides={"IS_NULLABLE":["b"*64,"b"*64]})}
        r=v.compare(a,b)
        self.assertEqual(r["properties"]["IS_NULLABLE"]["raw_changed"],1)
        self.assertEqual(r["properties"]["IS_NULLABLE"]["after_narrow_presentation_normalization"],1)
        self.assertEqual(r["unresolved_normalized_property_differences"],1)
        self.assertFalse(r["cutover_allowed"])

    def test_missing_column_identity_is_never_ignored(self):
        a={"a"*64:col()}
        b={"b"*64:col()}
        r=v.compare(a,b)
        self.assertEqual(r["source_only_column_identities"],1)
        self.assertEqual(r["target_only_column_identities"],1)
        self.assertFalse(r["normalization_grants_schema_equivalence"])

    def test_invalid_or_incomplete_evidence_fails_closed(self):
        x={"0"*64:col()}
        for replacement in (
            {}, {"wrong":col()}, {"0"*64:{"IS_NULLABLE":["a"*64,"a"*64]}},
            {"0"*64:dict(col(),EXTRA=["not-a-hash","a"*64])},
            {"0"*64:dict(col(),EXTRA=["a"*64])},
        ):
            with self.subTest(value=str(replacement)[:80]):
                with self.assertRaises(v.ColumnEvidenceBlocked):
                    v.compare(replacement,x)
        with self.assertRaises(v.ColumnEvidenceBlocked):
            v.compare(x,x,expected_column_count=761)
        with self.assertRaises(v.ColumnEvidenceBlocked):
            v.compare(x,x,expected_column_count=True)

    def test_advisory_column_match_cannot_override_conditional_ddl_block(self):
        import gzip
        import tempfile
        import server_migration_pull as pull
        value={"0"*64:col()}
        evidence=v.compare(value,value,expected_column_count=1)
        self.assertEqual(evidence["unresolved_normalized_property_differences"],0)
        self.assertFalse(evidence["normalization_grants_schema_equivalence"])
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"source.sql.gz"
            target=Path(tmp)/"target.sql.gz"
            with gzip.open(source,"wt",encoding="utf-8") as stream:
                stream.write(
                    "CREATE TABLE t (id int);\n"
                    "/*!50003 CREATE TRIGGER audit BEFORE INSERT ON t FOR EACH ROW SET @x=1 */;\n"
                    "INSERT INTO t VALUES (1);\n"
                )
            with gzip.open(target,"wt",encoding="utf-8") as stream:
                stream.write(
                    "CREATE TABLE t (id int);\n"
                    "INSERT INTO t VALUES (1);\n"
                )
            with self.assertRaisesRegex(
                pull.PullMigrationError,"MySQL verification failed \\[CONDITIONAL_DDL\\]"
            ):
                pull.compare_database_dumps(source,target)

    def test_privacy_does_not_emit_raw_metadata(self):
        x={"0"*64:col()}
        result=v.compare(x,x)
        self.assertNotIn("0"*64,str(result))
        self.assertNotIn("a"*64,str(result))
        self.assertEqual(len(result["properties"]),len(v.FIELDS))

if __name__=="__main__":
    unittest.main()
