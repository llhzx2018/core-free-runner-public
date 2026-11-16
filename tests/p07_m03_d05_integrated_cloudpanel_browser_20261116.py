#!/usr/bin/env python3
"""Disposable CloudPanel v2 actual browser UI: Add, Set Active, restore.

This script operates exclusively in a synthetic Runner QEMU VM. It never
updates CloudPanel's SQLite directly or discovers/contacts any Owner host.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "https://172.29.71.11:8443"
USER = "p07testadmin"
PASSWORD = "SyntheticOnly2026ABC!"
TARGET_PORT = 13307
TARGET_USER = "p07d05admin"
TARGET_PASSWORD = "P07_Synthetic_D05_Control_Only!"
SSH_KEY = os.environ.get("P07_D05_SSH_KEY", "")
EXPECTED_SSH = "172.29.71.11"


def mark(label, status="PASS"):
    print(f"P07_D05_CP_BROWSER_{label}={status}", flush=True)


class Block(Exception):
    pass


def ssh(sql):
    if not SSH_KEY.startswith("/") or not os.path.isfile(SSH_KEY):
        raise Block("SYNTHETIC_SSH_KEY_NOT_PROVEN")
    p = subprocess.run([
        "ssh", "-i", SSH_KEY, "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=8", "root@"+EXPECTED_SSH, sql
    ], capture_output=True, text=True, timeout=25, check=False)
    if p.returncode != 0:
        raise Block("SYNTHETIC_CP_DB_READBACK_UNVERIFIED")
    return p.stdout.strip()


def active_state():
    # Only public synthetic database_server metadata, no credentials.
    out=ssh("python3 -c 'import sqlite3; c=sqlite3.connect("
        "\"file:/home/clp/htdocs/app/data/db.sq3?mode=ro\",uri=True);"
        "r=list(c.execute(\"SELECT port,is_active FROM database_server ORDER BY id\"));"
        "print(\";\".join(str(p)+\":\"+str(a) for p,a in r))'")
    if not re.fullmatch(r"[0-9:;]+",out):
        raise Block("ACTIVE_STATE_UNVERIFIED")
    items=[tuple(map(int,entry.split(":"))) for entry in out.split(";")]
    if sum(a for _,a in items)!=1:
        raise Block("ACTIVE_STATE_INVALID")
    return items


def click_one(page,text,*, exact=False):
    pat = text if exact else re.compile(text,re.I)
    for kind in ("link","button","tab"):
        try:
            loc=page.get_by_role(kind,name=pat)
            if loc.count()==1 and loc.first.is_visible():
                loc.first.click(timeout=6000)
                return True
        except Exception:
            continue
    try:
        loc=page.get_by_text(pat,exact=exact)
        visible=[x for x in loc.all() if x.is_visible()]
        if len(visible)==1:
            visible[0].click(timeout=6000)
            return True
    except Exception:
        pass
    return False


def visible_actions(page):
    # Output only names/captions for synthetic UI debugging, no HTML/secrets.
    values=page.locator("a,button,[role=tab]").evaluate_all(
       """els=>els.filter(el=>el.offsetParent!==null).map(el=>(
         (el.innerText||el.getAttribute('aria-label')||'').trim()
       )).filter(s=>s && s.length<55).slice(0,55)"""
    )
    return "|".join(re.sub(r"[^A-Za-z0-9 _/-]","",x) for x in values)[:1700]


def input_fill(page,terms,value):
    for term in terms:
        for selector in (
            f'input[name*="{term}" i]',f'input[placeholder*="{term}" i]',
            f'input[id*="{term}" i]',
        ):
            try:
                loc=page.locator(selector + ":visible")
                if loc.count()==1:
                    loc.fill(value,timeout=4500)
                    return True
            except Exception:
                pass
    return False



def synthetic_management_smoke():
    """Only synthetic DB, isolated CloudPanel. Output fixed status codes."""
    if not SSH_KEY.startswith("/") or not os.path.isfile(SSH_KEY):
        raise Block("SYNTHETIC_SSH_KEY_NOT_PROVEN")
    script=r"""
