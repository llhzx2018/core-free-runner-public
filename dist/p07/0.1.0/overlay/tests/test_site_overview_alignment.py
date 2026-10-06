from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata
import unittest


ROOT = Path(__file__).resolve().parents[1]


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


class SiteOverviewAlignmentTests(unittest.TestCase):
    def test_overview_columns_align_for_mixed_width_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bin").mkdir()
            (root / "lib").mkdir()
            shutil.copy2(ROOT / "bin/vfops-site-ui", root / "bin/vfops-site-ui")
            shutil.copy2(ROOT / "lib/terminal_ui.sh", root / "lib/terminal_ui.sh")
            shutil.copy2(ROOT / "lib/restore_failure_ui.sh", root / "lib/restore_failure_ui.sh")

            sites = []
            for i in range(12):
                sites.append({
                    "domain": (
                        "very-long-subdomain-for-alignment.example.com"
                        if i == 1
                        else f"s{i + 1}.example.com"
                    ),
                    "runtime": {
                        "type": "node_or_reverse_proxy" if i == 2 else "php",
                        "version": "" if i == 2 else ("8.4" if i % 2 == 0 else "8.3"),
                    },
                    "mysql_databases": ["db"] if i in (0, 11) else [],
                    "sqlite_paths": [],
                    "ssl": {"configured": i != 3},
                })
            payload = {
                "system": {
                    "os": {"pretty_name": "Debian GNU/Linux 13 (trixie)"},
                    "cloudpanel_version": "6.0.8",
                },
                "summary": {
                    "mysql_database_count_known": 2,
                    "sqlite_file_count_known": 0,
                },
                "sites": sites,
            }
            stub = root / "bin/vfops"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                f"print(json.dumps({payload!r}, ensure_ascii=False))\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

            proc = subprocess.run(
                ["bash", str(root / "bin/vfops-site-ui"), "overview"],
                input="\n",
                text=True,
                capture_output=True,
                env={"PATH": "/usr/bin:/bin", "NO_COLOR": "1", "TERM": "dumb"},
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            lines = [line for line in proc.stdout.splitlines() if re.match(r"^\s*\d+\.\s", line)]
            self.assertEqual(len(lines), 12)

            separator_columns = []
            dot_columns = []
            for line in lines:
                positions = [i for i, ch in enumerate(line) if ch == "·"]
                self.assertEqual(len(positions), 3, line)
                separator_columns.append(tuple(display_width(line[:i]) for i in positions))
                dot_columns.append(display_width(line[: line.index(".")]))
            self.assertEqual(len(set(separator_columns)), 1, lines)
            self.assertEqual(len(set(dot_columns)), 1, lines)
            self.assertIn("Node.js / 反向代理", proc.stdout)
            self.assertIn("HTTPS 未启用/未知", proc.stdout)
            self.assertRegex(proc.stdout, r"(?m)^\s*10\.\s")


if __name__ == "__main__":
    unittest.main()
