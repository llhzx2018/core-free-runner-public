#!/usr/bin/env bash
set -Eeuo pipefail
: "${CANDIDATE_COMMIT:?}"; : "${CANDIDATE_TREE:?}"; : "${AUTHORITY_HEAD:?}"; : "${PRODUCTION_COMMIT:?}"; : "${PHP_TEST_IMAGE:?}"; : "${FIXTURE_PASS:?}"; : "${GATE_ROOT:?}"
TARGET_VERSION=1.35.4; SOURCE_VERSION=1.35.3; TARGET_SCHEMA=30; SOURCE_SCHEMA=29; MIGRATION_ID=M030_EXTERNAL_AUTHORITY_MEMORY_INDEX

test "$(git -C p03 rev-parse HEAD)" = "$CANDIDATE_COMMIT"
test "$(git -C p03 rev-parse HEAD^{tree})" = "$CANDIDATE_TREE"
test "$(git -C authority rev-parse HEAD)" = "$AUTHORITY_HEAD"
test "$(git -C production rev-parse HEAD)" = "$PRODUCTION_COMMIT"
python3 - <<'PY'
import json
p=json.load(open('authority/VF_PROJECT.json',encoding='utf-8'))
s=p['v1_35_4_candidate_authority_seal']
assert p['status'].endswith('CANDIDATE_VERIFIED / FORMAL_ARTIFACT_PRE_GATE')
assert s['candidate_status']=='VERIFIED'
assert s['product_commit']=='af34b84a3135333cf05077b3eb64e22ef6b3afef'
assert s['product_tree']=='08eee7e8c891a57c357553dd5de20c1a7bd79849'
assert s['runner_run']==31983385126 and s['runner_job']==95254992411 and s['runner_conclusion']=='SUCCESS'
assert s['runtime_files']==42 and s['runtime_fingerprint_sha256']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert s['formal_release']=='NOT_EXECUTED' and s['production_write']==0 and s['physical_delete']==0
print('AUTHORITY_SEAL_VALIDATION=PASS')
PY

grep -Fq "define('VFAB_VERSION', '1.35.4');" p03/src/app/bootstrap.php
grep -Fq "define('VFAB_SCHEMA_VERSION', 30);" p03/src/app/bootstrap.php
grep -Fq "M030_EXTERNAL_AUTHORITY_MEMORY_INDEX" p03/src/app/MigrationRunner.php
grep -Fq "CREATE TABLE IF NOT EXISTS authority_sources" p03/src/app/schema30.sql
grep -Fq "PROJECT-ASSET STORAGE = NONE" p03/docs/architecture/V1354_ZERO_PROJECT_ASSET_STORAGE_CONTRACT.md
if git -C p03 ls-files | grep -Ei '(^|/)(PRIVATE_DATA|storage/private|uploads|backup|backups|cache|session|sessions|logs|tmp)(/|$)|\.sqlite3?$|\.db$|(^|/)\.env$'; then echo 'TRACKED_PRIVATE_RUNTIME_DATA=FAIL' >&2; exit 81; fi
ORIGIN=$(git -C p03 config --get remote.origin.url); case "$ORIGIN" in *x-access-token*|*github_pat_*|*ghp_*) echo 'CREDENTIAL_IN_ORIGIN=FAIL' >&2; exit 82;; esac
echo 'FROZEN_PRODUCT_IDENTITY=PASS'