set -Eeuo pipefail
test -f /root/.p07-d05-synthetic-qemu
test -r /home/p07alpha/htdocs/alpha.p07.example.com/db-switch.php
echo P07_D05_INTEGRATED_SOURCE_SITE_REUSED=PASS
clpctl db:add --domainName=alpha.p07.example.com \
 --databaseName=p07target --databaseUserName=p07targetuser \
 --databaseUserPassword='SyntheticOnly2026ABC!' \
 >/root/p07-d05-cp-db-add.log 2>&1 || {
   python3 - <<'PY'
from pathlib import Path
import re
msg=Path('/root/p07-d05-cp-db-add.log').read_text(errors='replace')[:6000].lower()
classes=[
 ('AUTHENTICATION',r'access denied|authentication|login failed|password'),
 ('ENGINE_VERSION',r'unsupported|not supported|version|mysql 8[.]4|percona'),
 ('CONNECTION',r'connection refused|can.t connect|timed out|2002|2003'),
 ('PRIVILEGE',r'permission denied|privilege|1044|1045'),
 ('DDL_INCOMPATIBLE',r'collation|syntax|unknown option|1064'),
 ('SCHEMA_CONFLICT',r'already exists|duplicate|1007'),
]
found=next((name for name,pat in classes if re.search(pat,msg)), 'UNCLASSIFIED')
print('P07_D05_CP_CLI_DB_ADD_DIAG='+found)
PY
   echo P07_D05_CP_CLI_DB_ADD_NOT_PROVEN; exit 52;
 }
echo P07_D05_CP_CLI_DB_ADD=PASS
pw='P07_Synthetic_D05_Root_Only!'
if test "$P07_D05_SOURCE_ENGINE" = MYSQL_8.4; then cli=mariadb; else cli=mysql; fi
docker exec -e "MYSQL_PWD=$pw" p07-d05-active-target "$cli" \
 -uroot -N -B -e "SHOW DATABASES LIKE 'p07target'" | grep -Fxq p07target || {
   echo P07_D05_CP_CLI_WRONG_DB_SERVER; exit 53;
 }
docker exec -e "MYSQL_PWD=$pw" p07-d05-active-target "$cli" \
 -uroot p07target -e \
 "CREATE TABLE p07_cp_marker (id INT PRIMARY KEY, marker VARCHAR(40)); INSERT INTO p07_cp_marker VALUES (1,'SYNTHETIC_CP_ACTIVE_42')" >/root/p07-d05-cp-seed.log 2>&1 || exit 54
echo P07_D05_CP_CLI_DB_PLACEMENT=PASS

docker exec -e "MYSQL_PWD=$pw" p07-d05-active-target "$cli" \
 -uroot p07target -e \
 "CREATE TABLE vf_probe (id INT PRIMARY KEY, marker VARCHAR(64) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci; INSERT INTO vf_probe VALUES (1,'TARGET_MARIA_FIRST'),(2,'TARGET_MARIA_SECOND')" >/root/p07-d05-target-fixture.log 2>&1 || exit 60
echo P07_D05_INTEGRATED_CP_MANAGED_MARIA_TABLE_SEEDED=PASS
clpctl db:export --databaseName=p07target --file=/root/p07-d05-target-export.sql \
 >/root/p07-d05-cp-db-export.log 2>&1 || {
   echo P07_D05_CP_CLI_EXPORT_NOT_PROVEN; exit 55;
 }
grep -Fq SYNTHETIC_CP_ACTIVE_42 /root/p07-d05-target-export.sql || exit 56
echo P07_D05_CP_CLI_TARGET_EXPORT=PASS
# CloudPanel v2 official scheduled backup runs as the 'clp' service user
# and uses --retentionPeriod=7 (not the obsolete v1 --databases selector).
runuser -u clp -- /usr/bin/clpctl db:backup --retentionPeriod=7 \
 >/root/p07-d05-cp-db-backup.log 2>&1 || {
   python3 - <<'PY'
from pathlib import Path
import re
msg=Path('/root/p07-d05-cp-db-backup.log').read_text(errors='replace')[:6000].lower()
classes=[
 ('CLI_ARGUMENT',r'unrecognized option|option .* does not exist|unknown option|no such option'),
 ('ACCOUNT',r'only.*(root|clp)|must.*user|not allowed|permission denied'),
 ('DB_CONNECTION',r'access denied|can.t connect|connection|mysql|mariadb|percona'),
 ('BACKUP_PATH',r'backup|directory|mkdir|path|write'),
]
found=next((name for name,pat in classes if re.search(pat,msg)), 'UNCLASSIFIED')
print('P07_D05_CP_CLI_BACKUP_DIAG='+found)
PY
   echo P07_D05_CP_CLI_BACKUP_NOT_PROVEN; exit 57;
 }
test -d /home/p07alpha/backups || exit 58
find /home/p07alpha/backups -type f -size +0c -print -quit | grep -q . || exit 59
echo P07_D05_CP_CLI_TARGET_BACKUP=PASS

python3 - <<'PY'
import sys
sys.path.insert(0, '/root')
from db_engine_conversion_site_sandbox import (
    inspect_cloudpanel_fixture_site, SyntheticSiteSwitchBlocked
)
try:
 fail=inspect_cloudpanel_fixture_site(inject="after-target-probe",distinct_target=True)
