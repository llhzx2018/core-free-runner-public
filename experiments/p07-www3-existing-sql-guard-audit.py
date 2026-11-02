#!/usr/bin/env python3
"""P07 www3: classify the failing side-effect guard on EXISTING source SQL.

No database modifications, source export, deletion, migration retry or cutover.
Never print SQL text, row data, table names, source host or credentials.
Only bounded fixed categories and numbers may leave this script.
"""
from __future__ import annotations
import gzip,hashlib,importlib.util,os,re,sys,tempfile
from pathlib import Path

HELPER=Path(__file__).with_name("p07-www3-candidate-schema-probe.py")
STAGE=Path(__file__).with_name("p07-www3-isolated-stage.py")
HELPER_BLOB="8f640e7505c5b49ad5a7574d82c0030eb6e7b884"
STAGE_BLOB="d12659a4ba4f3dccf90a63bc656c02c357f7bfbf"

class Block(Exception): pass
def need(ok,reason):
    if not ok: raise Block(reason)
def module_from_pinned(file,expected,label):
    need(file.is_file() and not file.is_symlink(),"PINNED_"+label+"_MISSING")
    data=file.read_bytes()
    actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    need(actual==expected,"PINNED_"+label+"_DRIFT")
    spec=importlib.util.spec_from_file_location("p07_readonly_"+label,file)
    need(spec is not None and spec.loader is not None,"PINNED_"+label+"_UNLOADABLE")
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def bounded_dynamic_flow_shape(path, verifier):
    """Fixed-only source grammar evidence; no SQL, table, variable, or digest."""
    summary=verifier.sql_dynamic_guard_flow_diagnostic(path)
    pattern=(r"^SQL_GUARD_FLOW_V1 "
             r"(?:probe|assignment|safe_assignment|prepare|execute|deallocate|"
             r"unknown_set|unknown_control)=[0-9]{1,8}(?: "
             r"(?:probe|assignment|safe_assignment|prepare|execute|deallocate|"
             r"unknown_set|unknown_control)=[0-9]{1,8}){7} "
             r"recognized=[0-9]{1,8} outcome="
             r"(?:UNKNOWN_CONTROL_GRAMMAR|UNSAFE_BRANCH|"
             r"NO_COMPLETE_DYNAMIC_GROUP|UNBALANCED_STAGES|"
             r"SEQUENCE_REJECTED|RECOGNIZED)$")
    need(isinstance(summary,str) and len(summary)<512
         and re.fullmatch(pattern,summary),
         "SOURCE_GUARD_FLOW_FORMAT_UNPROVEN")
    totals={name:0 for name in ("RAW","MYSQL_4_TO_7","MYSQL_8_PLUS",
                                "MARIADB","UNKNOWN_VERSION")}
    probes={"MYSQL_8_PLUS":0,"MYSQL_4_TO_7":0,"MARIADB":0,"RAW":0}
    assigns=dict(probes)
    header=re.compile(r"^/\*(?P<flavor>!|M!)(?P<version>[0-9]{5,6})\s+"
                      r"(?P<body>.+?)\s*\*/;?$",re.I)
    first=re.compile(r"^(?P<verb>PREPARE|EXECUTE|DEALLOCATE)"
                     r"(?:\s+|$)",re.I)
    read=re.compile(r"^(?:SELECT\s+COUNT\s*\(\s*\*\s*\)\s+INTO|"
                    r"SET\s+@[a-z_])",re.I)
    try:
        with gzip.open(path,"rt",encoding="utf-8",errors="strict") as dump:
            for raw in dump:
                line=raw.strip()
                matched=header.fullmatch(line)
                body=matched.group("body") if matched else line
                version=int(matched.group("version")) if matched else None
                flavor=matched.group("flavor") if matched else ""
                if flavor=="M!":
                    kind="MARIADB"
                elif version is None:
                    kind="RAW"
                elif 40000<=version<80000:
                    kind="MYSQL_4_TO_7"
                elif 80000<=version<=999999:
                    kind="MYSQL_8_PLUS"
                else:
                    kind="UNKNOWN_VERSION"
                if first.match(body):
                    totals[kind]+=1
                if read.match(body):
                    if body.upper().startswith("SELECT"):
                        probes[kind]+=1
                    elif body.upper().startswith("SET"):
                        assigns[kind]+=1
    except (OSError,EOFError,UnicodeError):
        raise Block("SOURCE_GUARD_FLOW_SCAN_UNAVAILABLE") from None
    return summary, totals, probes, assigns