rm -rf "$GATE_ROOT"; mkdir -p "$GATE_ROOT"
PROD_RT="$GATE_ROOT/runtime-production"; TARGET_A="$GATE_ROOT/runtime-target-a"; TARGET_B="$GATE_ROOT/runtime-target-b"
python3 production/scripts/build_runtime.py "$PROD_RT" >/dev/null
python3 p03/scripts/build_runtime.py "$TARGET_A" >/dev/null
python3 p03/scripts/build_runtime.py "$TARGET_B" >/dev/null
test "$(find "$TARGET_A" -type f | wc -l | tr -d ' ')" = 42
test "$(find "$TARGET_B" -type f | wc -l | tr -d ' ')" = 42
diff -qr "$TARGET_A" "$TARGET_B" >/dev/null
grep -Fq "define('VFAB_VERSION', '1.35.3');" "$PROD_RT/app/bootstrap.php"
grep -Fq "define('VFAB_SCHEMA_VERSION', 29);" "$PROD_RT/app/bootstrap.php"
grep -Fq "define('VFAB_VERSION', '1.35.4');" "$TARGET_A/app/bootstrap.php"
grep -Fq "define('VFAB_SCHEMA_VERSION', 30);" "$TARGET_A/app/bootstrap.php"
echo 'RUNTIME_A_B_IDENTITY=PASS files=42'

