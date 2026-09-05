#!/usr/bin/env bash
set -Eeuo pipefail
BASE=bd2fb0f84a39cbbbdc0c4d999397c4c7c0f82f44
CANDIDATE=3a89aca6ea87e0bfabeab2cc414388ad3188bd9a

test "$(git rev-parse HEAD)" = "$CANDIDATE"
test "$(git merge-base "$BASE" "$CANDIDATE")" = "$BASE"

cat >/tmp/expected-scope <<'EOF'
.github/phase3/v121814-static-source-recovery-v2.php
VERSION
includes/content-model/lifecycle-service.php
includes/release/async-job-parts/01-job-create-trait.php
includes/release/async-job-parts/03-job-state-trait.php
includes/site-release/s01-static-candidate-readiness.php
includes/site-release/s01-static-source-recovery-v2.php
vf-ops.php
EOF
git diff --name-only "$BASE" "$CANDIDATE" | sort >/tmp/actual-scope
sort /tmp/expected-scope -o /tmp/expected-scope
diff -u /tmp/expected-scope /tmp/actual-scope

test "$(cat VERSION)" = 1.21.814
grep -Fq 'Version: 1.21.814' vf-ops.php
grep -Fq "VF_OPS_VERSION', '1.21.814'" vf-ops.php
grep -Fq "VF_OPS_ROUND', 'STATIC-SOURCE-RECOVERY-V2'" vf-ops.php
grep -Fq "s01-static-source-recovery-v2.php" vf-ops.php

echo SOURCE_IDENTITY_SCOPE=PASS

# Ordinary upgrade preserves release jobs; explicit full cleanup contract remains.
grep -Fq '$cleanup = vf_ops_lifecycle_cleanup_volatile_v121377(false);' includes/content-model/lifecycle-service.php
grep -Fq 'function vf_ops_lifecycle_cleanup_volatile_v121377(bool $fullReleaseCleanup = true)' includes/content-model/lifecycle-service.php
grep -Fq 'if ($fullReleaseCleanup && vf_ops_lifecycle_load_release_runtime_v121377())' includes/content-model/lifecycle-service.php
grep -Fq 'cleanup_expired_release_artifacts_v121339' includes/content-model/lifecycle-service.php

echo LIFECYCLE_PRESERVATION_CONTRACT=PASS

find . -path './.git' -prune -o -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/tmp/php-lint.txt
php .github/phase3/v121814-static-source-recovery-v2.php

echo PHP_AND_FOCUSED_CONTRACT=PASS

cat >/tmp/recovery-v2-harness.php <<'PHP'
<?php
define('ABSPATH','/tmp/');
$GLOBALS['vf_settings']=[];
$GLOBALS['vf_upload_base']='';
$GLOBALS['vf_record']=[];
$GLOBALS['vf_batch']=[];
function sanitize_key($s){return strtolower(preg_replace('/[^a-z0-9_\-]/i','',(string)$s));}
function current_time($x){return '2026-09-05 00:00:00';}
function get_option($k,$d=[]){if($k==='simply-static')return $GLOBALS['vf_settings'];return $d;}
function update_option($k,$v,$a=false){return true;}
function wp_upload_dir(){return ['basedir'=>$GLOBALS['vf_upload_base']];}
function add_action(...$x){}
function vf_toolsite_cf_release_record(){return $GLOBALS['vf_record'];}
function vf_ops_release_batch_active_id_v121363(){return 'batch';}
function vf_ops_release_batch_find_v121363($id){return $GLOBALS['vf_batch'];}
require getcwd().'/includes/site-release/s01-static-source-recovery-v2.php';
function must($ok,$name){if(!$ok){fwrite(STDERR,"FAIL_$name\n");exit(1);}}
$root=sys_get_temp_dir().'/vf-v121814-'.bin2hex(random_bytes(4));
mkdir($root,0700,true);
$one=$root.'/one.zip'; file_put_contents($one,"PK\x03\x04recovery-source-one");
$sha=hash_file('sha256',$one);
file_put_contents($root.'/ignore.txt','x');
$GLOBALS['vf_settings']=['temp_files_dir'=>$root];
$r=vf_ops_s01_static_source_recovery_v2_scan_v121814($sha);
must(!empty($r['ok']) && $r['code']==='SIMPLY_STATIC_SOURCE_UNIQUE_MATCH' && count($r['matches'])===1 && $r['zipCandidateCount']===1,'UNIQUE_MATCH');
copy($one,$root.'/two.zip');
$r=vf_ops_s01_static_source_recovery_v2_scan_v121814($sha);
must(empty($r['ok']) && $r['code']==='AMBIGUOUS_SIMPLY_STATIC_SOURCE' && count($r['matches'])===2,'AMBIGUOUS_BLOCK');
unlink($root.'/one.zip'); unlink($root.'/two.zip');
$r=vf_ops_s01_static_source_recovery_v2_scan_v121814($sha);
must(empty($r['ok']) && $r['code']==='SIMPLY_STATIC_SOURCE_NOT_FOUND','ZERO_MATCH_BLOCK');
$default=$root.'/simply-static/temp-files'; mkdir($default,0700,true);
$zip=$default.'/archive.zip'; file_put_contents($zip,"PK\x03\x04default-source"); $defaultSha=hash_file('sha256',$zip);
$GLOBALS['vf_settings']=[]; $GLOBALS['vf_upload_base']=$root;
$r=vf_ops_s01_static_source_recovery_v2_scan_v121814($defaultSha);
must(!empty($r['ok']) && $r['basis']==='default_uploads_temp_files','DEFAULT_DIR');
$a=str_repeat('a',64);$b=str_repeat('b',64);
$GLOBALS['vf_record']=['source_sha256'=>$a,'source_package_sha256'=>$a];
$GLOBALS['vf_batch']=['source_package_sha256'=>$a];
$r=vf_ops_s01_static_source_recovery_v2_sha_authority_v121814();
must(!empty($r['ok']) && $r['sha']===$a,'SHA_AUTHORITY');
$GLOBALS['vf_batch']=['source_package_sha256'=>$b];
$r=vf_ops_s01_static_source_recovery_v2_sha_authority_v121814();
must(empty($r['ok']) && $r['code']==='SOURCE_HASH_AUTHORITY_CONFLICT','SHA_CONFLICT_BLOCK');
echo "PASS_V121814_RECOVERY_BEHAVIOR_HARNESS\n";
PHP
php /tmp/recovery-v2-harness.php

