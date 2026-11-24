#!/usr/bin/env python3
"""Actual P07 rsync/SSH pull against ONLY isolated synthetic localhost files.

Uses real P07-M03-D04 server_migration_pull.pull_path from exact private SHA.
Never opens CloudPanel or connects to owner or external networks.
"""
from __future__ import annotations

import getpass
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time


def sh(args: list[str], *, timeout: int = 35) -> bool:
    try:
        proc = subprocess.run(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout, check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def checked(args: list[str], code: str) -> None:
    if not sh(args, timeout=45):
        raise RuntimeError(code)


def hash_files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def main() -> None:
    product = Path(sys.argv[1]).resolve(strict=True)
    assert product.name == ".p07-private" and (product / "lib/server_migration_pull.py").is_file()
    sys.path.insert(0, str(product / "lib"))
    import server_migration_pull as pull

    if not (shutil.which("sshd") and shutil.which("ssh")
            and shutil.which("rsync") and shutil.which("ssh-keygen")):
        raise RuntimeError("HOSTED_SSH_OR_RSYNC_MISSING")

    uid_name = getpass.getuser()
    with tempfile.TemporaryDirectory(prefix="p07-transport-synthetic-") as td:
        root = Path(td)
        private_key = root / "client_ed25519"
        host_key = root / "host_ed25519"
        checked(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f",
                 str(private_key)], "CLIENT_KEY_GENERATION_FAILED")
        checked(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f",
                 str(host_key)], "HOST_KEY_GENERATION_FAILED")
        (root / "authorized_keys").write_text(
            (root / "client_ed25519.pub").read_text(encoding="ascii"),
            encoding="ascii",
        )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        known_hosts = root / "known_hosts"
        known_hosts.write_text(
            f"[127.0.0.1]:{port} " +
            (root / "host_ed25519.pub").read_text(encoding="ascii"),
            encoding="ascii",
        )
        wrapper = root / "ssh-wrapper"
        wrapper.write_text(
            "#!/bin/sh\nexec /usr/bin/ssh -o IdentitiesOnly=yes "
            "-o IdentityAgent=none "
            "-o GlobalKnownHostsFile=/dev/null "
            "-o UserKnownHostsFile=" + shlex.quote(str(known_hosts)) +
            ' "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        config = root / "sshd_config"
        config.write_text(
            f"Port {port}\nListenAddress 127.0.0.1\n"
            f"HostKey {host_key}\nAuthorizedKeysFile {root / 'authorized_keys'}\n"
            f"PidFile {root / 'sshd.pid'}\n"
            f"AllowUsers {uid_name}\n"
            "PermitRootLogin no\nPasswordAuthentication no\n"
            "KbdInteractiveAuthentication no\nPubkeyAuthentication yes\n"
            "StrictModes no\nUsePAM yes\nLogLevel QUIET\n"
            "Subsystem sftp internal-sftp\n",
            encoding="utf-8",
        )
        source_home = root / "synthetic-source"
        fake_site = source_home / "htdocs" / "site example.test"
        (fake_site / "assets").mkdir(parents=True)
        (fake_site / "index.html").write_text(
            "<title>synthetic-local-only</title>", encoding="utf-8"
        )
        (fake_site / "assets" / "hello world.txt").write_bytes(b"site-asset-123")
        (fake_site / "secret-config.php").write_bytes(b"synthetic-secret-fixture")
        marker = fake_site / "single-marker.txt"
        marker.write_text("synthetic-file-object", encoding="utf-8")
        expected_source = hash_files(source_home)

        source = {
            "host": "127.0.0.1", "ssh_user": uid_name, "ssh_port": port,
            "identity_file": str(private_key), "ssh": str(wrapper),
        }
        os.environ["VFOPS_MIGRATION_PROGRESS"] = "0"
        server = None
        try:
            server = subprocess.Popen(
                ["sudo", "/usr/sbin/sshd", "-D", "-e", "-f", str(config)],
                stdout=subprocess.DEVNULL, stderr=(root / "daemon.log").open("wb"),
            )
            for _ in range(20):
                if server.poll() is not None:
                    raise RuntimeError("SSHD_START_FAILED")
                if sh([str(wrapper), "-p", str(port), "-i", str(private_key),
                       "-o", "BatchMode=yes", f"{uid_name}@127.0.0.1", "true"],
                      timeout=4):
                    break
                time.sleep(0.3)
            else:
                raise RuntimeError("SSH_KEY_ONLY_LOGIN_FAILED")
            print("P07_M03_REAL_SSH_KEY_ONLY_LOGIN=PASS", flush=True)

            dest = root / "synthetic-receiver"
            dest.mkdir()
            pull.pull_path(source, str(fake_site) + "/", dest, delete=False)
            assert (dest / "index.html").read_bytes() == (fake_site / "index.html").read_bytes()
            assert (dest / "assets" / "hello world.txt").read_bytes() == b"site-asset-123"
            print("P07_M03_REAL_RSYNC_DIRECTORY_CONTENTS=PASS", flush=True)

            extra = dest / "receiver-only.txt"
            extra.write_text("preserve", encoding="utf-8")
            pull.pull_path(source, str(fake_site) + "/", dest, delete=False)
            assert extra.read_text(encoding="utf-8") == "preserve"
            print("P07_M03_REAL_RSYNC_NO_DELETE_PRESERVES_RECEIVER=PASS", flush=True)

            pull.pull_path(source, str(fake_site) + "/", dest, delete=True)
            assert not extra.exists()
            assert (dest / "index.html").is_file()
            print("P07_M03_REAL_RSYNC_FINAL_DELETE_ONLY_RECEIVER=PASS", flush=True)

            single = root / "single-file-dest"
            pull.pull_path(source, str(marker), single)
            assert single.is_file() and single.read_text(encoding="utf-8") == "synthetic-file-object"
            print("P07_M03_REAL_RSYNC_FILE_SOURCE_NO_TRAILING_SLASH=PASS", flush=True)

            excluded = root / "excluded-receiver"
            excluded.mkdir()
            pull.pull_path(source, str(fake_site) + "/", excluded,
                           excludes=("secret-config.php",))
            assert (excluded / "index.html").is_file()
            assert not (excluded / "secret-config.php").exists()
            print("P07_M03_REAL_RSYNC_PROTECTED_EXCLUDE=PASS", flush=True)

            from server_migration_pull import PullMigrationError
            bad_dest = root / "invalid-source-receiver"
            try:
                pull.pull_path(source, "../relative", bad_dest)
            except PullMigrationError:
                assert not bad_dest.exists()
            else:
                raise RuntimeError("RELATIVE_REMOTE_PATH_NOT_REJECTED")
            print("P07_M03_RELATIVE_REMOTE_PATH_NO_WRITE=PASS", flush=True)

            other = root / "wrong_ed25519"
            checked(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f",
                     str(other)], "NEGATIVE_KEY_GENERATION_FAILED")
            wrong = dict(source, identity_file=str(other))
            rejected = root / "wrong-key-receiver"
            try:
                pull.pull_path(wrong, str(fake_site) + "/", rejected)
            except PullMigrationError:
                assert not rejected.exists() or not list(rejected.iterdir())
            else:
                raise RuntimeError("WRONG_IDENTITY_NOT_REJECTED")
            print("P07_M03_REAL_SSH_WRONG_IDENTITY_REFUSED=PASS", flush=True)

            assert hash_files(source_home) == expected_source
            print("P07_M03_REAL_SSH_SOURCE_FILE_BYTES_UNCHANGED=PASS", flush=True)
            print("P07_M03_REAL_TRANSPORT_ISOLATED_PASS=8", flush=True)
        finally:
            try:
                pid_path = root / "sshd.pid"
                if pid_path.is_file():
                    pid = int(pid_path.read_text().strip())
                    sh(["sudo", "kill", str(pid)], timeout=12)
                if server is not None and server.poll() is None:
                    server.terminate()
                    server.wait(timeout=8)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
    print("P07_M03_SYNTHETIC_DISK_AND_SSH_KEYS_CLEANUP=PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("P07_M03_REAL_TRANSPORT_BLOCK_CLASS=" + type(exc).__name__)
        raise SystemExit(37)