def bounded_branch_proof(path, verifier, evidence):
    """Use exact release113 grammar; print only fixed unsafe categories.

    The full branch SQL strings and conditional variable/table names remain
    entirely in the local private process. No statement is ever authorized
    by this diagnostic, including otherwise harmless SET/SELECT statements.
    """
    expected=evidence.dynamic_guard_syntax_counts(path)
    permitted_classes=set(evidence._UNSAFE_BRANCH_CLASSES)
    permitted_reasons={
        "CONTROL_OR_MULTISTATEMENT","GLOBAL_OR_PERSIST",
        "SIDE_EFFECT_OR_CONTROL_KEYWORD","SESSION_GRAMMAR_UNPROVEN",
        "READ_GRAMMAR_UNPROVEN","UNKNOWN_GRAMMAR"
    }
    findings=[]
    assignments=0
    try:
        with gzip.open(path,"rt",encoding="utf-8",errors="strict") as dump:
            for lineno,raw in enumerate(dump,1):
                match=evidence._GUARD_RE.fullmatch(raw.strip())
                if not match or not 40000<=int(match.group(1))<=89999:
                    continue
                body=re.sub(r"\s+"," ",match.group(2).strip())
                assign=verifier._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body)
                if not assign:
                    continue
                assignments+=1
                for branch in ("yes","no"):
                    literal=assign.group(branch)
                    if verifier._cross_engine_safe_dynamic_branch(literal):
                        continue
                    kind=evidence._unsafe_branch_category(literal)
                    reason=evidence._unsafe_branch_reason(literal)
                    need(kind in permitted_classes and reason in permitted_reasons,
                         "BRANCH_CLASS_OUT_OF_CONTRACT")
                    need(len(findings)<12 and lineno<1000000000,
                         "BRANCH_EVIDENCE_LIMIT_EXCEEDED")
                    findings.append((lineno,branch.upper(),kind,reason))
    except (OSError,EOFError,UnicodeError):
        raise Block("SOURCE_DYNAMIC_BRANCH_UNAVAILABLE") from None
    need(assignments==expected["recognized_safe"]+expected["recognized_unsafe"]
         and len(findings)==expected["unsafe_yes_branches"]+
                            expected["unsafe_no_branches"],
         "BRANCH_CLASSIFICATION_MISMATCH")
    need(expected["recognized_unsafe"]>0,"NO_UNSAFE_DYNAMIC_BRANCH_REPRODUCED")
    return expected,findings


