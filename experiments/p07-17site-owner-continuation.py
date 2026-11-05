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
    except (module.Stop,sql.AdvisoryDiagnosticUnavailable,
            verify.RestoreVerifyError,ValueError):
        raise Block('DYNAMIC_SQL_EXACT_PROOF_FAILED_STOP_IMPORT') from None
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
    p.add_argument('mode',choices=['plan','stage','verify-stage','restore-new-db'],
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
