#!/usr/bin/env python3
import argparse, hashlib, json, shutil, sqlite3
from pathlib import Path

EXPECTED_MANIFEST_SHA='3c00431c6050f7ee9a07da539f2946a9f2f3c19eab44cdf9c22a7a39e10289f6'
EXPECTED_UPDATE_SHA='f5b2d7e44cbc5ce1b7d7c7c13dbdc27fa4eaef1b117c54f67c2ac1f752deab75'

def create_schema(c):
    c.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, status TEXT NOT NULL);
    CREATE TABLE providers(id INTEGER PRIMARY KEY, provider_key TEXT NOT NULL UNIQUE);
    CREATE TABLE provider_accounts(id INTEGER PRIMARY KEY, provider_id INTEGER NOT NULL, archived_at TEXT NULL, FOREIGN KEY(provider_id) REFERENCES providers(id));
    CREATE TABLE domains(id INTEGER PRIMARY KEY, archived_at TEXT NULL);
    CREATE TABLE dns_zones(id INTEGER PRIMARY KEY, provider_account_id INTEGER NOT NULL, archived_at TEXT NULL, FOREIGN KEY(provider_account_id) REFERENCES provider_accounts(id));
    CREATE TABLE compute_instances(id INTEGER PRIMARY KEY, provider_account_id INTEGER NOT NULL, archived_at TEXT NULL, FOREIGN KEY(provider_account_id) REFERENCES provider_accounts(id));
    CREATE TABLE assets(id INTEGER PRIMARY KEY, asset_type TEXT NOT NULL, provider_account_id INTEGER NULL, archived_at TEXT NULL, FOREIGN KEY(provider_account_id) REFERENCES provider_accounts(id));
    CREATE TABLE asset_relations(id INTEGER PRIMARY KEY, from_asset_id INTEGER NOT NULL, to_asset_id INTEGER NOT NULL, relation_type TEXT NOT NULL, FOREIGN KEY(from_asset_id) REFERENCES assets(id), FOREIGN KEY(to_asset_id) REFERENCES assets(id));
    CREATE TABLE provider_billing_sync_state(provider_account_id INTEGER PRIMARY KEY, FOREIGN KEY(provider_account_id) REFERENCES provider_accounts(id));
    CREATE TABLE update_history(id INTEGER PRIMARY KEY AUTOINCREMENT,operation_id TEXT NOT NULL,package_id TEXT NOT NULL,from_version TEXT NOT NULL,to_version TEXT NOT NULL,started_at TEXT NOT NULL,completed_at TEXT NULL,result TEXT NOT NULL,failure_stage TEXT NOT NULL DEFAULT '',release_manifest_sha256 TEXT NOT NULL,update_package_sha256 TEXT NOT NULL,details_json TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE backups(id INTEGER PRIMARY KEY,filename TEXT NOT NULL,backup_type TEXT NOT NULL,note TEXT NOT NULL,size_bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL,source_version TEXT NOT NULL,schema_version INTEGER NOT NULL,integrity_status TEXT NOT NULL,foreign_key_status TEXT NOT NULL,protected INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE security_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,success INTEGER NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL);
    ''')

def fill_common(c, installed):
    c.executemany('INSERT INTO settings(key,value) VALUES(?,?)', [('installed_version',installed),('auth_generation','1')])
    c.executemany('INSERT INTO schema_migrations(version,status) VALUES(?,?)', [(i,'success') for i in range(1,15)])

def make_backup(path):
    con=sqlite3.connect(path)
    try:
        c=con.cursor(); create_schema(c); fill_common(c,'2.5.8'); con.commit()
    finally: con.close()
    raw=path.read_bytes(); return len(raw), hashlib.sha256(raw).hexdigest()

def make_live(path, backup_name, backup_size, backup_sha):
    con=sqlite3.connect(path)
    try:
        c=con.cursor(); create_schema(c); fill_common(c,'2.6.0')
        providers=['dynadot','cloudflare','linode','vultr','digitalocean']
        c.executemany('INSERT INTO providers(id,provider_key) VALUES(?,?)', list(enumerate(providers,1)))
        c.executemany('INSERT INTO provider_accounts(id,provider_id,archived_at) VALUES(?,?,NULL)', [(i,((i-1)%5)+1) for i in range(1,8)])
        c.executemany('INSERT INTO domains(id,archived_at) VALUES(?,NULL)',[(i,) for i in range(1,38)])
        c.executemany('INSERT INTO dns_zones(id,provider_account_id,archived_at) VALUES(?,?,NULL)',[(i,2) for i in range(1,14)])
        c.executemany('INSERT INTO compute_instances(id,provider_account_id,archived_at) VALUES(?,?,NULL)',[(1,3),(2,4)])
        assets=[(1,'domain',1,None),(2,'dns_zone',2,None)] + [(i,'generic',((i-1)%7)+1,None) for i in range(3,87)]
        c.executemany('INSERT INTO assets(id,asset_type,provider_account_id,archived_at) VALUES(?,?,?,?)',assets)
        c.execute("INSERT INTO asset_relations(id,from_asset_id,to_asset_id,relation_type) VALUES(1,1,2,'dns_managed_by')")
        c.execute('INSERT INTO provider_billing_sync_state(provider_account_id) VALUES(1)')
        c.execute('''INSERT INTO update_history(operation_id,package_id,from_version,to_version,started_at,completed_at,result,failure_stage,release_manifest_sha256,update_package_sha256,details_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',('op-v260-fixture','P04_APP','2.5.8','2.6.0','2026-08-17 06:30:00','2026-08-17 06:31:00','success','',EXPECTED_MANIFEST_SHA,EXPECTED_UPDATE_SHA,json.dumps({'schema':14})))
        c.execute('''INSERT INTO backups(id,filename,backup_type,note,size_bytes,sha256,created_at,source_version,schema_version,integrity_status,foreign_key_status,protected) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(260,backup_name,'pre_update','在线更新到 V2.6.0 前自动恢复点',backup_size,backup_sha,'2026-08-17 06:30:20','2.5.8',14,'ok','ok',1))
        c.execute('INSERT INTO security_logs(event_type,success,details_json,created_at) VALUES(?,?,?,?)',('online_update_prepared',1,json.dumps({'operation_id':'op-v260-fixture','from_version':'2.5.8','to_version':'2.6.0','recovery_backup_id':260}),'2026-08-17 06:30:30'))
        con.commit(); assert c.execute('PRAGMA integrity_check').fetchone()[0].lower()=='ok'; assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
    finally: con.close()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--private-root',required=True); args=ap.parse_args()
    root=Path(args.private_root).resolve()
    if root.exists(): shutil.rmtree(root)
    for d in ['database','backups','sessions','state','staging','temp','update/downloads']:(root/d).mkdir(parents=True,exist_ok=True)
    name='vf-infra-pre-update-v2.5.8-to-v2.6.0-fixture.sqlite'; size,sha=make_backup(root/'backups'/name); make_live(root/'database'/'vf-domain.sqlite',name,size,sha)
    print(json.dumps({'private_root':str(root),'backup':{'filename':name,'bytes':size,'sha256':sha}},sort_keys=True))
if __name__=='__main__': main()
