#!/usr/bin/env python3
import os,re,json,hashlib,base64,html as htmllib,sys
from urllib.parse import urljoin
import requests

BASE='https://infra.kewaro.com/'
TARGET='2.7.0'; SOURCE='2.6.0'; SCHEMA=14
ASSET_ID=518668721; ASSET_NAME='VF_Infra_V2.7.0_UPDATE.zip'; ASSET_BYTES=140557; ASSET_SHA='34d34daf9641c21c5387363136f5297b37af2cc6722e41f8967358a04ef3c559'
MANIFEST_ID=518668706; MANIFEST_SHA='e33605a9e716e4b53ce8dbd8c167fc99dcbab0063a19f6e382123e251e01afd4'
STATUS_PATH='p04-v270-production-status.json'
REPO=os.environ.get('GITHUB_REPOSITORY','llhzx2018/core-free-runner-public'); BRANCH=os.environ.get('GITHUB_REF_NAME','p04-v270-production-upgrade-tmp')
GH_TOKEN=os.environ.get('GITHUB_TOKEN','')
READ_TOKEN=os.environ.get('VF_PRIVATE_READ_TOKEN','') or os.environ.get('VF_RELEASE_WRITE_TOKEN','')
PASSWORD=''
for n in ['VF_INFRA_ADMIN_PASSWORD','P04_ADMIN_PASSWORD','P04_PRODUCTION_ADMIN_PASSWORD','VF_PRODUCTION_ADMIN_PASSWORD','VF_INFRA_PRODUCTION_PASSWORD']:
    if os.environ.get(n): PASSWORD=os.environ[n]; break

state={'project':'P04 · VF Infra','source':SOURCE,'target':TARGET,'schema':SCHEMA,'production_upgrade':'STARTING','main_alignment':'NOT_EXECUTED','run_id':int(os.environ.get('GITHUB_RUN_ID','0') or 0),'private_values_persisted':False}

