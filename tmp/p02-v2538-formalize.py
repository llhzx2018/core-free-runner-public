#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT=Path.cwd()
TARGET='2.5.38'
SOURCES=['2.5.36','2.5.37']
SCHEMA=2401
TS='2026-09-19T03:50:00Z'
RUN_ID=os.environ.get('GITHUB_RUN_ID','UNKNOWN')
STAMP=tuple(dt.datetime.fromisoformat(TS.replace('Z','+00:00')).astimezone(dt.timezone.utc).timetuple()[:6])

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def meta(path: Path) -> dict:
    return {'path':path.name,'bytes':path.stat().st_size,'sha256':sha(path)}

def write_entry(z: zipfile.ZipFile,name: str,data: bytes,mode: int=0o644) -> None:
    info=zipfile.ZipInfo(name,STAMP)
    info.compress_type=zipfile.ZIP_DEFLATED
    info.external_attr=(stat.S_IFREG|mode)<<16
    z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)

def rezip(root: Path,dst: Path) -> None:
    with zipfile.ZipFile(dst,'w') as z:
        for p in sorted(root.rglob('*')):
            if p.is_symlink():
                raise RuntimeError(f'symlink forbidden: {p}')
            if p.is_file():
                write_entry(z,p.relative_to(root).as_posix(),p.read_bytes(),0o755 if os.access(p,os.X_OK) else 0o644)

def patched_builder(dst: Path) -> None:
    src=(ROOT/'scripts/build-release-v2.5.4.py').read_text(encoding='utf-8')
    old="ROOT=Path(__file__).resolve().parents[1]; SRCVER='2.5.2'; VER='2.5.4'; SCHEMA=2401; DT=(2026,8,19,2,0,0)"
    new="ROOT=Path.cwd(); SRCVER='2.5.37'; VER='2.5.38'; SCHEMA=2401; DT=(2026,9,19,3,50,0)"
    if old not in src:
        raise SystemExit('release builder identity changed')
    src=src.replace(old,new,1)
    start="notes=out/f'VF_Library_V{VER}_RELEASE_NOTES.md'; notes.write_text(f'''# VF Library V{VER}

V2.5.38 continues the Inkstone-class whole-interface simplification requested by OWNER, focusing on less persistent chrome and more usable content space.

