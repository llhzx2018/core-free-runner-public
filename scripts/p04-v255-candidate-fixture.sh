#!/usr/bin/env bash
set -Eeuo pipefail

: "${RUNNER_TEMP:?}"
TARGET_SRC="$1"
PRIOR_SRC="$2"
V254_SRC="$3"
WORK="$RUNNER_TEMP/p04-v255-fixture"
rm -rf "$WORK"
mkdir -p "$WORK"

TARGET_RT="$WORK/target-runtime"
PRIOR_RT_BUILD="$WORK/prior-runtime-build"
V254_RT="$WORK/v254-runtime"
CAND="$WORK/candidate"

python3 "$TARGET_SRC/scripts/build-release-tree.py" "$TARGET_RT" --source-root "$TARGET_SRC" | tee "$WORK/target-build.json"
python3 "$PRIOR_SRC/scripts/build-release-tree.py" "$PRIOR_RT_BUILD" --source-root "$PRIOR_SRC" | tee "$WORK/prior-build.json"
python3 "$V254_SRC/scripts/build-release-tree.py" "$V254_RT" --source-root "$V254_SRC" | tee "$WORK/v254-build.json"

python3 - "$WORK/target-build.json" "$WORK/v254-build.json" "$TARGET_RT" "$V254_RT" <<'PY'
import hashlib,json,pathlib,sys
T=json.loads(pathlib.Path(sys.argv[1]).read_text().strip().splitlines()[-1])
B=json.loads(pathlib.Path(sys.argv[2]).read_text().strip().splitlines()[-1])
assert T['version']=='2.5.5' and T['schema']==14 and T['file_count']==150
assert B['version']=='2.5.4' and B['schema']==14 and B['file_count']==150
tr=pathlib.Path(sys.argv[3]); br=pathlib.Path(sys.argv[4])
tf={p.relative_to(tr).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in tr.rglob('*') if p.is_file()}
bf={p.relative_to(br).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in br.rglob('*') if p.is_file()}
assert set(tf)==set(bf)
diff=sorted(k for k in tf if tf[k]!=bf[k])
assert diff==['VERSION.txt','release-manifest.json'],diff
print('V254_TO_V255_RUNTIME_NONREGRESSION=PASS differences='+','.join(diff))
print('TARGET_RUNTIME_FILES='+str(T['file_count']))
print('TARGET_RUNTIME_FINGERPRINT='+T['source_fingerprint'])
PY

python3 "$TARGET_SRC/scripts/build-v255-update-release.py" --target-runtime "$TARGET_RT" --output "$CAND" | tee "$WORK/candidate-build.json"
UPDATE="$CAND/VF_Infra_V2.5.5_UPDATE.zip"
ATOMIC="$CAND/VF_Infra_V2.5.5_ATOMIC.zip"
test -f "$UPDATE" -a -f "$ATOMIC"
cmp -s "$UPDATE" "$ATOMIC"
UPDATE_BYTES="$(stat -c '%s' "$UPDATE")"
UPDATE_SHA="$(sha256sum "$UPDATE" | awk '{print $1}')"
python3 "$TARGET_SRC/scripts/validate-online-atomic-package.py" --runtime "$TARGET_RT" --zip "$UPDATE" --version 2.5.5 --sha256 "$UPDATE_SHA"
python3 - "$CAND/PACKAGE_MANIFEST.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
assert m['version']=='2.5.5' and m['schema']==14
assert m['allowed_source_versions']==['2.5.3']
assert m['payload_file_count']==10
assert m['schema_change'] is False
assert m['business_model_change'] is False
assert m['provider_write_authority_change'] is False
assert m['online_handoff_marker']=='VF_INFRA_ONLINE_HANDOFF_V1'
assert m['online_handoff_contract']=='consumer-derived'
assert m['online_handoff_gate']=='PASS'
print('PACKAGE_MANIFEST_GATE=PASS')
print('V254_TO_V255_SUPPORT=NOT_ADVERTISED_NOT_VERIFIED')
PY

echo "CANDIDATE_UPDATE_BYTES=$UPDATE_BYTES"
echo "CANDIDATE_UPDATE_SHA256=$UPDATE_SHA"

