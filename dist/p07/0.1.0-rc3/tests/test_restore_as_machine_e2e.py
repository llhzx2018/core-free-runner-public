from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "vfops"
RESTORE = ROOT / "lib" / "restore_as_verified.py"
MARKER = ".vfops-controlled-cloudpanel-target"
MARKER_VALUE = "VF_SERVER_OPS_CONTROLLED_CLOUDPANEL_TARGET_V1"


class RestoreAsMachineE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.rootfs = self.base / "rootfs"
        self.backups = self.base / "backups"
        self.fakebin = self.base / "fakebin"
        self.log = self.base / "clpctl.log"
        self.fakebin.mkdir(parents=True)
        self._make_cloudpanel_fixture()
        self._make_fake_tools()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def env(self, **extra: str) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "P07_TEST_ROOT": str(self.rootfs),
                "P07_TEST_CLPCTL_LOG": str(self.log),
                "PATH": f"{self.fakebin}:{env.get('PATH', '')}",
            }
        )
        env.update(extra)
        return env

    def _make_cloudpanel_fixture(self) -> None:
        root = self.rootfs
        (root / "etc/nginx/sites-enabled").mkdir(parents=True)
        (root / "etc/nginx/ssl-certificates").mkdir(parents=True)
        (root / "etc").mkdir(exist_ok=True)
        (root / "etc/os-release").write_text(
            'ID=debian\nVERSION_ID="13"\nPRETTY_NAME="Debian GNU/Linux 13"\n', encoding="utf-8"
        )
        (root / "etc/hostname").write_text("p07-machine-fixture\n", encoding="utf-8")
        (root / MARKER).write_text(MARKER_VALUE + "\n", encoding="utf-8")
        (root / "home/clp/htdocs/app/data").mkdir(parents=True)
        (root / "home/clp/htdocs/app/VERSION").write_text("6.0.8\n", encoding="utf-8")

        panel_db = root / "home/clp/htdocs/app/data/db.sq3"
        conn = sqlite3.connect(panel_db)
        conn.executescript(
            """
            CREATE TABLE site (id INTEGER PRIMARY KEY, domain_name TEXT, user TEXT, type TEXT, vhost_template TEXT);
            CREATE TABLE php_settings (site_id INTEGER, php_version TEXT);
            CREATE TABLE database (site_id INTEGER, name TEXT, user_name TEXT, password TEXT);
            INSERT INTO site VALUES (1, 'example.com', 'alice', 'php', 'Generic');
            INSERT INTO php_settings VALUES (1, '8.4');
            INSERT INTO database VALUES (1, 'example_prod', 'example_user', 'SOURCE_DB_PASSWORD');
            """
        )
        conn.commit()
        conn.close()

        (root / "etc/nginx/sites-enabled/example.com.conf").write_text(
            "server { listen 80; server_name example.com www.example.com; root /home/alice/htdocs/example.com/public; fastcgi_pass unix:/run/php/php8.4-fpm.sock; }\n",
            encoding="utf-8",
        )
        site = root / "home/alice/htdocs/example.com"
        (site / "public").mkdir(parents=True)
        (site / "public/index.php").write_text("<?php echo 'SOURCE_OK';\n", encoding="utf-8")
        (site / "wp-config.php").write_text(
            "<?php\n"
            "define('DB_NAME', 'example_prod');\n"
            "define('DB_USER', 'example_user');\n"
            "define('DB_PASSWORD', 'SOURCE_DB_PASSWORD');\n",
            encoding="utf-8",
        )
        (site / "SOURCE_SENTINEL").write_text("SOURCE_PRESERVED\n", encoding="utf-8")

    def _write_tool(self, name: str, text: str) -> Path:
        path = self.fakebin / name
        path.write_text(text, encoding="utf-8")
        path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        return path

    def _make_fake_tools(self) -> None:
        self.clpctl = self._write_tool(
            "clpctl",
            r'''#!/usr/bin/env python3
import gzip,json,os,pathlib,shutil,sys
root=pathlib.Path(os.environ['P07_TEST_ROOT'])
log=pathlib.Path(os.environ['P07_TEST_CLPCTL_LOG'])
cmd=sys.argv[1] if len(sys.argv)>1 else ''
args={}
flags=set()
for item in sys.argv[2:]:
    if item.startswith('--') and '=' in item:
        k,v=item[2:].split('=',1); args[k]=v
    elif item.startswith('--'):
        flags.add(item[2:])
with log.open('a',encoding='utf-8') as h:
    safe={k:v for k,v in args.items() if 'password' not in k.lower() and 'key' not in k.lower()}
    h.write(cmd+' '+json.dumps(safe,sort_keys=True)+'\n')
state=root/'.p07-fake-db'; state.mkdir(exist_ok=True)
if cmd.startswith('site:add:'):
    domain=args['domainName']; user=args['siteUser']
    target=root/'home'/user/'htdocs'/domain
    target.mkdir(parents=True,exist_ok=False)
    (target/'cloudpanel-bootstrap.html').write_text('BOOTSTRAP\n',encoding='utf-8')
    raise SystemExit(0)
if cmd=='site:delete':
    domain=args['domainName']
    for target in (root/'home').glob('*/htdocs/'+domain):
        if target.exists(): shutil.rmtree(target)
    raise SystemExit(0)
if cmd=='db:add':
    (state/(args['databaseName']+'.created')).write_text('1',encoding='utf-8')
    raise SystemExit(0)
if cmd=='db:import':
    src=pathlib.Path(args['file']); dst=state/(args['databaseName']+'.sql.gz')
    shutil.copy2(src,dst)
    raise SystemExit(0)
if cmd=='db:export':
    out=pathlib.Path(args['file']); out.parent.mkdir(parents=True,exist_ok=True)
    saved=state/(args['databaseName']+'.sql.gz')
    if saved.exists(): shutil.copy2(saved,out)
    else:
        with gzip.open(out,'wt',encoding='utf-8') as h:
            h.write('CREATE TABLE demo(id INT);\nINSERT INTO demo VALUES (1);\n')
    raise SystemExit(0)
if cmd=='db:delete':
    for suffix in ('.created','.sql.gz'):
        (state/(args['databaseName']+suffix)).unlink(missing_ok=True)
    raise SystemExit(0)
if cmd in {'system:permissions:reset','varnish-cache:purge'}:
    raise SystemExit(0)
if cmd=='--version' or '--version' in flags:
    print('6.0.8'); raise SystemExit(0)
raise SystemExit(0)
''',
        )
        self.runuser = self._write_tool(
            "runuser",
            """#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == '-u' ]] || exit 90
shift 2
[[ "${1:-}" == '--' ]] || exit 91
shift
exec "$@"
""",
        )
        self.wp = self._write_tool(
            "wp",
            r'''#!/usr/bin/env python3
import pathlib,sys
path_arg=next((x for x in sys.argv[1:] if x.startswith('--path=')),None)
if not path_arg: raise SystemExit(80)
root=pathlib.Path(path_arg.split('=',1)[1]); args=[x for x in sys.argv[1:] if not x.startswith('--path=')]
state=root/'.p07-wp-url'
if args[:3]==['option','get','home'] or args[:3]==['option','get','siteurl']:
    print(state.read_text(encoding='utf-8').strip() if state.exists() else 'https://example.com')
    raise SystemExit(0)
if args and args[0]=='search-replace':
    target=args[2].rstrip('/')
    state.write_text(target+'\n',encoding='utf-8')
    raise SystemExit(0)
raise SystemExit(82)
''',
        )
        self.curl = self._write_tool(
            "curl-probe",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "${P07_TEST_PROBE_FAIL:-0}" == '1' ]]; then exit 7; fi
