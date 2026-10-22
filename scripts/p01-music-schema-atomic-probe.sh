#!/usr/bin/env bash
set -Eeuo pipefail
test -n "$FULL" && test -n "$UPDATE" && test -n "$SOURCE_FULL"
WORK="$(mktemp -d /tmp/p01-music-schema-atomic-XXXXXXXX)"
PID=''
cleanup(){ if [[ -n "$PID" ]]; then kill "$PID" >/dev/null 2>&1 || :; fi; rm -rf "$WORK"; }
trap cleanup EXIT
trap 'echo P01_ATOMIC_FAILURE_LINE=$LINENO >&2' ERR
unzip -t "$FULL" >/dev/null
unzip -t "$UPDATE" >/dev/null
mkdir -p "$WORK/atomic"
unzip -q "$UPDATE" -d "$WORK/atomic"
REPAIR="$WORK/atomic/repair-v$VERSION.php"
test -f "$REPAIR"
php -l "$REPAIR" >/dev/null
php "$REPAIR" --self-test > "$WORK/selftest.json"
grep -Fq '"ok":true' "$WORK/selftest.json"
echo P01_MUSIC_ATOMIC_SELFTEST=PASS
for zip in "$FULL" "$UPDATE"; do
 if unzip -Z1 "$zip" | grep -Ei '(^|/)(\.runtime\.php|.*\.sqlite3?$|.*\.db$|private/|backups?/|sessions?/|tokens?/|staging/)'; then
  echo P01_ATOMIC_PRIVATE_PAYLOAD_LEAK >&2
  exit 90
 fi
done
echo P01_MUSIC_ARTIFACT_PRIVATE_GATE=PASS
install_fixture(){
 local zip="$1" dest="$2" port="$3"
 mkdir -p "$dest"
 unzip -q "$zip" -d "$dest"
 php -S "127.0.0.1:$port" -t "$dest" >"$WORK/server-$port.log" 2>&1 &
 PID=$!
 for _ in $(seq 1 45); do
  if curl -fsS -c "$WORK/cookie-$port" "http://127.0.0.1:$port/setup.php" -o "$WORK/setup-$port.html" 2>/dev/null; then break; fi
  sleep 0.2
 done
 test -f "$WORK/setup-$port.html"
 local csrf
 csrf="$(python3 - "$WORK/setup-$port.html" <<'PY'
import re,sys
m=re.search(r'name="setup_csrf"\s+value="([^"]+)"',open(sys.argv[1]).read())
assert m
print(m.group(1))
PY
)"
 curl -fsS -b "$WORK/cookie-$port" -c "$WORK/cookie-$port" \
  -X POST "http://127.0.0.1:$port/setup.php" \
  --data-urlencode "setup_csrf=$csrf" \
  --data-urlencode 'site_title=P01 Music Test Only' \
  --data-urlencode 'admin_password=SyntheticOnly!2026' \
  --data-urlencode 'admin_password_confirm=SyntheticOnly!2026' >"$WORK/setup-post-$port.html"
 kill "$PID" >/dev/null 2>&1 || :
 wait "$PID" 2>/dev/null || :
 PID=''
 (cd "$dest" && php cli/verify.php) >"$WORK/cli-$port.log"
 grep -Fx 'VERIFY_PASS=YES' "$WORK/cli-$port.log" >/dev/null
}
install_fixture "$FULL" "$WORK/new" 18801
test "$(tr -d '\r\n ' < "$WORK/new/VERSION.txt")" = "$VERSION"
echo P01_MUSIC_SCHEMA_FULL_INSTALL=PASS
install_fixture "$SOURCE_FULL" "$WORK/old" 18802
php -r '
require $argv[1]."/app/bootstrap.php";
$r=new VfRepository(vf_db());
$c=$r->createCategory(["name"=>"Synthetic Music Gate","description"=>"","icon"=>"","is_private"=>1,"sort_order"=>0]);
$r->saveLink(null,["surface"=>"start","category_id"=>$c,"title"=>"Original Owner Sentinel","url"=>"https://example.org/synthetic","description"=>"must survive","tags"=>[],"is_private"=>1,"is_pending"=>0]);
' "$WORK/old"
cp "$REPAIR" "$WORK/old/"
php "$WORK/old/repair-v$VERSION.php" --verify-source="$WORK/old" >"$WORK/source.json"
grep -Fq '"ok":true' "$WORK/source.json"
set +e
php "$WORK/old/repair-v$VERSION.php" --run="$WORK/old" >"$WORK/apply.json" 2>"$WORK/apply.err"
apply_rc=$?
set -e
if [[ "$apply_rc" -ne 0 ]]; then
  python3 - "$WORK/apply.json" "$WORK/apply.err" <<'PY'
