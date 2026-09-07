from __future__ import annotations

import configparser
import importlib.util
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

RUNTIME = Path(os.environ.get("P07_RC3_RUNTIME", "/tmp/p07-rc3"))
SETUP_SOURCE = RUNTIME / "bin" / "vfops-storage-setup"
OAUTH_SOURCE = RUNTIME / "lib" / "google_device_oauth.py"

if os.geteuid() != 0 and os.environ.get("P07_GUIDED_TEST_SUDO") != "1":
    env = os.environ.copy()
    env["P07_GUIDED_TEST_SUDO"] = "1"
    os.execvpe("sudo", ["sudo", "-E", sys.executable, *sys.argv], env)


class GuidedRemoteInitTests(unittest.TestCase):
    def test_google_device_oauth_contract_without_network(self) -> None:
        spec = importlib.util.spec_from_file_location("p07_google_oauth", OAUTH_SOURCE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

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
            self.assertIn("Recovery Key 未通过确认", proc.stdout + proc.stderr)
            self.assertEqual((state / "rclone.conf").read_text(encoding="utf-8"), old_rclone)
            self.assertEqual((state / "storage.json").read_text(encoding="utf-8"), old_storage)


if __name__ == "__main__":
    unittest.main()