def execute():
    need(os.geteuid()==0 and sys.argv[1:]==["--audit-existing-www3-side-effects-only"],
         "EXPLICIT_READONLY_GUARD_AUDIT_REQUIRED")
    base=module_from_pinned(HELPER,HELPER_BLOB,"HELPER")
    stage=module_from_pinned(STAGE,STAGE_BLOB,"STAGE")
    tail,db=base.verify_state()
    base.verify_current_runtime()
    sys.path.insert(0,str(base.RUNTIME/"lib"))
    import server_migration_pull as engine
    import verify
    need(engine.target_identity()==tail["target_server_identity"],
         "TARGET_IDENTITY_CHANGED")
    base.inspect_existing_site(base.DOMAIN,db)
    print("MODE=WWW3_EXISTING_SQL_READ_ONLY_GUARD_AUDIT",flush=True)
    print("SOURCE_NEW_EXPORT=NO",flush=True)
    print("SOURCE_TEMP_CLEANUP=NOT_ATTEMPTED_RETAINED",flush=True)
    print("CP2_DATABASE_CREATE_IMPORT_MODIFY=NO",flush=True)
    print("MIGRATION_STATE_MUTATED=NO",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    with tempfile.TemporaryDirectory(prefix="p07-www3-existing-guard-audit-",dir="/root") as folder:
        sql=Path(folder)/"source.sql.gz"
        stage.import_existing_verified_source(engine,tail,db,base,sql)
        need(base.strict_hex_export_utf8(sql),"SOURCE_UTF8_UNPROVEN")
        # This diagnostic must show only the reasons for the EXACT guard
        # that blocked the owner's earlier attempt. It is not an import gate.
        results=[]
        default=stage.standalone_sql_unproven_side_effects(sql,verify)
        analyzed=stage.standalone_sql_unproven_side_effects(
            sql,verify,findings=results
        )
        need(default==analyzed and analyzed and results,
             "SIDE_EFFECT_AUDIT_INCONSISTENT_OR_NO_LONGER_REPRODUCIBLE")
        summary,controls,probes,assignments=bounded_dynamic_flow_shape(
            sql,verify
        )
        print(summary,flush=True)
        for label in ("RAW","MYSQL_4_TO_7","MYSQL_8_PLUS","MARIADB",
                      "UNKNOWN_VERSION"):
            print("DYNAMIC_CONTROL_"+label+"="+str(controls[label]),flush=True)
        for label in ("RAW","MYSQL_4_TO_7","MYSQL_8_PLUS","MARIADB"):
            print("DYNAMIC_PROBE_"+label+"="+str(probes[label]),flush=True)
            print("DYNAMIC_ASSIGN_"+label+"="+str(assignments[label]),flush=True)
        import sql_diff_evidence
        evidence,branch_findings=bounded_branch_proof(
            sql,verify,sql_diff_evidence
        )
        print("DYNAMIC_UNSAFE_ASSIGNMENTS="+str(evidence["recognized_unsafe"]),flush=True)
        print("DYNAMIC_UNSAFE_YES="+str(evidence["unsafe_yes_branches"]),flush=True)
        print("DYNAMIC_UNSAFE_NO="+str(evidence["unsafe_no_branches"]),flush=True)
        print("DYNAMIC_UNSAFE_BRANCH_COUNT="+str(len(branch_findings)),flush=True)
        for i,(line,side,kind,reason) in enumerate(branch_findings,1):
            print("DYNAMIC_BRANCH_"+str(i)+"_LINE="+str(line),flush=True)
            print("DYNAMIC_BRANCH_"+str(i)+"_SIDE="+side,flush=True)
            print("DYNAMIC_BRANCH_"+str(i)+"_CLASS="+kind,flush=True)
            print("DYNAMIC_BRANCH_"+str(i)+"_REASON="+reason,flush=True)
        print("SIDE_EFFECT_GUARD=BLOCKED_REPRODUCED",flush=True)
        print("SIDE_EFFECT_FINDINGS_REPORTED="+str(len(results)),flush=True)
        for index,(reason,line_number) in enumerate(results,1):
            need(isinstance(reason,str) and reason.isupper() and
                 reason.replace("_","").isalpha() and
                 isinstance(line_number,int) and 1<=line_number<1000000000,
                 "DIAGNOSTIC_RESULT_UNSAFE")
            print("GUARD_FINDING_"+str(index)+"="+reason,flush=True)
            print("GUARD_LINE_"+str(index)+"="+str(line_number),flush=True)
    print("TARGET_DATABASE_WRITES=NONE",flush=True)
    return 0

if __name__=="__main__":
    try:raise SystemExit(execute())
    except Exception as exc:
        # A remote error or an unanticipated client exception must never
        # dump an SQL-bearing traceback, host or filesystem path.
        fixed=str(exc) if type(exc) is Block else "READONLY_GUARD_AUDIT_UNPROVEN"
        print("BLOCKED="+fixed,flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