import json,pathlib,re,sys
def scrub(x):
    x=str(x)[:600]
    return re.sub(r'/tmp/[^\s\"\\]+','[isolated-path]',x)
raw=pathlib.Path(sys.argv[1]).read_text(errors='replace')
try:
    x=json.loads(raw)
    if isinstance(x,dict):
        safe={k:scrub(x[k]) for k in ('ok','error','message','reason','rollback','rollback_verified','phase','code') if k in x}
        print('P01_MUSIC_ATOMIC_DIAG='+json.dumps(safe))
        print('P01_MUSIC_ATOMIC_RESULT_KEYS='+str(sorted(x.keys())))
    else: print('P01_MUSIC_ATOMIC_RESULT_TYPE='+type(x).__name__)
except Exception:
    print('P01_MUSIC_ATOMIC_OUTPUT_INVALID_JSON')
    print('P01_MUSIC_ATOMIC_OUTPUT_PREFIX='+scrub(raw[:250]))
e=pathlib.Path(sys.argv[2]).read_text(errors='replace')
print('P01_MUSIC_ATOMIC_STDERR='+scrub(e[-350:]))
PY
  test "$(tr -d '\r\n ' < "$WORK/old/VERSION.txt")" = "$SOURCE_VERSION" && echo 'P01_MUSIC_VERSION_ROLLBACK_RETAINED=YES' || echo 'P01_MUSIC_VERSION_ROLLBACK_RETAINED=NO'
  exit 1
fi
grep -Fq '"ok":true' "$WORK/apply.json"
test "$(tr -d '\r\n ' <"$WORK/old/VERSION.txt")" = "$VERSION"
(cd "$WORK/old" && php cli/verify.php) >"$WORK/new-verify.txt"
grep -Fx 'VERIFY_PASS=YES' "$WORK/new-verify.txt" >/dev/null
php -r '
require $argv[1]."/app/bootstrap.php";
$d=vf_db();
if((int)$d->query("SELECT COUNT(*) FROM links WHERE title='\''Original Owner Sentinel'\''")->fetchColumn()!==1)exit(1);
if((int)$d->query("SELECT COUNT(*) FROM sqlite_master WHERE type='\''table'\'' AND name='\''music_playlists'\''")->fetchColumn()!==1)exit(1);
if($d->query("PRAGMA integrity_check")->fetchColumn()!=="ok"||$d->query("PRAGMA foreign_key_check")->fetchAll(PDO::FETCH_ASSOC)!==[])exit(1);
' "$WORK/old"
echo P01_MUSIC_SCHEMA_ATOMIC_UPGRADE=PASS
# Normal Atomic flow deletes the repair script itself after success. A
# second invocation is a fresh deliberate operator action, so recopy it.
cp "$REPAIR" "$WORK/old/"
php "$WORK/old/repair-v$VERSION.php" --run="$WORK/old" >"$WORK/repeat.json"
grep -Fq '"already_current":true' "$WORK/repeat.json"
echo P01_MUSIC_ATOMIC_IDEMPOTENT=PASS
install_fixture "$SOURCE_FULL" "$WORK/rollback" 18803
cp "$REPAIR" "$WORK/rollback/"
set +e
VF_ATOMIC_TEST_FAIL_AFTER_APPLY=1 php "$WORK/rollback/repair-v$VERSION.php" --run="$WORK/rollback" > "$WORK/fault.json" 2>&1
code=$?
set -e
test "$code" -ne 0
test "$(tr -d '\r\n ' < "$WORK/rollback/VERSION.txt")" = "$SOURCE_VERSION"
(cd "$WORK/rollback" && php cli/verify.php) >"$WORK/rollback-verify.txt"
grep -Fx 'VERIFY_PASS=YES' "$WORK/rollback-verify.txt" >/dev/null
echo P01_MUSIC_SCHEMA_ATOMIC_ROLLBACK=PASS
