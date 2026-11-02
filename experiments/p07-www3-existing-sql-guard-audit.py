#!/usr/bin/env python3
"""P07 www3: classify the failing side-effect guard on EXISTING source SQL.

No database modifications, source export, deletion, migration retry or cutover.
Never print SQL text, row data, table names, source host or credentials.
Only bounded fixed categories and numbers may leave this script.
"""
from __future__ import annotations
import hashlib,importlib.util,os,sys,tempfile
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
    except (Block,OSError,ValueError,RuntimeError,UnicodeError) as exc:
        print("BLOCKED="+(str(exc) if type(exc) is Block else type(exc).__name__),flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
