#!/usr/bin/env bash
set -Eeuo pipefail

: "${CANDIDATE_COMMIT:?}"
: "${CANDIDATE_TREE:?}"
: "${PRODUCTION_COMMIT:?}"
: "${SOURCE_VERSION:?}"
: "${TARGET_VERSION:?}"
: "${TARGET_SCHEMA:?}"
: "${FIXTURE_PASS:?}"
: "${PHP_TEST_IMAGE:?}"
: "${GATE_ROOT:?}"

test -d p03/.git
test "$(git -C p03 rev-parse HEAD)" = "$CANDIDATE_COMMIT"
test "$(git -C p03 rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(tr -d '\r\n' < p03/VERSION)" = "$TARGET_VERSION"
grep -Fq "define('VFAB_VERSION', '1.35.3');" p03/src/app/bootstrap.php
grep -Fq "define('VFAB_SCHEMA_VERSION', 29);" p03/src/app/bootstrap.php
grep -Fq "TARGET_VERSION='1.35.3'" p03/scripts/build_atomic.py
grep -Fq "ALLOWED_SOURCES=['1.35.2']" p03/scripts/build_atomic.py
test -z "$(git -C p03 diff "$PRODUCTION_COMMIT"..HEAD -- database/schema database/migrations)"
ORIGIN=$(git -C p03 config --get remote.origin.url)
case "$ORIGIN" in *x-access-token*|*github_pat_*|*ghp_*) echo 'Credential persisted in origin URL' >&2; exit 80;; esac
if git -C p03 ls-files | grep -Ei '(^|/)(PRIVATE_DATA|storage/private|uploads|backup|backups|cache|session|sessions|logs|tmp)(/|$)|\.sqlite3?$|\.db$|(^|/)\.env$'; then
  echo 'Tracked private/runtime data found' >&2; exit 81
fi
echo 'EXACT_CANDIDATE_IDENTITY=PASS'
echo 'SCHEMA_MIGRATION=NONE_29_TO_29'
echo 'PERSIST_CREDENTIALS=FALSE_PASS'

cd p03
rm -rf "$GATE_ROOT"
mkdir -p "$GATE_ROOT"
PROD="$GATE_ROOT/runtime-production"
TARGET="$GATE_ROOT/runtime-target"
git worktree add --detach "$GATE_ROOT/production-worktree" "$PRODUCTION_COMMIT" >/dev/null
python3 "$GATE_ROOT/production-worktree/scripts/build_runtime.py" "$PROD" >/dev/null
python3 scripts/build_runtime.py "$TARGET" >/dev/null
test "$(find "$PROD" -type f | wc -l | tr -d ' ')" = '35'
test "$(find "$TARGET" -type f | wc -l | tr -d ' ')" = '37'
grep -Fq "define('VFAB_VERSION', '1.35.2');" "$PROD/app/bootstrap.php"
grep -Fq "define('VFAB_VERSION', '1.35.3');" "$TARGET/app/bootstrap.php"
echo 'EXACT_RUNTIME_BASE_TARGET=PASS'

for N in a b; do
  OUT="$GATE_ROOT/build-$N"; mkdir -p "$OUT"
  python3 - "$TARGET" "$OUT/VF_Forge_V1.35.3_FULL.zip" <<'PY'
import sys,zipfile
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2])
with zipfile.ZipFile(out,'w') as z:
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink(): continue
        rel=p.relative_to(root).as_posix()
        zi=zipfile.ZipInfo(rel,date_time=(2020,1,1,0,0,0)); zi.compress_type=zipfile.ZIP_DEFLATED; zi.external_attr=(0o100644 & 0xFFFF)<<16
        z.writestr(zi,p.read_bytes(),compresslevel=9)
PY
  python3 scripts/build_atomic.py --base-runtime "$PROD" --target-runtime "$TARGET" --output "$OUT" >"$OUT/build-atomic.json"
  cp "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" "$OUT/VF_Forge_V1.35.3_UPDATE.zip"
done
for F in VF_Forge_V1.35.3_FULL.zip VF_Forge_V1.35.3_UPDATE.zip VF_Forge_V1.35.3_Atomic_Upgrade.zip; do
  cmp "$GATE_ROOT/build-a/$F" "$GATE_ROOT/build-b/$F"
  echo "$F SHA256=$(sha256sum "$GATE_ROOT/build-a/$F" | awk '{print $1}') BYTES=$(stat -c%s "$GATE_ROOT/build-a/$F")"
