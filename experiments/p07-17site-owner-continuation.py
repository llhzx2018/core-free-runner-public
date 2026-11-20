#!/usr/bin/env python3
"""P07 17-site owner-side migration handoff, CP2 only.

No old-site freeze, source delete, target overwrite, configuration swap, DNS,
service restart or production cutover. Three pending sites only are staged;
14 already staged sites are left alone. The restore step creates NEW target
CloudPanel databases only, checks SQL for cross-schema/control commands and
stops on any uncertainty. Each action is explicit and journaled privately.
"""
from __future__ import annotations
import argparse
import fcntl
import gzip
import hashlib
import json
import os
import shlex
from pathlib import Path
import re
import shutil
import subprocess
import secrets
import stat
import sys
import tempfile
from datetime import datetime, timezone

STATE_ROOT=Path('/var/lib/vf-server-ops/server-migrations')
BUNDLE_ROOT=Path('/var/backups/vf-server-ops/p07-17site-owner-bundle')
LIB=Path('/opt/vf-server-ops/lib')
JOBS=(('ORIGINAL17','pull-20261101T045943Z-923729a1',17),
      ('LEGACY9','pull-20261101T052411Z-35663c25',9),
      ('LAST2','pull-20261102T005644Z-7178c7d5',2))
PENDING=('ilovem3u8.kewaro.com','unzip.kewaro.com','www3.m3u8.one')
SAFE_DOMAIN=re.compile(r'[a-z0-9][a-z0-9.-]{1,150}[a-z0-9]\Z')
SAFE_DB=re.compile(r'[A-Za-z0-9._-]{1,64}\Z')
SQL_DANGER=re.compile(
    r'\b(?:CREATE|DROP|ALTER)\s+(?:DATABASE|SCHEMA|USER|SERVER|FUNCTION|PROCEDURE|EVENT|TRIGGER)\b'
    r'|\b(?:USE\s+[`A-Za-z]|GRANT\b|REVOKE\b|FLUSH\b|LOAD\s+DATA\b|INTO\s+OUTFILE\b)'
    r'|\bSET\s+(?:@@)?(?:GLOBAL|PERSIST)\b|\bINSTALL\s+PLUGIN\b|\bDELIMITER\b',re.I)

class Block(RuntimeError):pass

def must(v,code):
    if not v: raise Block(code)

def file_read_json(p):
    st=p.lstat()
    must(stat.S_ISREG(st.st_mode) and st.st_uid==0 and not st.st_mode & 0o022
         and st.st_size<8*1024*1024, 'STATE_UNSAFE')
    return json.loads(p.read_text(encoding='utf8'))

def private_dir(p):
    if p.exists():
        st=p.lstat()
        must(stat.S_ISDIR(st.st_mode) and st.st_uid==0 and not st.st_mode&0o077
             and not p.is_symlink(), 'PRIVATE_DIRECTORY_UNSAFE')
    else:
        p.mkdir(mode=0o700,parents=True,exist_ok=False)
        os.chmod(p,0o700)

def safe_write(p,obj):
    must(p.parent.is_dir() and not p.is_symlink(),'RECEIPT_UNSAFE')
    data=json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=True).encode()+b'\n'
    fd,name=tempfile.mkstemp(prefix='.p07-',dir=p.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,p)
    finally:
        if os.path.exists(name):os.unlink(name)

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def lib():
    must(LIB.is_dir(),'P07_INSTALLED_RUNTIME_MISSING')
    sys.path.insert(0,str(LIB))
    import server_migration_pull as pull
    import cloudpanel
    import sql_diff_evidence
    import site_lifecycle
    return pull,cloudpanel,sql_diff_evidence,site_lifecycle

def topology(pull):
    seen={};states=[];source_ids=set();target_ids=set()
    for label,mid,total in JOBS:
        s=file_read_json(STATE_ROOT/mid/'state.json')
        must(s.get('migration_id')==mid and s.get('status')=='PREPARE_FAILED'
             and s.get('schema')=='vf-server-ops.server-migration.target-pull.v1'
             and len(s.get('sites',[]))==total,'MIGRATION_CHAIN_CHANGED')
        for k in ('source_runtime_frozen','target_runtime_activated',
                  'dns_changed_by_p07','source_delete_allowed',
                  'existing_target_overwrite_allowed'):
            must(s.get(k) is False,'BOUNDARY_CHANGED')
        must(isinstance(s.get('source'),dict) and s.get('source_runtime_path'),
             'SOURCE_CONNECTION_MISSING')
        source_ids.add((s['source'].get('host'),s['source'].get('ssh_user'),
                        str(s['source'].get('ssh_port'))))
        target_ids.add(s.get('target_server_identity'))
        for site in s['sites']:
            status=site.get('stage_status');dom=site.get('domain')
            if status not in ('PENDING','PULLED_STAGED'):continue
            must(isinstance(dom,str) and SAFE_DOMAIN.fullmatch(dom),
                 'SITE_IDENTITY_INVALID')
            # Parent/child/tail intentionally overlap. The final owner record
            # wins; never treat the original parent PENDING as the last status.
            seen.setdefault(dom,[]).append((s,site))
        states.append(s)
    seen={name:records[-1] for name,records in seen.items()}
    must(len(seen)==17 and sum(v[1]['stage_status']=='PULLED_STAGED' for v in seen.values())==14,
         'SEVENTEEN_SITE_STAGE_SCOPE_CHANGED')
    must({d for d,v in seen.items() if v[1]['stage_status']=='PENDING'}==set(PENDING),
         'THREE_PENDING_SCOPE_CHANGED')
    must(len(source_ids)==1 and len(target_ids)==1 and
         next(iter(target_ids))==pull.target_identity(),'SOURCE_OR_CP2_IDENTITY_CHANGED')
    for d,(s,site) in seen.items():
        path=site.get('site_root');dbs=site.get('mysql_databases')
        must(type(path) is str and path.startswith('/home/') and '/..' not in path,
             'UNSAFE_SITE_ROOT')
        must(type(dbs) is list and len(dbs)<=1 and all(type(db) is str and
             SAFE_DB.fullmatch(db) for db in dbs),'DATABASE_SCOPE_INVALID')
        must(Path(path).is_dir(),'CP2_SITE_ROOT_MISSING')
    must(all(len(seen[d][1]['mysql_databases'])==1 for d in PENDING),
         'PENDING_DB_SCOPE_CHANGED')
    return seen

def source_ping(pull,seen):
    s=seen[PENDING[0]][0]
    out=pull.source_remote(s['source'],'printf P07_SOURCE_REACHABLE',timeout=25,check=False)
    must(out.returncode==0 and out.stdout.strip()=='P07_SOURCE_REACHABLE',
         'SOURCE_SSH_UNAVAILABLE')