def publish(extra=None):
    if extra: state.update(extra)
    if not GH_TOKEN: return
    api=f'https://api.github.com/repos/{REPO}/contents/{STATUS_PATH}'
    hdr={'Authorization':f'Bearer {GH_TOKEN}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    r=requests.get(api,headers=hdr,params={'ref':BRANCH},timeout=20); old=None
    if r.status_code==200: old=r.json().get('sha')
    body={'message':'chore(P04): update production closure status','content':base64.b64encode((json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()).decode(),'branch':BRANCH}
    if old: body['sha']=old
    q=requests.put(api,headers=hdr,json=body,timeout=30)
    if q.status_code not in (200,201): print('STATUS_PUBLISH_WARNING',q.status_code,file=sys.stderr)

def fail(stage,msg):
    safe=re.sub(r'\s+',' ',str(msg))[:260]
    publish({'production_upgrade':'FAIL','failed_stage':stage,'failure':safe,'project_block':'PRODUCTION_GATE_FAILED'})
    raise SystemExit(f'P04_V270_PRODUCTION_FAIL_CLOSED stage={stage} reason={safe}')

def sha(b): return hashlib.sha256(b).hexdigest()
def csrf(text):
    m=re.search(r'name=["\']csrf["\'][^>]*value=["\']([^"\']+)',text,re.I) or re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']csrf["\']',text,re.I)
    if not m: raise RuntimeError('CSRF_NOT_FOUND')
    return htmllib.unescape(m.group(1))
def version_from_login(text):
    m=re.search(r'VF Infra\s*·\s*V([0-9]+(?:\.[0-9]+){2})',text)
    return m.group(1) if m else ''
def jget(s,action,**params):
    r=s.get(urljoin(BASE,'api.php'),params={'action':action,**params},timeout=40); r.raise_for_status(); d=r.json()
    if not d.get('ok'): raise RuntimeError(f'API_{action}_NOT_OK')
    return d
def jpost(s,action,token,data):
    hdr={'Origin':BASE.rstrip('/'),'Referer':BASE,'X-CSRF-Token':token}
    r=s.post(urljoin(BASE,'api.php'),params={'action':action},data=data,headers=hdr,timeout=90); r.raise_for_status(); d=r.json()
    if not d.get('ok'): raise RuntimeError(f'API_{action}_NOT_OK')
    return d

def count_contract(s):
    b=jget(s,'bootstrap')
    dash=b.get('dashboard') or {}
    picked={}
    def walk(prefix,obj):
        if isinstance(obj,dict):
            for k,v in obj.items():
                p=f'{prefix}.{k}' if prefix else str(k)
                if isinstance(v,(dict,list)): walk(p,v)
                elif isinstance(v,(int,float)) and (str(k).endswith('_count') or str(k) in {'total','domains','servers','assets'}): picked[p]=v
        elif isinstance(obj,list):
            pass
    walk('metrics',dash.get('metrics') or {})
    walk('infra',dash.get('infra') or {})
    # Always include public aggregate domain count if settings endpoint exposes it.
    try:
        st=jget(s,'settings')
        system=st.get('system') or {}
        if 'domain_count' in system: picked['system.domain_count']=int(system['domain_count'])
        asset=st.get('asset_summary') or {}
        for k,v in asset.items():
            if isinstance(v,(int,float)) and (str(k).endswith('_count') or str(k) in {'total','assets'}): picked[f'asset_summary.{k}']=v
    except Exception:
        pass
    if not picked: raise RuntimeError('AGGREGATE_COUNT_CONTRACT_EMPTY')
    return str(b.get('version','')),picked

def gh_asset(asset_id):
    if not READ_TOKEN: raise RuntimeError('PRIVATE_READ_TOKEN_MISSING')
    r=requests.get(f'https://api.github.com/repos/llhzx2018/vf-infra/releases/assets/{asset_id}',headers={'Authorization':f'Bearer {READ_TOKEN}','Accept':'application/octet-stream','X-GitHub-Api-Version':'2022-11-28'},timeout=90,allow_redirects=True)
    r.raise_for_status(); return r.content

publish()
if not PASSWORD: fail('CREDENTIAL','PRODUCTION_ADMIN_PASSWORD_CHANNEL_MISSING')
try:
    s=requests.Session(); s.headers.update({'User-Agent':'P04-V2.7.0-Authorized-Production-Upgrade/1.0'})
    # 1) PRE-UPDATE CURRENT TRUTH READBACK
    lg=s.get(urljoin(BASE,'login.php'),timeout=30); lg.raise_for_status(); before=version_from_login(lg.text)
    if before!=SOURCE: fail('PRE_CURRENT_TRUTH',f'EXPECTED_{SOURCE}_GOT_{before or "UNKNOWN"}')
    login_csrf=csrf(lg.text)
    lr=s.post(urljoin(BASE,'login.php'),data={'return':'maintenance.php','csrf':login_csrf,'password':PASSWORD},headers={'Origin':BASE.rstrip('/'),'Referer':urljoin(BASE,'login.php')},timeout=30,allow_redirects=False)
    if lr.status_code not in (302,303): fail('LOGIN','AUTH_FAILED')
    maint=s.get(urljoin(BASE,'maintenance.php'),timeout=30); maint.raise_for_status()
    if f'V{SOURCE}' not in maint.text or f'Schema {SCHEMA}' not in maint.text: fail('PRE_CURRENT_TRUTH','MAINTENANCE_IDENTITY_MISMATCH')
    pre_ver,pre_counts=count_contract(s)
    if pre_ver!=SOURCE: fail('PRE_CURRENT_TRUTH','BOOTSTRAP_VERSION_MISMATCH')
    boot=jget(s,'bootstrap'); api_csrf=str(boot.get('csrf',''))
    if not api_csrf: fail('PRE_CURRENT_TRUTH','API_CSRF_MISSING')
    publish({'pre_update_current_truth':'PASS','production_before':SOURCE,'schema_before':SCHEMA})

    # 2) PRE-UPDATE BACKUP + VERIFY
    bk=jpost(s,'backup_create',api_csrf,{'password':PASSWORD,'note':'P04 V2.7.0 OWNER-authorized pre-update protected recovery point','protected':'1'})
    bid=int((bk.get('backup') or {}).get('id') or 0)
    if bid<=0: fail('PRE_UPDATE_BACKUP','BACKUP_ID_INVALID')
    jpost(s,'backup_verify',api_csrf,{'id':str(bid)})
    publish({'pre_update_backup':'PASS','backup_verify':'PASS','protected_backup_recorded':True})

    # 3) EXACT RELEASE ASSET VERIFY
    pkg=gh_asset(ASSET_ID)
    if len(pkg)!=ASSET_BYTES or sha(pkg)!=ASSET_SHA: fail('ASSET_VERIFY','UPDATE_ASSET_IDENTITY_MISMATCH')
    expected_manifest=gh_asset(MANIFEST_ID)
    if sha(expected_manifest)!=MANIFEST_SHA: fail('ASSET_VERIFY','SOURCE_MANIFEST_ASSET_SHA_MISMATCH')
    publish({'release_asset_verify':'PASS','asset_name':ASSET_NAME,'asset_bytes':len(pkg),'asset_sha256':sha(pkg)})

    # 4) FORMAL ATOMIC PRECHECK / HANDOFF
    mc=csrf(maint.text)
    up=s.post(urljoin(BASE,'maintenance.php'),data={'csrf':mc,'expected_sha256':ASSET_SHA},files={'atomic_zip':(ASSET_NAME,pkg,'application/zip')},headers={'Origin':BASE.rstrip('/'),'Referer':urljoin(BASE,'maintenance.php')},timeout=90,allow_redirects=False)
    if up.status_code not in (302,303): fail('ATOMIC_PRECHECK',f'UPLOAD_HTTP_{up.status_code}')
    loc=htmllib.unescape(up.headers.get('Location',''))
    if 'repair-v2.7.0.php' not in loc: fail('ATOMIC_PRECHECK','HANDOFF_LOCATION_INVALID')
    repair_url=urljoin(BASE,loc)
    rp=s.get(repair_url,timeout=30); rp.raise_for_status(); repair_csrf=csrf(rp.text)
    if f'来源版本：V{SOURCE}' not in rp.text or 'Schema14' not in rp.text.replace(' ',''): fail('ATOMIC_PRECHECK','REPAIR_IDENTITY_MISMATCH')
    publish({'atomic_precheck':'PASS'})

    # 5) PRODUCTION ATOMIC UPGRADE. Repair itself creates protected pre_update backup and rolls back source + SQLite on failure.
    rr=s.post(repair_url,data={'csrf':repair_csrf},headers={'Origin':BASE.rstrip('/'),'Referer':repair_url},timeout=180)
    rr.raise_for_status()
    if '升级完成' not in rr.text: fail('ATOMIC_UPGRADE','SUCCESS_MARKER_MISSING')
    if '受保护 pre_update 恢复点：PASS' not in rr.text or 'SQLite integrity / FK：PASS' not in rr.text: fail('ATOMIC_UPGRADE','ATOMIC_BACKUP_OR_DB_MARKER_MISSING')
    publish({'production_upgrade':'PASS','atomic_pre_update_backup':'PASS'})

    # 6) VERSION / SCHEMA / DATA INTEGRITY / SMOKE
    lg2=requests.get(urljoin(BASE,'login.php'),timeout=30); lg2.raise_for_status(); after=version_from_login(lg2.text)
    if after!=TARGET: fail('VERSION_READBACK',f'EXPECTED_{TARGET}_GOT_{after or "UNKNOWN"}')
    post_ver,post_counts=count_contract(s)
    if post_ver!=TARGET: fail('VERSION_READBACK','BOOTSTRAP_TARGET_MISMATCH')
    if post_counts!=pre_counts: fail('DATA_INTEGRITY','AGGREGATE_RESOURCE_COUNT_CONTRACT_DRIFT')
    m2=s.get(urljoin(BASE,'maintenance.php'),timeout=30); m2.raise_for_status()
    if f'V{TARGET}' not in m2.text or f'Schema {SCHEMA}' not in m2.text: fail('SCHEMA_READBACK','MAINTENANCE_TARGET_SCHEMA_MISMATCH')
    idx=s.get(urljoin(BASE,'index.php'),timeout=30); idx.raise_for_status()
    for marker in ['概览','域名','服务器','服务商','设置']:
        if marker not in idx.text: fail('SMOKE',f'INDEX_MARKER_MISSING_{marker}')
    for action in ('bootstrap','dashboard'):
        jget(s,action)
    boot2=jget(s,'bootstrap'); csrf2=str(boot2.get('csrf',''))
    jpost(s,'backup_verify',csrf2,{'id':str(bid)})
    publish({'production':TARGET,'schema_after':SCHEMA,'data_integrity':'PASS','smoke':'PASS','backup_post_verify':'PASS'})

    # 7) SOURCE EXACT / RELEASE IDENTITY
    sm=s.get(urljoin(BASE,'maintenance.php'),params={'action':'source-manifest'},timeout=60); sm.raise_for_status()
    if sm.content!=expected_manifest: fail('SOURCE_EXACT',f'MANIFEST_MISMATCH prod={sha(sm.content)} expected={sha(expected_manifest)}')
    publish({'source_exact':'PASS','source_manifest_sha256':sha(sm.content)})

    # 8) ONLINE UPDATE STATE AFTER UPGRADE
    chk=jpost(s,'update_check',csrf2,{})
    upd=chk.get('update') or {}
    status=str(upd.get('status','')); latest=str(upd.get('latest_version','')); can=bool(upd.get('can_update',False))
    if status!='up_to_date' or latest!=TARGET or can: fail('ONLINE_STATE',f'BAD_STATE_{status}_{latest}_{can}')
    publish({'online_update_state':'NO_UPDATE_CURRENT','online_status':'up_to_date','latest_version':TARGET,'can_update':False,'final_online_pass':'PASS','production_upgrade':'PASS','production':TARGET,'schema_after':SCHEMA,'data_integrity':'PASS','smoke':'PASS','source_exact':'PASS','project_block':'NONE'})
    print('P04_V270_PRODUCTION_UPGRADE_AND_ONLINE_VERIFY_PASS')
except SystemExit:
    raise
except Exception as e:
    fail('UNHANDLED',e)