done
test "$(sha256sum "$GATE_ROOT/build-a/VF_Forge_V1.35.3_UPDATE.zip"|awk '{print $1}')" = "$(sha256sum "$GATE_ROOT/build-a/VF_Forge_V1.35.3_Atomic_Upgrade.zip"|awk '{print $1}')"
echo 'DETERMINISTIC_FULL_UPDATE_ATOMIC=PASS'

OUT="$GATE_ROOT/build-a"
unzip -t "$OUT/VF_Forge_V1.35.3_FULL.zip" >/dev/null
unzip -t "$OUT/VF_Forge_V1.35.3_UPDATE.zip" >/dev/null
unzip -t "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" >/dev/null
test "$(unzip -Z1 "$OUT/VF_Forge_V1.35.3_FULL.zip" | wc -l | tr -d ' ')" = '37'
test "$(unzip -Z1 "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip")" = 'repair-v1.35.3.php'
unzip -p "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" repair-v1.35.3.php >"$GATE_ROOT/repair-v1.35.3.php"
php -l "$GATE_ROOT/repair-v1.35.3.php" >/dev/null
grep -Fq "const VFF_ATOMIC_TARGET='1.35.3';" "$GATE_ROOT/repair-v1.35.3.php"
grep -Fq 'const VFF_ATOMIC_ALLOWED=["1.35.2"];' "$GATE_ROOT/repair-v1.35.3.php"
cat >"$GATE_ROOT/reverse_verify.py" <<'PY'
import base64,gzip,hashlib,json,re,sys,zipfile
from pathlib import Path
runtime=Path(sys.argv[1]); package=Path(sys.argv[2])
def die(x): print(x,file=sys.stderr); raise SystemExit(2)
def files(root):
    out={}
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink(): continue
        rel=p.relative_to(root).as_posix(); top=rel.split('/',1)[0]
        if rel=='app/.runtime.php' or re.match(r'^repair-v[^/]+\.php$',rel): continue
        if rel in {'api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','robots.txt','setup.php','share.php'} or top in {'app','assets','cli','mcp'}:
            b=p.read_bytes(); out[rel]=(len(b),hashlib.sha256(b).hexdigest())
    return out
with zipfile.ZipFile(package) as z:
    if z.namelist()!=['repair-v1.35.3.php']: die('atomic zip shape mismatch')
    php=z.read('repair-v1.35.3.php').decode()
def const(name):
    m=re.search(r"const "+re.escape(name)+r"='([^']*)';",php)
    if not m: die('missing '+name)
    return m.group(1)
raw=gzip.decompress(base64.b64decode(const('VFF_ATOMIC_PAYLOAD')))
if hashlib.sha256(raw).hexdigest()!=const('VFF_ATOMIC_PAYLOAD_JSON_SHA256'): die('payload sha mismatch')
obj=json.loads(raw)
want={k:(int(v['bytes']),v['sha256']) for k,v in obj['files'].items()}
got=files(runtime)
if got!=want: die('runtime payload mismatch')
rows=[f"{k}\t{v[0]}\t{v[1]}" for k,v in sorted(got.items())]
fp=hashlib.sha256(('\n'.join(rows)+'\n').encode()).hexdigest()
if fp!=obj['source_manifest_sha256'] or fp!=const('VFF_ATOMIC_SOURCE_MANIFEST_SHA256'): die('manifest mismatch')
print('ATOMIC_REVERSE_VERIFY_PASS',len(got),fp)
PY
python3 "$GATE_ROOT/reverse_verify.py" "$TARGET" "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip"
python3 - "$OUT/VF_Forge_V1.35.3_FULL.zip" <<'PY'
import re,sys,zipfile
z=zipfile.ZipFile(sys.argv[1])
for i in z.infolist():
    n=i.filename.replace('\\','/')
    assert n and not n.startswith('/') and not re.match(r'^[A-Za-z]:',n) and '..' not in n.split('/')
    assert not re.search(r'(^|/)(PRIVATE_DATA|storage/private|uploads|backup|backups|cache|session|sessions|logs|tmp)(/|$)',n,re.I)
    assert not re.search(r'\.(sqlite3?|db)$|(^|/)\.env$',n,re.I)
print('FULL_PATH_PRIVACY_PASS',len(z.infolist()))
PY
cp -a "$TARGET" "$GATE_ROOT/runtime-tampered"
printf '\n/* formal-gate-tamper */\n' >>"$GATE_ROOT/runtime-tampered/assets/forge-ui.css"
if python3 "$GATE_ROOT/reverse_verify.py" "$GATE_ROOT/runtime-tampered" "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" >/dev/null 2>&1; then
  echo 'Tampered runtime accepted' >&2; exit 84
