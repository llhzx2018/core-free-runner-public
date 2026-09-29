from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
USER_ENTRY = REPO_ROOT / "bin" / "vfops-user"


class UserEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="p07-user-entry-"))
        self.root = self.tmp / "vf-server-ops"
        (self.root / "bin").mkdir(parents=True)
        (self.root / "lib").mkdir(parents=True)
        for relative in (
            "bin/vfops-user",
            "bin/vfops-site-ui",
            "bin/vfops-migrate-ui",
            "bin/vfops-auto-backup",
            "bin/vfops-cloudpanel-ui",
        ):
            src = REPO_ROOT / relative
            dst = self.root / relative
            shutil.copy2(src, dst)
            os.chmod(dst, 0o755)
        shutil.copy2(REPO_ROOT / "lib" / "terminal_ui.sh", self.root / "lib" / "terminal_ui.sh")
        (self.root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        (self.root / "BUILD_ID").write_text("0.1.0-release4\n", encoding="utf-8")
        self.log = self.tmp / "core.log"
        self.backups = self.tmp / "backups"
        self.backups.mkdir()
        self.fakebin = self.tmp / "fakebin"
        self.fakebin.mkdir()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self._write_fake_core()
        self.env = os.environ.copy()
        self.env.update(
            {
                "VFOPS_TEST_LOG": str(self.log),
                "VFOPS_BACKUP_DIR": str(self.backups),
                "PATH": f"{self.fakebin}:{self.env.get('PATH','')}",
                "HOME": str(self.home),
                "TERM": "dumb",
            }
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_fake_core(self) -> None:
        core = self.root / "bin" / "vfops"
        core.write_text(
            textwrap.dedent(
                r'''#!/usr/bin/env bash
set -eu
printf '%s\n' "$*" >> "${VFOPS_TEST_LOG:?}"
case "${1:-}" in
  inventory)
    cat <<'JSON'
{"system":{"os":{"pretty_name":"Debian 13"},"cloudpanel_version":"2.x"},"sites":[{"domain":"one.example","runtime":{"type":"php"},"mysql_databases":[],"sqlite_paths":[],"ssl":{"configured":true}}],"summary":{"mysql_database_count_known":0,"sqlite_file_count_known":0}}
JSON
    ;;
  backup)
    package="${VFOPS_BACKUP_DIR}/one.example_backup"
    mkdir -p "$package"
    cat > "$package/manifest.json" <<'JSON'
{"site":{"domain":"one.example"},"backup_id":"one.example_backup","created_at":"2026-09-06T00:00:00+00:00"}
JSON
    cat > "$package/verification.json" <<'JSON'
{"status":"PASS"}
JSON
    printf '%s\n' "$package"
    ;;
  restore)
    case "${2:-}" in
      plan) printf '{"status":"READY"}\n' ;;
      apply-new-site) printf '{"status":"RESTORED"}\n' ;;
      *) exit 2 ;;
    esac
    ;;
  runtime)
    case "${2:-}" in
      plan)
        if [[ "${VFOPS_TEST_RUNTIME_PLAN:-ready}" == "manual" ]]; then
          printf '{"status":"READY_WITH_MANUAL_GATES","manual_cron":[{"reason":"SYSTEM_CRON_REQUIRES_MANUAL_RECONCILIATION"}],"user_crontab":null,"pm2":{"ready":false}}\n'
        else
          printf '{"status":"READY","manual_cron":[],"user_crontab":null,"pm2":{"ready":false}}\n'
        fi
        ;;
      apply-new-site) printf '{"status":"RUNTIME_ACTIVATED"}\n' ;;
      *) exit 2 ;;
    esac
    ;;
  migrate)
    printf '{"status":"TECHNICAL_CUTOVER_READY"}\n'
    ;;
  *)
    exit 2
    ;;
esac
'''
            ),
            encoding="utf-8",
        )
        os.chmod(core, 0o755)

    def _run(self, stdin: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = self.env.copy()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [str(self.root / "bin" / "vfops-user")],
            input=stdin,
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
            check=False,
        )

    def _make_backup(self, name: str = "one.example_backup", verified: bool = True) -> Path:
        package = self.backups / name
        package.mkdir(exist_ok=True)
        (package / "manifest.json").write_text(
            json.dumps(
                {
                    "site": {"domain": "one.example"},
                    "backup_id": name,
                    "created_at": "2026-09-06T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        if verified:
            (package / "verification.json").write_text(
                json.dumps({"status": "PASS"}), encoding="utf-8"
            )
        return package

    def _write_executable(self, name: str, body: str) -> Path:
        path = self.fakebin / name
        path.write_text(body, encoding="utf-8")
        os.chmod(path, 0o755)
        return path

    def _ready_ssh(self) -> None:
        self._write_executable(
            "ssh",
            "#!/usr/bin/env bash\ncase \"$*\" in *P07_SSH_READY*) printf P07_SSH_READY; exit 0;; *) exit 0;; esac\n",
        )

    def test_symlink_entry_resolves_real_root_and_version(self) -> None:
        install_bin = self.tmp / "usr" / "local" / "bin"
        install_bin.mkdir(parents=True)
        link = install_bin / "vfops"
        link.symlink_to(self.root / "bin" / "vfops-user")
        proc = subprocess.run(
            [str(link), "--version"],
            text=True,
            capture_output=True,
            env=self.env,
            timeout=10,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("VF Server Ops 0.1.0", proc.stdout)
        self.assertNotIn("UNKNOWN", proc.stdout)

    def test_site_selection_has_zero_back_and_does_not_backup(self) -> None:
        proc = self._run("2\n0\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("0. 返回", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn("inventory --compact", log)
        self.assertNotIn("backup --site", log)

    def test_backup_success_shows_beginner_result_card(self) -> None:
        proc = self._run("2\n1\ny\n\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("备份完成 ✓", proc.stdout)
        self.assertIn("网站：one.example", proc.stdout)
        self.assertIn("状态：已验证，可恢复", proc.stdout)
        self.assertIn("位置：", proc.stdout)
        self.assertIn("one.example_backup", proc.stdout)

    def test_migration_unreachable_fails_before_backup(self) -> None:
        self._write_executable("ssh", "#!/usr/bin/env bash\necho 'Connection timed out' >&2\nexit 255\n")
        proc = self._run("4\n3\n1\n203.0.113.10\n\n0\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("[1/3] 检查目标服务器", proc.stdout)
        self.assertIn("连接状态：无法连接", proc.stdout)
        self.assertIn("迁移尚未开始，也没有创建迁移备份", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertNotIn("backup --site", log)
        self.assertNotIn("migrate transfer-new-site", log)

    def test_migration_needs_key_setup_is_distinct_and_can_return(self) -> None:
        self._write_executable("ssh", "#!/usr/bin/env bash\necho 'Permission denied (publickey).' >&2\nexit 255\n")
        proc = self._run("4\n3\n1\n203.0.113.10\n0\n0\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("连接状态：需要配置 SSH 密钥", proc.stdout)
        self.assertIn("现在准备源服务器 → 目标服务器 SSH 密钥", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertNotIn("backup --site", log)

    def test_migration_key_setup_rechecks_and_reaches_ready(self) -> None:
        marker = self.tmp / "key-installed"
        ssh = textwrap.dedent(
            f'''#!/usr/bin/env bash
if [[ ! -f "{marker}" ]]; then
  echo 'Permission denied (publickey).' >&2
  exit 255
fi
if printf '%s ' "$@" | grep -q P07_SSH_READY; then
  printf P07_SSH_READY
  exit 0
fi
exit 0
'''
        )
        self._write_executable("ssh", ssh)
        self._write_executable("ssh-copy-id", f"#!/usr/bin/env bash\ntouch '{marker}'\nexit 0\n")
        ssh_dir = self.home / ".ssh"
        ssh_dir.mkdir()
        (ssh_dir / "id_ed25519").write_text("private-placeholder", encoding="utf-8")
        (ssh_dir / "id_ed25519.pub").write_text("public-placeholder", encoding="utf-8")
        proc = self._run("4\n3\n1\n203.0.113.10\n1\nn\n0\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("连接状态：需要配置 SSH 密钥", proc.stdout)
        self.assertIn("SSH 密钥已发送到目标服务器", proc.stdout)
        self.assertIn("连接状态：已就绪", proc.stdout)
        self.assertIn("CloudPanel：已就绪", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertNotIn("backup --site", log)

    def test_migration_target_not_cloudpanel_fails_before_backup(self) -> None:
        self._write_executable(
            "ssh",
            "#!/usr/bin/env bash\ncase \"$*\" in *P07_SSH_READY*) printf P07_SSH_READY; exit 0;; *) exit 43;; esac\n",
        )
        proc = self._run("4\n3\n1\n203.0.113.10\n\n0\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("连接状态：目标服务器未安装 CloudPanel", proc.stdout)
        self.assertIn("没有检测到可用的 CloudPanel", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertNotIn("backup --site", log)

    def test_migration_target_domain_conflict_fails_before_backup(self) -> None:
        self._write_executable(
            "ssh",
            "#!/usr/bin/env bash\ncase \"$*\" in *P07_SSH_READY*) printf P07_SSH_READY; exit 0;; *) exit 42;; esac\n",
        )
        proc = self._run("4\n3\n1\n203.0.113.10\n\n0\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("目标服务器已存在同名网站：one.example", proc.stdout)
        self.assertIn("连接状态：目标服务器存在同名网站", proc.stdout)
        self.assertIn("P07 不会覆盖", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertNotIn("backup --site", log)
        self.assertNotIn("migrate transfer-new-site", log)

    def test_migration_ready_shows_progress_and_dns_boundary(self) -> None:
        self._ready_ssh()
        proc = self._run("4\n3\n1\n203.0.113.10\ny\n\n0\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("[1/3] 检查目标服务器", proc.stdout)
        self.assertIn("[2/3] 创建并验证迁移备份", proc.stdout)
        self.assertIn("[3/3] 正在传输、恢复运行环境并做技术验证", proc.stdout)
        self.assertIn("迁移技术验证完成 ✓", proc.stdout)
        self.assertIn("当前流量：仍在源服务器", proc.stdout)
        self.assertIn("DNS：未修改", proc.stdout)
        self.assertIn("源服务器：保留", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn("backup --site one.example --kind pre_migration", log)
        self.assertIn("migrate transfer-new-site", log)

    def test_unverified_backup_is_hidden_from_beginner_restore(self) -> None:
        self._make_backup("unverified_backup", verified=False)
        proc = self._run("3\n\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        terminal = proc.stdout + proc.stderr
        self.assertIn("没有发现已验证、可恢复的 P07 本地备份", terminal)
        log = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        self.assertNotIn("restore plan", log)

    def test_restore_manual_runtime_gate_is_not_reported_complete(self) -> None:
        self._make_backup()
        proc = self._run("3\n1\n2\ny\n\n0\n", {"VFOPS_TEST_RUNTIME_PLAN": "manual"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("网站数据恢复完成 ✓", proc.stdout)
        self.assertIn("运行环境仍需按原恢复确认流程继续核验", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn("restore plan", log)
        self.assertIn("restore apply-new-site", log)
        self.assertNotIn("runtime apply-new-site", log)

    def test_restore_ready_runtime_continues_to_complete(self) -> None:
        self._make_backup()
        proc = self._run("3\n1\n2\ny\n\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("网站数据恢复完成 ✓", proc.stdout)
        self.assertIn("DNS：未修改", proc.stdout)
        log = self.log.read_text(encoding="utf-8")
        self.assertIn("restore apply-new-site", log)
        self.assertNotIn("runtime apply-new-site", log)

    def test_friendly_failure_hides_raw_engineering_body(self) -> None:
        core = self.root / "bin" / "vfops"
        original = core.read_text(encoding="utf-8")
        core.write_text(
            original.replace(
                "printf '%s\\n' \"$package\"",
                "printf 'raw-private-looking-detail should-not-surface\\n' >&2; printf 'VFOPS_DIAGNOSTIC_V1 stage=BACKUP error_class=BACKUP_ERROR blocker=FRESH_VERIFY_NOT_PASS cleanup=NOT_REPORTED exit_code=4\\n' >&2; exit 4",
                1,
            ),
            encoding="utf-8",
        )
        os.chmod(core, 0o755)
        proc = self._run("2\n1\ny\n\n0\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("备份完整性检查没有通过", proc.stdout)
        self.assertIn("阶段：BACKUP", proc.stdout)
        self.assertNotIn("raw-private-looking-detail", proc.stdout)


if __name__ == "__main__":
    unittest.main()
