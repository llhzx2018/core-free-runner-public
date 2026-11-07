#!/usr/bin/env python3
"""P07 original18 selected-site backup + fail-closed private recovery checkpoint.

CP2 only. Real actions: old source CloudPanel export + private site archive;
CP2 vfops backup and private rsync pull. NO business database imports, no
migration resume, no DNS, no restore to active databases. Synthetic tests are
separate. The existing vfops native-restore is the ONLY live isolated restore
entry and remains blocked until independent SQL safety proof.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

MID = os.environ.get("P07_MIGRATION_ID", "")
DOMAIN = os.environ.get("P07_MIGRATION_SITE", "")
SLUG = DOMAIN.split(".", 1)[0] if DOMAIN else ""
BUILD = "0.1.0-release115"
BACKUPS = Path("/var/backups/vf-server-ops")
RESERVE = 512 * 1024**2
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
OLD_FOLDER = re.compile(r"p07-original18-"+re.escape(SLUG)+r"-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\Z")


def out(k, v):
    print(f"{k}={v}", flush=True)


def require(condition, code):
    if not condition:
        raise GateError(code)


class GateError(Exception):
    pass


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def private_directory(path, create=False):
    if create:
        path.mkdir(mode=0o700, parents=False, exist_ok=True)
    meta = path.lstat()
    require(stat.S_ISDIR(meta.st_mode) and meta.st_uid == os.geteuid()
            and stat.S_IMODE(meta.st_mode) == 0o700, "PRIVATE_DIR_UNSAFE")
    return path


def parent_for_disk(path):
    current = path
    while not current.exists():
        parent = current.parent
        require(parent != current, "DISK_ROOT_UNAVAILABLE")
        current = parent
    require(current.is_dir() and not current.is_symlink(), "DISK_PATH_UNSAFE")
    return current


def tree_bytes(path, max_files=500000):
    require(path.is_dir() and not path.is_symlink(), "SITE_ROOT_UNSAFE")
    total = 0
    count = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        for n in dirs + files:
            st = os.lstat(os.path.join(base, n))
            count += 1
            require(count <= max_files, "TOO_MANY_FILES")
            if stat.S_ISREG(st.st_mode):
                total += st.st_size
    require(total > 0, "SITE_EMPTY")
    return total


def database_reference_size():
    # Conservative CloudPanel datastore footprint, matching P07's capacity
    # strategy; avoids requiring root DB credentials or querying live data.
    for path in (Path("/home/mysql"), Path("/var/lib/mysql")):
        if path.is_dir() and not path.is_symlink():
            return tree_bytes(path)
    raise GateError("MYSQL_DATASTORE_SIZE_UNAVAILABLE")


def capacity(site_root, backup_root, *, source_transfer_bytes=0):
    site = tree_bytes(Path(site_root))
    db = database_reference_size()
    # Logical dump may be larger than physical storage. Reserve for temp export,
    # package archive, existing CP2 target plus future source archive transfer.
    needed = int(site * 1.5 + db * 2.5) + RESERVE + source_transfer_bytes
    free = shutil.disk_usage(parent_for_disk(backup_root)).free
    return {"site_bytes": site, "mysql_reference_bytes": db,
            "required_bytes": needed, "free_bytes": free,
            "adequate": free >= needed}


def receipt_write(path, payload):
    require(not path.exists() and not path.is_symlink(), "RECEIPT_ALREADY_EXISTS")
    content = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    require(digest(path) == hashlib.sha256(content).hexdigest(), "RECEIPT_WRITE_FAILED")


def receipt_read(path):
    st = path.lstat()
    require(stat.S_ISREG(st.st_mode) and st.st_uid == os.geteuid()
            and stat.S_IMODE(st.st_mode) == 0o600 and st.st_nlink == 1
            and 0 < st.st_size <= 40960, "RECEIPT_UNSAFE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        r = json.load(f)
    require(type(r) is dict and r.get("mid") == MID
            and r.get("domain") == DOMAIN, "RECEIPT_IDENTITY_MISMATCH")
    return r


def exists_without_following(path):
    """Even a dangling symlink is existing (and therefore never replaceable)."""
    return path.exists() or path.is_symlink()


def same_source_identity(verified, recorded):
    """Old V1 receipts predate package_bytes: verify their pinned hashes as-is."""
    keys = ("status", "folder", "manifest_sha256", "checksum_sha256")
    require(all(recorded.get(k) == verified.get(k) for k in keys),
            "SOURCE_RECEIPT_HASH_CHANGED")
    if "package_bytes" in recorded:
        require(recorded["package_bytes"] == verified.get("package_bytes"),
                "SOURCE_RECEIPT_SIZE_CHANGED")


def remaining_cp2_space(backups, checkpoint, *, target_required, transfer_required,
                        target_observed_free=None):
    """Sum unfinished operations per filesystem; never double charge reused backups.

    A backup and private transfer may be on the SAME filesystem even if they
    have different parent directories. Check their summed remaining need against
    the filesystem free bytes, rather than checking each independently.
    """
    roots = ((backups, target_required), (checkpoint, transfer_required))
    devices = {}
    for path, required in roots:
        if not required:
            continue
        parent = parent_for_disk(path)
        dev = parent.stat().st_dev
        free = shutil.disk_usage(parent).free
        if path == backups and target_observed_free is not None:
            free = min(free, target_observed_free)
        item = devices.setdefault(dev, {"free":free, "needed":0})
        item["free"] = min(item["free"], free)
        item["needed"] += required
    return {"adequate":all(v["free"] >= v["needed"] for v in devices.values()),
            "required_bytes":sum(v["needed"] for v in devices.values()),
            "free_bytes":min((v["free"] for v in devices.values()), default=0),
            "filesystem_count":len(devices)}


# This helper runs ONLY on the already-registered old VPS over pinned P07 SSH.
# It never imports SQL or touches active DB records. No raw SQL leaves the old
# server except over encrypted rsync into the private CP2 checkpoint.
OLD_HELPER = r'''
import gzip, hashlib, json, os, re, shutil, stat, subprocess, sys, tarfile, time
from pathlib import Path
MID=sys.argv[6] if len(sys.argv)>6 else ""
DOMAIN=sys.argv[3] if len(sys.argv)>3 else ""
SLUG=DOMAIN.split(".",1)[0] if DOMAIN else ""
BACKUPS=Path("/var/backups/vf-server-ops")
RESERVE=512*1024**2

def fail(label): raise ValueError(label)
def require(ok,label):
    if not ok: fail(label)
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1048576),b""): h.update(chunk)
    return h.hexdigest()
def walking(path):
    require(path.is_dir() and not path.is_symlink(),"SOURCE_PATH_UNSAFE")
    size=0; count=0
    for base,dirs,files in os.walk(path,followlinks=False):
        for name in dirs+files:
            st=os.lstat(os.path.join(base,name));count+=1
            require(count<=500000,"SOURCE_FILE_COUNT_UNBOUNDED")
            if stat.S_ISREG(st.st_mode): size+=st.st_size
    require(size>0,"SOURCE_EMPTY")
    return size
def check_path(path):
    while not path.exists():
        path=path.parent
    require(path.is_dir() and not path.is_symlink(),"SOURCE_BACKUP_MOUNT_UNSAFE")
    return path
def plan(site):
    files=walking(site)
    mysql=next((p for p in (Path('/home/mysql'),Path('/var/lib/mysql'))
                if p.is_dir() and not p.is_symlink()),None)
    require(mysql is not None,"SOURCE_MYSQL_DISK_UNAVAILABLE")
    db=walking(mysql)
    free=shutil.disk_usage(check_path(BACKUPS)).free
    required=int(files*1.5+db*2.5)+RESERVE
    return {'free_bytes':free,'required_bytes':required,
            'site_bytes':files,'mysql_reference_bytes':db,
            'adequate':free>=required}
def secure_dir(path,create=False):
    if create: path.mkdir(mode=0o700)
    st=path.lstat()
    require(stat.S_ISDIR(st.st_mode) and st.st_uid==0 and stat.S_IMODE(st.st_mode)==0o700,
            'SOURCE_PRIVATE_DIR_UNSAFE')
def validate_sql(path,change_permissions=False):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size>0,
            'SOURCE_SQL_MISSING')
    if change_permissions: path.chmod(0o600)
    else: require(stat.S_IMODE(path.stat().st_mode)==0o600,'SOURCE_SQL_MODE_UNSAFE')
    # Check completed gzip CRC and stable bytes, not just the gzip header.
    before=path.stat(); total=0
    with gzip.open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''): total+=len(chunk)
    after=path.stat()
    require(total>0 and (before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_ino,after.st_size,after.st_mtime_ns), 'SOURCE_SQL_UNSTABLE')
    first=sha(path)
    time.sleep(1)
    require(sha(path)==first and path.stat().st_size==after.st_size,'SOURCE_SQL_CHANGED')
    return first
def valid_package(folder,db):
    secure_dir(folder)
    manifest=folder/'manifest.json'; index=folder/'checksums.sha256'
    require(not manifest.is_symlink() and not index.is_symlink(), 'SOURCE_PACKAGE_LINK_UNSAFE')
    data=json.loads(manifest.read_text())
    require(data.get('schema')=='vf-server-ops.backup-package.v1', 'SOURCE_PACKAGE_SCHEMA_UNVERIFIED')
    require(data.get('backup_id')==folder.name and data.get('backup_kind')=='pre_migration'
            and (data.get('site') or {}).get('domain')==DOMAIN,
            'SOURCE_PACKAGE_SCOPE_MISMATCH')
    checks={}
    for line in index.read_text().splitlines():
        h, rel=line.split('  ',1)
        require(re.fullmatch('[a-f0-9]{64}',h) and rel in
                {'manifest.json','mysql/'+db+'.sql.gz','files/site.tar.gz',
                 'native-source-receipt.json'}
                and rel not in checks, 'SOURCE_CHECKSUM_INDEX_UNSAFE')
        checks[rel]=h
    require(len(checks)==4,'SOURCE_CHECKSUM_COVERAGE')
    require((folder/'mysql').is_dir() and not (folder/'mysql').is_symlink()
            and (folder/'files').is_dir() and not (folder/'files').is_symlink(),
            'SOURCE_PACKAGE_TREE_UNSAFE')
    members=list(folder.rglob('*'))
    require(not any(p.is_symlink() for p in members),
            'SOURCE_PACKAGE_TREE_UNSAFE')
    actual={p.relative_to(folder).as_posix() for p in members if p.is_file()}
    require(actual==set(checks)|{'checksums.sha256'},'SOURCE_CHECKSUM_COVERAGE')
    for rel,h in checks.items():
        path=folder/rel
        require(path.is_file() and not path.is_symlink() and sha(path)==h,
                'SOURCE_PACKAGE_HASH_CHANGED')
    validate_sql(folder/'mysql'/ (db+'.sql.gz'))
    with tarfile.open(folder/'files/site.tar.gz','r:gz') as archive:
        require(bool(archive.getmembers()),'SOURCE_SITE_ARCHIVE_EMPTY')
    # The size is measured from the verified package rather than from an
    # unrelated whole-server MySQL datastore. Used only for a missing CP2
    # transfer; it is NOT a database parity or restore proof.
    package_bytes = sum((folder / rel).stat().st_size for rel in checks)
    package_bytes += index.stat().st_size
    require(package_bytes > 0, 'SOURCE_PACKAGE_SIZE_UNAVAILABLE')
    return {'status':'VERIFIED','folder':folder.name,
            'manifest_sha256':sha(manifest),'checksum_sha256':sha(index),
            'package_bytes':package_bytes}

try:
    mode,host_hash,domain,db,site_root,mid,*args=sys.argv[1:]
    require(domain==DOMAIN and mid==MID and re.fullmatch('[A-Za-z0-9._-]{1,128}',db),
            'SOURCE_SCOPE_MISMATCH')
    hostname=Path('/etc/hostname').read_text().strip()
    real_hash='sha256:'+hashlib.sha256(hostname.encode()).hexdigest()[:16]
    require(real_hash==host_hash,'SOURCE_IDENTITY_CHANGED')
    site=Path(site_root)
    require(bool(re.fullmatch('/home/[A-Za-z0-9_-]+/htdocs/'+re.escape(DOMAIN),str(site)))
            and not site.is_symlink() and site.is_dir() and site.resolve()==site,
            'SOURCE_SITE_ROOT_UNSAFE')
    if mode=='preflight':
        print(json.dumps({'status':'PREFLIGHT',**plan(site)},separators=(',',':')))
    elif mode=='create':
        size=plan(site)
        require(size['adequate'],'SOURCE_DISK_SPACE_LOW')
        if not BACKUPS.exists():
            BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=False)
        secure_dir(BACKUPS)
        stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
        folder=BACKUPS/('p07-original18-'+SLUG+'-'+stamp+'-'+os.urandom(6).hex())
        secure_dir(folder,create=True)
        (folder/'mysql').mkdir(mode=0o700);(folder/'files').mkdir(mode=0o700)
        sql=folder/'mysql'/ (db+'.sql.gz')
        env=os.environ.copy();env.setdefault('SUDO_USER','root')
        proc=subprocess.run(['clpctl','db:export','--databaseName='+db,'--file='+str(sql)],
                            env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            timeout=3600,check=False)
        require(proc.returncode==0,'SOURCE_CLOUDPANEL_EXPORT_FAILED')
        validate_sql(sql,change_permissions=True)
        tar=folder/'files/site.tar.gz'
        with tarfile.open(tar,'w:gz',dereference=False) as archive:
            archive.add(site,arcname='site',recursive=True)
        tar.chmod(0o600)
        with tarfile.open(tar,'r:gz') as archive:
            require(bool(archive.getmembers()),'SOURCE_SITE_ARCHIVE_EMPTY')
        manifest={'schema':'vf-server-ops.backup-package.v1',
                  'backup_id':folder.name,'backup_kind':'pre_migration',
                  'created_at':stamp,
                  'site':{'domain':DOMAIN,'site_root':str(site)},
                  'contents':{'files_archive':'files/site.tar.gz',
                              'mysql':[{'file':'mysql/'+db+'.sql.gz',
                                        'database':db,'method':'clpctl_db_export'}],
                              'sqlite':[], 'metadata':{}},
                  'security':{'classification':'PRIVATE_SENSITIVE_BACKUP',
                              'remote_storage_requires_encryption':True},
                  'snapshot_consistency':'LIVE_NOT_ATOMIC',
                  'actual_restore_verified':False}
        with (folder/'manifest.json').open('x',encoding='utf-8') as f:
            json.dump(manifest,f,separators=(',',':'),sort_keys=True);f.write('\n')
        (folder/'manifest.json').chmod(0o600)
        # Immutable source-side receipt, included in the package checksum index.
        with (folder/'native-source-receipt.json').open('x',encoding='utf-8') as f:
            json.dump({'schema':'P07_ORIGINAL18_SOURCE_NATIVE_RECEIPT_V1',
                       'migration_id':MID,'site':DOMAIN,
                       'backup_id':folder.name,
                       'sql_sha256':sha(sql),'site_archive_sha256':sha(tar),
                       'restore_verified':False,'cutover_allowed':False},f,
                       separators=(',',':'),sort_keys=True);f.write('\n')
        (folder/'native-source-receipt.json').chmod(0o600)
        entries=['manifest.json','mysql/'+db+'.sql.gz','files/site.tar.gz',
                 'native-source-receipt.json']
        with (folder/'checksums.sha256').open('x',encoding='ascii') as f:
            for rel in entries: f.write(sha(folder/rel)+'  '+rel+'\n')
        (folder/'checksums.sha256').chmod(0o600)
        result=valid_package(folder,db)
        print(json.dumps(result,separators=(',',':')))
    elif mode=='verify':
        require(len(args)==1 and re.fullmatch(
            'p07-original18-'+re.escape(SLUG)+'-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}',args[0]),
            'SOURCE_RECEIPT_NAME_UNSAFE')
        result=valid_package(BACKUPS/args[0],db)
        receipt=BACKUPS/args[0]/'native-source-receipt.json'
        proof=json.loads(receipt.read_text())
        require(proof.get('schema')=='P07_ORIGINAL18_SOURCE_NATIVE_RECEIPT_V1'
                and proof.get('migration_id')==MID and proof.get('site')==DOMAIN
                and proof.get('backup_id')==args[0]
                and proof.get('sql_sha256')==sha(BACKUPS/args[0]/'mysql'/(db+'.sql.gz'))
                and proof.get('site_archive_sha256')==sha(BACKUPS/args[0]/'files/site.tar.gz'),
                'SOURCE_RECEIPT_MISMATCH')
        print(json.dumps(result,separators=(',',':')))
    else: fail('SOURCE_MODE_INVALID')
except Exception as exc:
    known={'SOURCE_SCOPE_MISMATCH','SOURCE_IDENTITY_CHANGED','SOURCE_SITE_ROOT_UNSAFE',
           'SOURCE_PATH_UNSAFE','SOURCE_FILE_COUNT_UNBOUNDED','SOURCE_EMPTY',
           'SOURCE_MYSQL_DISK_UNAVAILABLE','SOURCE_BACKUP_MOUNT_UNSAFE',
           'SOURCE_PRIVATE_DIR_UNSAFE','SOURCE_DISK_SPACE_LOW',
           'SOURCE_SQL_MISSING','SOURCE_SQL_UNSTABLE','SOURCE_SQL_CHANGED',
           'SOURCE_SQL_MODE_UNSAFE',
           'SOURCE_CLOUDPANEL_EXPORT_FAILED','SOURCE_SITE_ARCHIVE_EMPTY',
           'SOURCE_PACKAGE_HASH_CHANGED','SOURCE_CHECKSUM_INDEX_UNSAFE',
           'SOURCE_CHECKSUM_COVERAGE','SOURCE_PACKAGE_TREE_UNSAFE',
           'SOURCE_PACKAGE_SCOPE_MISMATCH',
           'SOURCE_PACKAGE_SCHEMA_UNVERIFIED','SOURCE_PACKAGE_LINK_UNSAFE',
           'SOURCE_RECEIPT_MISMATCH','SOURCE_RECEIPT_NAME_UNSAFE','SOURCE_MODE_INVALID'}
    message=str(exc)
    print(json.dumps({'status':'BLOCKED','reason':message if message in known else
                       'SOURCE_PRIVATE_BACKUP_UNAVAILABLE'}))
    sys.exit(4)
'''


def check_result(data, name):
    require(type(data) is dict and data.get("status") == "VERIFIED"
            and OLD_FOLDER.fullmatch(str(data.get("folder", "")))
            and HEX64.fullmatch(str(data.get("manifest_sha256", "")))
            and HEX64.fullmatch(str(data.get("checksum_sha256", "")))
            and type(data.get("package_bytes")) is int
            and 0 < data["package_bytes"] < 2**61, name)
    return data


def remote_call(mig, source, mode, state, site, db, extra=()):
    args = [mode, str(state["source_server_identity"]), DOMAIN, db,
            str(site["site_root"]), MID, *extra]
    command = "python3 -c " + shlex.quote(OLD_HELPER) + " " + " ".join(
        shlex.quote(s) for s in args)
    p = mig.source_remote(source, command, timeout=3900, check=False)
    require(p.returncode == 0, "OLD_VPS_" + mode.upper() + "_FAILED")
    try:
        result = json.loads(p.stdout.strip())
    except (ValueError, TypeError):
        raise GateError("OLD_VPS_RESPONSE_UNVERIFIED") from None
    require(type(result) is dict, "OLD_VPS_RESPONSE_UNVERIFIED")
    return result


def verify_target_package(package_core, path, db):
    require(path.parent.resolve() == BACKUPS.resolve() and path.is_dir()
            and not path.is_symlink(), "TARGET_PACKAGE_PATH_INVALID")
    try:
        manifest = json.loads((path / "manifest.json").read_text())
    except (OSError, ValueError, TypeError):
        raise GateError("TARGET_PACKAGE_MANIFEST_UNAVAILABLE") from None
    require(manifest.get("backup_kind") == "pre_migration"
            and manifest.get("backup_id") == path.name
            and (manifest.get("site") or {}).get("domain") == DOMAIN
            and len((manifest.get("contents") or {}).get("mysql") or []) == 1
            and manifest["contents"]["mysql"][0].get("database") == db,
            "TARGET_PACKAGE_IDENTITY_UNVERIFIED")
    require(package_core.verify_package_stable(path).get("status") == "PASS",
            "TARGET_PACKAGE_HASH_UNVERIFIED")
    return {"path": str(path), "manifest_sha256": digest(path/"manifest.json"),
            "checksum_sha256": digest(path/"checksums.sha256")}


def verify_transferred_package(package_core, root, expected, db):
    # Source native package is intentionally stored as a private *copy* on CP2.
    # Existing vfops checksum verification is reused for both formats.
    require(root.is_dir() and not root.is_symlink(), "SOURCE_TRANSFER_PATH_INVALID")
    try:
        manifest=json.loads((root/"manifest.json").read_text())
    except (OSError, ValueError, TypeError):
        raise GateError("SOURCE_TRANSFER_MANIFEST_UNAVAILABLE") from None
    require(manifest.get("backup_kind") == "pre_migration"
            and (manifest.get("site") or {}).get("domain") == DOMAIN
            and manifest.get("backup_id") == expected["folder"]
            and len((manifest.get("contents") or {}).get("mysql") or []) == 1
            and manifest["contents"]["mysql"][0].get("database") == db,
            "SOURCE_TRANSFER_IDENTITY_UNVERIFIED")
    require(digest(root/"manifest.json") == expected["manifest_sha256"]
            and digest(root/"checksums.sha256") == expected["checksum_sha256"],
            "SOURCE_TRANSFER_CHECKSUM_MISMATCH")
    require(package_core.verify_package_stable(root).get("status") == "PASS",
            "SOURCE_TRANSFER_PACKAGE_INTEGRITY_UNVERIFIED")
    return True


def main():
    require(bool(re.fullmatch(r"pull-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", MID))
            and bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)+", DOMAIN))
            and bool(re.fullmatch(r"[a-z0-9-]+", SLUG)), "TASK_INPUT_INVALID")
    require(os.geteuid() == 0, "CP2_ROOT_REQUIRED")
    exe = shutil.which("vfops")
    require(bool(exe), "VFOPS_MISSING")
    root = Path(exe).resolve().parent.parent
    require((root / "BUILD_ID").read_text().strip() == BUILD,
            "RELEASE115_REQUIRED")
    sys.path.insert(0, str(root/"lib"))
    import server_migration_pull as mig
    import package_core
    state = mig.load_state(MID)
    sites = state.get("sites")
    require(state.get("migration_id") == MID
            and state.get("status") == "PREPARE_FAILED"
            and type(sites) is list and len(sites) == 18,
            "ORIGINAL18_TASK_CHANGED")
    site = sites[7]
    require(site.get("domain") == DOMAIN and site.get("stage_status") == "PENDING"
            and (state.get("last_sql_guard_failure") or {}).get("reason") == "CONDITIONAL_DDL"
            and state.get("source_runtime_frozen") is False
            and state.get("target_runtime_activated") is False
            and state.get("dns_changed_by_p07") is False,
            "ORIGINAL18_GUARD_CHANGED")
    require(mig.target_identity() == state.get("target_server_identity"),
            "CP2_SERVER_IDENTITY_CHANGED")
    dbs = site.get("mysql_databases")
    require(type(dbs) is list and len(dbs) == 1 and type(dbs[0]) is str
            and NAME.fullmatch(dbs[0]), "DB_SCOPE_UNVERIFIED")
    db = dbs[0]
    # This bounded native old-source package contains exactly MySQL + site-root
    # files. Additional external or live SQLite resources require their own
    # consistent snapshot; never silently label an incomplete site recoverable.
    root_name = str(site.get("site_root", ""))
    extra = site.get("external_paths") or []
    require(type(extra) is list and all(isinstance(x, str) for x in extra),
            "EXTERNAL_RESOURCE_INVENTORY_UNVERIFIED")
    require(all(x.startswith(root_name.rstrip("/") + "/") for x in extra),
            "EXTERNAL_RESOURCE_NOT_COVERED")
    sqlite_assets = state.get("sqlite_assets") or []
    require(type(sqlite_assets) is list
            and not any(isinstance(x, dict) and
                        (str(x.get("path", "")).startswith(root_name.rstrip("/") + "/")
                         or x.get("user") == site.get("site_user"))
                        for x in sqlite_assets),
            "LIVE_SQLITE_SNAPSHOT_REQUIRED")
    source = state.get("source")
    require(type(source) is dict and source.get("ssh_user") == "root"
            and bool(re.fullmatch(r"sha256:[0-9a-f]{16}",
                                      str(state.get("source_server_identity", "")))),
            "OLD_SOURCE_IDENTITY_UNVERIFIED")
    require(str(site.get("site_root", "")).startswith("/home/")
            and str(site.get("site_root", "")).endswith("/htdocs/" + DOMAIN),
            "SITE_ROOT_SCOPE_INVALID")

    # IMPORTANT: read and verify every existing private receipt BEFORE any
    # capacity calculation, backup creation or transfer. A valid checkpoint
    # removes its corresponding step and space reservation on EVERY retry.
    checkpoint = mig.state_dir(MID) / ("private-" + SLUG + "-recovery")
    had_checkpoint = exists_without_following(checkpoint)
    if had_checkpoint:
        private_directory(checkpoint)
    target_receipt_path = checkpoint / "target.json"
    source_receipt_path = checkpoint / "source.json"
    transfer_receipt_path = checkpoint / "source-cp2.json"
    local_source = checkpoint / "source-package"

    target_done = had_checkpoint and exists_without_following(target_receipt_path)
    source_done = had_checkpoint and exists_without_following(source_receipt_path)
    transfer_done = had_checkpoint and exists_without_following(transfer_receipt_path)
    require(not transfer_done or source_done, "TRANSFER_WITHOUT_SOURCE_RECEIPT")

    # Fail closed if a receipt exists but its contents, scope, hash or on-disk
    # backing package changed. Never fall back to a new backup in that case.
    package = None
    verified = None
    if target_done:
        rec = receipt_read(target_receipt_path)
        require(rec.get("side") == "CP2_TARGET", "TARGET_RECEIPT_SCOPE_CHANGED")
        package = verify_target_package(package_core, Path(rec["path"]), db)
        require(package == {k: rec.get(k) for k in package},
                "TARGET_RECEIPT_HASH_CHANGED")
        out("TARGET_BACKUP", "REUSED_VERIFIED")
    if source_done:
        rec = receipt_read(source_receipt_path)
        require(rec.get("side") == "OLD_SOURCE", "SOURCE_RECEIPT_SCOPE_CHANGED")
        verified = check_result(remote_call(mig, source, "verify", state,
                                            site, db, [rec["folder"]]),
                                "SOURCE_REVERIFY_FAILED")
        same_source_identity(verified, rec)
        out("SOURCE_BACKUP", "REUSED_VERIFIED")
    if transfer_done:
        rec = receipt_read(transfer_receipt_path)
        require(rec.get("side") == "SOURCE_TRANSFER_CP2",
                "TRANSFER_RECEIPT_SCOPE_CHANGED")
        same_source_identity(verified, rec)
        verify_transferred_package(package_core, local_source, verified, db)
        out("SOURCE_TRANSFER", "REUSED_VERIFIED")
    elif had_checkpoint and exists_without_following(local_source):
        # A crashed/incomplete transfer cannot be silently trusted or
        # overwritten, even when there is no receipt.
        raise GateError("UNRECEIPTED_SOURCE_TRANSFER_PRESENT")

    need_target = not target_done
    need_source = not source_done
    need_transfer = not transfer_done
    target_plan = capacity(site["site_root"], BACKUPS) if need_target else None
    old_plan = None
    if need_source:
        old_plan = remote_call(mig, source, "preflight", state, site, db)
        require(old_plan.get("status") == "PREFLIGHT"
                and all(type(old_plan.get(x)) is int for x in
                        ("required_bytes", "free_bytes", "site_bytes",
                         "mysql_reference_bytes"))
                and all(old_plan[x] >= 0 for x in
                        ("required_bytes", "free_bytes", "site_bytes",
                         "mysql_reference_bytes")),
                "OLD_SPACE_EVIDENCE_UNVERIFIED")
    # For already verified source backups, use their ACTUAL private package
    # length. Only an uncreated source needs the conservative export estimate.
    if need_transfer:
        source_transfer_size = (
            int(verified["package_bytes"]) if source_done else
            int(old_plan["site_bytes"] * 1.5 +
                old_plan["mysql_reference_bytes"] * 2.5))
        require(0 < source_transfer_size < 2**61,
                "SOURCE_TRANSFER_SIZE_UNVERIFIED")
        transfer_required = int(source_transfer_size * 1.20) + RESERVE
    else:
        transfer_required = 0
    target_required = (int(target_plan["required_bytes"])
                       if need_target else 0)
    local_space = remaining_cp2_space(
        BACKUPS, checkpoint,
        target_required=target_required,
        transfer_required=transfer_required,
        target_observed_free=(int(target_plan["free_bytes"]) if need_target else None),
    )
    source_required = int(old_plan["required_bytes"]) if need_source else 0
    source_free = int(old_plan["free_bytes"]) if need_source else 0
    source_adequate = (old_plan["adequate"] is True
                       and source_free >= source_required) if need_source else True
    out("CP2_TARGET_BACKUP_STEP", "PENDING" if need_target else "REUSED")
    out("OLD_SOURCE_BACKUP_STEP", "PENDING" if need_source else "REUSED")
    out("CP2_SOURCE_TRANSFER_STEP", "PENDING" if need_transfer else "REUSED")
    out("CP2_TARGET_BACKUP_REQUIRED_GIB", round(target_required / 1024**3, 2))
    out("CP2_TRANSFER_REQUIRED_GIB", round(transfer_required / 1024**3, 2))
    out("CP2_SPACE_REQUIRED_GIB", round(local_space["required_bytes"] / 1024**3, 2))
    out("CP2_SPACE_PREFLIGHT", "PASS" if local_space["adequate"] else "BLOCKED")
    out("OLD_SPACE_REQUIRED_GIB", round(source_required / 1024**3, 2))
    out("OLD_SPACE_PREFLIGHT", "PASS" if source_adequate else "BLOCKED")
    require(local_space["adequate"] and source_adequate,
            "REMAINING_SPACE_PREFLIGHT_FAILED")

    # No new state or receipt is written until all saved evidence is checked
    # and the remaining disk allocations pass. Each successful step writes
    # its own exclusive, private receipt before attempting the next one.
    if not had_checkpoint:
        private_directory(checkpoint, create=True)
    if need_target:
        result = subprocess.run([exe, "backup", "--site", DOMAIN,
              "--kind", "pre_migration", "--output-dir", str(BACKUPS)],
              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
              text=True, timeout=7200, check=False)
        require(result.returncode == 0, "CP2_VFOPS_BACKUP_FAILED")
        package = verify_target_package(package_core, Path(result.stdout.strip()), db)
        receipt_write(target_receipt_path, {"mid":MID,"domain":DOMAIN,
                      "side":"CP2_TARGET",**package,"restore_verified":False})
        out("TARGET_BACKUP", "NEW_VERIFIED")
    out("TARGET_PRIVATE_RECEIPT", str(target_receipt_path))

    if need_source:
        verified = check_result(remote_call(mig, source, "create", state, site, db),
                                "SOURCE_NATIVE_BACKUP_NOT_VERIFIED")
        receipt_write(source_receipt_path,{"mid":MID,"domain":DOMAIN,
                    "side":"OLD_SOURCE",**verified,"restore_verified":False})
        out("SOURCE_BACKUP", "NEW_VERIFIED")
    out("SOURCE_PRIVATE_RECEIPT", str(source_receipt_path))

    if need_transfer:
        # Recheck against the ACTUAL verified package size after both backup
        # steps. This guards an export larger than our preflight estimate and
        # changes in available space while the two backups were being made.
        actual_transfer_required = int(verified["package_bytes"] * 1.20) + RESERVE
        transfer_space = remaining_cp2_space(
            BACKUPS, checkpoint, target_required=0,
            transfer_required=actual_transfer_required,
        )
        out("CP2_TRANSFER_FINAL_SPACE", "PASS" if transfer_space["adequate"] else "BLOCKED")
        require(transfer_space["adequate"], "TRANSFER_SPACE_CHANGED_AFTER_BACKUPS")
        # Only this private, previously verified source package can be copied.
        # In-flight objects are retained if a transfer crashes; a later run
        # stops instead of overwriting or silently claiming provenance.
        require(not exists_without_following(local_source),
                "UNRECEIPTED_SOURCE_TRANSFER_PRESENT")
        temporary=Path(tempfile.mkdtemp(prefix="source-inflight-",dir=checkpoint))
        os.chmod(temporary,0o700)
        remote_path=str(BACKUPS/verified["folder"])+"/"
        mig.pull_path(source,remote_path,temporary)
        verify_transferred_package(package_core,temporary,verified,db)
        os.rename(temporary,local_source)
        receipt_write(transfer_receipt_path,{"mid":MID,"domain":DOMAIN,
                      "side":"SOURCE_TRANSFER_CP2",**verified,
                      "restore_verified":False})
        out("SOURCE_TRANSFER", "NEW_VERIFIED")
    out("SOURCE_CP2_PRIVATE_RECEIPT", str(transfer_receipt_path))

    # Use release115 evidence gate. Never auto-run unsafe SQL, scratch restore,
    # adoption or resume; existing SQL is still recognized unsafe (3 branches).
    proof = subprocess.run([exe,"server-migrate","recovery-evidence",
                    "--source-package",str(local_source),
                    "--target-package",package["path"],"--site",DOMAIN],
                    stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,
                    timeout=600,check=False)
    require(proof.returncode == 0,"RECOVERY_EVIDENCE_COMMAND_FAILED")
    try:
        evidence=json.loads(proof.stdout)
    except (TypeError, ValueError):
        raise GateError("RECOVERY_EVIDENCE_INVALID") from None
    backups_pass = (evidence.get("source_backup_integrity") == "PASS" and
                    evidence.get("target_backup_integrity") == "PASS")
    out("TWO_BACKUP_INTEGRITY", "PASS" if backups_pass else "NOT_VERIFIED")
    out("SQL_UNSAFE_BRANCHES", evidence.get("dynamic_unsafe", "UNAVAILABLE"))
    out("RECOVERY_EVIDENCE_STATUS", evidence.get("status", "UNKNOWN"))
    out("MIGRATION_RESUME_ALLOWED", "NO")
    out("DNS_CHANGED", "NO")
    require(backups_pass, "TWO_BACKUPS_NOT_VERIFIED")
    require(evidence.get("status") == "BLOCKED_INDEPENDENT_RESTORE_AND_OPERATOR_POLICY",
            "RECOVERY_EVIDENCE_NOT_READY")
    require(type(evidence.get("dynamic_unsafe")) is int and
            evidence["dynamic_unsafe"] == 0, "THREE_SQL_UNSAFE_NOT_APPROVED")
    # Native engine rechecks exact SQL and refuses unproven clauses before
    # starting an unprivileged scratch MariaDB. Never use db:import on CP2.
    restore = subprocess.run([exe, "server-migrate", "native-restore",
             "--source-package", str(local_source),
             "--target-package", package["path"], "--site", DOMAIN,
             "--confirm", "NATIVE_RESTORE_SCRATCH_ONLY"],
             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
             timeout=1800, check=False)
    require(restore.returncode == 0, "NATIVE_SCRATCH_COMMAND_FAILED")
    try:
        restored = json.loads(restore.stdout)
    except (ValueError, TypeError):
        raise GateError("NATIVE_SCRATCH_RESULT_UNVERIFIED") from None
    require(restored.get("status") == "NATIVE_SCRATCH_RESTORE_VERIFIED_NOT_CUTOVER"
            and restored.get("actual_source_restore_verified") is True
            and restored.get("actual_target_restore_verified") is True
            and restored.get("production_database_writes_performed") is False
            and restored.get("migration_resume_allowed") is False,
            "NATIVE_SCRATCH_RESTORE_NOT_PASS")
    out("NATIVE_ISOLATED_RESTORE", "BOTH_INDEPENDENT_SCRATCH_PASS")
    out("LIVE_DATABASE_PARITY", "NOT_VERIFIED")
    out("13_PK_DIFFERENCES", "UNRESOLVED")
    out("MIGRATION_RESUME_ALLOWED", "NO")

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        code=str(exc)
        allowed={"TASK_INPUT_INVALID","CP2_ROOT_REQUIRED","VFOPS_MISSING","RELEASE115_REQUIRED",
                 "ORIGINAL18_TASK_CHANGED","ORIGINAL18_GUARD_CHANGED",
                 "CP2_SERVER_IDENTITY_CHANGED","DB_SCOPE_UNVERIFIED",
                 "OLD_SOURCE_IDENTITY_UNVERIFIED","SITE_ROOT_SCOPE_INVALID",
                 "EXTERNAL_RESOURCE_INVENTORY_UNVERIFIED",
                 "EXTERNAL_RESOURCE_NOT_COVERED","LIVE_SQLITE_SNAPSHOT_REQUIRED",
                 "OLD_SPACE_EVIDENCE_UNVERIFIED","DUAL_SPACE_PREFLIGHT_FAILED",
                 "REMAINING_SPACE_PREFLIGHT_FAILED","SOURCE_TRANSFER_SIZE_UNVERIFIED",
                 "TRANSFER_SPACE_CHANGED_AFTER_BACKUPS",
                 "SOURCE_RECEIPT_SIZE_CHANGED","TRANSFER_WITHOUT_SOURCE_RECEIPT",
                 "CP2_VFOPS_BACKUP_FAILED","TARGET_PACKAGE_PATH_INVALID",
                 "TARGET_PACKAGE_IDENTITY_UNVERIFIED","TARGET_PACKAGE_HASH_UNVERIFIED",
                 "TARGET_PACKAGE_MANIFEST_UNAVAILABLE","SOURCE_TRANSFER_MANIFEST_UNAVAILABLE",
                 "TARGET_RECEIPT_HASH_CHANGED","TARGET_RECEIPT_SCOPE_CHANGED",
                 "SOURCE_RECEIPT_HASH_CHANGED","SOURCE_RECEIPT_SCOPE_CHANGED",
                 "SOURCE_NATIVE_BACKUP_NOT_VERIFIED","SOURCE_REVERIFY_FAILED",
                 "SOURCE_TRANSFER_PATH_INVALID","SOURCE_TRANSFER_IDENTITY_UNVERIFIED",
                 "SOURCE_TRANSFER_CHECKSUM_MISMATCH",
                 "SOURCE_TRANSFER_PACKAGE_INTEGRITY_UNVERIFIED",
                 "TRANSFER_RECEIPT_SCOPE_CHANGED","UNRECEIPTED_SOURCE_TRANSFER_PRESENT",
                 "RECOVERY_EVIDENCE_COMMAND_FAILED","RECOVERY_EVIDENCE_INVALID",
                 "TWO_BACKUPS_NOT_VERIFIED","RECOVERY_EVIDENCE_NOT_READY",
                 "THREE_SQL_UNSAFE_NOT_APPROVED","NATIVE_SCRATCH_COMMAND_FAILED",
                 "NATIVE_SCRATCH_RESULT_UNVERIFIED","NATIVE_SCRATCH_RESTORE_NOT_PASS",
                 "PRIVATE_DIR_UNSAFE","MYSQL_DATASTORE_SIZE_UNAVAILABLE",
                 "DISK_PATH_UNSAFE","SITE_ROOT_UNSAFE","SITE_EMPTY","TOO_MANY_FILES",
                 "RECEIPT_ALREADY_EXISTS","RECEIPT_WRITE_FAILED","RECEIPT_UNSAFE",
                 "RECEIPT_IDENTITY_MISMATCH","TARGET_PACKAGE_PATH_INVALID",
                 "OLD_VPS_PREFLIGHT_FAILED","OLD_VPS_CREATE_FAILED","OLD_VPS_VERIFY_FAILED",
                 "OLD_VPS_RESPONSE_UNVERIFIED","SOURCE_REVERIFY_FAILED","DISK_ROOT_UNAVAILABLE"}
        out("CHECK_BLOCKED",code if code in allowed else "PRIVATE_BACKUP_FLOW_UNAVAILABLE")
        out("DATABASE_IMPORTS",0)
        out("MIGRATION_RESUME_ALLOWED","NO")
        sys.exit(4)
