#!/bin/bash
# P07-M03 website/data D04 migration: true SSH + two independent MariaDB
# engines, on disposable GitHub Hosted only. No CloudPanel, real VPS or DNS.
set -Eeuo pipefail
set +x
P="$(realpath "$1")"
test "$(basename "$P")" = ".p07-private"
test -f "$P/tests/test_p07_m03_d04_same_engine_site_integration.py"
command -v docker >/dev/null
docker info >/dev/null
command -v ssh-keygen >/dev/null
command -v rsync >/dev/null
base="p07combo-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
echo "$base" > "$RUNNER_TEMP/p07-combined-base"
# Build SSH fixture before SQL containers so setup failures never masquerade as
# P07 data migration failures, and avoid installing packages during SSH boot.
command -v docker >/dev/null
docker pull -q ubuntu:24.04 >/dev/null
ssh-keygen -q -t ed25519 -N '' -f "$RUNNER_TEMP/p07-combined-ssh-key"
chmod 600 "$RUNNER_TEMP/p07-combined-ssh-key"
build="$RUNNER_TEMP/p07-combined-build"
mkdir -p "$build"
cat > "$build/Dockerfile" <<'DOCKER'
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    openssh-server openssh-client python3 rsync tar ca-certificates passwd \
    >/dev/null 2>&1 && rm -rf /var/lib/apt/lists/*
DOCKER
if ! docker build --quiet "$build" \
  > "$RUNNER_TEMP/p07-combined-image-id" \
  2> "$RUNNER_TEMP/p07-combined-build.log"; then
  echo P07_SSH_FIXTURE_IMAGE_BUILD=FAIL
  exit 45
fi
image="$(cat "$RUNNER_TEMP/p07-combined-image-id")"
test -n "$image"
rm -rf -- "$build"
docker run -d --name p07-d04-ssh-source \
  --publish 127.0.0.1:22287:22 \
  --mount "type=bind,src=$RUNNER_TEMP/p07-combined-ssh-key.pub,dst=/tmp/p07-authorized-keys,readonly" \
  "$image" bash -ec '
    install -d -m 0700 /root/.ssh /run/sshd
    install -m 0600 /tmp/p07-authorized-keys /root/.ssh/authorized_keys
    passwd -d root >/dev/null
    ssh-keygen -A >/dev/null 2>&1
    /usr/sbin/sshd -t
    exec /usr/sbin/sshd -D -e \
      -o UsePAM=no -o PermitRootLogin=prohibit-password \
      -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
      -o PubkeyAuthentication=yes -o AllowUsers=root
  ' >/dev/null
running="$(docker inspect --format '{{.State.Running}}' p07-d04-ssh-source 2>/dev/null || true)"
test "$running" = true || {
 echo P07_SSH_FIXTURE_DAEMON_NOT_RUNNING
 exit 46
}
# Pin the throwaway container's actual host key; never trust arbitrary network
# keys and never log the temporary private identity.
docker exec p07-d04-ssh-source cat /etc/ssh/ssh_host_ed25519_key.pub \
  > "$RUNNER_TEMP/p07-combined-hostkey.pub"
test -s "$RUNNER_TEMP/p07-combined-hostkey.pub"
printf '[127.0.0.1]:22287 %s\n' \
  "$(cat "$RUNNER_TEMP/p07-combined-hostkey.pub")" \
  > "$RUNNER_TEMP/p07-combined-known-hosts"
mkdir -p "$RUNNER_TEMP/p07-combined-bin"
cat > "$RUNNER_TEMP/p07-combined-bin/ssh" <<'SH'
#!/bin/sh
exec /usr/bin/ssh -o GlobalKnownHostsFile=/dev/null \
  -o UserKnownHostsFile="$RUNNER_TEMP/p07-combined-known-hosts" \
  -o IdentitiesOnly=yes -o IdentityAgent=none "$@"
SH
chmod 700 "$RUNNER_TEMP/p07-combined-bin/ssh"
export PATH="$RUNNER_TEMP/p07-combined-bin:$PATH"
ok=0
for trial in $(seq 1 24); do
  if ssh -i "$RUNNER_TEMP/p07-combined-ssh-key" \
      -p 22287 -o BatchMode=yes -o StrictHostKeyChecking=yes \
      -o ConnectTimeout=2 root@127.0.0.1 true >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
if test "$ok" != 1; then
  docker logs p07-d04-ssh-source \
    > "$RUNNER_TEMP/p07-combined-sshd.log" 2>&1 || true
  if grep -iqE 'account is locked|User root not allowed' "$RUNNER_TEMP/p07-combined-sshd.log"; then
    reason=ROOT_ACCOUNT_LOCKED
  elif grep -iqE 'Failed publickey|Permission denied|Authentication refused' "$RUNNER_TEMP/p07-combined-sshd.log"; then
    reason=PUBLIC_KEY_AUTH_DENIED
  elif grep -iqE 'Could not load host key|no hostkeys available' "$RUNNER_TEMP/p07-combined-sshd.log"; then
    reason=HOST_KEY_UNAVAILABLE
  elif grep -iqE 'Server listening' "$RUNNER_TEMP/p07-combined-sshd.log"; then
    reason=SSH_RUNNING_AUTH_UNVERIFIED
  else
    reason=SSH_CONTAINER_UNKNOWN
  fi
  echo "P07_SSH_FIXTURE_FAILURE_CLASS=$reason"
  exit 47
fi
echo P07_M03_COMBINED_REAL_SSH_SOURCE=PASS
docker pull -q mariadb:11.8 >/dev/null
mdb_id="$(docker image inspect mariadb:11.8 --format '{{.Id}}')"
test -n "$mdb_id"
for side in source target; do
  docker run -d --name "$base-$side" -e MARIADB_ROOT_PASSWORD=SYNTHETIC_ci_root_2026 "$mdb_id" >/dev/null
done
for side in source target; do
  ready=0
  for i in $(seq 1 90); do
    if docker exec -e MYSQL_PWD=SYNTHETIC_ci_root_2026 "$base-$side" \
      mariadb --user=root --batch --skip-column-names \
      --execute 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
    sleep 2
  done
  test "$ready" = 1 || { echo P07_COMBINED_MARIADB_NOT_READY; exit 35; }
done
a="$(docker exec -e MYSQL_PWD=SYNTHETIC_ci_root_2026 "$base-source" \
  mariadb --user=root --batch --skip-column-names \
  --execute 'SELECT @@version,@@version_comment')"
b="$(docker exec -e MYSQL_PWD=SYNTHETIC_ci_root_2026 "$base-target" \
  mariadb --user=root --batch --skip-column-names \
  --execute 'SELECT @@version,@@version_comment')"
test "$a" = "$b"
case "$a" in 11.8.*MariaDB*) ;; *) echo P07_COMBINED_ENGINE_MISMATCH; exit 36;; esac
echo P07_M03_COMBINED_TWO_ISOLATED_MARIADB118=PASS
test ! -e /home/p07native
sudo install -d -m 0700 -o "$(id -u)" -g "$(id -g)" /home/p07native/htdocs
echo yes > "$RUNNER_TEMP/p07-combined-created-home"
export P07_NATIVE_DB_ENGINE=MARIADB_11.8
export P07_NATIVE_DB_CONTAINER="$base"
export P07_D04_COMBINED_CI=1
export P07_D04_SSH_PRIVATE_KEY="$RUNNER_TEMP/p07-combined-ssh-key"
export PYTHONDONTWRITEBYTECODE=1
cd "$P"
if ! python3 -B -m unittest -v tests.test_p07_m03_d04_same_engine_site_integration \
    > "$RUNNER_TEMP/p07-combined-test.log" 2>&1; then
   python3 -B - <<'PY'
import pathlib,re,os,hashlib
txt=pathlib.Path(os.environ["RUNNER_TEMP"],"p07-combined-test.log").read_text(errors="replace")
names=re.findall(r"^(?:FAIL|ERROR): (test_[A-Za-z0-9_]+)",txt,re.M)
for name in sorted(set(names))[:5]:
 print("P07_COMBINED_FAILURE_TEST_HASH="+hashlib.sha256(name.encode()).hexdigest()[:16])
types=re.findall(r"\b(?:AssertionError|RuntimeError|FileNotFoundError|PermissionError|TimeoutExpired|PullMigrationError|SourceSnapshotBlocked)\b",txt)
print("P07_COMBINED_FAILURE_KINDS="+",".join(sorted(set(types))))
PY
   echo P07_M03_COMBINED_INTEGRATION=FAIL
   exit 38
fi
if ! grep -q 'Ran 2 tests' "$RUNNER_TEMP/p07-combined-test.log"; then
  echo P07_COMBINED_TEST_DISCOVERY_FAILED; exit 39
fi
if ! grep -q '^OK$' "$RUNNER_TEMP/p07-combined-test.log"; then
  echo P07_COMBINED_NO_COMPLETE_OK; exit 40
fi
echo P07_M03_COMBINED_REAL_SQL_SSH_HTTP_POSITIVE=PASS
echo P07_M03_COMBINED_CORRUPT_SQL_NO_IMPORT_NEGATIVE=PASS
echo P07_M03_COMBINED_2_TESTS=PASS
echo P07_M03_COMBINED_SOURCE_TLS_OR_DUAL_CLOUDPANEL=NOT_RUN
echo P07_M03_COMBINED_PRODUCTION=UNTOUCHED