def report(seen):
    print('MODE=PLAN_ONLY')
    print('SOURCE_TASKS=3')
    print('SITES_TOTAL='+str(len(seen)))
    print('SITES_ALREADY_STAGED=14')
    print('SITES_PENDING=3')
    for d in PENDING:print('PENDING_SITE='+d)
    print('SOURCE_MUTATION=NONE')
    print('TARGET_EXISTING_DATA_MUTATION=NONE')
    print('DNS_CHANGED=NO')
    print('CUTOVER_READY=NO')

def manifest_path():return BUNDLE_ROOT/'manifest.json'

def read_manifest():
    p=manifest_path()
    if not p.is_file():return {'schema':'P07_OWNER_STAGE_V1','phase':'NEW','sites':{}}
    val=file_read_json(p)
    must(val.get('schema')=='P07_OWNER_STAGE_V1' and type(val.get('sites')) is dict,
         'BUNDLE_MANIFEST_INVALID')
    return val

def www3_native_export(pull,state,domain,db,remote):
    """Use the already-proven pinned www3 hex-blob source exporter.

    Never retry the legacy incompatible source parser. The verified source
    worker authenticates CloudPanel locally and exports a separate file using
    a single consistent read transaction; no source business SQL mutations.
    """
    import ast
    must(domain=='www3.m3u8.one' and
         state.get('migration_id')==JOBS[2][1] and
         re.fullmatch(
             r'/var/lib/vf-server-ops/pull-source/pull-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}/data/www3-hex-[a-f0-9]{32}\.sql\.gz',
             remote), 'WWW3_HEX_SCOPE_UNVERIFIED')
    helper=Path(__file__).resolve().parent/'p07-www3-candidate-schema-probe.py'
    must(helper.is_file() and not helper.is_symlink(),
         'PINNED_WWW3_HEX_HELPER_MISSING')
    data=helper.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    must(blob=='8f640e7505c5b49ad5a7574d82c0030eb6e7b884',
         'PINNED_WWW3_HEX_HELPER_CHANGED')
    tree=ast.parse(data.decode('utf-8'))
    options=[
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node,ast.Assign)
        and len(node.targets)==1 and
        isinstance(node.targets[0],ast.Name) and
        node.targets[0].id=='REMOTE_HEX'
    ]
    must(len(options)==1 and type(options[0]) is str
         and 'HEX_SOURCE_EXPORT=CREATED_UNVERIFIED' in options[0]
         and '--hex-blob' in options[0], 'WWW3_HEX_EXPORT_SOURCE_INVALID')
    runtime=state.get('source_runtime_path')
    must(type(runtime) is str and runtime==(
         '/var/lib/vf-server-ops/pull-source/'+state['migration_id']+'/runtime'),
         'WWW3_SOURCE_RUNTIME_UNVERIFIED')
    command=shlex.join([
        'env','PYTHONDONTWRITEBYTECODE=1',
        'PYTHONPATH='+runtime+'/lib',
        'python3','-B','-c',options[0],
        domain,db,remote,state['migration_id']])
    try:
        result=pull.source_remote(
            state['source'],command,timeout=3600,check=False)
    except Exception:
        raise Block('WWW3_HEX_SOURCE_CONNECTION_FAILED') from None
    lines=(result.stdout or '').splitlines()
    safe={
        'HEX_SOURCE_EXPORT=CLIENT_UNAVAILABLE',
        'HEX_SOURCE_EXPORT=FLAGS_UNVERIFIED',
        'HEX_SOURCE_EXPORT=MASTER_DUMP_UNPROVEN',
        'HEX_EXPORT_AUTH=MASTER_COMMAND_UNAVAILABLE',
        'HEX_EXPORT_AUTH=MASTER_COMMAND_FORMAT_UNPROVEN',
        'HEX_EXPORT_AUTH=SQL_CLIENT_MISSING',
        'HEX_EXPORT_AUTH=READ_ONLY_CONNECTION_FAILED',
        'HEX_EXPORT_AUTH=READ_ONLY_CONNECTION_PASS',
    }
    for line in lines:
        if line in safe: print(line,flush=True)
    must(result.returncode==0 and
         lines and lines[-1]=='HEX_SOURCE_EXPORT=CREATED_UNVERIFIED' and
         'HEX_EXPORT_AUTH=READ_ONLY_CONNECTION_PASS' in lines,
         'WWW3_HEX_SOURCE_EXPORT_FAILED')
    print('WWW3_SOURCE_HEX_EXPORT=PASS',flush=True)


def staging(pull,sql,seen):
    must(os.geteuid()==0,'ROOT_REQUIRED')
    private_dir(BUNDLE_ROOT)
    m=read_manifest()
    must(m['phase'] in ('NEW','STAGING','STAGED'),'BUNDLE_PHASE_INVALID')
    m['phase']='STAGING';safe_write(manifest_path(),m)
    for domain in PENDING:
        s,site=seen[domain];db=site['mysql_databases'][0]
        token=hashlib.sha256(domain.encode()).hexdigest()[:16]
        local=BUNDLE_ROOT/(token+'.sql.gz')
        row=m['sites'].get(domain)
        if row:
            must(row['database']==db and local.is_file()
                 and digest(local)==row['sha256'],'PREVIOUS_STAGE_DRIFT')
            must(row.get('validation_status','PASS')=='PASS',
                 'PREVIOUS_STAGE_SQL_NOT_VERIFIED')
            print('DATABASE_STAGE_REUSED='+domain,flush=True)
            continue
        must(not local.exists() and not local.is_symlink(),'ARCHIVE_ALREADY_EXISTS')
        print('EXPORT_SOURCE_DATABASE='+domain,flush=True)
        if domain=='www3.m3u8.one':
            remote=pull.remote_staging_root(s)+'/www3-hex-'+secrets.token_hex(16)+'.sql.gz'
            print('WWW3_EXPORT_METHOD=PINNED_HEX_BLOB',flush=True)
            www3_native_export(pull,s,domain,db,remote)
        else:
            remote=pull.remote_staging_root(s)+'/owner-final-'+secrets.token_hex(12)+'.sql.gz'
            pull.source_export_database(s,db,remote)
        print('TRANSFER_PRIVATE_ARCHIVE='+domain,flush=True)
        pull.pull_path(s['source'],remote,local,delete=False)
        os.chmod(local,0o600)
        must(local.is_file() and local.stat().st_size>100 and not local.is_symlink(),
             'TRANSFER_ARCHIVE_INVALID')
        # If the native dump is not understood, retain its bytes and SHA
        # privately, but never label it verified or advance to an import.
        try:
            tables=sql.require_nonempty_source_schema(local)
        except Exception:
            m['sites'][domain]={
                'database':db,'sha256':digest(local),
                'size_bytes':local.stat().st_size,
                'create_table_statements':0,'validation_status':'UNVERIFIED',
                'remote_temp_retained':True,'import_status':'NOT_IMPORTED'}
            safe_write(manifest_path(),m)
            raise Block('SOURCE_SQL_SCHEMA_UNVERIFIED_'+
                        domain.replace('.','_').upper()) from None
        must(tables>0,'SOURCE_SQL_SCHEMA_MISSING')
        m['sites'][domain]={'database':db,'sha256':digest(local),
                            'size_bytes':local.stat().st_size,
                            'create_table_statements':tables,
                            'validation_status':'PASS',
                            'remote_temp_retained':True,'import_status':'NOT_IMPORTED'}
        safe_write(manifest_path(),m)
        print('SOURCE_DATABASE_SAVED='+domain,flush=True)
    m['phase']='STAGED';safe_write(manifest_path(),m)
    print('THREE_DATABASE_SOURCE_ARCHIVES=STAGED')
    print('BUNDLE_LOCATION='+str(BUNDLE_ROOT))
    print('EXISTING_CP2_DATABASE_WRITES=NONE')
    print('SOURCE_WAS_LIVE=YES')
    print('CUTOVER_READY=NO')