except SyntheticSiteSwitchBlocked as exc:
 print("P07_D05_INTEGRATED_APP_BLOCK="+str(exc))
 raise SystemExit(71)

assert fail["status"]=="FAIL_CLOSED_D05_SITE_INJECTED_AFTER_CONFIG", fail["status"]
assert fail["site_config_restored_byte_exact"]
assert fail["source_site_still_serving"]
print("P07_D05_INTEGRATED_SYNTHETIC_CONFIG_FAULT_AND_SOURCE_RESTORED=PASS")
try:
 ok=inspect_cloudpanel_fixture_site(distinct_target=True)
except SyntheticSiteSwitchBlocked as exc:
 print("P07_D05_INTEGRATED_APP_BLOCK="+str(exc))
 raise SystemExit(72)
assert ok["status"]=="SYNTHETIC_APP_SWITCH_READ_WRITE_PROVEN",ok["status"]
assert ok["distinct_synthetic_target_database_and_user"]
assert ok["target_app_read_write_proven"]
assert ok["site_config_restored_byte_exact"] and ok["source_site_still_serving"]
assert ok["cloudpanel_active_switch"]=="NOT_RUN"
assert not ok["business_conversion_enabled"]
print("P07_D05_INTEGRATED_CP_ACTIVE_HTTPS_SOURCE_TARGET_SOURCE=PASS")
PY
test "$(docker exec -e "MYSQL_PWD=$pw" p07-d05-active-target "$cli" -uroot p07target -N -B -e 'SELECT COUNT(*) FROM vf_probe')" = 3
echo P07_D05_INTEGRATED_CP_TARGET_APP_WRITE_READBACK=PASS
"""
    p=subprocess.run([
        "ssh","-i",SSH_KEY,"-o","BatchMode=yes",
        "-o","StrictHostKeyChecking=accept-new",
        "-o","UserKnownHostsFile=/dev/null",
        "-o","ConnectTimeout=8","root@"+EXPECTED_SSH,
        "P07_D05_SOURCE_ENGINE="+os.environ["P07_D05_SOURCE_ENGINE"]+" bash -se",
    ],input=script,capture_output=True,text=True,timeout=240,check=False)
    for line in p.stdout.splitlines():
        if re.fullmatch(r"P07_D05_CP_CLI_[A-Z0-9_]+=(?:PASS|AUTHENTICATION|ENGINE_VERSION|CONNECTION|PRIVILEGE|DDL_INCOMPATIBLE|SCHEMA_CONFLICT|UNCLASSIFIED|CLI_ARGUMENT|ACCOUNT|DB_CONNECTION|BACKUP_PATH)",line):
            print(line,flush=True)
        if re.fullmatch(r"P07_D05_INTEGRATED_[A-Z0-9_]+=(?:PASS|[A-Z0-9_]+)",line):
            print(line,flush=True)
    if p.returncode!=0:
        for line in p.stdout.splitlines():
            if re.fullmatch(r"P07_D05_CP_CLI_[A-Z0-9_]+_NOT_PROVEN",line):
                mark("CRUD_BLOCKED_REASON",line)
        raise Block("CLOUDPANEL_ACTIVE_DB_CRUD_OR_BACKUP_NOT_PROVEN")
    mark("OFFICIAL_ACTIVE_DATABASE_CRUD_BACKUP")

def browser_active():
    if (os.environ.get("P07_ALLOW_SYNTHETIC_D05")!="1"
            or os.environ.get("P07_D05_SOURCE_ENGINE") not in ("MARIADB_11.8","MYSQL_8.4")):
        raise Block("SYNTHETIC_ONLY_GUARD")
    origin=active_state()
    if len(origin)!=1 or origin[0][0]!=3306 or origin[0][1]!=1:
        raise Block("ORIGINAL_ACTIVE_NOT_EXCLUSIVE")
    with sync_playwright() as api:
        browser=api.chromium.launch(headless=True,args=["--no-sandbox"])
        ctx=browser.new_context(ignore_https_errors=True)
        page=ctx.new_page()
        page.set_default_timeout(9500)
        try:
            page.goto(URL+"/login",wait_until="domcontentloaded",timeout=30000)
            page.locator('input[name="userName"]').fill(USER)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.locator('input[type="password"]').press("Enter")
            page.wait_for_timeout(1400)
            if page.locator('input[name="userName"]').is_visible():
                raise Block("ADMIN_LOGIN_NOT_PROVEN")
            mark("AUTHENTICATED_REAL_ADMIN_SESSION")
            page.goto(URL+"/",wait_until="domcontentloaded",timeout=22000)
            if click_one(page,"Admin Area"):
                page.wait_for_timeout(700)
            if click_one(page,r"^Settings$"):
                page.wait_for_timeout(650)
            if not click_one(page,r"Database Servers"):
                mark("DISCOVERED_MENU_ACTIONS",visible_actions(page))
                raise Block("DATABASE_SERVERS_UI_NOT_DISCOVERED")
            page.wait_for_timeout(700)
            mark("DATABASE_SERVERS_OFFICIAL_BROWSER_PAGE")
            if not click_one(page,r"Add Database Server"):
                mark("DISCOVERED_MENU_ACTIONS",visible_actions(page))
                raise Block("ADD_DATABASE_SERVER_UI_NOT_FOUND")
            page.wait_for_timeout(450)
            required={
                "host":input_fill(page,["host"],"127.0.0.1"),
                "port":input_fill(page,["port"],str(TARGET_PORT)),
                "username":input_fill(page,["userName","username","user_name"],TARGET_USER),
                "password":input_fill(page,["password"],TARGET_PASSWORD),
            }
            if not all(required.values()):
                mark("ADD_FIELDS_PRESENT","_".join(k for k,v in required.items() if v))
                raise Block("DATABASE_SERVER_FORM_FIELDS_NOT_PROVEN")
            if not click_one(page,r"^Add Database Server$") and not click_one(page,r"^Add$"):
                raise Block("ADD_SUBMIT_BUTTON_NOT_PROVEN")
            page.wait_for_timeout(1350)
            rows=active_state()
            if not any(port==TARGET_PORT for port,_ in rows):
                raise Block("OFFICIAL_ADD_DID_NOT_REGISTER_TARGET")
            mark("OFFICIAL_ADD_EXTERNAL_TARGET")
            # At most one inactive row may be activated; identify by explicit
            # 13307 text in the *same rendered row*. No hidden routes invented.
            target=page.get_by_role("row").filter(has_text=str(TARGET_PORT))
            if target.count()!=1:
                raise Block("TARGET_ROW_NOT_UNAMBIGUOUS")
            action=target.get_by_role("button",name=re.compile("set active",re.I))
            if action.count()!=1:
                action=target.get_by_role("link",name=re.compile("set active",re.I))
            if action.count()!=1:
                raise Block("OFFICIAL_SET_ACTIVE_ACTION_NOT_FOUND")
            page.once("dialog",lambda dialog:dialog.accept())
            action.click()
            page.wait_for_timeout(1500)
            if not any(port==TARGET_PORT and active==1 for port,active in active_state()):
                raise Block("OFFICIAL_SET_ACTIVE_DID_NOT_SWITCH")
            mark("OFFICIAL_SET_ACTIVE_METADATA")
            smoke_failure=None
            try:
                synthetic_management_smoke()
            except Block as exc:
                smoke_failure=exc
            # Restore via the *same official row UI*, never SQLite editing.
            try:
                page.reload(wait_until="domcontentloaded")
                page.wait_for_timeout(450)
                original=page.get_by_role("row").filter(has_text="3306")
                if original.count()!=1:
                    raise Block("ORIGINAL_ROW_UNVERIFIED_FOR_ROLLBACK")
                act=original.get_by_role("button",name=re.compile("set active",re.I))
                if act.count()!=1:
                    act=original.get_by_role("link",name=re.compile("set active",re.I))
                if act.count()!=1:
                    raise Block("ORIGINAL_SET_ACTIVE_ACTION_NOT_FOUND")
                page.once("dialog",lambda dialog:dialog.accept())
                act.click()
                page.wait_for_timeout(1100)
                current=active_state()
                if not any(port==3306 and a==1 for port,a in current):
                    raise Block("OFFICIAL_SET_ACTIVE_ROLLBACK_UNVERIFIED")
                mark("OFFICIAL_SET_ACTIVE_ROLLBACK")
            except Block:
                raise
            # This phase does not claim site/CP CRUD/backup; those remain
            # separately unproven until real fixture and privilege testing.
            if smoke_failure is not None:
                raise smoke_failure
            mark("CP_DATABASE_CRUD_BACKUP","PROVEN_IN_SYNTHETIC_LAB")
            return 0
        finally:
            ctx.close()
            browser.close()


if __name__=="__main__":
    try:
        code=browser_active()
    except Block as exc:
        mark("BLOCKED_REASON",str(exc))
        code=3
    except (Exception,PWTimeout):
        mark("BLOCKED_REASON","BROWSER_OR_UI_NOT_PROVEN")
        code=3
    raise SystemExit(code)
