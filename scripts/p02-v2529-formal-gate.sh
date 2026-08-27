#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo P02_V2529_GATE_ERROR_LINE=$LINENO' ERR

ROOT="$(pwd)"
PRODUCT="$ROOT/product"
OLD="$ROOT/old"
CANDIDATE="${CANDIDATE:?}"
BASE="${BASE:?}"
VER=2.5.29
SRCVER=2.5.28
SCHEMA=2401
OUTA="$PRODUCT/build/v2529-a"
OUTB="$PRODUCT/build/v2529-b"
TMP="${RUNNER_TEMP:-/tmp}/p02-v2529-${GITHUB_RUN_ID:-local}"
PIDS=()
cleanup(){ for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$TMP"; }
trap cleanup EXIT
mkdir -p "$TMP"
log(){ printf '\n== %s ==\n' "$*"; }
start_server(){ local site="$1" port="$2" logf="$3"; php -d display_errors=0 -S "127.0.0.1:$port" -t "$site" >"$logf" 2>&1 & PIDS+=("$!"); for _ in $(seq 1 60); do curl -fsS "http://127.0.0.1:$port/setup.php" >/dev/null 2>&1 && return 0; sleep .25; done; cat "$logf" >&2; return 1; }
setup_site(){ local base="$1" cookie="$2" pass="$3" page="$4"; curl -fsS -c "$cookie" "$base/setup.php" > "$page"; local token; token=$(python3 - "$page" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read(); m=re.search(r'name="setup_csrf" value="([^"]+)"',s)
if not m: raise SystemExit('setup csrf missing')
print(html.unescape(m.group(1)))
PY
); local code; code=$(curl -sS -o "$TMP/setup-post.html" -w '%{http_code}' -b "$cookie" -c "$cookie" -H "Origin: $base" --data-urlencode "setup_csrf=$token" --data-urlencode "password=$pass" --data-urlencode "password_confirm=$pass" "$base/setup.php"); [[ "$code" == 303 ]] || { cat "$TMP/setup-post.html" >&2; return 1; }; }

log 'Exact source fence'
test "$(git -C "$PRODUCT" rev-parse HEAD)" = "$CANDIDATE"
test "$(git -C "$OLD" rev-parse HEAD)" = 7861999d99a8de385bdd73f7892477e197c4559c
test "$(tr -d '\r\n' < "$PRODUCT/VERSION")" = "$VER"
test "$(tr -d '\r\n' < "$OLD/VERSION")" = "$SRCVER"
test "$(git -C "$PRODUCT" merge-base "$BASE" "$CANDIDATE")" = "$BASE"
mapfile -t relfiles < <(git -C "$PRODUCT" diff --name-only "$BASE..$CANDIDATE" | sort)
test "${#relfiles[@]}" -eq 3
test "${relfiles[0]}" = SOURCE_MANIFEST.json
test "${relfiles[1]}" = SOURCE_MANIFEST.txt
test "${relfiles[2]}" = VERSION
python3 "$PRODUCT/scripts/verify-source-manifest.py"
echo P02_EXACT_SOURCE_FENCE=PASS

log 'Syntax and repository runtime gates'
while IFS= read -r -d '' f; do php -l "$f" >/dev/null; done < <(find "$PRODUCT/src" "$PRODUCT/public" -type f -name '*.php' -print0)
while IFS= read -r -d '' f; do node --check "$f" >/dev/null; done < <(find "$PRODUCT/public" -type f -name '*.js' -print0)
git -C "$PRODUCT" remote set-url origin https://github.com/llhzx2018/vf-library.git
( cd "$PRODUCT" && python3 scripts/repository-gates.py )
echo P02_SYNTAX_REPOSITORY=PASS

log 'Adapt existing builder only in runner worktree'
cp "$PRODUCT/scripts/build-release.py" "$TMP/build-release.original.py"
python3 - "$PRODUCT/scripts/build-release.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')
old="ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.4.25'; VER='2.4.26'; SCHEMA=2401; DT=(2026,8,18,6,35,0)"
new="ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.5.28'; VER='2.5.29'; SCHEMA=2401; DT=(2026,8,28,0,0,0)"
if old not in s: raise SystemExit('builder version anchor changed')
s=s.replace(old,new,1)
s=s.replace("ap.add_argument('--source-ref',default='release/v2.4.26')","ap.add_argument('--source-ref',default='release/p02-v2.5.29-common-baseline-v2-20260828')",1)
start="notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text("
pos=s.find(start)
if pos<0: raise SystemExit('release notes anchor missing')
end=s.find("\n arts=[sz,fz,uz,az,rf,notes]",pos)
if end<0: raise SystemExit('release notes end anchor missing')
replacement="notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'# VF Library V{VER}\\n\\nCommon Product Baseline V2 production release. It standardizes System Info / System Baseline / Runtime Health / Online Update / Backup-Restore semantics and PERSONAL_SINGLE_ADMIN session/security behavior. Existing application behavior is preserved; Schema remains {SCHEMA} with no migration. Existing V{SRCVER} sites use UPDATE/Atomic/repair; FULL is clean install only.\\n')"
s=s[:pos]+replacement+s[end:]
s=s.replace("'candidate_verification':'PASS_RUN_32107447358'","'candidate_verification':'PASS_COMMON_BASELINE_V2_AND_CURRENT_FORMAL_GATE'",1)
s=s.replace("'main_readback':'PRODUCTION_2.4.25_UNCHANGED'","'main_readback':'V2.5.28_FORMAL_BASELINE'",1)
p.write_text(s,encoding='utf-8')
PY
python3 -m py_compile "$PRODUCT/scripts/build-release.py"

log 'Deterministic formal artifact build A/B'
rm -rf "$OUTA" "$OUTB"
( cd "$PRODUCT" && python3 scripts/build-release.py --out build/v2529-a --source-commit "$CANDIDATE" --source-tree "$(git show -s --format=%T "$CANDIDATE")" --source-ref release/p02-v2.5.29-common-baseline-v2-20260828 > "$TMP/build-a.json" )
( cd "$PRODUCT" && python3 scripts/build-release.py --out build/v2529-b --source-commit "$CANDIDATE" --source-tree "$(git show -s --format=%T "$CANDIDATE")" --source-ref release/p02-v2.5.29-common-baseline-v2-20260828 > "$TMP/build-b.json" )
( cd "$OUTA" && sha256sum -c SHA256SUMS.txt )
( cd "$OUTB" && sha256sum -c SHA256SUMS.txt )
for f in $(cd "$OUTA" && find . -maxdepth 1 -type f -printf '%f\n' | sort); do test -f "$OUTB/$f"; test "$(sha256sum "$OUTA/$f"|awk '{print $1}')" = "$(sha256sum "$OUTB/$f"|awk '{print $1}')"; done
python3 - "$OUTA" <<'PY'
import json,sys,zipfile,re,hashlib
from pathlib import Path
out=Path(sys.argv[1]); ver='2.5.29'; src='2.5.28'
need=[f'VF_Library_V{ver}_FULL.zip',f'VF_Library_V{ver}_UPDATE.zip',f'VF_Library_V{ver}_ATOMIC.zip',f'repair-v{ver}.php',f'VF_Library_V{ver}_SOURCE.zip',f'VF_Library_V{ver}_RELEASE_MANIFEST.json',f'VF_Library_V{ver}_RELEASE_NOTES.md','SHA256SUMS.txt']
for n in need: assert (out/n).is_file(),n
with zipfile.ZipFile(out/f'VF_Library_V{ver}_ATOMIC.zip') as z:
 assert z.namelist()==[f'repair-v{ver}.php']; assert z.read(f'repair-v{ver}.php')==(out/f'repair-v{ver}.php').read_bytes()
with zipfile.ZipFile(out/f'VF_Library_V{ver}_UPDATE.zip') as z:
 names=z.namelist(); assert 'atomic-manifest.json' in names
 m=json.loads(z.read('atomic-manifest.json')); assert m['source_version']==src and m['target_version']==ver and m['source_schema']==m['target_schema']==2401
 assert set(names)=={'atomic-manifest.json'}|{'payload/'+e['path'] for e in m['files']}
 for e in m['files']:
  b=z.read('payload/'+e['path']); assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256']
with zipfile.ZipFile(out/f'VF_Library_V{ver}_FULL.zip') as z:
 low=[n.lower() for n in z.namelist()]; assert 'version.txt' in low and 'release-manifest.json' in low
 forbidden=[n for n in z.namelist() if re.search(r'(^|/)(_import_chunks|private_data|node_modules|\.git)(/|$)',n,re.I) or n.lower().endswith(('.sqlite','.sqlite3','.db','.log','.env'))]
 assert not forbidden,forbidden
print('P02_ARTIFACT_SHAPE_PRIVACY=PASS')
PY
echo P02_DETERMINISTIC_ARTIFACTS=PASS

log 'FULL fresh install + Common Baseline V2'
FULLSITE="$TMP/fullsite"; mkdir -p "$FULLSITE"; unzip -q "$OUTA/VF_Library_V2.5.29_FULL.zip" -d "$FULLSITE"
start_server "$FULLSITE" 18291 "$TMP/full-server.log"
setup_site http://127.0.0.1:18291 "$TMP/full.cookie" "P02-V2529-Full-${GITHUB_RUN_ID}!" "$TMP/full-setup.html"
test "$(tr -d '\r\n' < "$FULLSITE/VERSION.txt")" = "$VER"
( cd "$FULLSITE" && php cli/verify.php ) | tee "$TMP/full-verify.json"
( cd "$FULLSITE" && php cli/baseline-verify.php ) | tee "$TMP/full-baseline.txt"
grep -Fx 'BASELINE=VF-COMMON-PRODUCT-BASELINE@2.0' "$TMP/full-baseline.txt"
grep -Fx 'PROFILE=PERSONAL_SINGLE_ADMIN' "$TMP/full-baseline.txt"
grep -Fx 'DRIFT_COUNT=0' "$TMP/full-baseline.txt"
grep -Fx 'UNKNOWN_COUNT=0' "$TMP/full-baseline.txt"
grep -Fx 'BASELINE_FULL_PASS=YES' "$TMP/full-baseline.txt"
echo P02_FULL_FRESH_BASELINE=PASS

log 'Real V2.5.28 -> V2.5.29 repair/Atomic upgrade with business data'
OLDSITE="$TMP/oldsite"; bash "$OLD/scripts/build-deploy-tree.sh" "$OLDSITE" >/dev/null
start_server "$OLDSITE" 18290 "$TMP/old-server.log"
setup_site http://127.0.0.1:18290 "$TMP/old.cookie" "P02-V2529-Old-${GITHUB_RUN_ID}!" "$TMP/old-setup.html"
php -r 'require $argv[1]."/app/bootstrap.php";$d=vftb_db();$n=gmdate("c");$q=$d->prepare("INSERT INTO text_categories(parent_id,name,description,icon,sort_order,created_at,updated_at) VALUES(NULL,?,?,?,?,?,?)");$q->execute(["Pre V2529","fixture","folder",100,$n,$n]);$c=(int)$d->lastInsertId();$q=$d->prepare("INSERT INTO text_items(category_id,title,description,content,content_mode,content_format,primary_action,status,aliases,tags,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)");$q->execute([$c,"P02_V2529_SENTINEL","fixture","preserve common baseline release","quick","plain","copy","active","[]","[]",$n,$n]);' "$OLDSITE"
cp "$OUTA/repair-v2.5.29.php" "$OLDSITE/repair-v2.5.29.php"
BASEURL=http://127.0.0.1:18290
code=$(curl -sS -o /dev/null -w '%{http_code}' -b "$TMP/old.cookie" -c "$TMP/old.cookie" "$BASEURL/repair-v2.5.29.php"); [[ "$code" == 303 ]]
curl -fsS -b "$TMP/old.cookie" -c "$TMP/old.cookie" "$BASEURL/repair-v2.5.29.php" > "$TMP/repair-form.html"
RCSRF=$(python3 - "$TMP/repair-form.html" <<'PY'
import html,re,sys
s=open(sys.argv[1],encoding='utf-8').read(); m=re.search(r'name="csrf" value="([^"]+)"',s)
if not m: raise SystemExit('repair csrf missing')
print(html.unescape(m.group(1)))
PY
)
curl -fsS -b "$TMP/old.cookie" -c "$TMP/old.cookie" -H "Origin: $BASEURL" --data-urlencode action=upgrade --data-urlencode "csrf=$RCSRF" "$BASEURL/repair-v2.5.29.php" > "$TMP/repair-result.html"
grep -q '升级完成' "$TMP/repair-result.html"
test ! -e "$OLDSITE/repair-v2.5.29.php"
test "$(tr -d '\r\n' < "$OLDSITE/VERSION.txt")" = "$VER"
php -r 'require $argv[1]."/app/bootstrap.php";$d=vftb_db();if(VfLibrarySchemaMigration::currentVersion($d)!==2401)exit(2);$v=$d->query("SELECT content FROM text_items WHERE title=\"P02_V2529_SENTINEL\"")->fetchColumn();if($v!=="preserve common baseline release")exit(3);if($d->query("PRAGMA integrity_check")->fetchColumn()!=="ok")exit(4);if(count($d->query("PRAGMA foreign_key_check")->fetchAll())!==0)exit(5);' "$OLDSITE"
( cd "$OLDSITE" && php cli/verify.php ) | tee "$TMP/upgraded-verify.json"
( cd "$OLDSITE" && php cli/baseline-verify.php ) | tee "$TMP/upgraded-baseline.txt"
grep -Fx 'DRIFT_COUNT=0' "$TMP/upgraded-baseline.txt"
grep -Fx 'UNKNOWN_COUNT=0' "$TMP/upgraded-baseline.txt"
grep -Fx 'BASELINE_FULL_PASS=YES' "$TMP/upgraded-baseline.txt"
PRIV=$(php -r 'require $argv[1]."/app/bootstrap.php";echo VFTB_PRIVATE_ROOT;' "$OLDSITE")
! find "$PRIV" -maxdepth 1 \( -name '.repair-*' -o -name '.atomic-rollback-*' \) -print -quit | grep -q .
echo P02_V2528_TO_V2529_ATOMIC=PASS

log 'Final evidence'
mkdir -p "$ROOT/evidence"
UPDATE="$OUTA/VF_Library_V2.5.29_UPDATE.zip"
FULL="$OUTA/VF_Library_V2.5.29_FULL.zip"
REPAIR="$OUTA/repair-v2.5.29.php"
ATOMIC="$OUTA/VF_Library_V2.5.29_ATOMIC.zip"
cat > "$ROOT/evidence/P02-V2.5.29-FORMAL-GATE.env" <<EOF
P02_VERSION=2.5.29
P02_SOURCE=387655e222c1fed0b6e4559b66d254dba5d3c8e4
P02_SOURCE_TREE=$(git -C "$PRODUCT" show -s --format=%T "$CANDIDATE")
P02_SCHEMA=2401
P02_UPDATE_BYTES=$(stat -c%s "$UPDATE")
P02_UPDATE_SHA256=$(sha256sum "$UPDATE"|awk '{print $1}')
P02_FULL_BYTES=$(stat -c%s "$FULL")
P02_FULL_SHA256=$(sha256sum "$FULL"|awk '{print $1}')
P02_REPAIR_BYTES=$(stat -c%s "$REPAIR")
P02_REPAIR_SHA256=$(sha256sum "$REPAIR"|awk '{print $1}')
P02_ATOMIC_BYTES=$(stat -c%s "$ATOMIC")
P02_ATOMIC_SHA256=$(sha256sum "$ATOMIC"|awk '{print $1}')
P02_FORMAL_GATE=PASS
P02_PRODUCTION_CHANGED=NO
EOF
cat "$ROOT/evidence/P02-V2.5.29-FORMAL-GATE.env"
echo P02_V2529_FORMAL_MACHINE=PASS