def stage_site_files(pull,seen):
    """Copy only the 3 pending site roots into private, inactive staging.

    Nothing is copied into a CloudPanel document root. The source copy may
    change while the VPS remains live; this is not a final frozen snapshot.
    """
    private_dir(BUNDLE_ROOT)
    private_dir(BUNDLE_ROOT/'sites')
    m=read_manifest()
    must(m.get('phase') in ('STAGED','ISOLATED_RESTORING','ISOLATED_RESTORED'),
         'DATABASE_ARCHIVES_MUST_BE_STAGED_FIRST')
    # Guard against exhausting CP2 disk with a second site copy.
    needed=0
    for d in PENDING:
        state,site=seen[d]
        if m['sites'].get(d,{}).get('files_status')=='TRANSFERRED':continue
        remote_command='du -sk -- '+shlex.quote(site['site_root'])
        size=pull.source_remote(state['source'],remote_command,timeout=300,check=False)
        must(size.returncode==0 and re.match(r'^[0-9]+\s',size.stdout.strip()),
             'SOURCE_SITE_SIZE_NOT_VERIFIED')
        needed+=int(size.stdout.split()[0])*1024
    available=shutil.disk_usage(BUNDLE_ROOT).free
    must(available>=int(needed*1.25)+1024*1024*1024,
         'CP2_FREE_DISK_INSUFFICIENT_FOR_PRIVATE_STAGE')
    for d in PENDING:
        state,site=seen[d]
        row=m['sites'].get(d)
        must(type(row) is dict,'DB_ARCHIVE_MISSING_FOR_SITE')
        token=hashlib.sha256(d.encode()).hexdigest()[:16]
        dest=BUNDLE_ROOT/'sites'/token
        if row.get('files_status')=='TRANSFERRED':
            must(dest.is_dir() and not dest.is_symlink(),'STAGED_FILES_LOST')
            print('SITE_FILES_ALREADY_STAGED='+d,flush=True)
            continue
        must(not dest.exists() and not dest.is_symlink(),
             'PREVIOUS_FILE_TRANSFER_UNCERTAIN_NO_AUTO_RETRY')
        private_dir(dest)
        row['files_status']='TRANSFER_IN_PROGRESS'
        safe_write(manifest_path(),m)
        print('TRANSFER_SITE_FILES='+d,flush=True)
        pull.pull_path(state['source'],site['site_root'].rstrip('/')+'/',dest,
                       delete=False)
        # Minimal local file-existence evidence, not live source parity.
        must(any(dest.iterdir()),'SITE_TRANSFER_EMPTY')
        row['files_status']='TRANSFERRED'
        row['files_destination']='PRIVATE_INACTIVE_STAGE'
        safe_write(manifest_path(),m)
        print('SITE_FILES_STAGED='+d,flush=True)
    print('THREE_SITE_FILE_ROOTS=STAGED_INACTIVE')
    print('CP2_ACTIVE_SITE_FILES=UNCHANGED')
    print('LIVE_SOURCE_FILE_PARITY=NOT_VERIFIED')

