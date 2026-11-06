"""Actual isolated MariaDB-engine test for final shadow creation and rollback.

Runs only in a throwaway Docker container with --network=none and no ports.
No CP2, no source VPS, no CloudPanel daemon, no customer data, no DNS.
No mock of SQL execution or the guarded production dump comparator.

Requires Docker and a MariaDB 11.8 image; absence fails the CI gate rather
than silently skipping the only real-database shadow test.
"""
from __future__ import annotations

import gzip
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import migration_final_db_shadow as shadow
import migration_final_db_batch as batch
import server_migration as legacy
import server_migration_pull as pull

MID = "pull-20261101T045943Z-923729a1"
IDENTITY = "sha256:isolated-ci-target"
ORIGINAL_OWNERS = (
    "pull-20261101T045943Z-923729a1",
    "pull-20261101T052411Z-35663c25",
    "pull-20261031T095604Z-edae3c44",
)


class LiveShadowMariaDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(28)
        cls.container = "p07-shadow-ci-" + uuid.uuid4().hex[:12]
        try:
            subprocess.run(
                ["docker", "run", "--rm", "-d", "--name", cls.container,
                 "--network", "none", "--tmpfs",
                 "/var/lib/mysql:rw,nodev,nosuid,size=256m",
                 "-e", "MARIADB_ROOT_PASSWORD=" + cls.password,
                 "mariadb:11.8"],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=180,
            )
            for _ in range(75):
                ready = cls._run_cli(["mariadb", "-uroot", "-N", "-e", "SELECT 1"],
                                     check=False)
                if ready.returncode == 0 and ready.stdout.strip() == b"1":
                    break
                time.sleep(1)
            else:
                raise AssertionError("isolated MariaDB did not become ready")
            version = cls._run_cli(
                ["mariadb", "-uroot", "-N", "-e", "SELECT VERSION()"]
            ).stdout.decode("ascii", errors="replace").strip()
            if not version.startswith("11.8."):
                raise AssertionError("isolated MariaDB engine version unexpected")
        except (OSError, subprocess.SubprocessError, AssertionError):
            cls.tearDownClass()
            raise AssertionError("isolated MariaDB shadow test environment unavailable") from None

    @classmethod
    def tearDownClass(cls):
        subprocess.run(
            ["docker", "rm", "-f", cls.container],
            check=False, capture_output=True, timeout=30,
        )

    @classmethod
    def _run_cli(cls, command, *, input_data=None, check=True):
        proc = subprocess.run(
            ["docker", "exec", "-i", "-e", "MYSQL_PWD=" + cls.password,
             cls.container, *command],
            input=input_data, capture_output=True,
            check=False, timeout=45,
        )
        if check and proc.returncode != 0:
            raise AssertionError("isolated MariaDB command failed")
        return proc

    @classmethod
    def _sql(cls, statement):
        return cls._run_cli(
            ["mariadb", "-uroot", "-N", "-e", statement]
        ).stdout.decode("utf-8").strip()

    @classmethod
    def _dump(cls, database, output):
        raw = cls._run_cli(
            ["mariadb-dump", "-uroot", "--single-transaction",
             "--skip-comments", "--skip-dump-date", "--skip-lock-tables",
             "--skip-add-locks",
             "--no-tablespaces", "--skip-extended-insert", database],
        ).stdout
        with gzip.open(output, "wb") as file:
            file.write(raw)
        return output

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p07-live-shadow-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patch = mock.patch.object(legacy, "STATE_ROOT", self.root / "state")
        patch.start()
        self.addCleanup(patch.stop)
        self.sites = []
        self.source_dumps = {}
        self.original_configs = {}
        for index in range(len(ORIGINAL_OWNERS)):
            domain = f"isolated{index}.example.test"
            database = f"p07oldci{index}"
            site_root = self.root / domain
            site_root.mkdir()
            config = site_root / "wp-config.php"
            config.write_text(
                f"define('DB_NAME', '{database}');\n"
                f"define('DB_USER', 'p07original{index}');\n"
                f"define('DB_PASSWORD', 'synthetic-only-{index}');\n",
                encoding="utf-8",
            )
            self.original_configs[domain] = config.read_bytes()
            site = {
                "domain": domain, "site_root": str(site_root),
                "mysql_databases": [database], "stage_status": "PULLED_STAGED",
            }
            self.sites.append(site)
            marker = legacy.target_db_marker(
                ORIGINAL_OWNERS[index], domain, database, 1,
            )
            legacy.atomic_private_json(marker, {
                "domain": domain, "database": database,
                "username": f"p07original{index}",
                "password": f"synthetic-only-{index}",
                "created_by_migration": ORIGINAL_OWNERS[index],
            })
        self.state = {
            "migration_id": MID, "sites": self.sites, "status": "CUTOVER_RUNNING",
            "source_runtime_frozen": True, "target_runtime_activated": False,
            "dns_changed_by_p07": False, "source_delete_allowed": False,
            "existing_target_overwrite_allowed": False,
            "target_server_identity": IDENTITY,
            "original_db_migration_owners": {
                site["domain"]: ORIGINAL_OWNERS[index]
                for index, site in enumerate(self.sites)
            },
        }
        for index, site in enumerate(self.sites):
            original = site["mysql_databases"][0]
            source_database = f"p07srcci{index}"
            self._sql(f"DROP DATABASE IF EXISTS {source_database}")
            self._sql(f"DROP DATABASE IF EXISTS {original}")
            _, shadow_name = shadow.shadow_identity(self.state, site)
            self._sql(f"DROP DATABASE IF EXISTS {shadow_name}")
            self._sql(f"CREATE DATABASE {source_database}")
            self._sql(f"CREATE DATABASE {original}")
            self._sql(
                f"CREATE TABLE {source_database}.sample (id int PRIMARY KEY, payload varchar(30))"
            )
            self._sql(
                f"INSERT INTO {source_database}.sample VALUES ({index+1},'from-source')"
            )
            # A live WordPress cron option must survive the final source
            # shadow import byte-for-byte; the original target cron is kept.
            self._sql(
                f"CREATE TABLE {source_database}.wp_options "
                "(option_id BIGINT PRIMARY KEY, option_name VARCHAR(191) UNIQUE, "
                "option_value LONGTEXT NOT NULL, autoload VARCHAR(20) NOT NULL)"
            )
            self._sql(
                f"INSERT INTO {source_database}.wp_options "
                "VALUES (1, 'cron', 'a:1:{s:7:\"version\";i:2;}', 'yes')"
            )
            self._sql(
                f"CREATE TABLE {original}.owner_data (id int PRIMARY KEY)"
            )
            self._sql(f"INSERT INTO {original}.owner_data VALUES (999)")
            self._sql(
                f"CREATE TABLE {original}.wp_options "
                "(option_id BIGINT PRIMARY KEY, option_name VARCHAR(191) UNIQUE, "
                "option_value LONGTEXT NOT NULL, autoload VARCHAR(20) NOT NULL)"
            )
            self._sql(
                f"INSERT INTO {original}.wp_options "
                "VALUES (1, 'cron', 'a:1:{s:7:\"version\";i:1;}', 'yes')"
            )
            out = legacy.state_dir(MID) / "mysql" / "final" / f"source{index}.sql.gz"
            out.parent.mkdir(parents=True, exist_ok=True)
            self._dump(source_database, out)
            self.source_dumps[site["domain"]] = out
        def add_db(domain, database, username, password):
            self._sql(f"CREATE DATABASE {database}")
        def import_db(database, dump):
            with gzip.open(dump, "rb") as f:
                sql = f.read()
            self._run_cli(["mariadb", "-uroot", database], input_data=sql)
        def export_db(database, output, *, clpctl="clpctl"):
            return self._dump(database, output)
        self.db_patches = [
            mock.patch.object(shadow.cloudpanel, "add_database",
                              side_effect=add_db),
            mock.patch.object(shadow.cloudpanel, "import_database",
                              side_effect=import_db),
            mock.patch.object(shadow.cloudpanel, "export_database",
                              side_effect=export_db),
        ]
        for p in self.db_patches:
            p.start()
            self.addCleanup(p.stop)

    def test_real_engine_shadow_import_full_comparator_and_batch_rollback(self):
        for site in self.sites:
            result = shadow.stage_frozen_source_shadow(
                self.state, site, self.source_dumps[site["domain"]],
                actual_target_identity=IDENTITY,
            )
            self.assertEqual(result["status"], "STAGED_VERIFIED_NOT_ACTIVATED")
            self.assertNotEqual(result["shadow_database"],
                                site["mysql_databases"][0])
            self.assertEqual(
                self._sql(f"SELECT COUNT(*) FROM {result['shadow_database']}.sample"), "1"
            )
            self.assertEqual(
                self._sql(f"SELECT id FROM {site['mysql_databases'][0]}.owner_data"),
                "999",
            )
            self.assertEqual(
                self._sql(f"SELECT option_value FROM {result['shadow_database']}.wp_options "
                          "WHERE option_name='cron'"),
                'a:1:{s:7:"version";i:2;}',
            )
            self.assertEqual(
                self._sql(f"SELECT option_value FROM {site['mysql_databases'][0]}.wp_options "
                          "WHERE option_name='cron'"),
                'a:1:{s:7:"version";i:1;}',
            )
        # No app has switched yet.
        for site in self.sites:
            config = Path(site["site_root"]) / "wp-config.php"
            self.assertEqual(config.read_bytes(),
                             self.original_configs[site["domain"]])
        with mock.patch.object(
            pull, "target_identity", return_value=IDENTITY
        ), mock.patch.object(
            pull, "stage_frozen_final_mysql_shadows",
            return_value={
                "status": "ALL_SHADOW_DATABASES_STAGED_NOT_ACTIVATED",
                "database_count": 3, "app_config_modified": False,
                "cutover_allowed": False,
            },
        ) as already_staged:
            result = pull.run_frozen_final_mysql_shadow_transaction(
                self.state, expected_site_count=3,
            )
            already_staged.assert_called_once()
        self.assertEqual(
            result["status"],
            "FINAL_MYSQL_SHADOW_TRANSACTION_VERIFIED_NOT_CUTOVER",
        )
        self.assertFalse(result["cutover_allowed"])
        for site in self.sites:
            self.assertNotEqual(
                (Path(site["site_root"]) / "wp-config.php").read_bytes(),
                self.original_configs[site["domain"]],
            )
        self.state["status"] = "CUTOVER_PREP_READY"
        with mock.patch.object(pull, "target_identity", return_value=IDENTITY):
            recovered = pull.rollback_frozen_final_mysql_shadow_transaction(
                self.state, expected_site_count=3,
            )
        self.assertEqual(
            recovered["status"], "FINAL_MYSQL_APP_MAPPING_ROLLED_BACK"
        )
        for site in self.sites:
            self.assertEqual(
                (Path(site["site_root"]) / "wp-config.php").read_bytes(),
                self.original_configs[site["domain"]],
            )
            original = site["mysql_databases"][0]
            self.assertEqual(self._sql(f"SELECT id FROM {original}.owner_data"),
                             "999")
            self.assertEqual(
                self._sql(f"SELECT option_value FROM {original}.wp_options "
                          "WHERE option_name='cron'"),
                'a:1:{s:7:"version";i:1;}',
            )
            _, kept_shadow = shadow.shadow_identity(self.state, site)
            self.assertEqual(
                self._sql(f"SELECT option_value FROM {kept_shadow}.wp_options "
                          "WHERE option_name='cron'"),
                'a:1:{s:7:"version";i:2;}',
            )
        with self.assertRaisesRegex(
            pull.PullMigrationError, "FINAL_MYSQL_SAFE_REPLACEMENT_NOT_IMPLEMENTED"
        ):
            pull.require_non_destructive_final_db_plan(self.state)

    def tearDown(self):
        if hasattr(self, "sites"):
            for site in self.sites:
                orig = site["mysql_databases"][0]
                _, isolated = shadow.shadow_identity(self.state, site)
                for database in (orig, isolated):
                    self._sql(f"DROP DATABASE IF EXISTS {database}")
            for index in range(len(ORIGINAL_OWNERS)):
                self._sql(f"DROP DATABASE IF EXISTS p07srcci{index}")


if __name__ == "__main__":
    unittest.main()
