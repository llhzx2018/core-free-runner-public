#!/usr/bin/env python3
"""One-off P01 v2.47.517 release-scope native authority verification.

Source only exists in transient private checkout; no production hosts or
credentials are imported. Every database is synthetic and disposable.
"""
from pathlib import Path
import os
import sys
import tempfile
import subprocess

TARGET = "c00f54bed0fa3521a3c57bfcd591745fb45db776"
ENGINES = ("sqlite", "mariadb", "mysql")
SAFE_DB = {
    "mariadb": ("3307", "p01_d1_test_maria_20261111"),
    "mysql": ("3306", "p01_d1_test_mysql_20261111"),
}
PHP = r'''$port=(int)$argv[1];$name=$argv[2];
if(!in_array($name,["p01_d1_test_maria_20261111",
                      "p01_d1_test_mysql_20261111"],true))exit(14);
$db=new PDO("mysql:host=127.0.0.1;port=".$port.";charset=utf8mb4",
  "root","p01-only-synthetic-test",
  [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$q=chr(96);
$db->exec("DROP DATABASE IF EXISTS ".$q.$name.$q);
$db->exec("CREATE DATABASE ".$q.$name.$q." CHARACTER SET utf8mb4");'''


def reset(engine):
    if engine == "sqlite":
        return
    port, name = SAFE_DB[engine]
    subprocess.run(
        ["php8.3", "-r", PHP, port, name],
        check=True, timeout=35,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL
    )


def main():
    root = Path("candidate").resolve()
    bundle = Path(os.environ["RUNNER_TEMP"]) / "d60-official-full.zip"
    assert (root / "VERSION").read_text().strip() == "2.47.517"
    assert bundle.is_file() and not bundle.is_symlink()
    sys.path.insert(0, str(root / "tests/compatibility/laravel/http"))

    from run_cloudpanel_fpm_full_stage import Site

    # Site.run already runs D77's real Owner integration, which in turn
    # invokes D79 recovery, D82 SSRF, D86 schedules and D81/83/84/87.
    # Re-entering the same stateful probes would be a test harness bug:
    # the fixed synthetic seeded job summary is no longer a virgin fixture.

    for engine in ENGINES:
        reset(engine)
        with tempfile.TemporaryDirectory(prefix="p01-d14-stage-v517domain-") as tmp:
            site = Site(Path(tmp), engine, bundle)
            try:
                site.start()
                site.run()
            finally:
                site.stop()
        print("P01_V517_" + engine.upper() +
              "_PRIVATE_SEO_PROVIDER_SSRF_JOBS_CRASH_SCHEDULE_OBSERVABILITY=PASS",
              flush=True)

        reset(engine)
        with tempfile.TemporaryDirectory(prefix="p01-d14-stage-v517rss-") as tmp:
            site = Site(Path(tmp), engine, bundle)
            try:
                site.start()
                site.run(only_rss_native=True)
            finally:
                site.stop()
        print("P01_V517_" + engine.upper() +
              "_RSS_OWNER_CSRF_ESCROW_NATIVE_JOB_BACKUP_NO_REPLAY=PASS",
              flush=True)
    print("P01_V517_THREE_ENGINES_RELEASE_DOMAIN_MACHINE_PROOF_SCOPED=PASS",
          flush=True)
    print("P01_V517_OFFICIAL_MAJOR_EXECUTION_NOT_PERFORMED=YES", flush=True)


if __name__ == "__main__":
    main()
