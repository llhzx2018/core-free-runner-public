"""Real MySQL 8.4 <-> MariaDB 11.8 *synthetic-only* restore drill.

Only runs with the exact opt-in environment and local test containers. Never
uses any P07 migration state, CloudPanel credentials, remote SSH or production
databases. Each side is dumped with the real engine client and restored into
fresh, isolated scratch databases. A green CI result is *not* a restore proof
for either real VPS, a verified live snapshot, or a migration PASS gate.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import migration_conflict_recovery

PREFIX = "vf_p07_ci_"  # no other schema can be targeted
PORTS = {"mysql": 3307, "mariadb": 3308}
CLIENT = "mariadb"
DUMP = "mariadb-dump"


def _enabled() -> None:
    if os.getenv("P07_SYNTHETIC_DB_RESTORE_ONLY") != "1":
        raise RuntimeError("SYNTHETIC_RESTORE_ENV_NOT_CONFIRMED")
    if os.getenv("P07_SYNTHETIC_DB_HOST") != "127.0.0.1":
        raise RuntimeError("RESTORE_MUST_USE_LOCAL_TEST_SERVICES")
    for key in ("P07_SYNTHETIC_MYSQL_PASSWORD", "P07_SYNTHETIC_MARIADB_PASSWORD"):
        if not os.getenv(key):
            raise RuntimeError("SYNTHETIC_SERVICE_CREDENTIALS_NOT_CONFIGURED")


def _env(engine: str) -> dict[str, str]:
    _enabled()
    assert engine in PORTS
    env = dict(os.environ)
    env["MYSQL_PWD"] = os.environ[
        "P07_SYNTHETIC_MYSQL_PASSWORD" if engine == "mysql"
        else "P07_SYNTHETIC_MARIADB_PASSWORD"
    ]
    return env


def _cmd(engine: str, executable: str, *rest: str) -> list[str]:
    if engine not in PORTS or executable not in (CLIENT, DUMP):
        raise RuntimeError("NON_SYNTHETIC_COMMAND_REFUSED")
    return [
        executable, "--no-defaults", "--protocol=TCP", "--host=127.0.0.1",
        f"--port={PORTS[engine]}", "--user=root",
        "--default-character-set=utf8mb4", *rest,
    ]


def _run(engine: str, sql: str, *, database: str | None = None) -> str:
    if database is not None and not re.fullmatch(PREFIX + r"[a-z_]+", database):
        raise RuntimeError("NON_SYNTHETIC_DATABASE_REFUSED")
    args = _cmd(engine, CLIENT, "--batch", "--raw", "--skip-column-names")
    if database:
        args.append(database)
    result = subprocess.run(
        args, input=sql, text=True, capture_output=True,
        env=_env(engine), check=False, timeout=60,
    )
    if result.returncode:
        # Do not print database SQL or server stdout/stderr.
        raise RuntimeError("SYNTHETIC_MYSQL_OPERATION_FAILED")
    return result.stdout.strip()


def _sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _create(engine: str, name: str) -> None:
    _run(engine, f"CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")


def _data_sql(side: str) -> str:
    rows = []
    for identity in range(1, 197):
        text = "你好🌎" if identity == 1 else f"common_{identity:03d}"
        rows.append((identity, text, "shared"))
    for identity in range(197, 202):
        rows.append((identity, f"{side}_edited_{identity}", "conflict"))
    if side == "source":
        rows += [(identity, f"source_{identity}", "preserve") for identity in range(202, 205)]
    else:
        rows += [(identity, f"target_{identity}", "preserve") for identity in range(205, 210)]
    body = [
        "CREATE TABLE vf_rows (id INT NOT NULL, payload VARCHAR(80) NOT NULL,"
        " tag VARCHAR(80) NOT NULL, PRIMARY KEY (id)) ENGINE=InnoDB"
        " DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    ]
    for identity, payload, tag in rows:
        body.append(
            f"INSERT INTO vf_rows VALUES ({identity},"
            f"{_sql_quote(payload)},{_sql_quote(tag)});"
        )
    return "\n".join(body) + "\n"


def _rows(engine: str, db: str) -> dict[int, tuple[str, str]]:
    lines = _run(engine, "SELECT id,HEX(payload),HEX(tag) FROM vf_rows ORDER BY id;",database=db)
    output = {}
    for line in lines.splitlines():
        ident, payload, tag = line.split("\t")
        output[int(ident)] = (payload, tag)
    return output


def _dump(engine: str, db: str) -> bytes:
    if not re.fullmatch(PREFIX + r"[a-z_]+", db):
        raise RuntimeError("NON_SYNTHETIC_DATABASE_REFUSED")
    args = _cmd(
        engine, DUMP, "--single-transaction", "--skip-lock-tables",
        "--skip-comments", "--skip-dump-date", "--skip-add-drop-table",
        "--skip-extended-insert", "--hex-blob", "--quick",
        "--no-create-db", db,
    )
    proc = subprocess.run(
        args, capture_output=True, env=_env(engine),
        check=False, timeout=120,
    )
    if proc.returncode or not proc.stdout or b"CREATE TABLE" not in proc.stdout:
        raise RuntimeError("SYNTHETIC_BACKUP_EXPORT_UNUSABLE")
    return proc.stdout


def _restore(engine: str, db: str, dump: bytes, expected_sha256: str) -> None:
    if not re.fullmatch(PREFIX + r"[a-z_]+", db):
        raise RuntimeError("NON_SYNTHETIC_DATABASE_REFUSED")
    if hashlib.sha256(dump).hexdigest() != expected_sha256:
        raise RuntimeError("BACKUP_CHECKSUM_MISMATCH")
    proc = subprocess.run(
        _cmd(engine, CLIENT, db), input=dump, capture_output=True,
        env=_env(engine), check=False, timeout=120,
    )
    if proc.returncode:
        raise RuntimeError("SYNTHETIC_ISOLATED_RESTORE_FAILED")


class RealDualEngineSyntheticRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _enabled()
        v_mysql = _run("mysql", "SELECT VERSION();")
        v_mariadb = _run("mariadb", "SELECT VERSION();")
        if not v_mysql.startswith("8.4.") or not v_mariadb.startswith("11.8."):
            raise RuntimeError("EXACT_MYSQL_84_MARIADB_118_REQUIRED")
        cls.root = tempfile.TemporaryDirectory(prefix="vfops-synthetic-recovery-")
        cls.snapshots: dict[str, bytes] = {}
        cls.before: dict[str, dict[int, tuple[str,str]]] = {}
        for engine, side in (("mysql", "source"), ("mariadb", "target")):
            db = PREFIX + side
            _create(engine, db)
            _run(engine, _data_sql(side), database=db)
            cls.before[side] = _rows(engine, db)
            blob = _dump(engine, db)
            outfile = Path(cls.root.name) / f"{side}.sql"
            outfile.write_bytes(blob)
            outfile.chmod(0o600)
            cls.snapshots[side] = blob
            if outfile.read_bytes() != blob or outfile.stat().st_mode & 0o077:
                raise RuntimeError("BACKUP_NOT_PRIVATE_OR_IMMUTABLE")

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "root"):
            cls.root.cleanup()

    def test_exact_primary_key_conflict_counts_without_merge(self) -> None:
        a, b = self.before["source"], self.before["target"]
        common = a.keys() & b.keys()
        source_only = a.keys() - b.keys()
        target_only = b.keys() - a.keys()
        changed = {key for key in common if a[key] != b[key]}
        self.assertEqual((len(a),len(b)), (204,206))
        self.assertEqual((
            len(source_only),len(target_only),len(changed),
            len(common)-len(changed),
        ), (3,5,5,196))
        self.assertEqual(a[1],b[1])  # Unicode across two engines

    def test_both_independent_engine_restore_drills(self) -> None:
        for side, engine in (("source","mysql"),("target","mariadb")):
            with self.subTest(side=side):
                backup = self.snapshots[side]
                sha = hashlib.sha256(backup).hexdigest()
                isolated_db = PREFIX + side + "_restore"
                _create(engine, isolated_db)
                _restore(engine, isolated_db, backup, sha)
                self.assertEqual(_rows(engine,isolated_db), self.before[side])
                self.assertEqual(_rows(engine,PREFIX+side), self.before[side])
                self.assertEqual(hashlib.sha256(backup).hexdigest(),sha)

    def test_portable_cross_engine_backup_restores_both_directions(self) -> None:
        for side, receiver in (("source","mariadb"),("target","mysql")):
            with self.subTest(direction=side+"_to_"+receiver):
                blob = self.snapshots[side]
                db=PREFIX+side+"_cross"
                _create(receiver,db)
                _restore(receiver,db,blob,hashlib.sha256(blob).hexdigest())
                self.assertEqual(_rows(receiver,db),self.before[side])
        self.assertEqual(_rows("mysql",PREFIX+"source"),self.before["source"])
        self.assertEqual(_rows("mariadb",PREFIX+"target"),self.before["target"])

    def test_checksum_tamper_fails_before_import(self) -> None:
        blob=self.snapshots["source"]
        mismatch=blob+b"\n-- synthetic-tamper"
        with self.assertRaisesRegex(RuntimeError,"BACKUP_CHECKSUM_MISMATCH"):
            _restore("mysql",PREFIX+"source",mismatch,hashlib.sha256(blob).hexdigest())
        self.assertEqual(_rows("mysql",PREFIX+"source"),self.before["source"])

    def test_failed_restore_cannot_change_original_database(self) -> None:
        _create("mariadb",PREFIX+"broken")
        broken = self.snapshots["source"] + b"\nINSERT INTO nonexisting_private_table VALUES (100);\n"
        with self.assertRaisesRegex(RuntimeError,"SYNTHETIC_ISOLATED_RESTORE_FAILED"):
            _restore("mariadb",PREFIX+"broken",broken,hashlib.sha256(broken).hexdigest())
        self.assertEqual(_rows("mysql",PREFIX+"source"),self.before["source"])
        self.assertEqual(_rows("mariadb",PREFIX+"target"),self.before["target"])

    def test_real_compatible_fixtures_do_not_authorize_migration(self) -> None:
        # These backups are *synthetic fixtures*; no backup/restoration proof
        # for either of the owner's actual VPS is available here.
        self.assertTrue(self.snapshots["source"] and self.snapshots["target"])
        result = migration_conflict_recovery.draft({
            "status": "ADVISORY_DIAGNOSTIC_ONLY",
            "database_writes_performed": False,
            "migration_state_modified": False,
            "evidence": {
                "verification": "NOT_A_PASS_GATE",
                "pk_conflicts": {
                    "comparison":"PK_LITERAL_DIFFER",
                    "verification":"NOT_A_PASS_GATE",
                    "tables_examined":1, "pk_tables_evaluable":1,
                    "pk_tables_unavailable":0, "differing_pk_tables":1,
                    "differing_table_ordinals":[{
                        "table_ordinal":1,"source_only_keys":3,
                        "target_only_keys":5,"same_key_changed_literals":5,
                        "identical_key_identical_literals":196,
                    }],
                    "source_only_keys":3,"target_only_keys":5,
                    "same_key_changed_literals":5,
                },
                "row_tuples":{
                    "tables_examined":1,"differing_tables":1,
                    "differing_table_ordinals":[{
                        "table_ordinal":1,"source_rows":204,"target_rows":206,
                    }],
                },
                "row_multiset":{"tables_examined":1},
                "dynamic_guard":{"recognized_unsafe":3},
            }
        })
        self.assertEqual(result["status"],"BLOCKED_RECOVERY_AND_OPERATOR_DECISIONS")
        self.assertFalse(result["migration_resume_allowed"])
        self.assertFalse(result["data_writes_allowed"])
        self.assertFalse(result["cutover_allowed"])
        self.assertEqual(result["recovery_proof"],"NOT_ESTABLISHED")


if __name__=="__main__":
    unittest.main()