# Public read model cannot mutate, hash, or disclose sensitive source identity.
! grep -Eq 'sourceRecovery(Path|Sha|JobId|FileName|Url)' includes/site-release/s01-static-candidate-readiness.php
! grep -Fq 'source_recovery_v2_start_v121814(' includes/site-release/s01-static-candidate-readiness.php
! grep -Fq 'hash_file(' includes/site-release/s01-static-candidate-readiness.php

# No M3U8/Seed/content/DNS/schema mutation added by the V2 service delta.
! grep -Ei '(m3u8|seed hold|dns).*(update_option|delete_option|\$wpdb->|drop table|truncate)' includes/site-release/s01-static-source-recovery-v2.php

echo FAIL_CLOSED_PUBLIC_BOUNDARY=PASS

mkdir -p /tmp/v121814-release
python3 - <<'PY'
from pathlib import Path
import hashlib,json,re,zipfile
files=[]
for p in Path('.').rglob('*'):
    if not p.is_file() or p.is_symlink(): continue
    rel=p.as_posix().lstrip('./'); parts=rel.split('/')
    if any(x.lower() in {'.git','.github','test','tests','doc','docs','evidence','private','tmp','temp','cache','log','logs'} for x in parts): continue
    if re.search(r'\.(sql|sqlite|sqlite3|db|log|zip|tar|gz|bak|tmp)$',rel,re.I): continue
    if '/' not in rel:
        if rel not in {'vf-ops.php','uninstall.php'}: continue
    elif parts[0] not in {'includes','assets','languages','config'}: continue
    files.append((rel,p.read_bytes()))
files.sort(key=lambda x:x[0])
fp=hashlib.sha256()
for rel,b in files: fp.update((rel+'\0'+hashlib.sha256(b).hexdigest()+'\n').encode())
z=Path('/tmp/v121814-release/vf-tools-ops_V1.21.814.zip')
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as out:
    for rel,b in files:
        i=zipfile.ZipInfo('vf-ops/'+rel,(2026,9,5,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o100644<<16; out.writestr(i,b)
a={'bytes':z.stat().st_size,'sha256':hashlib.sha256(z.read_bytes()).hexdigest(),'runtime_files':len(files),'runtime_fingerprint':fp.hexdigest()}
print('V121814_ARTIFACT_AUTHORITY='+json.dumps(a,separators=(',',':')))
assert len(files)==901, len(files)
PY
unzip -tq /tmp/v121814-release/vf-tools-ops_V1.21.814.zip >/dev/null
unzip -p /tmp/v121814-release/vf-tools-ops_V1.21.814.zip vf-ops/vf-ops.php | grep -Fq 'Version: 1.21.814'

echo PASS_V121814_CANDIDATE_GATE