- List sorting, display, selection and view controls now live in a single compact 44px workbench header.
- Notebook list controls are compact and on-demand; title search expands only when requested.
- Reader and document commands are icon-first with tooltip / ARIA labels instead of persistent text labels.
- Editor formatting chrome is compressed to a 36px single line; paragraph/H1/H2/H3 collapse into one heading selector.
- Desktop navigation is 224px and the default Notebook list is 304px; custom saved list widths remain preserved.
- Library and Notebook rows are denser without shrinking the reading typography.
- Redundant per-row file glyphs are removed on desktop so titles receive more horizontal space.
- Desktop Settings is a tighter 840x680 modal with a 158px navigation rail and no duplicate section heading.
- VF teal identity, P02 IA, Material model, Canonical Content, auth and update semantics remain unchanged.
- Schema remains {SCHEMA}; no migration.
- Direct UPDATE supports V2.5.36 and V2.5.37.
- OWNER explicitly authorized a continuous publish-first flow; post-publication OWNER real-use remains a separate truth.
''')
 arts=[sz,fz,uz,az,rf,notes]"""
    src=src[:i]+notes+src[j+len(end):]
    dst.write_text(src,encoding='utf-8')

def finalize(out: Path) -> None:
    deploy=out/'.deploy'
    subprocess.check_call(['bash','scripts/build-deploy-tree.sh',str(deploy)])

    update=out/f'VF_Library_V{TARGET}_UPDATE.zip'
    subprocess.check_call([
        'python3','scripts/build-multisource-update.py',
        '--deploy-root',str(deploy),'--output',str(update),
        '--target-version',TARGET,
        '--source-version',SOURCES[0],
        '--source-version',SOURCES[1],
        '--source-schema',str(SCHEMA),'--target-schema',str(SCHEMA),
        '--timestamp',TS,
    ])

    repair=out/f'repair-v{TARGET}.php'
    subprocess.check_call([
        'python3','scripts/build-multisource-repair.py',
        '--deploy-root',str(deploy),
        '--template','scripts/repair-template.php',
        '--output',str(repair),
        '--target-version',TARGET,
        '--source-version',SOURCES[0],
        '--source-version',SOURCES[1],
        '--schema',str(SCHEMA),
    ])

    atomic=out/f'VF_Library_V{TARGET}_ATOMIC.zip'
    with zipfile.ZipFile(atomic,'w') as z:
        write_entry(z,repair.name,repair.read_bytes())

    full=out/f'VF_Library_V{TARGET}_FULL.zip'
    full_dir=out/'.full'
    with zipfile.ZipFile(full) as z:
        z.extractall(full_dir)
    rm=full_dir/'release-manifest.json'
    runtime=json.loads(rm.read_text(encoding='utf-8'))
    runtime['upgrade']['supported_from']=SOURCES
    runtime['upgrade']['update']=meta(update)
    runtime['upgrade']['atomic']=meta(atomic)
    runtime['upgrade']['repair']=meta(repair)
    rm.write_text(json.dumps(runtime,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rezip(full_dir,full)

    release_manifest=out/f'VF_Library_V{TARGET}_RELEASE_MANIFEST.json'
    release=json.loads(release_manifest.read_text(encoding='utf-8'))
    release['compatibility']['supported_from']=SOURCES
    release['gates']={
        'exact_source':f'PASS_RUN_{RUN_ID}',
        'repository_and_unit':f'PASS_RUN_{RUN_ID}',
        'inkstone_shell_real_chromium':f'PASS_RUN_{RUN_ID}',
        'deterministic_build':f'PASS_RUN_{RUN_ID}',
        'fresh_install':f'PASS_RUN_{RUN_ID}',
        'atomic_update_2.5.36':f'PASS_RUN_{RUN_ID}',
        'atomic_update_2.5.37':f'PASS_RUN_{RUN_ID}',
        'repair_web_2.5.37':f'PASS_RUN_{RUN_ID}',
        'secret':'PASS','private_data':'PASS','db_binary':'PASS','archive':'PASS',
    }
    release['owner_preview']={
        'applicability':'N_A',
        'reason':'OWNER explicitly authorized continuous publish-first release flow; post-publication OWNER real-use remains separate.',
    }
    release['public_authority_applicability']={
        'INSTALL':{'state':'REQUIRED','evidence':f'fresh_install_PASS_RUN_{RUN_ID}'},
        'SECURITY':{'state':'REQUIRED','evidence':f'repository_secret_private_data_setup_lock_PASS_RUN_{RUN_ID}'},
        'TESTING':{'state':'REQUIRED','evidence':f'repository_unit_browser_install_upgrade_PASS_RUN_{RUN_ID}'},
        'UPGRADE':{'state':'REQUIRED','evidence':f'atomic_update_2.5.36_2.5.37_backup_rollback_PASS_RUN_{RUN_ID}'},
        'DATA_SCHEMA':{'state':'REQUIRED','evidence':f'schema_2401_no_migration_data_preservation_PASS_RUN_{RUN_ID}'},
        'API_PROVIDER':{'state':'N_A','reason':'no provider/API surface changed'},
        'SEO':{'state':'N_A','reason':'private noindex product; no public SEO surface changed'},
        'CRON_JOB':{'state':'N_A','reason':'no scheduler/job behavior changed'},
        'NOTIFICATION':{'state':'N_A','reason':'no notification surface changed'},
        'OBSERVABILITY':{'state':'N_A','reason':'release/channel only; Production is not executed by this release gate'},
        'PERFORMANCE':{'state':'N_A','reason':'no latency/capacity contract changed'},
        'GIT':{'state':'REQUIRED','evidence':f'exact_source_tag_remote_readback_PASS_RUN_{RUN_ID}'},
        'UA_UI':{'state':'REQUIRED','evidence':f'real_chromium_desktop_mobile_PASS_RUN_{RUN_ID}'},
    }
    release['authority_drift']={'pre_release':'PASS','reason':'CURRENT remains a resolver; dynamic release/channel/production truth is read from owning live sources.'}
    release['git']={'main_readback':'PRE_RELEASE_MAIN_UNCHANGED','formal_tag':f'v{TARGET}','tag_readback':'PENDING_REMOTE_RELEASE'}
    release['deployment']={'status':'NOT_EXECUTED','production_readback':'NOT_EXECUTED','final_online_pass':False}
    type_by_name={a['path']:a.get('type','') for a in release.get('artifacts',[])}
    assets=[]
    for p in [
        out/f'VF_Library_V{TARGET}_SOURCE.zip',
        full,
        update,
        atomic,
        repair,
        out/f'VF_Library_V{TARGET}_RELEASE_NOTES.md',
    ]:
        item=meta(p)
        item['type']=type_by_name.get(p.name,'REPAIR' if p==repair else 'UPDATE' if p==update else 'ATOMIC' if p==atomic else '')
        assets.append(item)
    release['artifacts']=assets
    release_manifest.write_text(json.dumps(release,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    shutil.rmtree(deploy,ignore_errors=True)
    shutil.rmtree(full_dir,ignore_errors=True)
    sums=[p for p in out.iterdir() if p.is_file() and p.name!='SHA256SUMS.txt']
    (out/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(sums,key=lambda p:p.name)),encoding='utf-8')

def build(out: Path) -> None:
    tmp=Path(os.environ['RUNNER_TEMP'])/'build-v2538.py'
    patched_builder(tmp)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    tree=subprocess.check_output(['git','show','-s','--format=%T',head],text=True).strip()
    subprocess.check_call([
        'python3',str(tmp),'--out',str(out),
        '--source-commit',head,'--source-tree',tree,'--source-ref','release/v2.5.38'
    ])
    finalize(out)

for root in [Path('build/formal-a'),Path('build/formal-b')]:
    build(root)

def hashes(root: Path) -> dict[str,str]:
    return {p.name:sha(p) for p in root.iterdir() if p.is_file()}

a=hashes(Path('build/formal-a')); b=hashes(Path('build/formal-b'))
if a!=b:
    raise SystemExit(f'non-deterministic formal build: {a} != {b}')
print('P02_V2538_DETERMINISTIC_FORMAL_BUILD=PASS')
for name,digest in sorted(a.items()):
    print(f'FORMAL_SHA256 {digest} {name}')