# Negative package contract tests.
NEG="$WORK/negative"; mkdir -p "$NEG"
python3 - "$UPDATE" "$NEG" <<'PY'
from pathlib import Path
import re,sys,zipfile
src=Path(sys.argv[1]); out=Path(sys.argv[2])
with zipfile.ZipFile(src) as z:
    name=[x for x in z.namelist() if not x.endswith('/')][0]
    raw=z.read(name)
def write(label,data,extra=False):
    p=out/(label+'.zip')
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(name,data)
        if extra:z.writestr('unexpected.txt',b'x')
marker=b'VF_INFRA_ONLINE_HANDOFF_V1'
assert marker in raw
write('missing-marker',raw.replace(marker,b'NO_ONLINE_HANDOFF_MARKER'))
write('wrong-marker',raw.replace(marker,b'VF_INFRA_ONLINE_HANDOFF_V999'))
write('malformed-repair',raw+b"\n<?php this is not valid php !!!\n")
m=re.search(rb"const VF_INFRA_ATOMIC_PAYLOAD_SHA256='([a-f0-9]{64})';",raw)
assert m
old=m.group(1); new=(b'0' if old[:1]!=b'0' else b'1')+old[1:]
write('wrong-payload',raw[:m.start(1)]+new+raw[m.end(1):])
write('wrong-structure',raw,True)
PY

expect_fail(){ local label="$1"; shift; if "$@" >"$WORK/$label.out" 2>"$WORK/$label.err"; then echo "$label=UNEXPECTED_PASS"; exit 1; else echo "$label=FAIL_CLOSED_PASS"; fi; }
expect_fail MISSING_HANDOFF_MARKER python3 "$TARGET_SRC/scripts/validate-online-atomic-package.py" --runtime "$TARGET_RT" --zip "$NEG/missing-marker.zip" --version 2.5.5
expect_fail WRONG_HANDOFF_MARKER python3 "$TARGET_SRC/scripts/validate-online-atomic-package.py" --runtime "$TARGET_RT" --zip "$NEG/wrong-marker.zip" --version 2.5.5
expect_fail MALFORMED_REPAIR python3 "$TARGET_SRC/scripts/validate-online-atomic-package.py" --runtime "$TARGET_RT" --zip "$NEG/malformed-repair.zip" --version 2.5.5
expect_fail WRONG_SHA python3 "$TARGET_SRC/scripts/validate-online-atomic-package.py" --runtime "$TARGET_RT" --zip "$UPDATE" --version 2.5.5 --sha256 "$(printf '0%.0s' {1..64})"
expect_fail WRONG_PAYLOAD python3 "$TARGET_SRC/scripts/validate-online-atomic-package.py" --runtime "$TARGET_RT" --zip "$NEG/wrong-payload.zip" --version 2.5.5
expect_fail WRONG_PACKAGE_STRUCTURE python3 "$TARGET_SRC/scripts/validate-online-atomic-package.py" --runtime "$TARGET_RT" --zip "$NEG/wrong-structure.zip" --version 2.5.5

# Build exact prior Production-like fixture from main 2.5.3.
SITE="$WORK/site"
mkdir -p "$SITE/htdocs"
cp -a "$PRIOR_RT_BUILD/." "$SITE/htdocs/"
PORT=18555
BASE="http://127.0.0.1:$PORT"
SERVER_LOG="$WORK/php-server.log"
php -S "127.0.0.1:$PORT" -t "$SITE/htdocs" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
for i in {1..40}; do curl -fsS "$BASE/setup.php" -o "$WORK/setup.html" && break || sleep .25; done
COOKIE="$WORK/cookies.txt"
curl -fsS -c "$COOKIE" -b "$COOKIE" "$BASE/setup.php" -o "$WORK/setup.html"
CSRF="$(python3 - "$WORK/setup.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)"
SETUP_CODE="$(curl -sS -o "$WORK/setup-post.html" -D "$WORK/setup-post.headers" -c "$COOKIE" -b "$COOKIE" -w '%{http_code}' \
  -H "Origin: $BASE" -H "Referer: $BASE/setup.php" \
  --data-urlencode "csrf=$CSRF" --data-urlencode 'site_name=VF Infra Fixture' \
  --data-urlencode 'password=FixturePass12345' --data-urlencode 'password_confirm=FixturePass12345' \
  "$BASE/setup.php")"
