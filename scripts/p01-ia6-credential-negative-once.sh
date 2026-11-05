#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "P01_CREDENTIAL_FIXTURE_SCRIPT_EXIT=FAIL_LINE_$LINENO"' ERR
test "$#" -eq 1
candidate="$(cd "$1" && pwd)"
test -f "$candidate/src/update-credential.php"
test "${P01_TEST_ORIGIN:-}" = "http://127.0.0.1:18631"
work="$(mktemp -d /tmp/p01-ia6-credential-negative-XXXXXXXX)"
pid=''
cleanup() {
  if test -n "$pid"; then kill "$pid" >/dev/null 2>&1 || :; wait "$pid" 2>/dev/null || :; fi
  rm -rf "$work"
}
trap cleanup EXIT
cp -a "$candidate/src/." "$work/"
echo P01_CREDENTIAL_FIXTURE_SOURCE=PASS
php -S 127.0.0.1:18631 -t "$work" >"$work/server.log" 2>&1 &
pid="$!"
ready=0
for i in $(seq 1 40); do
  if curl -fsS --max-time 2 "$P01_TEST_ORIGIN/setup.php" -o "$work/setup.html" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 0.25
done
test "$ready" = 1
echo P01_CREDENTIAL_FIXTURE_SETUP_GET=PASS
csrf="$(python3 - "$work/setup.html" <<'PY'
import pathlib,re,sys
html=pathlib.Path(sys.argv[1]).read_text()
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',html)
assert m
print(m.group(1))
PY
)"
curl -fsS -c "$work/cookie" -b "$work/cookie" -X POST "$P01_TEST_ORIGIN/setup.php" \
  --data-urlencode "setup_csrf=$csrf" \
  --data-urlencode "site_title=P01 Synthetic Credential Fallback" \
  --data-urlencode "admin_password=P01SyntheticRecovery2026!" \
  --data-urlencode "admin_password_confirm=P01SyntheticRecovery2026!" \
  -o "$work/installed.html"
if ! test -f "$work/app/.runtime.php"; then
  echo P01_CREDENTIAL_FIXTURE_RUNTIME_MISSING
  echo "P01_CREDENTIAL_FIXTURE_SETUP_RESPONSE_TITLE=$(grep -o "<title>[^<]*" "$work/installed.html" | head -1 || :)"
  exit 1
fi
echo P01_CREDENTIAL_FIXTURE_INSTALL=PASS
echo P01_CREDENTIAL_FIXTURE_BROWSER_BEGIN
P01_TEST_PASSWORD=P01SyntheticRecovery2026! \
  node scripts/p01-ia6-credential-failure-once.cjs "$candidate"
(cd "$work" && php cli/verify.php) | grep -Fx VERIFY_PASS=YES
echo P01_IA6_CREDENTIAL_INVALID_TOKEN_ROLLBACK_DISPOSABLE=PASS