fi
echo 'ZIP_PATH_PRIVACY_TAMPER_FAIL_CLOSED=PASS'

FORMAL_FULL="$OUT/VF_Forge_V1.35.3_FULL.zip"
export FORMAL_FULL
python3 - <<'PY'
from pathlib import Path
s=Path('tests/maintenance/current_reverify.sh').read_text(encoding='utf-8')
old='rm -rf "$RUNTIME" "$DATA_ROOT" "$COOKIE"\nmkdir -p "$DATA_ROOT"\npython3 scripts/build_runtime.py "$RUNTIME" >/dev/null'
new='rm -rf "$RUNTIME" "$DATA_ROOT" "$COOKIE"\nmkdir -p "$RUNTIME" "$DATA_ROOT"\nunzip -q "$FORMAL_FULL" -d "$RUNTIME"'
if old not in s: raise SystemExit('current_reverify bootstrap block drifted')
s=s.replace(old,new,1).replace("d['version']=='1.35.0'","d['version']=='1.35.3'",1)
Path('/tmp/p03-formal-full-reverify.sh').write_text(s,encoding='utf-8',newline='\n')
PY
chmod +x /tmp/p03-formal-full-reverify.sh
bash /tmp/p03-formal-full-reverify.sh
echo 'FORMAL_FULL_FRESH_EXISTING_BACKUP_RESTORE=PASS'