printf '200'
""",
        )
        self.nginx = self._write_tool(
            "nginx-probe",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "${P07_TEST_PROBE_FAIL:-0}" == '1' ]]; then exit 1; fi
printf 'server { server_name restore.example.com; }\\n'
""",
        )

    def make_backup(self) -> Path:
        proc = subprocess.run(
            [
                str(CLI),
                "backup",
                "--site",
                "example.com",
                "--root",
                str(self.rootfs),
                "--output-dir",
                str(self.backups),
                "--clpctl",
                str(self.clpctl),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=self.env(VFOPS_NOW="2026-09-10T12:00:00+00:00"),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("SOURCE_DB_PASSWORD", proc.stdout + proc.stderr)
        package = Path(proc.stdout.strip())
        self.assertTrue((package / "verification.json").is_file())
        verification = json.loads((package / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(verification["status"], "PASS")
        return package

    def confirm(self, package: Path, target: str) -> str:
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        return f"RESTORE_AS:{manifest['site']['domain']}:{target}:{manifest['backup_id']}"

    def run_restore(self, package: Path, target: str, *, fail_probe: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(RESTORE),
                "--package",
                str(package),
                "--target-domain",
                target,
                "--target-root",
                str(self.rootfs),
                "--clpctl",
                str(self.clpctl),
                "--runuser",
                str(self.runuser),
                "--wp",
                str(self.wp),
                "--curl",
                str(self.curl),
                "--nginx",
                str(self.nginx),
                "--confirm",
                self.confirm(package, target),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=self.env(P07_TEST_PROBE_FAIL="1" if fail_probe else "0"),
        )

    def test_backup_to_restore_as_success_exercises_cloudpanel_db_wp_and_host_sni(self) -> None:
        package = self.make_backup()
        proc = self.run_restore(package, "restore.example.com")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("SOURCE_DB_PASSWORD", proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "RESTORE_AS_VERIFIED")
        self.assertEqual(result["machine_verification_scope"], "FILES_DB_APP_HOST_SNI")
        self.assertEqual(result["local_verification"]["host"]["status"], "PASS")
        self.assertEqual(result["local_verification"]["sni"]["status"], "PASS")
        self.assertFalse(result["dns_changed"])
        self.assertFalse(result["source_deleted"])
        self.assertFalse(result["existing_site_overwrite_allowed"])
        self.assertFalse(result["source_ssl_reused"])

        target = self.rootfs / result["target_site_root"].lstrip("/")
        self.assertTrue((target / "public/index.php").is_file())
        config = (target / "wp-config.php").read_text(encoding="utf-8")
        self.assertIn(result["target_database"], config)
        self.assertIn(result["target_database_user"], config)
        self.assertNotIn("SOURCE_DB_PASSWORD", config)
        self.assertEqual((target / ".p07-wp-url").read_text(encoding="utf-8").strip(), "https://restore.example.com")
        self.assertEqual(
            (self.rootfs / "home/alice/htdocs/example.com/SOURCE_SENTINEL").read_text(encoding="utf-8"),
            "SOURCE_PRESERVED\n",
        )
        log = self.log.read_text(encoding="utf-8")
        for command in ("site:add:php", "db:add", "db:import", "db:export", "system:permissions:reset"):
            self.assertIn(command, log)
        self.assertNotIn("SOURCE_DB_PASSWORD", log)
        self.assertNotIn("dns", log.lower())

    def test_existing_target_path_is_zero_write_before_cloudpanel_create(self) -> None:
        package = self.make_backup()
        occupied = self.rootfs / "home/other/htdocs/occupied.example.com"
        occupied.mkdir(parents=True)
        sentinel = occupied / "TARGET_SENTINEL"
        sentinel.write_text("DO_NOT_TOUCH\n", encoding="utf-8")
        before = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        proc = self.run_restore(package, "occupied.example.com")
        self.assertNotEqual(proc.returncode, 0)
        after = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        self.assertEqual(before, after)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "DO_NOT_TOUCH\n")
        self.assertEqual(
            (self.rootfs / "home/alice/htdocs/example.com/SOURCE_SENTINEL").read_text(encoding="utf-8"),
            "SOURCE_PRESERVED\n",
        )

    def test_post_restore_probe_failure_rolls_back_only_new_target(self) -> None:
        package = self.make_backup()
        proc = self.run_restore(package, "fail.example.com", fail_probe=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("rollback=PASS", proc.stderr)
        self.assertFalse(any((self.rootfs / "home").glob("*/htdocs/fail.example.com")))
        self.assertEqual(
            (self.rootfs / "home/alice/htdocs/example.com/SOURCE_SENTINEL").read_text(encoding="utf-8"),
            "SOURCE_PRESERVED\n",
        )
        log = self.log.read_text(encoding="utf-8")
        self.assertIn("db:delete", log)
        self.assertIn("site:delete", log)
        self.assertNotIn("SOURCE_DB_PASSWORD", log)


if __name__ == "__main__":
    unittest.main()
