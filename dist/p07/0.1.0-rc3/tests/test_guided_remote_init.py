from __future__ import annotations

import configparser
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

RUNTIME = Path(os.environ.get("P07_RC3_RUNTIME", "/tmp/p07-rc3"))
SETUP_SOURCE = RUNTIME / "bin" / "vfops-storage-setup"
OAUTH_SOURCE = RUNTIME / "lib" / "google_device_oauth.py"

if os.geteuid() != 0 and os.environ.get("P07_GUIDED_TEST_SUDO") != "1":
    env = os.environ.copy()
    env["P07_GUIDED_TEST_SUDO"] = "1"
    os.execvpe("sudo", ["sudo", "-E", sys.executable, *sys.argv], env)


class GuidedRemoteInitTests(unittest.TestCase):
    def _oauth_module(self):
        spec = importlib.util.spec_from_file_location("p07_google_oauth", OAUTH_SOURCE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_google_device_oauth_contract_without_network(self) -> None:
        module = self._oauth_module()

        class Response:
            def __init__(self, payload: dict[str, object]) -> None:
                self.raw = json.dumps(payload).encode()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return self.raw

        def fake_urlopen(req, timeout=20):
            body = (req.data or b"").decode()
            if req.full_url == module.DEVICE_ENDPOINT:
                self.assertIn("client_id=P07_SYNTH_CLIENT", body)
                self.assertIn("drive.file", body)
                return Response({
                    "device_code": "SYNTH_DEVICE_SECRET",
                    "user_code": "P07-TEST",
                    "verification_url": "https://www.google.com/device",
                    "expires_in": 30,
                    "interval": 1,
                })
            if req.full_url == module.TOKEN_ENDPOINT:
                self.assertIn("client_secret=P07_SYNTH_CLIENT_SECRET", body)
                self.assertIn("device_code=SYNTH_DEVICE_SECRET", body)
                return Response({
                    "access_token": "SYNTH_ACCESS_SECRET",
                    "refresh_token": "SYNTH_REFRESH_SECRET",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                })
            raise AssertionError(req.full_url)

        module.urllib.request.urlopen = fake_urlopen
        token = module.authorize("P07_SYNTH_CLIENT", "P07_SYNTH_CLIENT_SECRET")
        self.assertEqual(token["access_token"], "SYNTH_ACCESS_SECRET")
        self.assertEqual(token["refresh_token"], "SYNTH_REFRESH_SECRET")

    def test_google_oauth_failure_ux_and_slow_down_without_network(self) -> None:
        module = self._oauth_module()
        expected = {
            "access_denied": "已被拒绝",
            "expired_token": "已过期",
            "invalid_client": "Client ID / Secret",
            "unauthorized_client": "TVs and Limited Input devices",
            "invalid_grant": "已经失效",
            "temporarily_unavailable": "暂时不可用",
        }
        for code, text in expected.items():
            with self.subTest(code=code):
                message = module.friendly_oauth_error(code)
                self.assertIn(text, message)
                self.assertIn("没有修改配置", message)

        device = {
            "device_code": "SYNTH_DEVICE_SECRET",
            "user_code": "P07-TEST",
            "verification_url": "https://www.google.com/device",
            "expires_in": 30,
            "interval": 1,
        }
        success = {
            "access_token": "SYNTH_ACCESS_SECRET",
            "refresh_token": "SYNTH_REFRESH_SECRET",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        stderr = io.StringIO()
        with mock.patch.object(module, "post_form", side_effect=[device, {"error": "slow_down"}, success]), \
             mock.patch.object(module.time, "monotonic", side_effect=[100.0, 100.0, 100.0]), \
             mock.patch.object(module.time, "sleep") as sleep, \
             contextlib.redirect_stderr(stderr):
            token = module.authorize("P07_SYNTH_CLIENT", "P07_SYNTH_CLIENT_SECRET")
        self.assertEqual(token["refresh_token"], "SYNTH_REFRESH_SECRET")
        sleep.assert_called_once_with(6)
        self.assertIn("已自动放慢等待", stderr.getvalue())

        with mock.patch.object(module, "post_form", return_value={**device, "expires_in": 1}), \
             mock.patch.object(module.time, "monotonic", side_effect=[10.0, 12.0]):
            with self.assertRaises(module.OAuthError) as ctx:
                module.authorize("P07_SYNTH_CLIENT", "P07_SYNTH_CLIENT_SECRET")
        self.assertIn("超时", str(ctx.exception))
        self.assertIn("重新进入初始化", str(ctx.exception))

    def _app(self, root: Path) -> tuple[Path, Path, dict[str, str]]:
        app = root / "app"
        fakebin = root / "fakebin"
        state = root / "state"
        (app / "bin").mkdir(parents=True)
        (app / "lib").mkdir(parents=True)
        fakebin.mkdir()
        state.mkdir()
        shutil.copy2(SETUP_SOURCE, app / "bin" / "vfops-storage-setup")
        os.chmod(app / "bin" / "vfops-storage-setup", 0o755)

        (app / "lib" / "google_device_oauth.py").write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import json,sys
            secret=sys.stdin.readline().rstrip('\\r\\n')
            assert sys.argv[1:]==['--client-id','P07_SYNTH_CLIENT']
            assert secret=='P07_SYNTH_CLIENT_SECRET'
            print('Google 官方浏览器授权', file=sys.stderr)
            print('1. 打开：https://www.google.com/device', file=sys.stderr)
            print('2. 输入一次性代码：P07-TEST', file=sys.stderr)
            print(json.dumps({
                'access_token':'SYNTH_ACCESS_SECRET',
                'refresh_token':'SYNTH_REFRESH_SECRET',
                'token_type':'Bearer',
                'expiry':'2026-09-07T23:59:59Z',
            }))
        """), encoding="utf-8")
        (app / "lib" / "storage_setup.py").write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import argparse,json,os,sys
            if len(sys.argv)>1 and sys.argv[1]=='inspect':
                print(json.dumps({'remotes':[]})); raise SystemExit(0)
            p=argparse.ArgumentParser(); p.add_argument('cmd'); p.add_argument('--config')
            p.add_argument('--google-direct'); p.add_argument('--google-crypt'); p.add_argument('--b2-crypt')
            a=p.parse_args(); os.makedirs(os.path.dirname(a.config),exist_ok=True)
            with open(a.config,'w',encoding='utf-8') as f: json.dump({'schema':'vf-server-ops.storage-config.v1'},f)
            os.chmod(a.config,0o600); print('{}')
        """), encoding="utf-8")
        (app / "bin" / "vfops").write_text(textwrap.dedent("""\
            #!/usr/bin/env bash
            cat <<'JSON'
            {"accounts":[{"provider":"google","enabled":true,"health":"OK"},{"provider":"b2","enabled":true,"health":"OK"}]}
            JSON
        """), encoding="utf-8")
        os.chmod(app / "bin" / "vfops", 0o755)

        (fakebin / "rclone").write_text(textwrap.dedent("""\
            #!/usr/bin/env bash
            set -euo pipefail
            case "${1:-}" in
              config)
                if [[ "${2:-}" == file ]]; then printf 'Configuration file is stored at:\\n%s\\n' "$P07_TEST_RCLONE"; exit 0; fi
                ;;
              listremotes)
                [[ -f "$P07_TEST_RCLONE" ]] && awk '/^\\[/{gsub(/[\\[\\]]/,"",$0); print $0":"}' "$P07_TEST_RCLONE" || true
                exit 0;;
              obscure)
                read -r s; printf 'OBSCURED_%s\\n' "$(printf '%s' "$s" | sha256sum | awk '{print $1}')"; exit 0;;
              about) printf '{}\\n'; exit 0;;
              backend) printf 'encoded\\n'; exit 0;;
              lsf) printf 'p07-backups/\\n'; exit 0;;
            esac
            exit 0
        """), encoding="utf-8")
        os.chmod(fakebin / "rclone", 0o755)
        env = os.environ.copy()
        env["PATH"] = f"{fakebin}:{env['PATH']}"
        env["P07_TEST_RCLONE"] = str(state / "rclone.conf")
        env["VFOPS_STORAGE_CONFIG"] = str(state / "storage.json")
        return app, state, env

    def test_fresh_init_creates_fixed_remotes_without_secret_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-guided-init-") as td:
            app, state, env = self._app(Path(td))
            recovery = "P07_SYNTH_RECOVERY_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            user_input = "\n".join([
                "1", "1", recovery, recovery,
                "P07_SYNTH_CLIENT", "P07_SYNTH_CLIENT_SECRET",
                "B2_SYNTH_ACCOUNT", "B2_SYNTH_SECRET", "", "0", "",
            ])
            proc = subprocess.run(
                ["bash", str(app / "bin" / "vfops-storage-setup")],
                input=user_input, text=True, capture_output=True, env=env, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            output = proc.stdout + proc.stderr
            self.assertIn("远程备份初始化完成", output)
            self.assertIn("https://www.google.com/device", output)
            self.assertIn("SOURCE：保留", output)
            for secret in [recovery, "P07_SYNTH_CLIENT_SECRET", "B2_SYNTH_SECRET", "SYNTH_ACCESS_SECRET", "SYNTH_REFRESH_SECRET"]:
                self.assertNotIn(secret, output)

            cfg = configparser.RawConfigParser(interpolation=None)
            cfg.read(state / "rclone.conf", encoding="utf-8")
            self.assertEqual(set(cfg.sections()), {"p07-google", "p07-google-crypt", "p07-b2", "p07-b2-crypt"})
            self.assertEqual(cfg["p07-google"]["scope"], "drive.file")
            self.assertEqual(cfg["p07-google"]["client_id"], "P07_SYNTH_CLIENT")
            self.assertTrue(cfg["p07-google"]["client_secret"].startswith("OBSCURED_"))
            self.assertEqual(cfg["p07-google-crypt"]["remote"], "p07-google:VF-Server-Ops")
            self.assertEqual(cfg["p07-b2-crypt"]["remote"], "p07-b2:p07-backups/VF-Server-Ops")
            self.assertEqual(stat.S_IMODE((state / "rclone.conf").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((state / "storage.json").stat().st_mode), 0o600)
            for path in state.rglob("*"):
                if path.is_file(): self.assertNotIn(recovery, path.read_text(encoding="utf-8"))

    def test_recovery_mismatch_rolls_back_without_p07_remote(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-guided-rollback-") as td:
            app, state, env = self._app(Path(td))
            old_rclone = "[legacy]\ntype = local\n"
            old_storage = "OLD_STORAGE\n"
            (state / "rclone.conf").write_text(old_rclone, encoding="utf-8")
            (state / "storage.json").write_text(old_storage, encoding="utf-8")
            recovery = "P07_SYNTH_RECOVERY_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            different = "DIFFERENT_RECOVERY_KEY_0123456789_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            user_input = "\n".join(["1", "1", recovery, different, "", "0", ""])
            proc = subprocess.run(
                ["bash", str(app / "bin" / "vfops-storage-setup")],
                input=user_input, text=True, capture_output=True, env=env, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("两次 Recovery Key 不一致", proc.stdout + proc.stderr)
            self.assertEqual((state / "rclone.conf").read_text(encoding="utf-8"), old_rclone)
            self.assertEqual((state / "storage.json").read_text(encoding="utf-8"), old_storage)

    def test_current_settings_reports_health_and_next_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-guided-status-") as td:
            app, state, env = self._app(Path(td))
            (state / "rclone.conf").write_text("[legacy]\ntype = local\n", encoding="utf-8")
            (state / "storage.json").write_text("{}\n", encoding="utf-8")
            user_input = "\n".join(["3", "", "0", ""])
            proc = subprocess.run(
                ["bash", str(app / "bin" / "vfops-storage-setup")],
                input=user_input, text=True, capture_output=True, env=env, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            output = proc.stdout + proc.stderr
            self.assertIn("P07 远程备份健康状态", output)
            self.assertIn("Google：READY", output)
            self.assertIn("B2：READY", output)
            self.assertIn("建议先“立即完整备份一次”", output)

    def test_import_second_install_failure_restores_existing_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p07-guided-import-atomic-") as td:
            root = Path(td)
            app, state, env = self._app(root)
            fakebin = root / "fakebin"
            source = root / "source"
            source.mkdir()
            source_rclone = "[p07-google]\ntype = drive\ntoken = SYNTH_SOURCE_TOKEN\n"
            source_storage = '{"schema":"vf-server-ops.storage-config.v1","marker":"SYNTH_SOURCE_STORAGE"}\n'
            (source / "rclone.conf").write_text(source_rclone, encoding="utf-8")
            (source / "storage.json").write_text(source_storage, encoding="utf-8")

            (fakebin / "ssh").write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                set -euo pipefail
                args="$*"
                if [[ "$args" == *'printf P07_SOURCE_READY'* ]]; then printf 'P07_SOURCE_READY'; exit 0; fi
                if [[ "$args" == *'rclone config file'* ]]; then printf '/root/.config/rclone/rclone.conf\\n'; exit 0; fi
                if [[ "$args" == *'test -s'* ]]; then exit 0; fi
                exit 0
            """), encoding="utf-8")
            (fakebin / "scp").write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                set -euo pipefail
                src="${@: -2:1}"; dst="${@: -1}"
                if [[ "$src" == *'rclone.conf' ]]; then cp "$P07_TEST_SOURCE/rclone.conf" "$dst"; else cp "$P07_TEST_SOURCE/storage.json" "$dst"; fi
            """), encoding="utf-8")
            (fakebin / "install").write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                set -euo pipefail
                count=0
                [[ -f "$P07_TEST_INSTALL_COUNT" ]] && count="$(cat "$P07_TEST_INSTALL_COUNT")"
                count=$((count+1)); printf '%s' "$count" > "$P07_TEST_INSTALL_COUNT"
                if [[ "$count" -eq 2 ]]; then exit 44; fi
                exec /usr/bin/install "$@"
            """), encoding="utf-8")
            for name in ["ssh", "scp", "install"]:
                os.chmod(fakebin / name, 0o755)

            old_rclone = "OLD_TARGET_RCLONE\n"
            old_storage = "OLD_TARGET_STORAGE\n"
            (state / "rclone.conf").write_text(old_rclone, encoding="utf-8")
            (state / "storage.json").write_text(old_storage, encoding="utf-8")
            env["P07_TEST_SOURCE"] = str(source)
            env["P07_TEST_INSTALL_COUNT"] = str(root / "install.count")

            proc = subprocess.run(
                ["bash", str(app / "bin" / "vfops-storage-setup")],
                input="\n".join(["2", "192.0.2.10", "", "0", ""]),
                text=True, capture_output=True, env=env, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            output = proc.stdout + proc.stderr
            self.assertIn("TARGET P07 storage 配置安装失败，正在恢复安装前配置", output)
            self.assertEqual((state / "rclone.conf").read_text(encoding="utf-8"), old_rclone)
            self.assertEqual((state / "storage.json").read_text(encoding="utf-8"), old_storage)
            self.assertNotIn("SYNTH_SOURCE_TOKEN", output)
            self.assertNotIn("SYNTH_SOURCE_STORAGE", output)


if __name__ == "__main__":
    unittest.main()