def warm_stage_remaining_site_files(pull, seen):
    """Pre-copy the 14 already registered sites into PRIVATE, inactive CP2.

    The 3 pending site roots are reused from their existing verified stage.
    This is live-source warm staging only, NOT a frozen or active-site sync.
    Existing CloudPanel roots and all existing databases remain untouched.
    """
    must(len(seen)==17 and set(PENDING).issubset(seen),
         'WARM_SITE_SCOPE_CHANGED')
    private_dir(BUNDLE_ROOT)
    private_dir(BUNDLE_ROOT/'sites')
    m=read_manifest()
    must(m.get('phase') in ('STAGED','ISOLATED_RESTORING','ISOLATED_RESTORED'),
         'WARM_DATABASE_ARCHIVES_MISSING')
    for d in PENDING:
        row=m.get('sites',{}).get(d)
        dest=BUNDLE_ROOT/'sites'/hashlib.sha256(d.encode()).hexdigest()[:16]
        must(type(row) is dict and row.get('files_status')=='TRANSFERRED'
             and dest.is_dir() and not dest.is_symlink()
             and any(dest.iterdir()),
             'WARM_THREE_ORIGINAL_SITE_ROOTS_UNVERIFIED')
    others=sorted(set(seen)-set(PENDING))
    must(len(others)==14,'WARM_FOURTEEN_SITE_SCOPE_CHANGED')
    warm=m.setdefault('warm_sites',{})
    must(type(warm) is dict and set(warm).issubset(others),
         'WARM_SITE_MANIFEST_SCOPE_CHANGED')
    source_need=0
    for d in others:
        s,site=seen[d]
        path=site['site_root']
        identity=hashlib.sha256(
            (s['migration_id']+'\x00'+d+'\x00'+path).encode()
        ).hexdigest()
        dest=BUNDLE_ROOT/'sites'/hashlib.sha256(d.encode()).hexdigest()[:16]
        row=warm.get(d)
        if row is not None:
            must(type(row) is dict and row.get('identity_sha256')==identity,
                 'WARM_ORIGINAL_OWNER_IDENTITY_CHANGED')
            must(row.get('status')=='TRANSFERRED',
                 'WARM_PARTIAL_COPY_NO_AUTO_RETRY')
            must(dest.is_dir() and not dest.is_symlink() and any(dest.iterdir()),
                 'WARM_PREVIOUS_COPY_MISSING')
            continue
        must(not dest.exists() and not dest.is_symlink(),
             'WARM_DESTINATION_EXISTS_NO_OVERWRITE')
        response=pull.source_remote(
            s['source'],'du -sk -- '+shlex.quote(path),timeout=600,check=False)
        must(response.returncode==0 and
             re.fullmatch(r'[0-9]+\s+.+',response.stdout.strip()),
             'WARM_SOURCE_SIZE_UNVERIFIED')
        source_need+=int(response.stdout.split()[0])*1024
    free=shutil.disk_usage(BUNDLE_ROOT).free
    must(free>=int(source_need*1.25)+1024*1024*1024,
         'WARM_CP2_DISK_HEADROOM_INSUFFICIENT')
    for d in others:
        s,site=seen[d]
        if d in warm:
            print('WARM_SITE_REUSED='+d,flush=True)
            continue
        path=site['site_root']
        identity=hashlib.sha256(
            (s['migration_id']+'\x00'+d+'\x00'+path).encode()
        ).hexdigest()
        dest=BUNDLE_ROOT/'sites'/hashlib.sha256(d.encode()).hexdigest()[:16]
        must(not dest.exists() and not dest.is_symlink(),
             'WARM_STAGE_CONCURRENT_DESTINATION')
        warm[d]={
            'identity_sha256':identity,
            'status':'TRANSFER_IN_PROGRESS',
            'destination':'PRIVATE_INACTIVE',
            'frozen_snapshot':False,
        }
        safe_write(manifest_path(),m)
        private_dir(dest)
        print('WARM_TRANSFER_SITE='+d,flush=True)
        pull.pull_path(s['source'],path.rstrip('/')+'/',dest,delete=False)
        must(dest.is_dir() and not dest.is_symlink() and any(dest.iterdir()),
             'WARM_SITE_COPY_EMPTY')
        warm[d]['status']='TRANSFERRED'
        safe_write(manifest_path(),m)
        print('WARM_SITE_STAGED='+d,flush=True)
    print('WARM_FOURTEEN_SITE_FILE_ROOTS=14/14_INACTIVE',flush=True)
    print('TOTAL_INACTIVE_SITE_FILE_ROOTS=17/17',flush=True)
    print('LIVE_SOURCE_FILE_PARITY=NOT_VERIFIED',flush=True)
    print('EXISTING_CP2_SITE_FILES=UNCHANGED',flush=True)
    print('EXISTING_CP2_DATABASES=UNCHANGED',flush=True)
    print('SOURCE_BUSINESS_WRITES=NONE',flush=True)
    print('DNS_CHANGED=NO',flush=True)
    print('CUTOVER_READY=NO',flush=True)


def verify_warm_site_files(seen):
    """Local-only readback of all inactive roots; no source network or writes."""
    must(len(seen)==17 and set(PENDING).issubset(seen),
         'WARM_SITE_SCOPE_CHANGED')
    m=read_manifest()
    warm=m.get('warm_sites',{})
    must(type(warm) is dict and len(warm)==14,
         'WARM_FOURTEEN_COPY_RECEIPTS_MISSING')
    count=0
    for d in sorted(seen):
        s,site=seen[d]
        dest=BUNDLE_ROOT/'sites'/hashlib.sha256(d.encode()).hexdigest()[:16]
        must(dest.is_dir() and not dest.is_symlink() and any(dest.iterdir()),
             'WARM_SITE_PRIVATE_COPY_MISSING')
        if d in PENDING:
            must(m['sites'][d].get('files_status')=='TRANSFERRED',
                 'WARM_THREE_PENDING_FILE_RECEIPTS_MISSING')
        else:
            owner=hashlib.sha256(
                (s['migration_id']+'\x00'+d+'\x00'+site['site_root']).encode()
            ).hexdigest()
            row=warm.get(d)
            must(type(row) is dict
                 and row.get('identity_sha256')==owner
                 and row.get('status')=='TRANSFERRED'
                 and row.get('frozen_snapshot') is False,
                 'WARM_SITE_ORIGINAL_OWNER_RECEIPT_INVALID')
        count+=1
    print('WARM_INACTIVE_SITE_ROOTS_VERIFIED='+str(count)+'/17',flush=True)
    print('FINAL_FROZEN_FILE_PARITY=NOT_VERIFIED',flush=True)
    print('ACTIVE_CP2_SITE_FILES=UNCHANGED',flush=True)
    print('OLD_VPS_BUSINESS_WRITES=NONE',flush=True)
    print('CUTOVER_READY=NO',flush=True)


def sql_safety(sql,p):
    """Prove bounded legacy session/read guards before any database writes."""
    import importlib.util
    import verify
    sql.require_nonempty_source_schema(p)
    guards=sql.dynamic_guard_syntax_counts(p)
    unsafe=sum(int(guards.get(x,0)) for x in (
        'recognized_unsafe','double_quoted_if','other_unknown_set'))
    helper=Path(__file__).resolve().parent/'p07-www3-isolated-stage.py'
    must(helper.is_file() and not helper.is_symlink(),
         'PINNED_SQL_GUARD_HELPER_MISSING')
    raw=helper.read_bytes()
    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    must(blob=='8939ff6bd08442a26459a6878d1f94a5c34d000b',
         'PINNED_SQL_GUARD_HELPER_CHANGED')
    spec=importlib.util.spec_from_file_location(
        'p07_owner_safe_sql_proof',helper)
    must(spec is not None and spec.loader is not None,
         'PINNED_SQL_GUARD_HELPER_UNLOADABLE')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        if unsafe:
            must(guards.get('recognized_unsafe')==3
                 and guards.get('double_quoted_if')==0
                 and guards.get('other_unknown_set')==0
                 and guards.get('recognized_safe')==0,
                 'DYNAMIC_SQL_UNKNOWN_SHAPE_STOP_IMPORT')
            proven=module.prove_legacy_mysql_dynamic_groups(p,verify,sql)
            must(len(proven)==13,
                 'DYNAMIC_SQL_SEQUENCE_UNVERIFIED_STOP_IMPORT')
            must(not module.standalone_sql_unproven_side_effects(
                 p,verify,known_safe_lines=proven),
                 'DYNAMIC_SQL_NONLOCAL_EFFECTS_STOP_IMPORT')
            print('DYNAMIC_SQL=EXACT_3_GROUP_SESSION_READ_ONLY_PROOF_PASS',
                  flush=True)
        else:
            must(guards.get('recognized_safe')==0,
                 'DYNAMIC_SQL_OTHER_GROUPS_UNVERIFIED_STOP_IMPORT')
            must(not module.standalone_sql_unproven_side_effects(
                 p,verify,known_safe_lines=set()),
                 'SQL_NONLOCAL_EFFECTS_STOP_IMPORT')
            print('DYNAMIC_SQL=NO_UNPROVEN_CONTROL_GROUPS',flush=True)
    except module.Stop as exc:
        reason=str(exc)
        allowed={
            'DYNAMIC_SOURCE_ASSIGNMENT_IDENTITY_CHANGED',
            'DYNAMIC_SOURCE_GROUP_COUNT_CHANGED',
            'DYNAMIC_BRANCH_STILL_UNSAFE',
            'DYNAMIC_GROUP_SEQUENCE_UNPROVEN',
        }
        raise Block(reason if reason in allowed else
                    'DYNAMIC_SQL_EXACT_PROOF_FAILED_STOP_IMPORT') from None
    except (sql.AdvisoryDiagnosticUnavailable,
            verify.RestoreVerifyError,ValueError):
        raise Block('DYNAMIC_SQL_INPUT_OR_GRAMMAR_UNVERIFIED') from None
    with gzip.open(p,'rb') as f:
        for line in f:
            must(len(line)<16*1024*1024,'SQL_LINE_TOO_LARGE')
            # Conservative: do not import a source dump containing commands
            # that may act outside the fresh database, even in comments.
            line_text=line.decode('latin1').lstrip()
            # DML value literals can legitimately contain these words. Analyze
            # SQL control/DDL line prefixes, not arbitrary INSERT payload text.
            if line_text.upper().startswith(('INSERT ','REPLACE ','UPDATE ')):
                continue
            must(not SQL_DANGER.search(line_text),
                 'CROSS_DATABASE_OR_PRIVILEGED_SQL_BLOCKED')

