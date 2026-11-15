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
            mark("CP_DATABASE_CRUD","NOT_TESTED")
            mark("CP_DATABASE_BACKUP","NOT_TESTED")
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
