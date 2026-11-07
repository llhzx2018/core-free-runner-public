#!/usr/bin/env python3
"""P07 local-only readback of three guarded SQL groups from VERIFIED CP2 backup packages.

Never exports, executes SQL, contacts source, changes databases, creates files,
updates receipts, restores, resumes, or emits private SQL/table/variable names.
Output is advisory ONLY. An unproven control branch ALWAYS blocks migration.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys

MID = os.environ.get('P07_MIGRATION_ID', '')
DOMAIN = os.environ.get('P07_MIGRATION_SITE', '')
BUILD = '0.1.0-release115'
MIGRATION_RE = re.compile(r'pull-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}\Z')
DOMAIN_RE = re.compile(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)+\Z')
TOKEN_RE = re.compile(r'[A-Za-z_][A-Za-z_0-9$]*\Z')
SET_RE = re.compile(r'^SET\s+(?:SESSION\s+|@@SESSION\.)(?P<name>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*(?P<value>.+)$', re.I)
SET_RE_ALTERNATE = re.compile(r'^SET\s+(?P<name>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*(?P<value>.+)$', re.I)
SAVE_RE = re.compile(r'^SET\s+@(?P<var>[A-Za-z_][A-Za-z_0-9$]*)\s*=\s*@@(?:(?:SESSION|LOCAL)\.)?(?P<source>[A-Za-z_][A-Za-z_0-9$]*)\s*;?$',re.I)
USER_VAR_RE = re.compile(r'@[A-Za-z_][A-Za-z_0-9$]*\Z')
NUMBER_RE = re.compile(r'[-+]?(?:0|[1-9][0-9]{0,17})\Z')
KNOWN_SESSION = {'SQL_MODE','SQL_NOTES','TIME_ZONE','CHARACTER_SET_CLIENT','CHARACTER_SET_RESULTS','COLLATION_CONNECTION','FOREIGN_KEY_CHECKS','UNIQUE_CHECKS','AUTOCOMMIT'}
REPLICATION_SESSION = {'SQL_LOG_BIN','GTID_NEXT','GTID_PURGED','LOG_BIN'}

class Blocked(Exception): pass

def need(test, why):
    if not test: raise Blocked(why)

def out(k,v): print(str(k)+'='+str(v),flush=True)

def private_json(path, side):
    st=path.lstat()
    need(stat.S_ISREG(st.st_mode) and st.st_uid==os.geteuid() and st.st_nlink==1
         and stat.S_IMODE(st.st_mode)==0o600 and 0<st.st_size<=40960, 'PRIVATE_RECEIPT_UNSAFE')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        data=f.read(40961)
        need(len(data)<=40960,'PRIVATE_RECEIPT_UNBOUNDED')
        body=json.loads(data)
    need(type(body) is dict and body.get('mid')==MID and body.get('domain')==DOMAIN
         and body.get('side')==side, 'PRIVATE_RECEIPT_IDENTITY_CHANGED')
    return body

def sha(path):
    d=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):d.update(c)
    return d.hexdigest()

def package_sql(pkg, package_core, db, receipt, label):
    need(pkg.is_dir() and not pkg.is_symlink(), 'PACKAGE_DIRECTORY_UNSAFE')
    need(package_core.verify_package_stable(pkg).get('status')=='PASS',label+'_PACKAGE_INTEGRITY_NOT_PASS')
    need(sha(pkg/'manifest.json')==receipt.get('manifest_sha256') and sha(pkg/'checksums.sha256')==receipt.get('checksum_sha256'),label+'_PACKAGE_RECEIPT_HASH_MISMATCH')
    j=json.loads((pkg/'manifest.json').read_bytes())
    need(j.get('backup_kind')=='pre_migration' and (j.get('site') or {}).get('domain')==DOMAIN, label+'_PACKAGE_PROVENANCE_CHANGED')
    mysql=(j.get('contents') or {}).get('mysql')
    need(type(mysql) is list and len(mysql)==1 and mysql[0].get('database')==db,label+'_DB_CHANGED')
    rel=mysql[0].get('file')
    need(type(rel) is str and not rel.startswith('/') and '\\' not in rel and '..' not in PurePosixPath(rel).parts and len(PurePosixPath(rel).parts)==2 and rel.startswith('mysql/') and rel.endswith('.sql.gz'),label+'_SQL_PATH_UNSAFE')
    path=pkg/rel
    need(path.is_file() and not path.is_symlink(),label+'_SQL_UNAVAILABLE')
    return path

def unpack(literal):
    if (not literal.startswith("'") or not literal.endswith("'") or len(literal)>4098):
        return None,'OUTER_LITERAL_UNPROVEN'
    inside=literal[1:-1]
    if any(c in inside for c in ('\\','\r','\n','\x00')):
        return None,'ESCAPE_OR_SQL_MODE_CONTEXT_UNPROVEN'
    if "'" in inside.replace("''",''):
        return None,'QUOTE_CONTEXT_UNPROVEN'
    return inside.replace("''", "'"),'QUOTE_CONTEXT_SIMPLE'

def branch_class(text):
    if text is None:return {'class':'UNPROVEN','target':'UNKNOWN','value':'UNKNOWN','name':None,'value_name':None}
    text=text.strip().rstrip(';').strip()
    m=SET_RE.fullmatch(text) or SET_RE_ALTERNATE.fullmatch(text)
    if m is None:
        return {'class':'NOT_SINGLE_SESSION_SET','target':'UNKNOWN','value':'UNKNOWN','name':None,'value_name':None}
    name=m.group('name').upper();value=m.group('value').strip()
    cls=('REPLICATION_OR_LOGGING_SETTING' if name in REPLICATION_SESSION else
         'KNOWN_SESSION_SETTING' if name in KNOWN_SESSION else 'UNKNOWN_SESSION_SETTING')
    value_cls=('NUMERIC_LITERAL' if NUMBER_RE.fullmatch(value) else
               'USER_VARIABLE_NEEDS_SAVE_PROOF' if USER_VAR_RE.fullmatch(value) else 'UNKNOWN_VALUE_EXPRESSION')
    return {'class':cls,'target':'IDENTITY_REDACTED','value':value_cls,'name':name,
            'value_name':value[1:].upper() if USER_VAR_RE.fullmatch(value) else None}

def parse_guarded_lines(lines, verify):
    """Analyze only the already-observed single probe + 3 ordered IF groups."""
    guard=re.compile(r'^/\*!([0-9]{5,6})\s+(.+?)\s*\*/;?$',re.I)
    items=[]
    for line in lines:
        m=guard.fullmatch(line.strip())
        need(m is not None and 40000<=int(m.group(1))<80000, 'VERSIONED_GUARD_UNPROVEN')
        body=m.group(2).strip()
        if p:=verify._CROSS_ENGINE_TABLE_COUNT_RE.fullmatch(body):
            items.append(('PROBE',p.group('flag').upper(),'',''))
        elif d:=verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body):
            items.append(('ASSIGN',d.group('stmt').upper(),d.group('flag').upper(),(d.group('yes'),d.group('no'))))
        elif p:=verify._CROSS_ENGINE_PREPARE_RE.fullmatch(body):
            items.append(('PREPARE',p.group(1).upper(),p.group(2).upper(),''))
        elif p:=verify._CROSS_ENGINE_EXECUTE_RE.fullmatch(body):
            items.append(('EXECUTE',p.group(1).upper(),'',''))
        elif p:=verify._CROSS_ENGINE_DEALLOCATE_RE.fullmatch(body):
            items.append(('DEALLOCATE',p.group(1).upper(),'',''))
        else:raise Blocked('THIRTEEN_LINE_GRAMMAR_CHANGED')
    need(len(items)==13 and items[0][0]=='PROBE' and
         [x[0] for x in items[1:]]==['ASSIGN','PREPARE','EXECUTE','DEALLOCATE']*3,
         'THIRTEEN_LINE_ORDER_CHANGED')
    flag=items[0][1]
    details=[]
    for idx in (1,5,9):
        assignment,prepared,execute,dealloc=items[idx:idx+4]
        need(assignment[2]==flag and prepared[2]==assignment[1] and
             execute[1]==prepared[1] and dealloc[1]==prepared[1],
             'PREPARE_EXECUTE_BINDINGS_CHANGED')
        yes,no=assignment[3]
        y,q=unpack(yes);n,nq=unpack(no)
        if idx==1:
            kind='METADATA_SELECT_WITH_USER_VARIABLE' if y and re.match(r'^SELECT\s+COUNT\s*\(',y,re.I) else 'METADATA_QUERY_UNPROVEN'
            if kind=='METADATA_SELECT_WITH_USER_VARIABLE':
                need(re.match(r'^SELECT\s+COUNT\s*\(\s*\*\s*\)\s+INTO\s+@[A-Za-z_][A-Za-z_0-9$]*\s+FROM\s+',y,re.I) is not None, 'METADATA_QUERY_SHAPE_UNPROVEN')
            details.append({'kind':kind,'quote':q,'class':'CONTROL_READ_UNPROVEN','name':None,'value_name':None,'value':'N/A'})
        else:
            item=branch_class(y)
            item['quote']=q
            details.append(item)
        need(n is not None and (re.fullmatch(r'SELECT\s+0',n,re.I) or re.fullmatch(r'SET\s+@[A-Za-z_][A-Za-z_0-9$]*\s*=\s*0',n,re.I)),
             'GUARD_NO_BRANCH_CHANGED')
    return details

def read_control_lines(sql, verify):
    """Locate exactly the 13 bound events, regardless of interleaving/order.

    The release115 verifier accepts prepare/execute/deallocate interleavings.
    Other versioned dump SET commands are *not* part of this 13-event flow.
    This analyzer does not approve or execute any SQL.
    """
    guard = re.compile(r'^/\*!([0-9]{5,6})\s+(.+?)\s*\*/;?$', re.I)
    stage = re.compile(r'^(?:SELECT\s+COUNT\s*\(|SET\s+@|PREPARE\s+|EXECUTE\s+|DEALLOCATE\s+PREPARE\s+)', re.I)
    matches = []
    saves = []
    unrelated = 0
    scanned = 0
    total = 0
    with gzip.open(sql, 'rt', encoding='utf-8', errors='strict') as f:
        for number, raw in enumerate(f, 1):
            scanned = number
            total += len(raw)
            need(number <= 2_000_000 and total <= 1_000_000_000,
                 'SQL_SCAN_BOUND_EXCEEDED')
            if len(raw) > 16384:
                continue
            line = raw.strip()
            versioned = guard.fullmatch(line)
            body = None
            if versioned and 40000 <= int(versioned.group(1)) < 80000:
                body = versioned.group(2).strip()
            saved = SAVE_RE.fullmatch(body if body is not None else line)
            if saved:
                need(len(saves) < 128, 'SESSION_SAVE_SCAN_BOUND_EXCEEDED')
                saves.append((number, saved.group('var').upper(),
                              saved.group('source').upper()))
            if body is None:
                continue
            if found := verify._CROSS_ENGINE_TABLE_COUNT_RE.fullmatch(body):
                event = ('PROBE', found.group('flag').upper(), '', line)
            elif found := verify._CROSS_ENGINE_DYNAMIC_IF_RE.fullmatch(body):
                event = ('ASSIGN', found.group('stmt').upper(),
                         found.group('flag').upper(), line)
            elif found := verify._CROSS_ENGINE_PREPARE_RE.fullmatch(body):
                event = ('PREPARE', found.group(1).upper(),
                         found.group(2).upper(), line)
            elif found := verify._CROSS_ENGINE_EXECUTE_RE.fullmatch(body):
                event = ('EXECUTE', found.group(1).upper(), '', line)
            elif found := verify._CROSS_ENGINE_DEALLOCATE_RE.fullmatch(body):
                event = ('DEALLOCATE', found.group(1).upper(), '', line)
            else:
                if stage.match(body):
                    unrelated += 1
                continue
            need(len(matches) < 128, 'DYNAMIC_EVENT_SCAN_BOUND_EXCEEDED')
            matches.append((number, *event))
    kinds = ['PROBE', 'ASSIGN', 'PREPARE', 'EXECUTE', 'DEALLOCATE']
    counts = {k: sum(x[1] == k for x in matches) for k in kinds}
    need(counts == {'PROBE': 1, 'ASSIGN': 3, 'PREPARE': 3,
                    'EXECUTE': 3, 'DEALLOCATE': 3},
         'DYNAMIC_EVENT_COUNT_CHANGED')
    probes = set()
    used_probes = set()
    unconsumed = {}
    active = {}
    completed = set()
    groups = []
    probe_line = None
    for lineno, kind, name, other, line in matches:
        if kind == 'PROBE':
            need(not probes, 'DYNAMIC_EVENT_BINDING_CHANGED')
            probes.add(name)
            probe_line = line
        elif kind == 'ASSIGN':
            need(other in probes and name not in unconsumed,
                 'DYNAMIC_EVENT_BINDING_CHANGED')
            group = {'assign': line, 'assign_at': lineno}
            groups.append(group)
            unconsumed[name] = len(groups) - 1
            used_probes.add(other)
        elif kind == 'PREPARE':
            need(name not in active and other in unconsumed,
                 'DYNAMIC_EVENT_BINDING_CHANGED')
            group_id = unconsumed.pop(other)
            groups[group_id]['prepare'] = line
            active[name] = (group_id, False)
        elif kind == 'EXECUTE':
            need(name in active and active[name][1] is False,
                 'DYNAMIC_EVENT_BINDING_CHANGED')
            group_id = active[name][0]
            groups[group_id]['execute'] = line
            active[name] = (group_id, True)
        elif kind == 'DEALLOCATE':
            need(name in active and active[name][1] is True,
                 'DYNAMIC_EVENT_BINDING_CHANGED')
            group_id = active.pop(name)[0]
            need(group_id not in completed, 'DYNAMIC_EVENT_BINDING_CHANGED')
            groups[group_id]['deallocate'] = line
            completed.add(group_id)
    need(probes == used_probes and not unconsumed and not active
         and len(completed) == 3 and len(groups) == 3,
         'DYNAMIC_EVENT_BINDING_CHANGED')
    # Canonical arrangement is for classification only. Each original event
    # has already been verified in its actual source order above.
    canonical = [probe_line]
    for group in groups:
        canonical.extend(group[x] for x in ('assign', 'prepare',
                                           'execute', 'deallocate'))
    details = parse_guarded_lines(canonical, verify)
    a, b, c = details
    preceding = {(name, src) for at, name, src in saves
                 if at < groups[2]['assign_at']}
    save_relation = (b['name'] is not None and b['name'] == c['name']
                     and c['value_name'] is not None
                     and (c['value_name'], c['name']) in preceding)
    return details, save_relation, len(preceding), unrelated

def main():
    need(os.geteuid()==0,'CP2_ROOT_REQUIRED')
    need(MIGRATION_RE.fullmatch(MID) and DOMAIN_RE.fullmatch(DOMAIN), 'TASK_SCOPE_UNSAFE')
    exe=shutil.which('vfops');need(bool(exe),'VFOPS_MISSING')
    root=Path(exe).resolve().parent.parent
    need((root/'BUILD_ID').read_text().strip()==BUILD,'RELEASE115_REQUIRED')
    sys.path.insert(0,str(root/'lib'))
    import server_migration_pull as mig
    import package_core
    import verify
    state=mig.load_state(MID)
    sites=state.get('sites')
    need(state.get('migration_id')==MID and state.get('status')=='PREPARE_FAILED'
         and type(sites) is list and len(sites)==18 and mig.target_identity()==state.get('target_server_identity'),
         'ORIGINAL_MIGRATION_SCOPE_CHANGED')
    site=sites[7]
    need(site.get('domain')==DOMAIN and site.get('stage_status')=='PENDING'
         and (state.get('last_sql_guard_failure') or {}).get('reason')=='CONDITIONAL_DDL',
         'SITE_GUARD_SCOPE_CHANGED')
    dbs=site.get('mysql_databases');need(type(dbs) is list and len(dbs)==1 and type(dbs[0]) is str,'SITE_DB_SCOPE_CHANGED')
    db=dbs[0];slug=DOMAIN.split('.',1)[0]
    checkpoint=mig.state_dir(MID)/('private-'+slug+'-recovery')
    st=checkpoint.lstat();need(stat.S_ISDIR(st.st_mode) and st.st_uid==os.geteuid() and stat.S_IMODE(st.st_mode)==0o700,'CHECKPOINT_PRIVATE_UNSAFE')
    src=private_json(checkpoint/'source.json','OLD_SOURCE')
    transfer=private_json(checkpoint/'source-cp2.json','SOURCE_TRANSFER_CP2')
    target=private_json(checkpoint/'target.json','CP2_TARGET')
    keys=('folder','manifest_sha256','checksum_sha256','status')
    need(all(src.get(k)==transfer.get(k) for k in keys),'SOURCE_TRANSFER_RECEIPT_CHANGED')
    cp2source=checkpoint/'source-package'
    cp2target=Path(target['path'])
    need(cp2source.resolve().parent==checkpoint.resolve() and
         cp2target.resolve().parent==Path('/var/backups/vf-server-ops').resolve(),
         'PACKAGE_SCOPE_CHANGED')
    source_sql=package_sql(cp2source,package_core,db,transfer,'SOURCE')
    _=package_sql(cp2target,package_core,db,target,'TARGET')
    details,save_relation,save_count,other_controls=read_control_lines(source_sql,verify)
    out('TWO_BACKUPS_REVALIDATED','PASS')
    out('SOURCE_CP2_COPY_INTEGRITY','PASS')
    out('CONTROL_LINES',13)
    out('OTHER_VERSIONED_CONTROL_LINES',other_controls)
    out('DYNAMIC_SQL_GROUPS',3)
    for i,v in enumerate(details,1):
        out(f'G{i}_CATEGORY', v.get('kind',v.get('class')))
        out(f'G{i}_QUOTE_CONTEXT',v['quote'])
        if i>1:out(f'G{i}_VALUE_CLASS',v['value'])
    out('G2_G3_SESSION_TARGET_SAME',details[1]['name'] is not None and details[1]['name']==details[2]['name'])
    out('G2_G3_RESTORE_VAR_SAVED',save_relation)
    out('PRECEDING_SESSION_SAVE_ASSIGNMENTS',save_count)
    out('ACTUAL_SESSION_VARIABLE_IDENTITIES','PRIVATE_REDACTED')
    out('SEMANTIC_SAFETY','NOT_APPROVED')
    out('ISOLATED_RESTORE','NOT_RUN')
    out('DATABASE_PARITY','NOT_VERIFIED')
    out('SOURCE_OR_TARGET_DB_WRITES',0)
    out('MIGRATION_RESUME_ALLOWED','NO')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        codes={'CP2_ROOT_REQUIRED','TASK_SCOPE_UNSAFE','VFOPS_MISSING','RELEASE115_REQUIRED',
               'ORIGINAL_MIGRATION_SCOPE_CHANGED','SITE_GUARD_SCOPE_CHANGED','SITE_DB_SCOPE_CHANGED',
               'CHECKPOINT_PRIVATE_UNSAFE','PRIVATE_RECEIPT_UNSAFE','PRIVATE_RECEIPT_UNBOUNDED',
               'PRIVATE_RECEIPT_IDENTITY_CHANGED','SOURCE_TRANSFER_RECEIPT_CHANGED',
               'PACKAGE_SCOPE_CHANGED','PACKAGE_DIRECTORY_UNSAFE','SOURCE_PACKAGE_INTEGRITY_NOT_PASS',
               'SOURCE_PACKAGE_RECEIPT_HASH_MISMATCH','SOURCE_PACKAGE_PROVENANCE_CHANGED',
               'SOURCE_DB_CHANGED','SOURCE_SQL_PATH_UNSAFE','SOURCE_SQL_UNAVAILABLE',
               'TARGET_PACKAGE_INTEGRITY_NOT_PASS','TARGET_PACKAGE_RECEIPT_HASH_MISMATCH',
               'TARGET_PACKAGE_PROVENANCE_CHANGED','TARGET_DB_CHANGED','TARGET_SQL_PATH_UNSAFE',
               'TARGET_SQL_UNAVAILABLE','THIRTEEN_LINE_GRAMMAR_CHANGED','THIRTEEN_LINE_ORDER_CHANGED',
               'PREPARE_EXECUTE_BINDINGS_CHANGED','METADATA_QUERY_SHAPE_UNPROVEN',
               'GUARD_NO_BRANCH_CHANGED','SQL_SCAN_BOUND_EXCEEDED','DYNAMIC_EVENT_COUNT_CHANGED',
               'DYNAMIC_EVENT_BINDING_CHANGED','SESSION_SAVE_SCAN_BOUND_EXCEEDED',
               'DYNAMIC_EVENT_SCAN_BOUND_EXCEEDED',
               'THIRTEEN_CONTROL_LINES_NOT_FOUND'}
        val=str(exc)
        out('CHECK_BLOCKED',val if val in codes else 'PRIVATE_ANALYSIS_UNAVAILABLE')
        out('SQL_SAFETY','NOT_VERIFIED')
        out('MIGRATION_RESUME_ALLOWED','NO')
        raise SystemExit(13)