case "$SETUP_CODE" in 301|302|303) ;; *) echo "SETUP_HTTP=$SETUP_CODE"; cat "$WORK/setup-post.html"; exit 1;; esac
curl -fsS -c "$COOKIE" -b "$COOKIE" "$BASE/login.php" -o "$WORK/login.html"
LCSRF="$(python3 - "$WORK/login.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)"
LOGIN_CODE="$(curl -sS -o "$WORK/login-post.html" -D "$WORK/login-post.headers" -c "$COOKIE" -b "$COOKIE" -w '%{http_code}' \
  -H "Origin: $BASE" -H "Referer: $BASE/login.php" \
  --data-urlencode "csrf=$LCSRF" --data-urlencode 'password=FixturePass12345' "$BASE/login.php")"
case "$LOGIN_CODE" in 301|302|303) ;; *) echo "LOGIN_HTTP=$LOGIN_CODE"; exit 1;; esac
curl -fsS -c "$COOKIE" -b "$COOKIE" "$BASE/index.php" -o "$WORK/index.html"
grep -Fq 'VF Infra' "$WORK/index.html"
echo 'EXACT_253_FIXTURE_BOOT_LOGIN=PASS'

DATA="$SITE/.vfinfra-data"
DB="$DATA/database/vf-domain.sqlite"
test -f "$DB"
python3 - "$DB" <<'PY'
import sqlite3,sys
p=sys.argv[1];c=sqlite3.connect(p);c.execute('PRAGMA foreign_keys=ON')
now='2026-08-16 05:05:00'
c.execute("INSERT INTO domain_groups(name,sort_order,created_at,updated_at) VALUES(?,?,?,?)",('Fixture Group',10,now,now))
gid=c.execute("SELECT id FROM domain_groups WHERE name='Fixture Group'").fetchone()[0]
c.execute("INSERT INTO domains(domain,project_name,group_id,created_at,updated_at) VALUES(?,?,?,?,?)",('fixture-example.test','Fixture Project',gid,now,now))
c.commit(); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
print('SYNTHETIC_BUSINESS_STATE=PASS')
PY

python3 - "$DB" "$WORK/business-before.json" <<'PY'
import sqlite3,json,hashlib,sys
c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row
names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
tables=['domain_groups','domains','assets','asset_relations','provider_accounts','credentials','compute_instances','ip_addresses','dns_zones','dns_records','projects','project_assets','provider_billing_balances','provider_billing_invoices','provider_billing_transactions','provider_billing_alert_rules','alerts']
out={}
for t in tables:
    if t not in names: continue
    rows=[dict(r) for r in c.execute('SELECT * FROM "'+t+'" ORDER BY rowid')]
    raw=json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    out[t]={'count':len(rows),'sha256':hashlib.sha256(raw).hexdigest()}
open(sys.argv[2],'w').write(json.dumps(out,sort_keys=True,indent=2))
PY