def import_as_restricted_user(database,user,password,archive):
    """Do NOT run a foreign SQL archive using CloudPanel master credentials.

    The newly created database's own restricted user should have grants on
    that database only. The source SQL can therefore never modify the 14
    existing CP2 databases even if it contains escaped/qualified statements.
    """
    must(re.fullmatch(r'[A-Za-z0-9]{1,64}',database) and
         re.fullmatch(r'[A-Za-z0-9]{1,64}',user),
         'ISOLATED_DATABASE_IDENTITY_INVALID')
    must(re.fullmatch(r'[A-Za-z0-9_-]{20,128}',password),
         'ISOLATED_DATABASE_PASSWORD_INVALID')
    with tempfile.TemporaryDirectory(prefix='.p07-import-',dir=BUNDLE_ROOT) as t:
        conf=Path(t)/'client.cnf';plain=Path(t)/'source.sql'
        os.chmod(t,0o700)
        fd=os.open(conf,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            f.write('[client]\nhost=127.0.0.1\nprotocol=tcp\n'
                    'user="'+user+'"\npassword="'+password+'"\n')
        base=['mariadb','--defaults-extra-file='+str(conf),
              '--batch','--skip-column-names']
        try:
            grants=subprocess.run(base+['--execute','SHOW GRANTS'],
                  stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL,timeout=20,check=False)
        except (OSError,subprocess.SubprocessError):
            raise Block('RESTRICTED_DB_USER_UNAVAILABLE') from None
        must(grants.returncode==0 and len(grants.stdout)<16*1024,
             'NEW_DB_GRANTS_UNVERIFIED')
        # USAGE ON *.* is not a write privilege. All other grants must be
        # database-local for exactly the NEW empty, isolated schema.
        for raw in grants.stdout.decode('utf8','replace').splitlines():
            x=raw.upper()
            if ' ON *.* ' in x:
                must(x.startswith('GRANT USAGE ON *.* '),
                     'NEW_DB_USER_HAS_GLOBAL_GRANTS')
            else:
                must((' ON `'+database.upper()+'`.* ') in x or
                     (' ON '+database.upper()+'.* ') in x,
                     'NEW_DB_USER_HAS_FOREIGN_GRANTS')
        # Decompress into a private bounded file to prevent feeding compressed
        # bytes to mariadb or accumulating SQL in RAM.
        total=0
        with gzip.open(archive,'rb') as src, plain.open('xb') as out:
            os.chmod(plain,0o600)
            for part in iter(lambda:src.read(1024*1024),b''):
                total+=len(part)
                must(total<=2*1024**3,'IMPORT_SQL_SIZE_CAP_EXCEEDED')
                out.write(part)
        must(total>1024,'DECOMPRESSED_SQL_EMPTY')
        try:
            with plain.open('rb') as source:
                result=subprocess.run(base+['--database='+database],
                       stdin=source,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=3600,check=False)
        except (OSError,subprocess.SubprocessError):
            raise Block('RESTRICTED_DB_IMPORT_UNAVAILABLE') from None
        must(result.returncode==0,'RESTRICTED_DB_IMPORT_FAILED')

def restore_isolated(cloud,sql,lifecycle,seen,selected):
    must(BUNDLE_ROOT.is_dir() and not BUNDLE_ROOT.is_symlink(),'BUNDLE_NOT_FOUND')
    m=read_manifest()
    must(m['phase'] in ('STAGED','ISOLATED_RESTORING','ISOLATED_RESTORED'),
         'STAGE_NOT_COMPLETE')
    # pre-check all three archives BEFORE any target database creation.
    for d in selected:
        row=m['sites'].get(d)
        must(row is not None and row['database']==seen[d][1]['mysql_databases'][0],
             'STAGE_SITE_BINDING_CHANGED')
        path=BUNDLE_ROOT/(hashlib.sha256(d.encode()).hexdigest()[:16]+'.sql.gz')
        must(path.is_file() and not path.is_symlink() and digest(path)==row['sha256'],
             'SOURCE_ARCHIVE_CHANGED')
        sql_safety(sql,path)
    m['phase']='ISOLATED_RESTORING';safe_write(manifest_path(),m)
    for d in selected:
        row=m['sites'][d]
        if row.get('import_status')=='IMPORT_SUCCEEDED':
            print('ISOLATED_DB_RETAINED='+d)
            continue
        must(row.get('import_status')=='NOT_IMPORTED',
             'UNCERTAIN_IMPORT_REQUIRES_REVIEW_NO_AUTO_RETRY')
        site=seen[d][1]
        db,user,pw=lifecycle.derive_database_identity(d,'p07-owner-'+secrets.token_hex(8),1)
        # Journal intent before mutating CloudPanel. Existing DBs are untouched.
        row.update({'import_status':'INTENT_RECORDED','isolated_database':db,
                    'isolated_user':user, 'isolated_password':pw})
        safe_write(manifest_path(),m)
        try:
            cloud.add_database(d,db,user,pw)
            row['import_status']='NEW_DB_CREATED'
            safe_write(manifest_path(),m)
            path=BUNDLE_ROOT/(hashlib.sha256(d.encode()).hexdigest()[:16]+'.sql.gz')
            import_as_restricted_user(db,user,pw,path)
            row['import_status']='IMPORT_SUCCEEDED'
            safe_write(manifest_path(),m)
            print('NEW_DB_IMPORT_SUCCEEDED='+d)
        except Exception:
            print('BLOCKED=ISOLATED_IMPORT_FAILED_RETAIN_NEW_DB_NO_RETRY',flush=True)
            raise
    m['phase']='ISOLATED_RESTORED' if all(
        m['sites'][d].get('import_status')=='IMPORT_SUCCEEDED' for d in PENDING
    ) else 'STAGED'
    safe_write(manifest_path(),m)
    print('ISOLATED_DATABASE_IMPORTS='+str(sum(
        m['sites'][d].get('import_status')=='IMPORT_SUCCEEDED' for d in PENDING
    ))+'/3_NOT_PARITY_VERIFIED')
    print('EXISTING_CP2_DATABASES=UNCHANGED_BY_SCRIPT')
    print('APPLICATION_CONFIGS=UNCHANGED')
    print('CUTOVER_READY=NO')

def continue_safe_imports(cloud,sql,lifecycle,seen):
    """Independently process the two approved isolated restores; no retry of uncertain imports."""
    verify_stage(sql)
    selected=('ilovem3u8.kewaro.com','unzip.kewaro.com')
    failures=0
    for domain in selected:
        row=read_manifest()['sites'].get(domain)
        if not isinstance(row,dict):
            print('SITE_STATUS='+domain+':MISSING_ARCHIVE',flush=True)
            failures+=1
            continue
        status=row.get('import_status')
        if status=='IMPORT_SUCCEEDED':
            print('SITE_STATUS='+domain+':ALREADY_RECORDED_NOT_REVERIFIED',flush=True)
            continue
        if status!='NOT_IMPORTED':
            print('SITE_STATUS='+domain+':UNCERTAIN_PRIOR_IMPORT_NO_RETRY',flush=True)
            failures+=1
            continue
        archive=BUNDLE_ROOT/(hashlib.sha256(domain.encode()).hexdigest()[:16]+'.sql.gz')
        try:
            must(archive.is_file() and not archive.is_symlink()
                 and digest(archive)==row['sha256'],'ARCHIVE_CHANGED')
            sql_safety(sql,archive)
        except Block as exc:
            print('SITE_STATUS='+domain+':SQL_PREFLIGHT_BLOCKED',flush=True)
            print('SITE_BLOCK_REASON='+str(exc),flush=True)
            failures+=1
            continue
        except Exception:
            print('SITE_STATUS='+domain+':SQL_PREFLIGHT_UNVERIFIED',flush=True)
            failures+=1
            continue
        print('SQL_PREFLIGHT_PASS='+domain,flush=True)
        try:
            restore_isolated(cloud,sql,lifecycle,seen,(domain,))
        except Block as exc:
            print('SITE_STATUS='+domain+':RESTORE_BLOCKED',flush=True)
            print('SITE_BLOCK_REASON='+str(exc),flush=True)
            failures+=1
        except Exception:
            print('SITE_STATUS='+domain+':RESTORE_FAILED_KEEP_JOURNAL_NO_RETRY',flush=True)
            failures+=1
        else:
            print('SITE_STATUS='+domain+':ISOLATED_IMPORT_RECORDED',flush=True)
    m=read_manifest()
    total=sum(m['sites'][d].get('import_status')=='IMPORT_SUCCEEDED'
              for d in selected)
    print('TWO_SITE_ISOLATED_IMPORT_COUNT='+str(total)+'/2',flush=True)
    print('BLOCKED_SITE_COUNT='+str(failures),flush=True)
    print('SOURCE_BUSINESS_WRITES=NONE',flush=True)
    print('EXISTING_CP2_DATABASE_OVERWRITES=NONE',flush=True)
    print('DNS_CHANGED=NO',flush=True)
    print('CUTOVER_READY=NO',flush=True)
    if failures:
        raise Block('CONTINUE_SAFE_PARTIAL_REVIEW_REQUIRED')

def restore_two_quarantined_static(cloud,sql,lifecycle,seen):
    """Strictly isolated COPY only, never final SQL equivalence or cutover.

    The pinned transformation removes exactly the known 13 dynamic-control
    lines and preserves every other source byte. Never import into an existing
    database or alter application config. All originals remain immutable.
    """
    import importlib.util
    target=('ilovem3u8.kewaro.com','unzip.kewaro.com')
    expected={'ilovem3u8.kewaro.com':42,'unzip.kewaro.com':12}
    helper=Path(__file__).resolve().parent/'p07-www3-isolated-stage.py'
    must(helper.is_file() and not helper.is_symlink(),
         'QUARANTINE_GUARD_HELPER_MISSING')
    data=helper.read_bytes()
    h=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    must(h=='8939ff6bd08442a26459a6878d1f94a5c34d000b',
         'QUARANTINE_GUARD_HELPER_CHANGED')
    spec=importlib.util.spec_from_file_location('p07_two_static_quarantine',helper)
    must(spec is not None and spec.loader is not None,
         'QUARANTINE_GUARD_UNAVAILABLE')
    guard=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    verify_stage(sql)
    failures=0
    for domain in target:
        m=read_manifest()
        row=m['sites'][domain]
        prior=row.get('quarantine_status')
        if prior=='IMPORTED_STATIC_UNVERIFIED':
            print('QUARANTINE_ALREADY_IMPORTED='+domain,flush=True)
            continue
        if prior is not None:
            print('QUARANTINE_PRIOR_INTENT_REVIEW_REQUIRED='+domain,flush=True)
            failures+=1
            continue
        if row.get('import_status')!='NOT_IMPORTED':
            print('QUARANTINE_EXISTING_IMPORT_STATE_UNSAFE='+domain,flush=True)
            failures+=1
            continue
        token=hashlib.sha256(domain.encode()).hexdigest()[:16]
        original=BUNDLE_ROOT/(token+'.sql.gz')
        transformed=BUNDLE_ROOT/(token+'.quarantine.sql.gz')
        try:
            must(original.is_file() and not original.is_symlink()
                 and digest(original)==row['sha256'],
                 'QUARANTINE_ORIGINAL_ARCHIVE_CHANGED')
            must(sql.require_nonempty_source_schema(original)==expected[domain],
                 'QUARANTINE_SOURCE_SCHEMA_DRIFT')
            must(not transformed.exists() and not transformed.is_symlink(),
                 'QUARANTINE_OUTPUT_ALREADY_EXISTS')
            # Record irreversible intent before writing ANY candidate bytes.
            row['quarantine_status']='COPY_INTENT_RECORDED'
            safe_write(manifest_path(),m)
            print('QUARANTINE_STATIC_COPY_START='+domain,flush=True)
            transformed_sha=guard.make_quarantined_sql(original,transformed)
            os.chmod(transformed,0o600)
            must(digest(transformed)==transformed_sha,
                 'QUARANTINE_TRANSFORM_DIGEST_CHANGED')
            must(sql.require_nonempty_source_schema(transformed)==expected[domain],
                 'QUARANTINE_SCHEMA_LOST')
            sql_safety(sql,transformed)
            row['quarantine_status']='STATIC_COPY_VALIDATED'
            row['quarantine_sha256']=transformed_sha
            row['quarantine_original_sha256']=row['sha256']
            safe_write(manifest_path(),m)
            print('QUARANTINE_STATIC_COPY_VALIDATED='+domain,flush=True)
            isolated_db,user,password=lifecycle.derive_database_identity(
                domain,'p07-quarantine-'+secrets.token_hex(8),1)
            must(isolated_db!=row['database'],
                 'QUARANTINE_NAME_COLLIDES_WITH_SOURCE')
            row.update({
                'quarantine_status':'NEW_DB_INTENT_RECORDED',
                'quarantine_database':isolated_db,
                'quarantine_user':user,
                'quarantine_password':password,
            })
            safe_write(manifest_path(),m)
            cloud.add_database(domain,isolated_db,user,password)
            row['quarantine_status']='NEW_DB_CREATED'
            safe_write(manifest_path(),m)
            import_as_restricted_user(isolated_db,user,password,transformed)
            row['quarantine_status']='IMPORTED_STATIC_UNVERIFIED'
            safe_write(manifest_path(),m)
            print('QUARANTINE_STATIC_DB_IMPORTED='+domain,flush=True)
        except (Block,guard.Stop) as exc:
            code=str(exc)
            allowed={
                'QUARANTINE_SOURCE_SHAPE_CHANGED',
                'QUARANTINE_ELSE_BRANCH_UNPROVEN',
                'QUARANTINE_SOURCE_SQL_UNREADABLE',
                'QUARANTINE_CONTROL_COUNT_CHANGED',
                'QUARANTINE_CONTROL_TYPE_COUNTS_UNPROVEN',
                'QUARANTINE_CONTROL_UNIQUE_LINES_UNPROVEN',
                'QUARANTINE_OUTPUT_PATH_UNSAFE',
                'QUARANTINE_SCHEMA_LOST',
                'QUARANTINE_STATIC_SQL_UNPROVEN',
                'DYNAMIC_SQL_OTHER_GROUPS_UNVERIFIED_STOP_IMPORT',
                'SQL_NONLOCAL_EFFECTS_STOP_IMPORT',
                'CROSS_DATABASE_OR_PRIVILEGED_SQL_BLOCKED',
                'SQL_LINE_TOO_LARGE',
                'NEW_DB_GRANTS_UNVERIFIED',
                'NEW_DB_USER_HAS_GLOBAL_GRANTS',
                'NEW_DB_USER_HAS_FOREIGN_GRANTS',
                'RESTRICTED_DB_USER_UNAVAILABLE',
                'RESTRICTED_DB_IMPORT_FAILED',
            }
            print('QUARANTINE_SITE_BLOCKED='+domain,flush=True)
            print('QUARANTINE_REASON='+(
                code if code in allowed else 'SAFE_GATE_UNVERIFIED'),flush=True)
            failures+=1
        except Exception:
            print('QUARANTINE_SITE_BLOCKED='+domain,flush=True)
            print('QUARANTINE_REASON=UNVERIFIED_RETAIN_PRIVATE_JOURNAL',flush=True)
            failures+=1
    m=read_manifest()
    succeeded=sum(
        m['sites'][d].get('quarantine_status')=='IMPORTED_STATIC_UNVERIFIED'
        for d in target)
    print('QUARANTINED_STATIC_IMPORT_COUNT='+str(succeeded)+'/2',flush=True)
    print('BLOCKED_SITE_COUNT='+str(failures),flush=True)
    print('ORIGINAL_SOURCE_ARCHIVES=RETAINED_UNCHANGED',flush=True)
    print('SOURCE_BUSINESS_WRITES=NONE',flush=True)
    print('EXISTING_CP2_DATABASE_WRITES=NONE',flush=True)
    print('APP_DATABASE_CONNECTIONS=UNCHANGED',flush=True)
    print('ORIGINAL_SQL_EFFECT_EQUIVALENCE=NOT_PROVEN',flush=True)
    print('SOURCE_TARGET_PARITY=NOT_PROVEN',flush=True)
    print('DNS_CHANGED=NO',flush=True)
    print('CUTOVER_READY=NO',flush=True)
    if failures:
        raise Block('QUARANTINE_PARTIAL_REVIEW_REQUIRED')


def verify_isolated_imports(pull,cloud,sql,seen):
    """Read-only DB export + logical comparison of the two static copies.

    The two databases contain the quarantine input with 13 guarded SQL
    control lines omitted. Even a full copy/export match is never equivalent
    to original-source SQL semantics, a final frozen source snapshot, or
    17-site cutover approval.
    """
    must(BUNDLE_ROOT.is_dir() and not BUNDLE_ROOT.is_symlink(),
         'PRIVATE_STAGE_MISSING')
    m=read_manifest()
    expected={'ilovem3u8.kewaro.com':42,'unzip.kewaro.com':12}
    forbidden_dbs={
        db for _state,site in seen.values()
        for db in site['mysql_databases']
    }
    passed=0
    for domain,table_count in expected.items():
        row=m['sites'].get(domain)
        if not isinstance(row,dict):
            print('ISOLATED_VERIFY_BLOCKED='+domain+':MANIFEST_MISSING',flush=True)
            continue
        if row.get('quarantine_status')!='IMPORTED_STATIC_UNVERIFIED':
            print('ISOLATED_VERIFY_BLOCKED='+domain+':IMPORT_NOT_RECORDED',flush=True)
            continue
        iso=row.get('quarantine_database')
        if (type(iso) is not str or not re.fullmatch(r'[A-Za-z0-9]{1,64}',iso)
                or iso in forbidden_dbs):
            print('ISOLATED_VERIFY_BLOCKED='+domain+':DB_IDENTITY_UNSAFE',flush=True)
            continue
        token=hashlib.sha256(domain.encode()).hexdigest()[:16]
        original=BUNDLE_ROOT/(token+'.sql.gz')
        transformed=BUNDLE_ROOT/(token+'.quarantine.sql.gz')
        if (not original.is_file() or original.is_symlink()
                or not transformed.is_file() or transformed.is_symlink()
                or digest(original)!=row.get('sha256')
                or digest(original)!=row.get('quarantine_original_sha256')
                or digest(transformed)!=row.get('quarantine_sha256')):
            print('ISOLATED_VERIFY_BLOCKED='+domain+':ARCHIVE_CHANGED',flush=True)
            continue
        try:
            before=sql.require_nonempty_source_schema(transformed)
            must(before==table_count,
                 'SOURCE_STATIC_TABLE_COUNT_CHANGED')
            with tempfile.TemporaryDirectory(prefix='p07-verify-',dir=BUNDLE_ROOT) as folder:
                output=Path(folder)/'target.sql.gz'
                cloud.export_database(iso,output,clpctl='clpctl')
                must(output.is_file() and not output.is_symlink(),
                     'ISOLATED_DB_EXPORT_UNAVAILABLE')
                after=sql.require_nonempty_source_schema(output)
                print('ISOLATED_SITE='+domain,flush=True)
                print('STATIC_SOURCE_TABLES='+str(before),flush=True)
                print('RESTORED_TARGET_TABLES='+str(after),flush=True)
                must(before==after,
                     'ISOLATED_TABLE_COUNT_MISMATCH')
                mode=pull.compare_database_dumps(transformed,output)
                allowed={
                    'CANONICAL_SQL_EXACT',
                    'CROSS_ENGINE_GUARDED_SESSION_SQL_EXACT',
                    'CROSS_ENGINE_KNOWN_DUMP_FORMAT_SQL_EXACT',
                    'CROSS_ENGINE_LOGICAL_CONTENT',
                }
                must(mode in allowed,'SQL_PARITY_MODE_UNRECOGNIZED')
                print('STATIC_COPY_EXPORT_PARITY='+mode,flush=True)
                passed+=1
        except Exception:
            # Private DB dumps/SQL/errors can contain secrets or user data.
            # Never print raw exception strings or the name of the new DB.
            print('ISOLATED_VERIFY_BLOCKED='+domain+':PARITY_NOT_PROVEN',
                  flush=True)
    print('ISOLATED_STATIC_PARITY_VERIFIED='+str(passed)+'/2',flush=True)
    print('ORIGINAL_SOURCE_SQL_EFFECTS=NOT_PROVEN',flush=True)
    print('FROZEN_SOURCE_DATABASE_PARITY=NOT_VERIFIED',flush=True)
    print('EXISTING_CP2_DB_WRITES=NONE',flush=True)
    print('SOURCE_BUSINESS_WRITES=NONE',flush=True)
    print('APP_CONFIG_WRITES=NONE',flush=True)
    print('DNS_CHANGED=NO',flush=True)
    print('CUTOVER_READY=NO',flush=True)
    if passed!=2:raise Block('ISOLATED_STATIC_PARITY_NOT_PROVEN')


def verify_stage(sql):
    m=read_manifest()
    must(m.get('phase') in ('STAGED','ISOLATED_RESTORING','ISOLATED_RESTORED'),
         'NO_COMPLETED_STAGE')
    for d in PENDING:
        row=m['sites'].get(d)
        must(type(row) is dict,'SITE_STAGE_MISSING')
        path=BUNDLE_ROOT/(hashlib.sha256(d.encode()).hexdigest()[:16]+'.sql.gz')
        must(path.is_file() and digest(path)==row['sha256'], 'ARCHIVE_SHA256_MISMATCH')
        must(sql.require_nonempty_source_schema(path)>0,'SOURCE_SCHEMA_EMPTY')
        print('ARCHIVE_VERIFIED='+d)
        print('ISOLATED_IMPORT_STATUS='+str(row.get('import_status','NOT_IMPORTED')))
        print('SITE_FILES_STATUS='+str(row.get('files_status','NOT_STAGED')))
    print('CHECKED_SOURCE_ARCHIVES=3')
    print('LIVE_SOURCE_TARGET_PARITY=NOT_VERIFIED')
    print('CUTOVER_READY=NO')

def main():
    p=argparse.ArgumentParser(description='P07 17-site owner migration continuation on CP2')
    p.add_argument('mode',choices=['plan','stage','verify-stage','warm-stage-14','verify-warm','restore-new-db','continue-safe','restore-quarantine','verify-imports'],
                   help='plan: read-only; stage: export pending DBs; restore-new-db: fresh DBs only')
    p.add_argument('--site',choices=PENDING,
                   help='Limit isolated DB import to one of the 3 pending sites')
    p.add_argument('--confirm-new-databases',action='store_true',
                   help='Explicit permission to create three NEW CloudPanel DBs only')
    a=p.parse_args()
    must(os.geteuid()==0,'RUN_AS_ROOT_ON_CP2')
    pull,cloud,sql,lifecycle=lib()
    seen=topology(pull)
    if a.mode=='plan':report(seen)
    elif a.mode=='stage':
        source_ping(pull,seen)
        staging(pull,sql,seen)
        stage_site_files(pull,seen)
    elif a.mode=='verify-stage':verify_stage(sql)
    elif a.mode=='warm-stage-14':
        must(not a.site and not a.confirm_new_databases,
             'WARM_SITE_FILES_ONLY_NO_DB_WRITES')
        source_ping(pull,seen)
        warm_stage_remaining_site_files(pull,seen)
    elif a.mode=='verify-warm':
        must(not a.site and not a.confirm_new_databases,
             'WARM_READONLY_ONLY')
        verify_warm_site_files(seen)
    elif a.mode=='verify-imports':
        must(not a.site and not a.confirm_new_databases,
             'READONLY_VERIFICATION_ONLY')
        verify_isolated_imports(pull,cloud,sql,seen)
    elif a.mode=='continue-safe':
        must(a.confirm_new_databases,'EXPLICIT_NEW_DB_PERMISSION_REQUIRED')
        must(not a.site,'CONTINUE_SAFE_SCOPE_FIXED_TWO_SITES')
        continue_safe_imports(cloud,sql,lifecycle,seen)
    elif a.mode=='restore-quarantine':
        must(a.confirm_new_databases,'EXPLICIT_NEW_DB_PERMISSION_REQUIRED')
        must(not a.site,'QUARANTINE_SCOPE_FIXED_TWO_SITES')
        restore_two_quarantined_static(cloud,sql,lifecycle,seen)
    else:
        must(a.confirm_new_databases,'EXPLICIT_NEW_DB_PERMISSION_REQUIRED')
        restore_isolated(cloud,sql,lifecycle,seen,(a.site,) if a.site else PENDING)

if __name__=='__main__':
    try:main()
    except Block as e:
        print('BLOCKED='+str(e),flush=True);raise SystemExit(13) from None
    except Exception as e:
        # Don't leak production credentials, stderr or private paths.
        print('BLOCKED=OPERATION_FAILED_REVIEW_PRIVATE_LOCAL_RECEIPT',flush=True)
        raise SystemExit(13) from None
