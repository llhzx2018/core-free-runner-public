"""Interactive fake-shell tests: fresh CP2 must stay inside P07 menu 5 -> 1."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "bin" / "vfops-migrate-ui"


class FreshMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = UI.read_text(encoding="utf-8")
        marker = "\nmigration_menu\n"
        assert cls.source.count(marker) == 1
        cls.definitions = cls.source.rsplit(marker, 1)[0] + "\n"

    def test_shell_syntax(self):
        with subprocess.Popen(["bash", "-n", str(UI)], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as p:
            _out, err = p.communicate(timeout=10)
            self.assertEqual(p.returncode, 0, err.decode(errors="replace"))

    def run_screen(self, case, inputs):
        stubs = r'''
# Run only guarded flow functions in synthetic mode, never real SSH or SQL.
read_old_ip() { OLD_SERVER_IP=192.0.2.19; return 0; }
ensure_source_access() { SOURCE_IDENTITY_FILE=''; SOURCE_IDENTITY_MANAGED=0; return 0; }
run_quiet_with_progress() {
  printf 'MENU_PREVIEW_ARGS=%s\n' "$*"
  if [[ "$P07_TEST_CASE" == blocked ]]; then
    WAIT_PAYLOAD='{"status":"BLOCKED","reason":"FRESH_SOURCE_SQL_UNPROVEN_SIDE_EFFECTS"}'
    return 13
  fi
  WAIT_PAYLOAD='{"status":"PREFLIGHT_PASS_NOT_CUTOVER_READY","source_site_count":17,"source_db_count":3,"target_empty_verified":true}'
  return 0
}
run_migration_live() {
  printf 'MENU_PREPARE_ARGS=%s\n' "$*"
  MIGRATION_PAYLOAD='{"status":"FRESH_FIRST_COPY_COMPLETED_NOT_CUTOVER_READY"}'
  return 0
}
pause() { :; }
whole_server_in
'''
        # Create under repo/bin so ROOT_DIR and terminal_ui paths stay canonical.
        fd, name = tempfile.mkstemp(prefix=".p07-ux-synthetic-", suffix=".sh",
                                    dir=ROOT / "bin")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(self.definitions + stubs)
            p = subprocess.run(["bash", name], input=inputs, text=True,
                               capture_output=True, timeout=15,
                               env={**os.environ, "P07_TEST_CASE":case})
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout + "\n" + p.stderr
        finally:
            Path(name).unlink(missing_ok=True)

    def test_preflight_block_never_calls_prepare(self):
        output = self.run_screen("blocked", "y\n")
        self.assertIn("fresh-17site preview --source-ip 192.0.2.19", output)
        self.assertNotIn("MENU_PREPARE_ARGS", output)

    def test_declining_preflight_does_not_write(self):
        output = self.run_screen("ok", "n\n")
        self.assertNotIn("MENU_PREVIEW_ARGS", output)
        self.assertNotIn("MENU_PREPARE_ARGS", output)

    def test_declining_first_copy_does_not_prepare(self):
        output = self.run_screen("ok", "y\nn\n")
        self.assertIn("fresh-17site preview --source-ip 192.0.2.19", output)
        self.assertNotIn("MENU_PREPARE_ARGS", output)

    def test_confirmed_first_copy_calls_guarded_fresh_not_old_prepare(self):
        output = self.run_screen("ok", "y\ny\n")
        self.assertIn("fresh-17site preview --source-ip 192.0.2.19", output)
        self.assertIn("MENU_PREPARE_ARGS=fresh-17site prepare", output)
        self.assertNotIn("MENU_PREPARE_ARGS=server-migrate prepare", output)
        self.assertIn("PREPARE_FRESH_CP2_17_SITES", output)

    def test_known_sql_guard_rejects_resume_menu(self):
        # The operator can inspect a PREPARE_FAILED task but must not
        # re-import a partially populated database after CONDITIONAL_DDL.
        self.assertIn("guard_reason=\"$(json_field \"$payload\" last_sql_guard_failure.reason", self.source)
        self.assertIn("\"$guard_reason\" == 'CONDITIONAL_DDL'", self.source)
        self.assertIn("数据库验证被安全拦截；不能直接续跑或重新导入", self.source)
        self.assertIn("旧服务器继续运行，DNS 不修改", self.source)

    def test_initial_failure_does_not_claim_unconditional_resume(self):
        self.assertNotIn("目标端状态已保留，可从“继续未完成迁移”续跑", self.source)
        self.assertNotIn("首轮迁入未完成，可继续", self.source)

    def test_guarded_18_site_readonly_diagnostic_stays_in_menu(self):
        self.assertIn("first_failed_sql_site", self.source)
        self.assertIn("first_failed_sql_evidence.status", self.source)
        self.assertIn("server-migrate diagnose-sql --migration-id", self.source)
        self.assertIn("不重复迁入", self.source)
        self.assertIn("不更改任务状态，不重导数据库", self.source)
        self.assertIn("数据库验证被安全拦截；不能直接续跑或重新导入", self.source)

    def test_protected_18_site_adoption_and_resume_need_separate_confirmations(self):
        self.assertIn('first_stage_adopted_sql_site', self.source)
        self.assertIn('server-migrate adopt-existing-guarded-db --migration-id', self.source)
        self.assertIn('server-migrate resume-verified-adoption --migration-id', self.source)
        self.assertIn('RESUME_VERIFIED_ADOPTION:', self.source)
        self.assertIn('ADOPT_EXISTING_DB:', self.source)
        self.assertIn('FIRST_STAGE_ADOPTED_REQUIRES_CHAIN_RECOVERY', self.source)
        self.assertIn('旧 VPS 不停写', self.source)

    def test_full_site_prepared_cutover_guard_in_original_ui(self):
        self.assertIn('if [[ "$scope_count" == 17 || "$scope_count" == 18 ]]; then', self.source)
        self.assertIn("最终同步与回滚尚须独立现场门禁", self.source)


if __name__ == "__main__":
    unittest.main()