# Recovery contract fixture on an isolated clone, never on the success fixture.
REC="$WORK/recovery-site"
cp -a "$SITE" "$REC"
python3 - "$REC/htdocs/config.php" "$SITE/.vfinfra-data" "$REC/.vfinfra-data" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text(); assert sys.argv[2] in s;p.write_text(s.replace(sys.argv[2],sys.argv[3]))
PY
cat >"$WORK/recovery-fixture.php" <<'PHP'
<?php
declare(strict_types=1);
$root=$argv[1];require $root.'/bootstrap.php';
$orig=hash_file('sha256',$root.'/VERSION.txt');if(!is_string($orig))throw new RuntimeException('orig hash');
$payloadRoot=Config::path('temp/recovery-contract-fixture');@mkdir($payloadRoot,0700,true);file_put_contents($payloadRoot.'/VERSION.txt',"9.9.9\n");
$target=hash_file('sha256',$payloadRoot.'/VERSION.txt');
$j=new \VFInfra\Core\Release\DurableReleaseJournal();$tx=new \VFInfra\Core\Release\AtomicFilesystemTransaction($root,$j);
$tx->begin('2.5.3','2.5.5',['VERSION.txt'=>$orig]);$tx->stageDirectory($payloadRoot,['VERSION.txt'=>$target]);$tx->markDbSnapshotted();$tx->replace(['VERSION.txt'=>$target]);
if(trim((string)file_get_contents($root.'/VERSION.txt'))!=='9.9.9')throw new RuntimeException('replace fixture failed');
$tx->rollback('candidate_recovery_fixture');clearstatcache();
if(!hash_equals($orig,(string)hash_file('sha256',$root.'/VERSION.txt'))||trim((string)file_get_contents($root.'/VERSION.txt'))!=='2.5.3')throw new RuntimeException('rollback fixture failed');
echo "RECOVERY_FIXTURE_PASS\n";
PHP
php "$WORK/recovery-fixture.php" "$REC/htdocs"
echo 'RECOVERY_CONTRACT=PASS'

# Real OnlineUpdateService::prepare() with isolated authenticated/private transport simulation.
cat >"$WORK/prepare-fixture.php" <<'PHP'
<?php
declare(strict_types=1);
$root=$argv[1];$zip=$argv[2];$out=$argv[3];
require $root.'/bootstrap.php';
$bytes=filesize($zip);$sha=hash_file('sha256',$zip);if(!is_int($bytes)||!is_string($sha))throw new RuntimeException('candidate identity');
$token=(string)getenv('P04_FIXTURE_PRIVATE_TOKEN');if($token==='')throw new RuntimeException('fixture private auth missing');
$manifest=['schema_version'=>'1.0','project_id'=>'P04','component_id'=>'APP','enabled'=>true,'target_version'=>'2.5.5','update_type'=>'ATOMIC','from_versions'=>['2.5.3'],'schema_from'=>'14','schema_to'=>'14','repository'=>'llhzx2018/vf-infra','release_tag'=>'v2.5.5','asset_name'=>'VF_Infra_V2.5.5_UPDATE.zip','asset_bytes'=>$bytes,'asset_sha256'=>$sha,'backup_required'=>true,'rollback_supported'=>true,'released_at'=>'2026-08-16T05:05:00Z','minimum_php'=>'8.0.0','notes'=>'isolated V2.5.5 candidate fixture'];
$source=new class($manifest,$bytes) implements \VFInfra\Core\Update\UpdateSourceInterface {private array $m;private int $b;function __construct($m,$b){$this->m=$m;$this->b=$b;}function fetchProjectManifest():array{$r=json_encode($this->m,JSON_UNESCAPED_SLASHES);return ['manifest'=>$this->m,'raw'=>$r,'sha256'=>hash('sha256',$r)];}function resolveReleaseAsset(string $repository,string $releaseTag,string $assetName):array{return ['id'=>255,'url'=>'private-fixture://p04/v255','name'=>$assetName,'size'=>$this->b,'tag'=>$releaseTag];}};
$transport=new class($zip,$token) implements \VFInfra\Core\Update\UpdateTransportInterface {private string $z;private string $t;function __construct($z,$t){$this->z=$z;$this->t=$t;}function fetch(string $url,int $maxBytes,int $timeoutSeconds,array $requestHeaders=[]):array{if($this->t==='')throw new RuntimeException('private auth');return ['body'=>'','status'=>200,'content_type'=>'application/json','etag'=>'fixture'];}function download(string $url,string $destination,int $expectedBytes,string $expectedSha256):array{if($this->t==='')throw new RuntimeException('private auth');if(!copy($this->z,$destination))throw new RuntimeException('fixture download');$b=filesize($destination);$s=hash_file('sha256',$destination);if($b!==$expectedBytes||!is_string($s)||!hash_equals(strtolower($expectedSha256),strtolower($s)))throw new RuntimeException('fixture bytes/sha');return ['bytes'=>$b,'sha256'=>$s];}};
$ms=new \VFInfra\Core\Update\UpdateManifestService($source,'2.5.3',14);$svc=new \VFInfra\Core\Update\OnlineUpdateService($ms,$transport);$r=$svc->prepare();
file_put_contents($out,json_encode($r,JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR));
PHP
P04_FIXTURE_PRIVATE_TOKEN='fixture-private-auth' php "$WORK/prepare-fixture.php" "$SITE/htdocs" "$UPDATE" "$WORK/prepare-private.json"
python3 - "$WORK/prepare-private.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]));assert r['from_version']=='2.5.3' and r['to_version']=='2.5.5';assert r['handoff_url']=='repair-v2.5.5.php';assert isinstance(r['handoff_token'],str) and len(r['handoff_token'])>=32;assert int(r['recovery_backup_id'])>0
print('UPDATE_PREPARE=PASS');print('HANDOFF_URL=PASS');print('HANDOFF_TOKEN=PASS');print('PRIVATE_ASSET_TRANSPORT_FIXTURE=PASS')
PY

