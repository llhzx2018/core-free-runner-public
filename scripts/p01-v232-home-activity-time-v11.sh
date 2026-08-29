#!/usr/bin/env bash
set -Eeuo pipefail
: "${PRODUCT:?}"; : "${ROOT:?}"; : "${EVID:?}"; : "${SOURCE:?}"; : "${SOURCE_TREE:?}"; : "${DEVELOP_SOURCE:?}"; : "${ADMIN_PASS:?}"
mkdir -p "$EVID"

test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$SOURCE"
test "$(git -C "$PRODUCT" rev-parse HEAD^{tree})" = "$SOURCE_TREE"
git -C "$PRODUCT" diff --name-only "$DEVELOP_SOURCE"...HEAD >"$EVID/activity-time-diff.txt"
grep -Fx src/app/FunctionalHome.php "$EVID/activity-time-diff.txt" >/dev/null
test "$(wc -l < "$EVID/activity-time-diff.txt" | tr -d ' ')" = 1

# Full V2.32 Home regression first.
bash "$(dirname "$0")/p01-v232-home-activity-rail-v9.sh"

# Deterministic relative-time contract tests.
php -r '
require getenv("ROOT")."/app/bootstrap.php";
require_once getenv("ROOT")."/app/FunctionalHome.php";
$now=(new DateTimeImmutable("2026-08-29T16:00:00+00:00"))->getTimestamp();
$cases=[
 ["2026-08-29T15:59:30+00:00","刚刚"],
 ["2026-08-29T15:57:00+00:00","3 分钟前"],
 ["2026-08-29T14:00:00+00:00","2 小时前"],
 ["2026-08-26T16:00:00+00:00","3 天前"],
 ["not-a-date","时间未知"],
];
foreach($cases as [$input,$expected]){$actual=vf_home_relative_age($input,$now);if($actual!==$expected){fwrite(STDERR,"RELATIVE_TIME_FAIL input=$input expected=$expected actual=$actual\n");exit(2);}echo "$expected=PASS\n";}
' | tee "$EVID/activity-time-helper.txt"

# Re-open the V9 fresh runtime and assert rendered activity semantics.
POST_PORT=18643
PID=/tmp/p01-v232-activity-time-server.pid
COOKIE=/tmp/p01-v232-activity-time.cookies
cleanup_time(){ if test -f "$PID"; then kill "$(cat "$PID")" >/dev/null 2>&1 || true; fi; }
trap cleanup_time EXIT
php -S "127.0.0.1:${POST_PORT}" -t "$ROOT" >"$EVID/activity-time-server.log" 2>&1 & echo $! >"$PID"
for i in $(seq 1 40); do if curl -fsS "http://127.0.0.1:${POST_PORT}/api.php?action=health" >/dev/null; then break; fi; sleep .25; done
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d "{\"password\":\"${ADMIN_PASS}\"}" "http://127.0.0.1:${POST_PORT}/api.php?action=login" >"$EVID/activity-time-login.json"
curl -fsS -c "$COOKIE" -b "$COOKIE" "http://127.0.0.1:${POST_PORT}/home.php" >"$EVID/activity-time-home.html"
grep -F 'vf-home-activity-section' "$EVID/activity-time-home.html" >/dev/null
if grep -F '>完成</i>' "$EVID/activity-time-home.html" >/dev/null; then echo 'ACTIVITY_TIME_REPEATED_COMPLETE=FAIL' >&2; exit 3; fi
if grep -F '时间未知</i>' "$EVID/activity-time-home.html" >/dev/null; then echo 'ACTIVITY_TIME_UNKNOWN_LIVE=FAIL' >&2; exit 4; fi
grep -Eq '<i>(刚刚|[0-9]+ 分钟前|[0-9]+ 小时前|[0-9]+ 天前)</i>' "$EVID/activity-time-home.html"

cat >>"$EVID/verdict.txt" <<EOF
P01_V232_HOME_ACTIVITY_TIME_SOURCE=$SOURCE
P01_V232_HOME_ACTIVITY_TIME_TREE=$SOURCE_TREE
P01_V232_HOME_ACTIVITY_TIME_SINGLE_FILE_DELTA=PASS
P01_V232_HOME_ACTIVITY_TIME_RELATIVE_HELPER=PASS
P01_V232_HOME_ACTIVITY_TIME_RENDERED=PASS
P01_V232_HOME_ACTIVITY_TIME_NO_REPEATED_COMPLETE=PASS
P01_V232_SCHEMA_UNCHANGED_2026082901=PASS
P01_V232_VERSION_UNCHANGED_2.31.0=PASS
OWNER_PRODUCTION_WRITE=NO
RELEASE=NO
EOF
cat >>"$EVID/browser-verdict.txt" <<EOF
P01_V232_HOME_ACTIVITY_TIME_RENDERED=PASS
P01_V232_HOME_ACTIVITY_TIME_NO_REPEATED_COMPLETE=PASS
EOF
cat "$EVID/verdict.txt"