RUNTIME="$GATE_ROOT/upgrade-runtime"; DATA="$GATE_ROOT/upgrade-data"; COOKIE="$GATE_ROOT/upgrade-cookie"; BASE='http://127.0.0.1:18082'; NAME='p03-v1353-upgrade'
rm -rf "$RUNTIME" "$DATA" "$COOKIE"; cp -a "$PROD" "$RUNTIME"; mkdir -p "$DATA"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --rm --name "$NAME" -p 18082:18082 -v "$RUNTIME:/app" -v "$DATA:$DATA" -w /app "$PHP_TEST_IMAGE" php -S 0.0.0.0:18082 -t /app >/dev/null
for i in $(seq 1 60); do curl -fsS "$BASE/setup.php" >/dev/null 2>&1 && break; sleep .25; done
curl -fsS -c "$COOKIE" "$BASE/setup.php" -o "$GATE_ROOT/upgrade-setup.html"
SCSRF=$(python3 - "$GATE_ROOT/upgrade-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -i -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" --data-urlencode "setup_csrf=$SCSRF" --data-urlencode 'site_title=Formal Upgrade Fixture' --data-urlencode "data_root=$DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$BASE/setup.php" >"$GATE_ROOT/upgrade-setup-post.txt"
LOGIN=$(printf '{"password":"%s"}' "$FIXTURE_PASS")
curl -fsS -b "$COOKIE" -c "$COOKIE" -H "Origin: $BASE" -H 'Content-Type: application/json' --data "$LOGIN" "$BASE/api.php?action=login" -o "$GATE_ROOT/upgrade-login.json"
TOKEN=$(python3 - "$GATE_ROOT/upgrade-login.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.35.2';print(d['csrf'])
PY
)
curl -fsS -b "$COOKIE" -H "Origin: $BASE" -H "X-CSRF-Token: $TOKEN" -H 'Content-Type: application/json' --data '{"name":"Formal Preserve Project","development_stage":"maintenance"}' "$BASE/api.php?action=project_save" -o "$GATE_ROOT/preserve-project.json"
DB=$(find "$DATA/database" -maxdepth 1 -type f -name '*.sqlite' | head -1); test -f "$DB"
python3 - "$DB" "$GATE_ROOT/business-before.json" <<'PY'
import hashlib,json,sqlite3,sys
db=sqlite3.connect(sys.argv[1]); db.row_factory=sqlite3.Row
out={}
for (t,) in db.execute("select name from sqlite_master where type='table' order by name"):
    if t=='sqlite_sequence' or t=='search_documents' or t.startswith('search_fts'): continue
    rows=[dict(r) for r in db.execute('select * from "'+t.replace('"','""')+'" order by rowid')]
    out[t]=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
json.dump(out,open(sys.argv[2],'w'),sort_keys=True)
print('BUSINESS_FINGERPRINT_BEFORE',len(out))
PY
unzip -p "$OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" repair-v1.35.3.php >"$RUNTIME/repair-v1.35.3.php"
curl -fsS -b "$COOKIE" "$BASE/repair-v1.35.3.php" -o "$GATE_ROOT/repair-form.html"
RCSRF=$(python3 - "$GATE_ROOT/repair-form.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -b "$COOKIE" -H "Origin: $BASE" --data-urlencode "_csrf=$RCSRF" --data-urlencode 'confirmation=UPGRADE' "$BASE/repair-v1.35.3.php" -o "$GATE_ROOT/repair-result.html"
grep -q '升级完成' "$GATE_ROOT/repair-result.html"
grep -Fq "define('VFAB_VERSION', '1.35.3');" "$RUNTIME/app/bootstrap.php"
test ! -e "$RUNTIME/repair-v1.35.3.php"
test "$(sqlite3 "$DB" 'pragma integrity_check;')" = 'ok'
test -z "$(sqlite3 "$DB" 'pragma foreign_key_check;')"
test "$(sqlite3 "$DB" "select count(*) from projects where name='Formal Preserve Project';")" = '1'
python3 - "$DB" "$GATE_ROOT/business-before.json" <<'PY'
import hashlib,json,sqlite3,sys
before=json.load(open(sys.argv[2])); db=sqlite3.connect(sys.argv[1]); db.row_factory=sqlite3.Row; now={}
for t in before:
    rows=[dict(r) for r in db.execute('select * from "'+t.replace('"','""')+'" order by rowid')]
    now[t]=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
assert now==before, sorted(k for k in before if before[k]!=now.get(k))
print('BUSINESS_DATA_PRESERVATION=PASS',len(now))
PY
python3 scripts/semantic_consistency_audit.py "$DB" >"$GATE_ROOT/semantic-after-upgrade.json"
python3 - "$GATE_ROOT/semantic-after-upgrade.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]));assert d['ok'] and d['finding_count']==0;print('SEMANTIC_CONSISTENCY_AFTER_UPGRADE=PASS',d['check_count'])
PY
curl -fsS -b "$COOKIE" "$BASE/maintenance.php?action=source-manifest" -o "$GATE_ROOT/runtime-source-manifest.txt"
python3 - "$GATE_ROOT/runtime-source-manifest.txt" "$OUT/SOURCE_MANIFEST.txt" <<'PY'
import sys
p=[x for x in open(sys.argv[1],encoding='utf-8').read().splitlines() if x and not x.startswith('# ')]
e=open(sys.argv[2],encoding='utf-8').read().splitlines();assert p==e,(len(p),len(e));print('UPGRADED_RUNTIME_SOURCE_EXACT=PASS',len(p))
PY
cp "$GATE_ROOT/repair-v1.35.3.php" "$RUNTIME/repair-v1.35.3.php"
BEFORE_REPEAT=$(find "$RUNTIME" -type f ! -name 'repair-v1.35.3.php' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
curl -fsS -b "$COOKIE" "$BASE/repair-v1.35.3.php" -o "$GATE_ROOT/repeat-result.html"
grep -q '版本不允许' "$GATE_ROOT/repeat-result.html"
AFTER_REPEAT=$(find "$RUNTIME" -type f ! -name 'repair-v1.35.3.php' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
test "$BEFORE_REPEAT" = "$AFTER_REPEAT"
rm -f "$RUNTIME/repair-v1.35.3.php"
docker rm -f "$NAME" >/dev/null
echo 'EXACT_UPGRADE_SCHEMA_BUSINESS_SEMANTIC_IDEMPOTENCY=PASS'

FAIL_OUT="$GATE_ROOT/fail-build"
python3 scripts/build_atomic.py --base-runtime "$PROD" --target-runtime "$TARGET" --output "$FAIL_OUT" --test-fail-stage after_source_switch >/dev/null
setup_case(){
  local suffix="$1" port="$2" runtime="$GATE_ROOT/$suffix-runtime" data="$GATE_ROOT/$suffix-data" cookie="$GATE_ROOT/$suffix-cookie" base="http://127.0.0.1:$port" name="p03-$suffix"
  rm -rf "$runtime" "$data" "$cookie"; cp -a "$PROD" "$runtime"; mkdir -p "$data"
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker run -d --rm --name "$name" -p "$port:$port" -v "$runtime:/app" -v "$data:$data" -w /app "$PHP_TEST_IMAGE" php -S 0.0.0.0:"$port" -t /app >/dev/null
  for i in $(seq 1 60); do curl -fsS "$base/setup.php" >/dev/null 2>&1 && break; sleep .25; done
  curl -fsS -c "$cookie" "$base/setup.php" -o "$GATE_ROOT/$suffix-setup.html"
  local scsrf; scsrf=$(python3 - "$GATE_ROOT/$suffix-setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
  curl -fsS -i -b "$cookie" -c "$cookie" -H "Origin: $base" --data-urlencode "setup_csrf=$scsrf" --data-urlencode "site_title=$suffix" --data-urlencode "data_root=$data" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$base/setup.php" >"$GATE_ROOT/$suffix-setup-post.txt"
  local login; login=$(printf '{"password":"%s"}' "$FIXTURE_PASS")
  curl -fsS -b "$cookie" -c "$cookie" -H "Origin: $base" -H 'Content-Type: application/json' --data "$login" "$base/api.php?action=login" -o "$GATE_ROOT/$suffix-login.json"
}
setup_case rollback 18083
RR="$GATE_ROOT/rollback-runtime"; RD="$GATE_ROOT/rollback-data"; RC="$GATE_ROOT/rollback-cookie"; RB='http://127.0.0.1:18083'
RDB=$(find "$RD/database" -type f -name '*.sqlite' | head -1); sqlite3 "$RDB" 'pragma wal_checkpoint(truncate);' >/dev/null
DB_BEFORE=$(sha256sum "$RDB"|awk '{print $1}')
SRC_BEFORE=$(find "$RR" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
unzip -p "$FAIL_OUT/VF_Forge_V1.35.3_Atomic_Upgrade.zip" repair-v1.35.3.php >"$RR/repair-v1.35.3.php"
curl -fsS -b "$RC" "$RB/repair-v1.35.3.php" -o "$GATE_ROOT/rollback-form.html"
RCSRF=$(python3 - "$GATE_ROOT/rollback-form.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -b "$RC" -H "Origin: $RB" --data-urlencode "_csrf=$RCSRF" --data-urlencode 'confirmation=UPGRADE' "$RB/repair-v1.35.3.php" -o "$GATE_ROOT/rollback-result.html"
grep -q '原子升级失败，已执行回滚' "$GATE_ROOT/rollback-result.html"
rm -f "$RR/repair-v1.35.3.php"
grep -Fq "define('VFAB_VERSION', '1.35.2');" "$RR/app/bootstrap.php"
sqlite3 "$RDB" 'pragma wal_checkpoint(truncate);' >/dev/null
DB_AFTER=$(sha256sum "$RDB"|awk '{print $1}')
SRC_AFTER=$(find "$RR" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
test "$DB_BEFORE" = "$DB_AFTER"
test "$SRC_BEFORE" = "$SRC_AFTER"
docker rm -f p03-rollback >/dev/null
setup_case wrong-source 18084
WR="$GATE_ROOT/wrong-source-runtime"; WC="$GATE_ROOT/wrong-source-cookie"; WB='http://127.0.0.1:18084'
sed -i "s/define('VFAB_VERSION', '1.35.2');/define('VFAB_VERSION', '1.35.1');/" "$WR/app/bootstrap.php"
cp "$GATE_ROOT/repair-v1.35.3.php" "$WR/repair-v1.35.3.php"
WRONG_BEFORE=$(find "$WR" -type f ! -name 'repair-v1.35.3.php' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
curl -fsS -b "$WC" "$WB/repair-v1.35.3.php" -o "$GATE_ROOT/wrong-source-result.html"
grep -q '版本不允许' "$GATE_ROOT/wrong-source-result.html"
WRONG_AFTER=$(find "$WR" -type f ! -name 'repair-v1.35.3.php' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')
test "$WRONG_BEFORE" = "$WRONG_AFTER"
docker rm -f p03-wrong-source >/dev/null
echo 'FAILURE_INJECTION_ROLLBACK=PASS'
echo 'WRONG_SOURCE_VERSION_FAIL_CLOSED=PASS'

# Emit safe gate-only metadata before cleanup.
for F in VF_Forge_V1.35.3_FULL.zip VF_Forge_V1.35.3_UPDATE.zip VF_Forge_V1.35.3_Atomic_Upgrade.zip; do
  echo "GATE_ONLY $F SHA256=$(sha256sum "$OUT/$F" | awk '{print $1}') BYTES=$(stat -c%s "$OUT/$F")"
done

git worktree remove --force "$GATE_ROOT/production-worktree" >/dev/null 2>&1 || true
rm -rf "$GATE_ROOT" /tmp/p03-formal-full-reverify.sh
echo 'CANDIDATE_PACKAGES_PERSISTED=NO'
echo 'EPHEMERAL_GATE_CORE=PASS'
