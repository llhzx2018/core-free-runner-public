#!/usr/bin/env python3
"""Synthetic-only tests: redacted www3 SQL attribute classification."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
import contextlib
import io
import json
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dist/p07/0.1.0/overlay/lib"))

SCRIPT = Path(__file__).with_name("p07-www3-existing-scratch-parity-readonly.py")
spec = importlib.util.spec_from_file_location("p07_www3_readonly", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
classify = module._column_attribute_delta_groups


class AttributeEvidenceTests(unittest.TestCase):
    def test_default_change_does_not_misclassify_embedded_keyword(self):
        self.assertEqual(
            classify("varchar(20) NOT NULL DEFAULT 'COLLATE x'",
                     "varchar(20) NOT NULL DEFAULT 'COLLATE y'"),
            {"DEFAULT"},
        )

    def test_collation_delta(self):
        self.assertEqual(
            classify("varchar(20) COLLATE utf8mb4_general_ci",
                     "varchar(20) COLLATE utf8mb4_unicode_ci"),
            {"COLLATION"},
        )

    def test_charset_delta(self):
        self.assertEqual(
            classify("varchar(20) CHARACTER SET utf8mb4",
                     "varchar(20) CHARACTER SET latin1"),
            {"CHARSET"},
        )

    def test_nullability_delta(self):
        self.assertEqual(classify("int NOT NULL", "int NULL"), {"NULLABILITY"})

    def test_default_expression_delta(self):
        self.assertEqual(
            classify("int DEFAULT (uuid())", "int DEFAULT (now())"),
            {"DEFAULT"},
        )

    def test_unsigned_delta(self):
        self.assertEqual(
            classify("bigint UNSIGNED NOT NULL", "bigint NOT NULL"),
            {"UNSIGNED_ZEROFILL"},
        )

    def test_comment_literal_does_not_count_as_default(self):
        self.assertEqual(
            classify("text COMMENT 'DEFAULT a'", "text COMMENT 'DEFAULT b'"),
            {"COMMENT"},
        )

    def test_timestamp_on_update_delta(self):
        self.assertEqual(
            classify("timestamp ON UPDATE CURRENT_TIMESTAMP(6)",
                     "timestamp ON UPDATE CURRENT_TIMESTAMP(3)"),
            {"ON_UPDATE"},
        )

    def test_unparsed_constraint_fails_closed(self):
        self.assertEqual(
            classify("int NOT NULL CHECK (x > 0)",
                     "int NOT NULL CHECK (x > 1)"),
            {"OTHER_OR_UNPARSED"},
        )

    def test_multiple_changes_all_retained(self):
        self.assertEqual(
            classify("varchar(20) NOT NULL DEFAULT 'a' COLLATE abc",
                     "varchar(20) NULL DEFAULT 'b' COLLATE xyz"),
            {"NULLABILITY", "DEFAULT", "COLLATION"},
        )

    def test_no_delta_is_never_reported_as_approved(self):
        self.assertEqual(classify("int NOT NULL", "int NOT NULL"),
                         {"OTHER_OR_UNPARSED"})



class RiskDetailSyntheticTests(unittest.TestCase):
    def test_numeric_default_quotation_is_not_approved(self):
        self.assertEqual(
            module._attribute_detail_categories("int NOT NULL DEFAULT 0",
                                                "int NOT NULL DEFAULT '0'"),
            {"DEFAULT_NUMERIC_QUOTING_UNPROVEN"},
        )

    def test_changed_default_value_is_distinct_from_formatting(self):
        self.assertEqual(
            module._attribute_detail_categories("int DEFAULT 0", "int DEFAULT 1"),
            {"DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_missing_default_is_separate_blocker(self):
        self.assertEqual(
            module._attribute_detail_categories("int NOT NULL DEFAULT 0",
                                                "int NOT NULL"),
            {"DEFAULT_PRESENCE_OR_MULTIPLE"},
        )

    def test_on_update_precision_change_keeps_risk(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "timestamp ON UPDATE CURRENT_TIMESTAMP(6)",
                "timestamp ON UPDATE CURRENT_TIMESTAMP(3)"),
            {"ON_UPDATE_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_on_update_removed_is_separate_blocker(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "timestamp ON UPDATE CURRENT_TIMESTAMP",
                "timestamp"),
            {"ON_UPDATE_PRESENCE_OR_MULTIPLE"},
        )

    def test_unrecognized_sql_change_never_approved(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "int CHECK (x > 0)", "int CHECK (x > 1)"),
            {"UNRECOGNIZED_TOKENS_CHANGED"},
        )

    def test_only_presentation_change_remains_unproven(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "int DEFAULT 0", "int  DEFAULT 0"),
            {"PRESENTATION_OR_CASE_UNPROVEN"},
        )

    def test_literal_sql_keywords_do_not_escape_group(self):
        self.assertEqual(
            module._attribute_detail_categories(
                "text DEFAULT 'ON UPDATE source'",
                "text DEFAULT 'ON UPDATE target'"),
            {"DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_classification_never_executes_sql_or_requires_server(self):
        source="varchar(20) NOT NULL DEFAULT 'source'"
        target="varchar(20) DEFAULT 'target'"
        self.assertEqual(
            module._attribute_detail_categories(source, target),
            {"NULLABILITY_PRESENCE_OR_MULTIPLE",
             "DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"},
        )

    def test_mysql8_to_mariadb_collation_is_not_approved(self):
        self.assertEqual(
            module._collation_risk_class(
                "ENGINE=InnoDB COLLATE=utf8mb4_0900_ai_ci;",
                "ENGINE=InnoDB COLLATE=utf8mb4_uca1400_ai_ci;"),
            "MYSQL0900_TO_UCA1400",
        )

    def test_different_collation_same_charset_still_risky(self):
        self.assertEqual(
            module._collation_risk_class(
                "COLLATE=utf8mb4_general_ci;",
                "COLLATE=utf8mb4_unicode_ci;"),
            "SAME_CHARSET_DIFFERENT_RULE",
        )

    def test_unknown_collation_does_not_become_safe(self):
        self.assertEqual(
            module._collation_risk_class("COLLATE=custom_a", "COLLATE=custom_b"),
            "OTHER_OR_UNPROVEN",
        )

    def test_missing_collation_is_not_approved(self):
        self.assertEqual(
            module._collation_risk_class("ENGINE=InnoDB", "COLLATE=utf8mb4_uca1400_ai_ci"),
            "TARGET_ONLY",
        )

    def test_multiple_collation_values_is_unproven(self):
        self.assertEqual(
            module._collation_risk_class(
                "COLLATE=utf8mb4_general_ci COLLATE=utf8mb4_bin",
                "COLLATE=utf8mb4_unicode_ci"),
            "OTHER_OR_UNPROVEN",
        )


class ClosureEvidenceTests(unittest.TestCase):
    def test_charset_introducer_is_part_of_default(self):
        a = "varchar(20) DEFAULT _utf8mb4'private text'"
        b = "varchar(20) DEFAULT 'private text'"
        self.assertEqual(classify(a,b), {"DEFAULT"})
        self.assertEqual(module._attribute_detail_categories(a,b),
                         {"DEFAULT_LITERAL_INTRODUCER_REQUIRES_CHARSET_PROOF"})

    def test_literal_value_change_not_treated_as_prefix_format(self):
        result=module._attribute_detail_categories(
            "varchar(20) DEFAULT _utf8mb4'old'", "varchar(20) DEFAULT 'new'")
        self.assertEqual(result,{"DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"})

    def test_enum_type_parenthesis_in_literal_not_attribute(self):
        a="enum('a)b','c') DEFAULT 'a)b'"
        b="enum('a)b','c') DEFAULT 'c'"
        self.assertEqual(classify(a,b),{"DEFAULT"})

    def test_timestamp_synonym_and_zero_precision_only(self):
        for b in ("CURRENT_TIMESTAMP()","current_timestamp(0)","NOW()"):
            with self.subTest(b=b):
                self.assertEqual(module._attribute_detail_categories(
                    "timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
                    "timestamp DEFAULT "+b+" ON UPDATE "+b),
                    {"DEFAULT_TIMESTAMP_SYNTAX_ONLY","ON_UPDATE_TIMESTAMP_SYNTAX_ONLY"})

    def test_timestamp_precision_change_and_quoted_function_block(self):
        for b in ("CURRENT_TIMESTAMP(6)","'CURRENT_TIMESTAMP'","UUID()"):
            with self.subTest(b=b):
                self.assertEqual(module._attribute_detail_categories(
                    "timestamp DEFAULT CURRENT_TIMESTAMP", "timestamp DEFAULT "+b),
                    {"DEFAULT_EXPRESSION_OR_LITERAL_CHANGED"})

    def test_nullable_blob_default_null_presentation_only(self):
        self.assertEqual(module._attribute_detail_categories("longblob","longblob DEFAULT NULL"),
                         {"DEFAULT_NULLABLE_LOB_NULL_PRESENTATION"})
        for a in ("text NOT NULL", "timestamp", "text CHECK (x > 0)"):
            self.assertNotIn("DEFAULT_NULLABLE_LOB_NULL_PRESENTATION",
                             module._attribute_detail_categories(a,a+" DEFAULT NULL"))

    def test_missing_values_and_unbalanced_expressions_fail_closed(self):
        for bad in ("int DEFAULT", "int DEFAULT (1", "text DEFAULT 'unterminated"):
            self.assertEqual(module._attribute_detail_categories(bad,"int DEFAULT 0"),
                             {"PARSER_UNPROVEN"})

    def test_hex_bit_and_national_literals_are_not_unknown_tail(self):
        for prefix in ("x", "b", "N"):
            self.assertEqual(classify("text DEFAULT "+prefix+"'00'", "text DEFAULT '00'"),
                             {"DEFAULT"})

    def files(self, source, target):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        a,b=Path(tmp.name)/"source.sql",Path(tmp.name)/"target.sql"
        a.write_text(source); b.write_text(target)
        return a,b

    def ddl(self, attrs="DEFAULT 'old'", typ="varchar(30)", key="PRIMARY KEY (`id`)"):
        return "CREATE TABLE `private_table` (`id` int NOT NULL, `private_field` "+typ+" "+attrs+", "+key+") ENGINE=InnoDB;\n"

    def test_attribute_drift_pk_evidence_does_not_change_strict_gate(self):
        import sql_pk_conflict_evidence as strict
        row="INSERT INTO `private_table` VALUES (1,'secret_value');\n"
        a,b=self.files(self.ddl()+row,self.ddl("DEFAULT 'new'")+row)
        result=module._pk_literal_identity_report(a,b)
        self.assertEqual(result["TABLES_EVALUABLE"],1)
        self.assertEqual(result["SCHEMA_DRIFT_TABLES_STILL_BLOCKED"],1)
        self.assertEqual(result["STATUS"],"LITERAL_EQUAL_NOT_VERIFIED")
        self.assertEqual(strict.diagnostic(a,b)["pk_tables_evaluable"],0)
        for secret in ("private_table","private_field","secret_value"):
            self.assertNotIn(secret,json.dumps(result))

    def test_157_table_scope_with_20_default_differences(self):
        left=[];right=[]
        for i in range(157):
            name="private_table_%03d"%i
            row=("INSERT INTO `"+name+"` VALUES (1,'value');\n")
            left.append(self.ddl().replace("private_table",name)+row)
            right.append(self.ddl("DEFAULT 'new'" if i<20 else "DEFAULT 'old'").replace("private_table",name)+row)
        a,b=self.files("".join(left),"".join(right))
        result=module._pk_literal_identity_report(a,b)
        self.assertEqual((result["TABLES_EXAMINED"],result["TABLES_EVALUABLE"],
                          result["SCHEMA_DRIFT_TABLES_STILL_BLOCKED"],result["IDENTICAL_ROWS"]),
                         (157,157,20,157))

    def test_index_pk_and_type_change_remain_ineligible(self):
        for altered in (self.ddl(typ="varchar(40)"),self.ddl(key="PRIMARY KEY (`private_field`)"),
                        self.ddl().replace("int NOT NULL","int UNSIGNED NOT NULL"),
                        self.ddl(key="PRIMARY KEY (`id`), KEY `extra` (`private_field`)")):
            a,b=self.files(self.ddl(),altered)
            result=module._pk_literal_identity_report(a,b)
            self.assertEqual(result["TABLES_EVALUABLE"],0)
            self.assertEqual(result["STATUS"],"UNPROVEN")

    def test_key_change_and_payload_change_detected_with_attribute_drift(self):
        a,b=self.files(self.ddl()+"INSERT INTO `private_table` VALUES (1,'a'),(2,'b');\n",
                      self.ddl("DEFAULT 'new'")+"INSERT INTO `private_table` VALUES (1,'changed'),(3,'c');\n")
        result=module._pk_literal_identity_report(a,b)
        self.assertEqual(result["STATUS"],"LITERAL_DIFFER")
        self.assertEqual((result["SOURCE_ONLY_KEYS"],result["TARGET_ONLY_KEYS"],result["SAME_KEY_CHANGED_LITERALS"]),(1,1,1))

    def test_duplicate_null_missing_column_and_invalid_dml_fail_closed(self):
        for bad in ("(1,'a'),(1,'a')", "(NULL,'a')", "(1)", "(1,UUID())"):
            a,b=self.files(self.ddl()+"INSERT INTO `private_table` VALUES "+bad+";\n",self.ddl("DEFAULT 'new'"))
            self.assertEqual(module._pk_literal_identity_report(a,b)["STATUS"],"UNPROVEN")

    def test_conditional_ddl_other_alter_is_not_key_toggle(self):
        toggles="/*!40000 ALTER TABLE `private_table` DISABLE KEYS */;\n/*!40000 ALTER TABLE `private_table` ENABLE KEYS */;\n"
        a,b=self.files(self.ddl()+toggles,self.ddl()+toggles+"/*!40000 ALTER TABLE `private_table` DROP COLUMN private_field */;\n")
        out=io.StringIO()
        with contextlib.redirect_stdout(out):module.explain_conditional_ddl(a,b)
        text=out.getvalue()
        self.assertIn("ADVISORY_CONDITIONAL_TARGET_OTHER_DDL_LINES=1",text)
        self.assertIn("ADVISORY_CONDITIONAL_SOURCE_KEY_TOGGLE_PAIRS=1",text)
        self.assertNotIn("private_table",text)
        self.assertNotIn("=PASS",text)
        self.assertIn("ADVISORY_CONDITIONAL_TOGGLE_IDENTITY=UNKNOWN_DDL_PRESENT",text)

    def test_dynamic_shape_redacts_literals_identifiers_and_variables(self):
        shape=module._redacted_branch_shape("'SET @private_var = ''private_value'';'")
        self.assertEqual(shape,"SET+USER_VAR+=+LITERAL+;")
        self.assertNotIn("private",shape)
        shape=module._redacted_branch_shape("'SELECT private_column FROM private_table'")
        self.assertEqual(shape,"SELECT+IDENTIFIER+FROM+IDENTIFIER")

    def test_dynamic_three_group_summary_and_scope_failure_are_redacted(self):
        line="/*!50000 SET @private_stmt = IF(@private_flag, 'SET @private_name = ''private_value''', 'SELECT 1') */;\n"
        for count in (2,3,4):
            a,_=self.files(line*count,"")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                module.explain_quarantined_dynamic(a)
            text=out.getvalue()
            self.assertNotIn("private",text)
            self.assertNotIn("=PASS",text)
            if count==3:
                self.assertIn("ADVISORY_DYNAMIC_3_NO_SHAPE=SELECT+NUMBER",text)
                self.assertIn("ADVISORY_DYNAMIC_EFFECTS=NOT_PROVEN_NO_EXECUTION",text)
            else:self.assertEqual(text,"ADVISORY_DYNAMIC_CLASS=UNPROVEN\n")

    def test_compatibility_mode_does_not_rerun_multisets(self):
        a,b=self.files(self.ddl(),self.ddl())
        with patch.object(module,"explain_row_multisets",side_effect=AssertionError("must not rerun")), contextlib.redirect_stdout(io.StringIO()) as out:
            module.explain_advisory(a,b,compatibility_only=True)
        self.assertIn("ADVISORY_PREVIOUS_ROW_MULTISET_RESULT=NOT_RERUN",out.getvalue())
        self.assertNotIn("=PASS",out.getvalue())

    def test_enum_parameter_after_literal_parenthesis_is_not_attribute(self):
        import sql_diff_evidence as evidence
        left=[];right=[]
        for i in range(157):
            name="private_%03d"%i
            a=self.ddl(typ="enum('a)b','c')").replace("private_table",name)
            b=self.ddl(typ="enum('a)b','d')").replace("private_table",name) if i==0 else a
            left.append(a);right.append(b)
        a,b=self.files("".join(left),"".join(right))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            module.explain_column_change_classes(a,b,evidence)
        self.assertIn("ADVISORY_COLUMN_TYPE_PARAMETER_CHANGED=1",out.getvalue())
        self.assertIn("ADVISORY_COLUMN_ATTRIBUTES_CHANGED=0",out.getvalue())
        self.assertNotIn("private",out.getvalue())

    def test_missing_primary_key_and_reordered_columns_stay_unavailable(self):
        for altered in (self.ddl(key="KEY `secondary` (`id`)"),
                        "CREATE TABLE `private_table` (`private_field` varchar(30), `id` int NOT NULL, PRIMARY KEY (`id`)) ENGINE=InnoDB;\n"):
            a,b=self.files(self.ddl(),altered)
            self.assertEqual(module._pk_literal_identity_report(a,b)["TABLES_UNAVAILABLE"],1)


class ReadOnlyBoundaryTests(unittest.TestCase):
    def test_cli_rejects_other_arguments_before_loading_code(self):
        for args in ([],["--import"],["--read-only-existing-www3-compatibility-closure","--force"]):
            with patch.object(sys,"argv",["probe"]+args), patch.object(module,"load") as load:
                with self.assertRaises(module.Block):module.run()
                load.assert_not_called()

    def test_companion_tamper_blocks_before_import(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"companion.py"
            p.write_text("raise AssertionError('must not execute')\n")
            with patch.object(module,"__file__",str(Path(td)/"probe.py")):
                with self.assertRaisesRegex(module.Block,"PINNED_CODE_DRIFT"):
                    module.load(p.name,"0"*40)

    def test_closure_uses_one_native_export_without_old_full_parity_path(self):
        for status,encoding in (("COMPLETE","VALID"),("EXPORT_REJECTED","VALID"),("COMPLETE","INVALID")):
            with self.subTest(status=status,encoding=encoding), tempfile.TemporaryDirectory() as td:
                marker=Path(td)/"existing-receipt.json"
                marker.write_bytes(b"existing receipt remains unchanged")
                base=SimpleNamespace(
                    RUNTIME=Path(td),DOMAIN="fixture.example",
                    verify_state=Mock(return_value=({"target_server_identity":"target"},"source_db")),
                    verify_current_runtime=Mock(),inspect_existing_site=Mock())
                stage=SimpleNamespace(
                    import_existing_verified_source=Mock(return_value="source-digest"),
                    make_quarantined_sql=Mock(return_value="different-gzip-header"),strict_scope=Mock())
                record={"scratch_database":"p07fixture00000","source_snapshot_sha256":"source-digest",
                        "input_transform_sha256":"original-gzip-header"}
                engine=SimpleNamespace(target_identity=lambda:"target",
                    compare_database_dumps=Mock(side_effect=AssertionError("must not invoke full gate")))
                cloud=SimpleNamespace(export_database=Mock(side_effect=AssertionError("known binary export must not repeat")))
                temporary_directory=tempfile.TemporaryDirectory
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(sys,"argv",["probe","--read-only-existing-www3-compatibility-closure"]))
                    stack.enter_context(patch.object(sys,"path",list(sys.path)))
                    stack.enter_context(patch.dict(sys.modules,{"server_migration_pull":engine,"cloudpanel":cloud}))
                    stack.enter_context(patch.object(module.os,"geteuid",return_value=0))
                    stack.enter_context(patch.object(module.os,"umask"))
                    stack.enter_context(patch.object(module.tempfile,"TemporaryDirectory",
                        side_effect=lambda **kwargs:temporary_directory(prefix=kwargs["prefix"],dir=td)))
                    stack.enter_context(patch.object(module,"load",side_effect=[base,stage]))
                    stack.enter_context(patch.object(module,"load_receipt",return_value=record))
                    stack.enter_context(patch.object(module,"count_scratch_metadata",return_value=(157,1848)))
                    stack.enter_context(patch.object(module,"explain_quarantined_dynamic"))
                    stack.enter_context(patch.object(module,"prove_transformed_copy_without_compressed_header"))
                    native=stack.enter_context(patch.object(module,"native_readonly_scratch_dump",return_value=status))
                    stack.enter_context(patch.object(module,"inspect_target_export_bytes",return_value=("PASS",encoding,100)))
                    advisory=stack.enter_context(patch.object(module,"explain_advisory"))
                    output=stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if status=="COMPLETE" and encoding=="VALID":
                        self.assertEqual(module.run(),13)
                        self.assertTrue(advisory.call_args.kwargs["compatibility_only"])
                        self.assertIn("SCRATCH_STATIC_COPY_PARITY=NOT_PROVEN",output.getvalue())
                    else:
                        with self.assertRaises(module.Block):module.run()
                        advisory.assert_not_called()
                    native.assert_called_once()
                    cloud.export_database.assert_not_called()
                    engine.compare_database_dumps.assert_not_called()
                    self.assertIn("CUTOVER_ALLOWED=NO",output.getvalue())
                    self.assertEqual(marker.read_bytes(),b"existing receipt remains unchanged")


if __name__ == "__main__":
    unittest.main()