BUILD_A="$GATE_ROOT/build-a"; BUILD_B="$GATE_ROOT/build-b"
python3 harness/scripts/p03_v1354_formal_builder.py --base-runtime "$PROD_RT" --target-runtime "$TARGET_A" --output "$BUILD_A" | tee "$GATE_ROOT/build-a.json"
python3 harness/scripts/p03_v1354_formal_builder.py --base-runtime "$PROD_RT" --target-runtime "$TARGET_B" --output "$BUILD_B" | tee "$GATE_ROOT/build-b.json"
python3 - "$GATE_ROOT/build-a.json" "$GATE_ROOT/build-b.json" <<'PY'
import json,sys
A=json.load(open(sys.argv[1]));B=json.load(open(sys.argv[2]));assert A==B
assert A['runtime_files']==42 and A['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
assert A['deleted_runtime_files']==[], A['deleted_runtime_files']
print('BUILDER_CONTRACT=PASS runtime_delete_paths=0')
PY

ARTS=(VF_Forge_V1.35.4_FULL.zip VF_Forge_V1.35.4_UPDATE.zip VF_Forge_V1.35.4_Atomic_Upgrade.zip repair-v1.35.4.php VF_Forge_V1.35.4_RELEASE_MANIFEST.json VF_Forge_V1.35.4_SOURCE_MANIFEST.txt VF_Forge_V1.35.4_RELEASE_NOTES.md VF_Forge_V1.35.4_PACKAGE_MANIFEST.json SHA256SUMS.txt)
for F in "${ARTS[@]}"; do
  test -f "$BUILD_A/$F"; test -f "$BUILD_B/$F"
  BA=$(stat -c%s "$BUILD_A/$F"); BB=$(stat -c%s "$BUILD_B/$F"); test "$BA" = "$BB"
  SA=$(sha256sum "$BUILD_A/$F"|awk '{print $1}'); SB=$(sha256sum "$BUILD_B/$F"|awk '{print $1}'); test "$SA" = "$SB"
  echo "ARTIFACT $F EXISTS_A=PASS EXISTS_B=PASS BYTES=$BA SHA256=$SA A_EQ_B=PASS"
done
cmp "$BUILD_A/VF_Forge_V1.35.4_UPDATE.zip" "$BUILD_A/VF_Forge_V1.35.4_Atomic_Upgrade.zip"
echo 'BUILD_A_EQ_BUILD_B=PASS'
echo 'UPDATE_EQ_ATOMIC=PASS'

unzip -t "$BUILD_A/VF_Forge_V1.35.4_FULL.zip" >/dev/null
unzip -t "$BUILD_A/VF_Forge_V1.35.4_Atomic_Upgrade.zip" >/dev/null
test "$(unzip -Z1 "$BUILD_A/VF_Forge_V1.35.4_FULL.zip"|wc -l|tr -d ' ')" = 42
test "$(unzip -Z1 "$BUILD_A/VF_Forge_V1.35.4_Atomic_Upgrade.zip")" = 'repair-v1.35.4.php'
php -l "$BUILD_A/repair-v1.35.4.php" >/dev/null
python3 - "$BUILD_A" "$TARGET_A" <<'PY'
import base64,gzip,hashlib,json,re,sys,zipfile
from pathlib import Path
b=Path(sys.argv[1]);rt=Path(sys.argv[2]);full=b/'VF_Forge_V1.35.4_FULL.zip';repair=(b/'repair-v1.35.4.php').read_text()
with zipfile.ZipFile(full) as z:
    names=z.namelist();assert len(names)==42 and len(names)==len(set(names))
    for n in names:
        assert n and not n.startswith('/') and '..' not in n.split('/') and not re.search(r'(^|/)(PRIVATE_DATA|storage/private|uploads|backup|backups|cache|session|sessions|logs|tmp)(/|$)',n,re.I) and not re.search(r'\.(sqlite3?|db)$|(^|/)\.env$',n,re.I)
        raw=z.read(n);p=rt/n;assert p.is_file() and raw==p.read_bytes()
sm=(b/'VF_Forge_V1.35.4_SOURCE_MANIFEST.txt').read_bytes();rows=sm.decode().splitlines();assert len(rows)==42
for row in rows:
    p,bs,h=row.split('\t');data=(rt/p).read_bytes();assert int(bs)==len(data) and h==hashlib.sha256(data).hexdigest()
const=lambda n: re.search(r"const "+re.escape(n)+r"='([^']*)';",repair).group(1)
raw=gzip.decompress(base64.b64decode(const('VFF_ATOMIC_PAYLOAD')));assert hashlib.sha256(raw).hexdigest()==const('VFF_ATOMIC_PAYLOAD_JSON_SHA256');obj=json.loads(raw)
assert obj['format']=='vf-forge-atomic-payload-v2' and obj['source_version']=='1.35.3' and obj['target_version']=='1.35.4' and obj['source_schema']==29 and obj['target_schema']==30
assert obj['migration']=='M030_EXTERNAL_AUTHORITY_MEMORY_INDEX' and obj['migration_runtime_path']=='app/schema30.sql'
assert obj['files']['app/schema30.sql']['sha256']==obj['migration_runtime_sha256']
assert obj['source_file_count']==42 and obj['source_manifest_sha256']==hashlib.sha256(sm).hexdigest()
assert obj['delete_paths']==[]
rm=json.load(open(b/'VF_Forge_V1.35.4_RELEASE_MANIFEST.json'))
assert rm['project']=='P03' and rm['version']=='1.35.4' and rm['schema']==30 and rm['source_version']=='1.35.3' and rm['schema_from']==29 and rm['schema_to']==30 and rm['migration']=='M030_EXTERNAL_AUTHORITY_MEMORY_INDEX'
assert rm['product_commit']=='af34b84a3135333cf05077b3eb64e22ef6b3afef' and rm['product_tree']=='08eee7e8c891a57c357553dd5de20c1a7bd79849'
assert rm['runtime_fingerprint']=='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083' and rm['project_asset_storage']=='NONE' and rm['user_upload']=='RETIRED' and rm['backup_required'] is True and rm['formal_release']=='NOT_EXECUTED'
print('PACKAGE_CONTENTS_MANIFEST_M030=PASS')
print('EXPECTED_PRODUCTION_SOURCE_MANIFEST_SHA256='+hashlib.sha256(sm).hexdigest())
PY

# Secret/private scan: actual ephemeral credential must never appear in formal files.
python3 - "$BUILD_A" <<'PY'
import os,re,sys
from pathlib import Path
root=Path(sys.argv[1]);token=os.environ.get('VF_PRIVATE_READ_TOKEN','').encode()
for p in root.iterdir():
    if not p.is_file(): continue
    b=p.read_bytes()
    if token and len(token)>=8: assert token not in b, p.name
print('SECRET_PRIVATE_SCAN=PASS')
PY

# FULL fresh install package gate.
FRESH_RT="$GATE_ROOT/full-fresh-runtime"; FRESH_DATA="$GATE_ROOT/full-fresh-private"; FRESH_COOKIE="$GATE_ROOT/full-fresh-cookie"; FRESH_BASE=http://127.0.0.1:18083
rm -rf "$FRESH_RT" "$FRESH_DATA" "$FRESH_COOKIE"; mkdir -p "$FRESH_RT" "$FRESH_DATA"; unzip -q "$BUILD_A/VF_Forge_V1.35.4_FULL.zip" -d "$FRESH_RT"
docker rm -f p03-v1354-full-fresh >/dev/null 2>&1||true
docker run -d --rm --name p03-v1354-full-fresh -p 18083:18083 -v "$FRESH_RT:/app" -v "$FRESH_DATA:$FRESH_DATA" -w /app "$PHP_TEST_IMAGE" php -S 0.0.0.0:18083 -t /app >/dev/null
for i in $(seq 1 80);do curl -fsS "$FRESH_BASE/setup.php" >/dev/null 2>&1&&break;sleep .25;done
curl -fsS -c "$FRESH_COOKIE" "$FRESH_BASE/setup.php" -o "$GATE_ROOT/fresh-setup.html"
FCSRF=$(python3 - "$GATE_ROOT/fresh-setup.html" <<'PY'
import re,sys;s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -i -b "$FRESH_COOKIE" -c "$FRESH_COOKIE" -H "Origin: $FRESH_BASE" --data-urlencode "setup_csrf=$FCSRF" --data-urlencode 'site_title=VF Forge V1.35.4 Formal FULL' --data-urlencode "data_root=$FRESH_DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$FRESH_BASE/setup.php" >"$GATE_ROOT/fresh-post.txt"
grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/fresh-post.txt"
FDB=$(find "$FRESH_DATA/database" -maxdepth 1 -type f -name '*.sqlite'|head -1);test -f "$FDB";test "$(sqlite3 "$FDB" 'select max(version) from schema_migrations;')" = 30;test "$(sqlite3 "$FDB" 'pragma integrity_check;')" = ok;test -z "$(sqlite3 "$FDB" 'pragma foreign_key_check;')";test "$(sqlite3 "$FDB" 'select count(*) from asset_files;')" = 0
docker rm -f p03-v1354-full-fresh >/dev/null
echo 'FULL_FRESH_INSTALL=PASS schema=30 project_asset_files=0'

# Real Production 1.35.3 fixture -> formal Atomic artifact -> 1.35.4 / Schema30.
UP_RT="$GATE_ROOT/upgrade-runtime"; UP_DATA="$GATE_ROOT/upgrade-private"; UP_COOKIE="$GATE_ROOT/upgrade-cookie"; UP_BASE=http://127.0.0.1:18084
rm -rf "$UP_RT" "$UP_DATA" "$UP_COOKIE";cp -a "$PROD_RT" "$UP_RT";mkdir -p "$UP_DATA"
docker rm -f p03-v1354-upgrade >/dev/null 2>&1||true
docker run -d --rm --name p03-v1354-upgrade -p 18084:18084 -v "$UP_RT:/app" -v "$UP_DATA:$UP_DATA" -w /app "$PHP_TEST_IMAGE" php -S 0.0.0.0:18084 -t /app >/dev/null
trap 'docker logs p03-v1354-upgrade 2>/dev/null||true;docker rm -f p03-v1354-upgrade >/dev/null 2>&1||true' EXIT
for i in $(seq 1 80);do curl -fsS "$UP_BASE/setup.php" >/dev/null 2>&1&&break;sleep .25;done
curl -fsS -c "$UP_COOKIE" "$UP_BASE/setup.php" -o "$GATE_ROOT/up-setup.html"
UCSRF=$(python3 - "$GATE_ROOT/up-setup.html" <<'PY'
import re,sys;s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="setup_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -i -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" --data-urlencode "setup_csrf=$UCSRF" --data-urlencode 'site_title=VF Forge Formal Upgrade Fixture' --data-urlencode "data_root=$UP_DATA" --data-urlencode "password=$FIXTURE_PASS" --data-urlencode "password_confirm=$FIXTURE_PASS" "$UP_BASE/setup.php" >"$GATE_ROOT/up-post.txt";grep -Eq '^HTTP/.* 302|^HTTP/.* 303' "$GATE_ROOT/up-post.txt"
LOGIN=$(printf '{"password":"%s"}' "$FIXTURE_PASS");curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" -H 'Content-Type: application/json' --data "$LOGIN" "$UP_BASE/api.php?action=login" -o "$GATE_ROOT/up-login.json"
TOKEN=$(python3 - "$GATE_ROOT/up-login.json" <<'PY'
import json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and d['version']=='1.35.3';print(d['csrf'])
PY
)
api_post(){ curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" -H "X-CSRF-Token: $TOKEN" -H 'Content-Type: application/json' --data "$2" "$UP_BASE/api.php?action=$1" -o "$3"; }
api_post project_save '{"name":"Formal Legacy Preserve","slug":"formal-legacy-preserve","project_code":"P99","development_stage":"maintenance"}' "$GATE_ROOT/up-project.json"
PID=$(python3 - "$GATE_ROOT/up-project.json" <<'PY'
import json,sys;d=json.load(open(sys.argv[1]));assert d['ok'];print(d['project']['id'])
PY
)
printf 'legacy-formal-binary-do-not-touch' >"$GATE_ROOT/legacy.bin"
curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" -H "X-CSRF-Token: $TOKEN" -F "project_id=$PID" -F 'scope=project' -F 'status=active' -F "files[]=@$GATE_ROOT/legacy.bin;filename=Legacy_FORMAL.bin" "$UP_BASE/api.php?action=upload" -o "$GATE_ROOT/up-upload.json"
AID=$(python3 - "$GATE_ROOT/up-upload.json" <<'PY'
import json,sys;d=json.load(open(sys.argv[1]));assert d['ok'] and len(d['uploaded'])==1;print(d['uploaded'][0]['id'])
PY
)
UDB=$(find "$UP_DATA/database" -maxdepth 1 -type f -name '*.sqlite'|head -1);test -f "$UDB"
python3 - "$UDB" "$PID" "$AID" "$GATE_ROOT/preserve-before.json" <<'PY'
import hashlib,json,os,sqlite3,sys
p=sys.argv[1];pid=int(sys.argv[2]);aid=int(sys.argv[3]);out=sys.argv[4];db=sqlite3.connect(p);db.row_factory=sqlite3.Row;now='2026-08-17T01:20:00Z'
u=lambda n:f'00000000-0000-4000-8000-{n:012d}'
db.execute("insert into release_records(uuid,project_id,version,release_status,created_at,updated_at) values (?,?,?,'stable',?,?)",(u(1),pid,'9.9.9',now,now));rid=db.execute('select last_insert_rowid()').fetchone()[0]
db.execute("insert into evidence_records(uuid,project_id,evidence_type,evidence_text,verification_result,context_fingerprint,created_at,updated_at) values (?,?,'fixture','formal evidence','pass','formal-fixture',?,?)",(u(2),pid,now,now));eid=db.execute('select last_insert_rowid()').fetchone()[0]
db.execute("insert into project_snapshots(uuid,project_id,snapshot_key,snapshot_kind,schema_version,completeness,fingerprint,snapshot_json,sealed_at,created_at) values (?,?,?,'manual',29,'complete',?,'{}',?,?)",(u(3),pid,'formal-snapshot',hashlib.sha256(b'formal-snapshot').hexdigest(),now,now));sid=db.execute('select last_insert_rowid()').fetchone()[0]
db.execute("insert into recipes(uuid,recipe_key,project_id,name,recipe_kind,status,system_managed,created_at,updated_at) values (?,?,?,?, 'custom','active',0,?,?)",(u(4),'formal-recipe',pid,'Formal Recipe',now,now));recipe=db.execute('select last_insert_rowid()').fetchone()[0]
db.execute("insert into recipe_revisions(uuid,recipe_id,revision_no,status,definition_fingerprint,created_at) values (?,?,1,'current',?,?)",(u(5),recipe,hashlib.sha256(b'formal-recipe').hexdigest(),now));rev=db.execute('select last_insert_rowid()').fetchone()[0];db.execute('update recipes set current_revision_id=? where id=?',(rev,recipe));db.commit()
queries={
'project':('select id,uuid,name,slug,project_code from projects where id=?',(pid,)),
'asset':('select a.id,a.uuid,a.file_id,a.primary_project_id,a.original_name,a.version,f.sha256,f.size_bytes,f.storage_path from assets a join asset_files f on f.id=a.file_id where a.id=?',(aid,)),
'recipe':('select r.id,r.recipe_key,r.name,r.current_revision_id,rr.revision_no,rr.definition_fingerprint from recipes r join recipe_revisions rr on rr.id=r.current_revision_id where r.id=?',(recipe,)),
'snapshot':('select id,uuid,project_id,snapshot_key,snapshot_kind,schema_version,fingerprint,snapshot_json,sealed_at from project_snapshots where id=?',(sid,)),
'release':('select id,uuid,project_id,version,release_status from release_records where id=?',(rid,)),
'evidence':('select id,uuid,project_id,evidence_type,evidence_text,verification_result,context_fingerprint from evidence_records where id=?',(eid,))}
res={k:dict(db.execute(q,a).fetchone()) for k,(q,a) in queries.items()};path=res['asset']['storage_path'];res['binary']={'path':path,'sha256':hashlib.sha256(open(path,'rb').read()).hexdigest(),'bytes':os.path.getsize(path),'mtime_ns':os.stat(path).st_mtime_ns};json.dump(res,open(out,'w'),sort_keys=True,ensure_ascii=False,indent=2);print('PRESERVATION_FIXTURE_READY')
PY
cp "$BUILD_A/repair-v1.35.4.php" "$UP_RT/repair-v1.35.4.php"
curl -fsS -b "$UP_COOKIE" "$UP_BASE/repair-v1.35.4.php" -o "$GATE_ROOT/repair-form.html"
RCSRF=$(python3 - "$GATE_ROOT/repair-form.html" <<'PY'
import re,sys;s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="_csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)
curl -fsS -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" --data-urlencode "_csrf=$RCSRF" --data-urlencode 'confirmation=UPGRADE' "$UP_BASE/repair-v1.35.4.php" -o "$GATE_ROOT/repair-result.html"
grep -q '升级完成' "$GATE_ROOT/repair-result.html";test ! -e "$UP_RT/repair-v1.35.4.php";grep -Fq "define('VFAB_VERSION', '1.35.4');" "$UP_RT/app/bootstrap.php";grep -Fq "define('VFAB_SCHEMA_VERSION', 30);" "$UP_RT/app/bootstrap.php"
test "$(sqlite3 "$UDB" 'select max(version) from schema_migrations;')" = 30;test "$(sqlite3 "$UDB" 'pragma integrity_check;')" = ok;test -z "$(sqlite3 "$UDB" 'pragma foreign_key_check;')";sqlite3 "$UDB" "select migration_id,status from schema_migrations where version=30;"|grep -q '^M030_EXTERNAL_AUTHORITY_MEMORY_INDEX|applied$'
python3 - "$UDB" "$GATE_ROOT/preserve-before.json" <<'PY'
import hashlib,json,os,sqlite3,sys
before=json.load(open(sys.argv[2]));db=sqlite3.connect(sys.argv[1]);db.row_factory=sqlite3.Row
ids={k:int(before[k]['id']) for k in ['project','asset','recipe','snapshot','release','evidence']}
queries={
'project':('select id,uuid,name,slug,project_code from projects where id=?',(ids['project'],)),
'asset':('select a.id,a.uuid,a.file_id,a.primary_project_id,a.original_name,a.version,f.sha256,f.size_bytes,f.storage_path from assets a join asset_files f on f.id=a.file_id where a.id=?',(ids['asset'],)),
'recipe':('select r.id,r.recipe_key,r.name,r.current_revision_id,rr.revision_no,rr.definition_fingerprint from recipes r join recipe_revisions rr on rr.id=r.current_revision_id where r.id=?',(ids['recipe'],)),
'snapshot':('select id,uuid,project_id,snapshot_key,snapshot_kind,schema_version,fingerprint,snapshot_json,sealed_at from project_snapshots where id=?',(ids['snapshot'],)),
'release':('select id,uuid,project_id,version,release_status from release_records where id=?',(ids['release'],)),
'evidence':('select id,uuid,project_id,evidence_type,evidence_text,verification_result,context_fingerprint from evidence_records where id=?',(ids['evidence'],))}
for k,(q,a) in queries.items():assert dict(db.execute(q,a).fetchone())==before[k],k
b=before['binary'];assert os.path.isfile(b['path']);assert hashlib.sha256(open(b['path'],'rb').read()).hexdigest()==b['sha256'];assert os.path.getsize(b['path'])==b['bytes'];assert os.stat(b['path']).st_mtime_ns==b['mtime_ns']
assert db.execute('select count(*) from legacy_asset_reconciliation where legacy_asset_id=?',(ids['asset'],)).fetchone()[0]==1
print('EXACT_EXISTING_OBJECT_PRESERVATION=PASS')
print('EXISTING_BINARY_SHA_BYTES_PATH_MTIME=UNCHANGED')
PY
# New project-file ingestion is retired after package upgrade.
code=$(curl -sS -o "$GATE_ROOT/retired-upload.json" -w '%{http_code}' -b "$UP_COOKIE" -c "$UP_COOKIE" -H "Origin: $UP_BASE" -H "X-CSRF-Token: $TOKEN" -F "project_id=$PID" -F "files[]=@$GATE_ROOT/legacy.bin;filename=should-not-upload.bin" "$UP_BASE/api.php?action=upload");test "$code" = 410
docker rm -f p03-v1354-upgrade >/dev/null;trap - EXIT
echo 'ARTIFACT_UPGRADE_1.35.3_TO_1.35.4=PASS'
echo 'SCHEMA_29_TO_30_PACKAGE_GATE=PASS'
echo 'MIGRATION_030_PACKAGED_APPLIED=PASS'
echo 'PROJECT_ASSET_STORAGE=NONE'
echo 'USER_UPLOAD=RETIRED'
echo 'PHYSICAL_PROJECT_ASSET_DELETE=0'

# Public-safe evidence only: no Actions artifact is uploaded; private checkout and packages are deleted.
python3 - "$BUILD_A" <<'PY'
from pathlib import Path
import hashlib
b=Path(__import__('sys').argv[1])
for n in ['VF_Forge_V1.35.4_FULL.zip','VF_Forge_V1.35.4_UPDATE.zip','VF_Forge_V1.35.4_Atomic_Upgrade.zip','repair-v1.35.4.php','VF_Forge_V1.35.4_RELEASE_MANIFEST.json','VF_Forge_V1.35.4_SOURCE_MANIFEST.txt','SHA256SUMS.txt']:
 p=b/n;print(f'FINAL_IDENTITY {n} BYTES={p.stat().st_size} SHA256={hashlib.sha256(p.read_bytes()).hexdigest()}')
PY
SRC_SHA=$(sha256sum "$BUILD_A/VF_Forge_V1.35.4_SOURCE_MANIFEST.txt"|awk '{print $1}');echo "EXPECTED_PRODUCTION_SOURCE_MANIFEST_SHA256=$SRC_SHA"
echo 'FORMAL_ARTIFACT_PRE_GATE=PASS_COMPLETE'
echo 'CANDIDATE=V1.35.4_VERIFIED'
echo 'PRODUCT_FAILURE=NONE';echo 'PROJECT_BLOCK=NONE';echo 'TAG_RELEASE_CORE_UPDATES_PRODUCTION=NOT_EXECUTED';echo 'PRODUCTION_WRITE=0';echo 'NEXT=STOP_FOR_MASTER'