# Protected backup is created only after bytes/SHA/package/marker gates pass.
python3 - "$DB" "$DATA" "$WORK/prepare-private.json" <<'PY'
import sqlite3,json,hashlib,pathlib,sys
c=sqlite3.connect(sys.argv[1]);r=json.load(open(sys.argv[3]));bid=int(r['recovery_backup_id'])
row=c.execute('SELECT filename,backup_type,sha256,source_version,schema_version,protected FROM backups WHERE id=?',(bid,)).fetchone();assert row
fn,typ,sha,ver,schema,prot=row;assert typ=='pre_update' and ver=='2.5.3' and schema==14 and prot==1
p=pathlib.Path(sys.argv[2])/'backups'/fn;assert p.is_file();assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
b=sqlite3.connect(p);assert b.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert b.execute('PRAGMA foreign_key_check').fetchall()==[]
print('BACKUP=PASS')
PY

# Missing handoff token must fail closed without consuming the real pending token.
cat >"$WORK/missing-token.php" <<'PHP'
<?php
declare(strict_types=1);$root=$argv[1];require $root.'/bootstrap.php';try{\VFInfra\Core\Update\OnlineUpdateHandoff::authorize('2.5.5','', 'repair-v2.5.5.php');fwrite(STDERR,"unexpected pass\n");exit(2);}catch(Throwable $e){echo "HANDOFF_TOKEN_MISSING_FAIL_CLOSED_PASS\n";}
PHP
php "$WORK/missing-token.php" "$SITE/htdocs"

HANDOFF_TOKEN="$(python3 - "$WORK/prepare-private.json" <<'PY'
import json,sys;print(json.load(open(sys.argv[1]))['handoff_token'])
PY
)"
HANDOFF_CODE="$(curl -sS -o "$WORK/handoff.html" -c "$COOKIE" -b "$COOKIE" -w '%{http_code}' \
  -H "Origin: $BASE" -H "Referer: $BASE/index.php" --data-urlencode "vf_online_handoff=$HANDOFF_TOKEN" "$BASE/repair-v2.5.5.php")"
