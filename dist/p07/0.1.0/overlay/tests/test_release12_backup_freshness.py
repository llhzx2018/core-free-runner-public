from __future__ import annotations

import gzip
import os
from pathlib import Path
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "lib"))

import package as package_engine


class Release12BackupFreshnessTests(unittest.TestCase):
    def test_mysql_export_waits_for_background_writer_to_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out = base / "mysql"
            fake = base / "fake-clpctl"
            fake.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import gzip
                    import os
                    from pathlib import Path
                    import sys
                    import time

                    args = dict(
                        item[2:].split("=", 1)
                        for item in sys.argv[2:]
                        if item.startswith("--") and "=" in item
                    )
                    target = Path(args["file"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    pid = os.fork()
                    if pid == 0:
                        with target.open("wb") as raw:
                            with gzip.GzipFile(fileobj=raw, mode="wb") as zipped:
                                zipped.write(b"CREATE TABLE demo(id INT);\\n")
                                zipped.flush()
                                raw.flush()
                                os.fsync(raw.fileno())
                                time.sleep(0.35)
                                zipped.write(b"INSERT INTO demo VALUES (1);\\n")
                        os._exit(0)
                    raise SystemExit(0)
                    """
                ),
                encoding="utf-8",
            )
            fake.chmod(0o700)

            rows = package_engine._export_mysql_via_cloudpanel(
                ["example_prod"], out, str(fake)
            )
            self.assertEqual(rows[0]["database"], "example_prod")
            exported = out / "example_prod.sql.gz"
            with gzip.open(exported, "rb") as handle:
                payload = handle.read()
            self.assertIn(b"CREATE TABLE demo", payload)
            self.assertIn(b"INSERT INTO demo", payload)

    def test_restore_list_does_not_hide_fresh_verification_failures(self) -> None:
        text = (ROOT / "bin" / "vfops-site-ui").read_text(encoding="utf-8")
        self.assertIn("MySQL 备份文件在创建后发生变化", text)
        self.assertIn("发现了本地备份，但当前完整性复检未通过", text)
        self.assertNotIn("except Exception:\n            pass", text)

    def test_backup_is_verified_after_atomic_commit(self) -> None:
        text = (ROOT / "lib" / "package_core.py").read_text(encoding="utf-8")
        self.assertIn("final_verification = verify_package_stable(final_dir)", text)
        self.assertIn("consecutive_passes: int = 2", text)
        self.assertIn("backup failed post-commit fresh verification", text)


if __name__ == "__main__":
    unittest.main()
