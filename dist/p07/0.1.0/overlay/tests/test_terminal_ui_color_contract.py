from __future__ import annotations

import os
import pty
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TerminalUiColorContractTests(unittest.TestCase):
    def _run_pty(self, command: str, *, no_color: bool = False) -> bytes:
        master, slave = pty.openpty()
        env = os.environ.copy()
        if no_color:
            env["NO_COLOR"] = "1"
        else:
            env.pop("NO_COLOR", None)
        proc = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)
        chunks: list[bytes] = []
        try:
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(master)
        self.assertEqual(proc.wait(timeout=10), 0)
        return b"".join(chunks)

    def test_shared_helper_exposes_canonical_semantics(self) -> None:
        text = (ROOT / "lib" / "terminal_ui.sh").read_text(encoding="utf-8")
        self.assertIn('[[ -t 1 && -z "${NO_COLOR:-}" ]]', text)
        for helper in (
            "ui_title()",
            "ui_rule()",
            "ui_menu_good()",
            "ui_menu_info()",
            "ui_menu_warn()",
            "ui_menu_danger()",
            "ui_menu_flow()",
            "ui_menu_back()",
            "ui_note()",
            "ui_good()",
            "ui_attention()",
            "ui_bad()",
            "ui_flow()",
        ):
            self.assertIn(helper, text)

    def test_interactive_tty_has_semantic_ansi_hierarchy(self) -> None:
        output = self._run_pty(
            "source lib/terminal_ui.sh; "
            "ui_title TITLE; ui_good READY; ui_attention REVIEW; "
            "ui_bad FAIL; ui_flow MIGRATION; ui_note BOUNDARY"
        )
        for code, word in (
            (b"\x1b[36m", b"TITLE"),
            (b"\x1b[32m", b"READY"),
            (b"\x1b[33m", b"REVIEW"),
            (b"\x1b[31m", b"FAIL"),
            (b"\x1b[35m", b"MIGRATION"),
            (b"\x1b[90m", b"BOUNDARY"),
        ):
            self.assertIn(code, output)
            self.assertIn(word, output)

    def test_no_color_disables_ansi_even_on_tty(self) -> None:
        output = self._run_pty(
            "source lib/terminal_ui.sh; ui_good READY; ui_bad FAIL; ui_flow MIGRATION",
            no_color=True,
        )
        self.assertNotIn(b"\x1b[", output)
        self.assertIn(b"READY", output)
        self.assertIn(b"FAIL", output)
        self.assertIn(b"MIGRATION", output)

    def test_non_tty_is_plain_text(self) -> None:
        proc = subprocess.run(
            [
                "bash",
                "-lc",
                "source lib/terminal_ui.sh; "
                "ui_good READY; ui_attention REVIEW; ui_bad FAIL; ui_flow MIGRATION; ui_note BOUNDARY",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertNotIn("\x1b[", proc.stdout)
        self.assertEqual(
            proc.stdout.splitlines(),
            ["READY", "REVIEW", "FAIL", "MIGRATION", "BOUNDARY"],
        )

    def test_machine_identity_output_remains_plain(self) -> None:
        version = subprocess.run(
            ["bash", "bin/vfops-user", "--version"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        build = subprocess.run(
            ["bash", "bin/vfops-user", "--build-id"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        self.assertEqual(version, "VF Server Ops 0.1.0\n")
        self.assertEqual(build, "0.1.0-release2\n")
        self.assertNotIn("\x1b[", version + build)

        core = (ROOT / "bin" / "vfops").read_text(encoding="utf-8")
        self.assertNotIn("terminal_ui.sh", core)

    def test_slot3_semantic_mapping_is_locked(self) -> None:
        migrate = (ROOT / "bin" / "vfops-migrate-ui").read_text(encoding="utf-8")
        site = (ROOT / "bin" / "vfops-site-ui").read_text(encoding="utf-8")
        auto = (ROOT / "bin" / "vfops-auto-backup").read_text(encoding="utf-8")
        storage = (ROOT / "bin" / "vfops-storage-setup").read_text(encoding="utf-8")
        admin = (ROOT / "lib" / "cloudpanel_ui_admin.sh").read_text(encoding="utf-8")

        self.assertIn("ui_menu_flow 1 '整机迁移（推荐）'", migrate)
        self.assertIn("ui_menu_flow 3 '单站迁移'", migrate)
        self.assertIn("ui_menu_warn 1 '恢复为新网站", site)
        self.assertIn("ui_menu_danger 1 '确认关闭'", auto)
        self.assertIn("ui_good 'Google：READY ✓'", storage)
        self.assertIn("ui_menu_danger 2 '关闭 Panel Basic Auth'", admin)
        self.assertIn("ui_menu_danger 4 '关闭用户 2FA'", admin)

    def test_color_contract_is_in_owning_authority(self) -> None:
        rpd = (ROOT / "docs" / "authority" / "RPD.md").read_text(encoding="utf-8")
        matrix = (ROOT / "docs" / "authority" / "ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
        self.assertIn("Terminal UI / Color System Contract", rpd)
        self.assertIn("Terminal UI Color Contract", matrix)
        for term in ("Cyan", "Green", "Yellow", "Red", "Magenta", "Gray", "NO_COLOR", "non-TTY"):
            self.assertIn(term, rpd)

    def test_slot3_ui_files_stay_bounded(self) -> None:
        caps = {
            "bin/vfops-user": 150,
            "bin/vfops-site-ui": 500,
            "bin/vfops-migrate-ui": 900,
            "bin/vfops-auto-backup": 800,
            "bin/vfops-cloudpanel-ui": 160,
            "bin/vfops-storage-setup": 850,
            "lib/cloudpanel_ui_common.sh": 260,
            "lib/cloudpanel_ui_sites.sh": 240,
            "lib/cloudpanel_ui_ops.sh": 220,
            "lib/cloudpanel_ui_admin.sh": 320,
        }
        for relative, cap in caps.items():
            count = len((ROOT / relative).read_text(encoding="utf-8").splitlines())
            self.assertLessEqual(count, cap, f"{relative} unexpectedly expanded to {count} lines")


if __name__ == "__main__":
    unittest.main()