test "$HANDOFF_CODE" = '200'
if grep -Fq "$HANDOFF_TOKEN" "$WORK/handoff.html"; then echo 'HANDOFF_TOKEN_EXPOSED=FAIL'; exit 1; fi
ATOMIC_CSRF="$(python3 - "$WORK/handoff.html" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'name="csrf" value="([^"]+)"',s);assert m;print(m.group(1))
PY
)"
python3 - "$DATA/state/update/pending-handoff-v1.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]));assert p.get('authorized_at');assert p.get('handoff_digest','')=='';assert p.get('target_version')=='2.5.5'
print('ONLINE_HANDOFF=PASS')
PY

ATOMIC_CODE="$(curl -sS -o "$WORK/atomic-result.html" -c "$COOKIE" -b "$COOKIE" -w '%{http_code}' \
  -H "Origin: $BASE" -H "Referer: $BASE/repair-v2.5.5.php" --data-urlencode "csrf=$ATOMIC_CSRF" "$BASE/repair-v2.5.5.php")"
test "$ATOMIC_CODE" = '200'
grep -Fq '升级完成' "$WORK/atomic-result.html"
test "$(cat "$SITE/htdocs/VERSION.txt")" = '2.5.5'
echo 'ATOMIC_UPGRADE_FIXTURE=PASS'

# New-runtime boot reconciliation finalizes Update History and retires handoff state.
cat >"$WORK/reconcile.php" <<'PHP'
<?php
declare(strict_types=1);$root=$argv[1];require $root.'/bootstrap.php';\VFInfra\Core\Update\OnlineUpdateHandoff::reconcileAfterBoot();echo "RECONCILE_AFTER_BOOT=PASS\n";
PHP
php "$WORK/reconcile.php" "$SITE/htdocs"

python3 - "$DB" "$WORK/prepare-private.json" <<'PY'
import sqlite3,json,sys
c=sqlite3.connect(sys.argv[1]);r=json.load(open(sys.argv[2]));op=r['operation_id']
assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
schema=c.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations WHERE status='success'").fetchone()[0];assert schema==14
ver=c.execute("SELECT value FROM settings WHERE key='installed_version'").fetchone()[0];assert ver=='2.5.5'
h=c.execute('SELECT result,failure_stage FROM update_history WHERE operation_id=?',(op,)).fetchone();assert h and h[0]=='success',h
print('SCHEMA_14=PASS');print('UPDATE_HISTORY_V255_SUCCESS=PASS')
PY

test ! -e "$DATA/state/update/pending-handoff-v1.json"
test ! -e "$SITE/htdocs/repair-v2.5.5.php"

# Exact candidate runtime reconciliation (config.php is protected runtime-local state).
python3 - "$TARGET_RT" "$SITE/htdocs" <<'PY'
import hashlib,pathlib,sys
exp=pathlib.Path(sys.argv[1]);got=pathlib.Path(sys.argv[2])
E={p.relative_to(exp).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in exp.rglob('*') if p.is_file()}
G={p.relative_to(got).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in got.rglob('*') if p.is_file() and p.name!='config.php'}
assert set(E)==set(G),(sorted(set(E)-set(G)),sorted(set(G)-set(E)))
bad=[k for k in E if E[k]!=G[k]];assert not bad,bad
print('RUNTIME_RECONCILIATION=PASS files='+str(len(E)))
PY

python3 - "$DB" "$WORK/business-before.json" <<'PY'
import sqlite3,json,hashlib,sys
c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row;before=json.load(open(sys.argv[2]));after={}
for t in before:
    rows=[dict(r) for r in c.execute('SELECT * FROM "'+t+'" ORDER BY rowid')]
    raw=json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();after[t]={'count':len(rows),'sha256':hashlib.sha256(raw).hexdigest()}
assert before==after,(before,after)
print('PRODUCTION_LIKE_BUSINESS_STATE_PRESERVATION=PASS')
PY

# Candidate evidence contains identities only, never the handoff token.
python3 - "$WORK/target-build.json" "$CAND/PACKAGE_MANIFEST.json" "$UPDATE" "$WORK/candidate-evidence.json" <<'PY'
import json,hashlib,pathlib,sys
b=json.loads(pathlib.Path(sys.argv[1]).read_text().strip().splitlines()[-1]);m=json.load(open(sys.argv[2]));z=pathlib.Path(sys.argv[3])
e={'version':'2.5.5','schema':14,'runtime_files':b['file_count'],'runtime_fingerprint':b['source_fingerprint'],'update_asset':z.name,'update_bytes':z.stat().st_size,'update_sha256':hashlib.sha256(z.read_bytes()).hexdigest(),'payload_files':m['payload_file_count'],'handoff_marker':m['online_handoff_marker'],'from_versions':m['allowed_source_versions'],'gates':{'builder_contract':'PASS','package_contract':'PASS','negative_contracts':'PASS','update_prepare':'PASS','handoff':'PASS','backup':'PASS','atomic':'PASS','runtime_reconciliation':'PASS','business_state':'PASS','recovery':'PASS'}}
pathlib.Path(sys.argv[4]).write_text(json.dumps(e,indent=2)+'\n')
print(json.dumps(e,separators=(',',':')))
PY

echo 'P04_V255_CANDIDATE_FIXTURE_ALL_PASS'
