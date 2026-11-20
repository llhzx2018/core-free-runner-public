#!/usr/bin/env python3
"""P07 unzip.kewaro.com: compare wp_options keyed by option_name, read-only.

Never prints option_name or option_value, credentials, IDs or database names.
Only anonymized option fingerprints cross SSH. An advisory difference is never
permission to discard option rows, promote stage, import, restore or cut over.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
DOMAIN = "unzip.kewaro.com"
BASE_FILE = "p07-two-pending-live-db-worker.py"
BASE_BLOB = "e1983a25dff3adca390b579a987345056ec8eb17"
PAIR_FILE = "p07-two-pending-live-db-parity.py"
PAIR_BLOB = "a7e4f2e664e4ecaea33d8a285a9ac072de19140a"
CATEGORIES = ("TRANSIENT", "RUNTIME", "CORE_CONFIG", "OTHER")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
DB_NAME = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")

class Block(RuntimeError):
    pass

def need(ok, reason):
    if not ok:
        raise Block(reason)

def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def checked_file(filename, expected):
    path = HERE / filename
    need(path.is_file() and not path.is_symlink(), "PINNED_COMPANION_UNAVAILABLE")
    need(blob(path.read_bytes()) == expected, "PINNED_COMPANION_CHANGED")
    return path

def load_base():
    try:
        import p07_options_base as base
        return base
    except ImportError:
        path = checked_file(BASE_FILE, BASE_BLOB)
        spec = importlib.util.spec_from_file_location("p07_options_base", path)
        need(spec is not None and spec.loader is not None, "BASE_IMPORT_UNAVAILABLE")
        base = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(base)
        return base

def category(name):
    if name.startswith((b"_transient_", b"_site_transient_")):
        return "TRANSIENT"
    if name in (b"cron", b"rewrite_rules", b"recently_edited",
                b"recently_activated", b"update_core", b"update_plugins",
                b"update_themes"):
        return "RUNTIME"
    if name in (b"siteurl", b"home", b"active_plugins", b"template",
                b"stylesheet", b"permalink_structure", b"users_can_register",
                b"default_role", b"blog_public"):
        return "CORE_CONFIG"
    return "OTHER"

def option_map(raw):
    need(isinstance(raw, bytes) and len(raw) <= 16 * 1024 * 1024,
         "OPTION_STREAM_LIMIT")
    result = {}
    for line in raw.splitlines():
        parts = line.split(b"\t")
        need(len(parts) == 4, "OPTION_ROW_FORMAT")
        name_hex, id_text, value_hex, autoload_hex = parts
        need(0 < len(name_hex) <= 2048 and len(name_hex) % 2 == 0
             and re.fullmatch(rb"[0-9A-Fa-f]+", name_hex) is not None
             and re.fullmatch(rb"[0-9]{1,20}", id_text) is not None,
             "OPTION_IDENTITY_FORMAT")
        name = bytes.fromhex(name_hex.decode("ascii"))
        need(name and b"\x00" not in name, "OPTION_NAME_UNVERIFIED")
        def field(code):
            need(code == b"N" or (code.startswith(b"V") and
                 (len(code) - 1) % 2 == 0 and
                 re.fullmatch(rb"[0-9A-Fa-f]*", code[1:]) is not None),
                 "OPTION_VALUE_ENCODING")
            return hashlib.sha256(code[:1] + (
                bytes.fromhex(code[1:].decode("ascii"))
                if code[:1] == b"V" else b""
            )).hexdigest()
        key = hashlib.sha256(name).hexdigest()
        need(key not in result, "OPTION_DUPLICATE_NAME")
        result[key] = [
            hashlib.sha256(str(int(id_text)).encode("ascii")).hexdigest(),
            field(value_hex),
            field(autoload_hex),
            category(name)
        ]
        need(len(result) <= 10000, "OPTION_ROW_COUNT_LIMIT")
    need(result, "OPTION_EMPTY_OR_UNREADABLE")
    return result

def worker(mode, database):
    need(os.geteuid() == 0 and mode in ("SOURCE", "TARGET")
         and isinstance(database, str)
         and DB_NAME.fullmatch(database) is not None, "WORKER_SCOPE_INVALID")
    base = load_base()
    host, port, user, password = (base.source_auth(DOMAIN, database)
                                   if mode == "SOURCE" else
                                   base.target_auth(DOMAIN, database))
    cli = shutil.which("mariadb") or shutil.which("mysql")
    timeout_binary = shutil.which("timeout")
    need(cli is not None and timeout_binary is not None,
         "SQL_CLIENT_UNAVAILABLE")
    with base.memory_file("p07-options-client") as config, \
         base.memory_file("p07-options-readonly-query") as query:
        esc = lambda v: v.replace("\\", "\\\\").replace('"', '\\"')
        config.write(('[client]\nuser="' + esc(user) + '"\npassword="' +
                      esc(password) + '"\n').encode("utf-8"))
        config.flush()
        config.seek(0)
        ident = chr(96) + database + chr(96) + "." + chr(96) + "wp_options" + chr(96)
        sql = (
            "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;\n"
            "SELECT HEX(CAST(option_name AS BINARY)), "
            "CAST(option_id AS CHAR), "
            "IF(option_value IS NULL,'N',CONCAT('V',HEX(CAST(option_value AS BINARY)))), "
            "IF(autoload IS NULL,'N',CONCAT('V',HEX(CAST(autoload AS BINARY)))) "
            "FROM " + ident + ";\nROLLBACK;\n"
        )
        query.write(sql.encode("ascii"))
        query.flush()
        query.seek(0)
        env = {k:v for k,v in os.environ.items()
               if k not in ("MYSQL_PWD", "MYSQL_TEST_LOGIN_FILE", "MYSQL_HISTFILE")}
        try:
            proc = subprocess.run([
                timeout_binary, "240", cli,
                "--defaults-file=/proc/self/fd/" + str(config.fileno()),
                "--protocol=tcp", "--host=" + host, "--port=" + str(port),
                "--batch", "--raw", "--skip-column-names",
                "--default-character-set=utf8mb4"
            ], stdin=query, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                pass_fds=(config.fileno(),), env=env, check=False, timeout=250)
        except (OSError, subprocess.SubprocessError):
            raise Block("OPTIONS_READONLY_QUERY_UNAVAILABLE") from None
        need(proc.returncode == 0, "OPTIONS_READONLY_QUERY_FAILED")
        rows = option_map(proc.stdout)
    print(json.dumps({
        "mode":mode, "domain":DOMAIN, "table":"wp_options",
        "transaction":"READ_ONLY", "rows":len(rows),
        "options":rows, "final_snapshot_proof":False
    }, sort_keys=True, separators=(",",":")), flush=True)

def parse(text, mode):
    need(isinstance(text, str) and 0 < len(text) <= 4 * 1024 * 1024,
         "OPTIONS_WORKER_OUTPUT_INVALID")
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        raise Block("OPTIONS_WORKER_JSON_INVALID") from None
    need(type(data) is dict and set(data)=={
         "mode","domain","table","transaction","rows","options","final_snapshot_proof"
    } and data["mode"] == mode and data["domain"] == DOMAIN
         and data["table"] == "wp_options" and data["transaction"] == "READ_ONLY"
         and data["final_snapshot_proof"] is False, "OPTIONS_WORKER_IDENTITY_INVALID")
    rows = data["options"]
    need(type(rows) is dict and type(data["rows"]) is int and
         len(rows) == data["rows"] and 0 < len(rows) <= 10000,
         "OPTIONS_WORKER_ROW_COUNT_INVALID")
    for key, value in rows.items():
        need(type(key) is str and SHA256.fullmatch(key) is not None
             and type(value) is list and len(value) == 4
             and all(type(x) is str and SHA256.fullmatch(x) is not None
                     for x in value[:3])
             and value[3] in CATEGORIES, "OPTIONS_WORKER_ROW_INVALID")
    return rows

def compare(source, target):
    common = set(source) & set(target)
    only_src, only_dst = set(source)-set(target), set(target)-set(source)
    keys = only_src | only_dst | {
        key for key in common if source[key] != target[key]
    }
    group = Counter((source.get(k) or target.get(k))[3] for k in keys)
    id_diff = sum(source[k][0] != target[k][0] for k in common)
    value_diff = sum(source[k][1] != target[k][1] for k in common)
    autoload_diff = sum(source[k][2] != target[k][2] for k in common)
    need(all(source[k][3] == target[k][3] for k in common),
         "OPTIONS_CATEGORY_DRIFT")
    conclusion = (
        "MATCH_ADVISORY_ONLY" if not keys else
        "TRANSIENT_ONLY_DIFFER_ADVISORY" if group["TRANSIENT"] == len(keys) else
        "NON_TRANSIENT_DIFFER_ADVISORY"
    )
    return {
        "SOURCE_OPTION_ROWS":len(source),
        "TARGET_OPTION_ROWS":len(target),
        "ONLY_SOURCE_OPTION_NAMES":len(only_src),
        "ONLY_TARGET_OPTION_NAMES":len(only_dst),
        "SAME_NAME_ID_DIFFERENCES":id_diff,
        "SAME_NAME_VALUE_DIFFERENCES":value_diff,
        "SAME_NAME_AUTOLOAD_DIFFERENCES":autoload_diff,
        "TOTAL_CHANGED_OPTION_NAMES":len(keys),
        "CHANGED_NAMES_BY_CLASS":json.dumps(
            {k:group[k] for k in CATEGORIES}, sort_keys=True,
            separators=(",",":")
        ),
        "OPTION_NAME_KEYED_PARITY":conclusion
    }

def main():
    need(os.geteuid() == 0, "ROOT_REQUIRED")
    args = sys.argv[1:]
    if len(args) == 2 and args[0] in ("--worker-source","--worker-target"):
        worker("SOURCE" if args[0] == "--worker-source" else "TARGET",args[1])
        return 0
    need(args == ["--classify-current-unzip-options-read-only"],
         "EXPLICIT_SINGLE_SITE_READONLY_FLAG_REQUIRED")
    checked_file(BASE_FILE, BASE_BLOB)
    pair_path = checked_file(PAIR_FILE, PAIR_BLOB)
    spec = importlib.util.spec_from_file_location("p07_unzip_pair",pair_path)
    need(spec is not None and spec.loader is not None, "PARITY_IMPORT_UNAVAILABLE")
    pair = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pair)
    pair.verify_file()
    engine=Path("/opt/vf-server-ops/lib/server_migration_pull.py")
    need(engine.is_file() and pair.gitblob(engine.read_bytes())==pair.ENGINE_BLOB,
         "RELEASE113_ENGINE_CHANGED")
    try:
        version = subprocess.run(["vfops","--build-id"],capture_output=True,
                                 text=True,timeout=20,check=False)
    except (OSError,subprocess.SubprocessError):
        raise Block("INSTALLED_RUNTIME_UNAVAILABLE") from None
    need(version.returncode == 0 and version.stdout.strip() == "0.1.0-release113",
         "RELEASE113_RUNTIME_REQUIRED")
    sys.path.insert(0, "/opt/vf-server-ops/lib")
    import server_migration_pull as migration
    import inventory
    state,source_db,target_db,remote_runtime=pair.preflight(
        migration,inventory,DOMAIN,pair.CURRENT_CHILD,9,6,12)
    need(target_db is not None,"TARGET_DB_NOT_REGISTERED")
    print("PROBE=P07_UNZIP_WP_OPTIONS_KEYED_READONLY",flush=True)
    print("SITE=unzip.kewaro.com",flush=True)
    try:
        local=subprocess.run(["python3","-B",str(Path(__file__)),"--worker-target",target_db],
              stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
              timeout=300,check=False,text=True,
              env={**os.environ,"PYTHONPATH":"/opt/vf-server-ops/lib",
                   "PYTHONDONTWRITEBYTECODE":"1"})
    except (OSError,subprocess.SubprocessError):
        raise Block("LOCAL_OPTIONS_WORKER_UNAVAILABLE") from None
    need(local.returncode == 0,"LOCAL_OPTIONS_WORKER_FAILED")
    target=parse(local.stdout,"TARGET")
    base_code=(HERE/BASE_FILE).read_text(encoding="utf8")
    script_code=Path(__file__).read_text(encoding="utf8")
    bootstrap=(
        "import sys,types\n"
        "b=types.ModuleType('p07_options_base')\n"
        "exec("+repr(base_code)+",b.__dict__)\n"
        "sys.modules['p07_options_base']=b\n"
        "ns={'__name__':'__main__','__file__':'p07-unzip-options-keyed-readonly.py'}\n"
        "exec("+repr(script_code)+",ns)\n"
    )
    command=shlex.join(["env","PYTHONDONTWRITEBYTECODE=1",
        "PYTHONPATH="+remote_runtime+"/lib","python3","-B","-c",
        bootstrap,"--worker-source",source_db])
    try:
        remote=migration.source_remote(state["source"],command,
                                        timeout=300,check=False)
    except Exception:
        raise Block("SOURCE_OPTIONS_READONLY_WORKER_UNAVAILABLE") from None
    need(remote.returncode == 0,"SOURCE_OPTIONS_READONLY_WORKER_FAILED")
    source=parse(remote.stdout,"SOURCE")
    for key,value in compare(source,target).items():
        print(str(key)+"="+str(value),flush=True)
    print("NOT_SIMULTANEOUS_SOURCE_TARGET_SNAPSHOTS=YES",flush=True)
    print("ORIGINAL_SQL_EXPORT_SNAPSHOT_PARITY=NOT_VERIFIED",flush=True)
    print("OLD_VPS_DATABASE_WRITES=NONE",flush=True)
    print("CP2_DATABASE_WRITES=NONE",flush=True)
    print("MIGRATION_STATE_WRITES=NONE",flush=True)
    print("CUTOVER_ALLOWED=NO",flush=True)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Block,Exception) as exc:
        # Public output must contain a fixed reason, never SQL, passwords or row content.
        reason=str(exc) if isinstance(exc,Block) else "OPTIONS_UNVERIFIED_RUNTIME"
        print("BLOCKED="+reason,flush=True)
        print("CUTOVER_ALLOWED=NO",flush=True)
        raise SystemExit(13) from None
