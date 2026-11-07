#!/usr/bin/env python3
"""P01 #1935 focused V500 installer/auth/Owner-browser/worker negatives.

Only runs in disposable Public Runner work with synthetic PHP/SQLite data.
No Production credentials, DB, website access, or persisted private artifact.
Existing candidate package, regression and rollback PASS are reused, not re-run.
"""
from __future__ import annotations
import argparse
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

PASSWORD="SyntheticOnly!Passw0rd"

def require(condition, message):
    if not condition:raise AssertionError(message)

def run(*cmd,cwd=None,timeout=120,expect=0,env=None):
    p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                     cwd=cwd,timeout=timeout,env=env)
    if expect is not None:
        require(p.returncode==expect,"command exited "+str(p.returncode)+" "+p.stderr[-350:])
    return p

def http(op,url,method="GET",json_body=None):
    data=json.dumps(json_body).encode() if json_body is not None else None
    headers={"Accept":"application/json"}
    if data is not None: headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,method=method,data=data,headers=headers)
    try:
        with op.open(req,timeout=8) as r:return r.status,r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code,e.read().decode(errors="replace")

def http_server(root,port):
    p=subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(root)],
                      cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            with urllib.request.urlopen(url+"/VERSION.txt",timeout=1) as res:
                if res.status==200:return p,url
        except Exception:time.sleep(.12)
    p.terminate();p.wait(timeout=4)
    raise AssertionError("synthetic localhost server failed to start")

def terminate(p):
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)

def locate_db(site):
    code='require $argv[1]."/app/bootstrap.php"; echo VF_DB_FILE;'
    p=run("php","-r",code,str(site),cwd=site)
    db=Path(p.stdout.strip())
    require(db.is_file(),"private SQLite not installed")
    return db

def sql_check(db):
    import sqlite3
    u="file:"+urllib.parse.quote(str(db))+"?mode=ro"
    con=sqlite3.connect(u,uri=True,timeout=5)
    try:
        result=con.execute("PRAGMA quick_check").fetchone()
        require(result and result[0]=="ok","SQLite quick_check not ok")
    finally:con.close()

def installed_reentry_and_guest_denials(site,port):
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    server,url=http_server(site,port)
    try:
        code,page=http(op,url+"/setup.php")
        require(code in (200,302) and "name=\"setup_csrf\"" not in page,
                "installed setup page still exposing install form")
        # Replay POST after successful installation must never recreate or
        # replace the existing SQLite/config. No valid install token is reused.
        payload=urllib.parse.urlencode({
            "setup_csrf":"untrusted-old-value",
            "site_title":"Overwrite me",
            "admin_password":PASSWORD,
            "admin_password_confirm":PASSWORD}).encode()
        req=urllib.request.Request(url+"/setup.php",data=payload,method="POST")
        try:
            with op.open(req,timeout=6) as resp: replay=resp.read().decode(errors="replace")
        except urllib.error.HTTPError as e: replay=e.read().decode(errors="replace")
        require("name=\"setup_csrf\"" not in replay,
                "revisit POST unexpectedly presented a setup form")
        require((site/"VERSION.txt").read_text().strip()=="2.47.500",
                "installer revisit changed version")
        sql_check(locate_db(site))
        print("P01_247500_INSTALLED_SETUP_REVISIT_AND_POST_REPLAY_DENIED=PASS",flush=True)

        statuses=[]
        for action,method,body in [("update_status","GET",None),
                                    ("update_prepare","POST",{}),
                                    ("update_install","POST",{"operation_id":"synthetic-invalid"})]:
            status,body_text=http(op,url+"/api.php?action="+action,method,body)
            require(status in (401,403,405,419,422,429),
                "guest update action "+action+" unexpectedly answered HTTP "+str(status))
            statuses.append((action,status))
        print("P01_247500_GUEST_UPDATE_STATUS_PREPARE_INSTALL_DENIED=PASS",flush=True)
        return url
    finally:terminate(server)

def concurrent_worker_lock_and_recovery(site):
    code=('require $argv[1]."/app/bootstrap.php";'
          '$lease=VfMaintenanceBarrier::globalExclusive();'
          'echo "HELD\\n";fflush(STDOUT);sleep(8);')
    holder=subprocess.Popen(["php","-r",code,str(site)],
        cwd=site,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    workers=[]
    try:
        ready,_,_=select.select([holder.stdout],[],[],4)
        require(bool(ready) and holder.stdout.readline().strip()=="HELD",
                "exclusive holder did not acquire lock")
        start=time.monotonic()
        for _ in range(4):
            workers.append(subprocess.Popen(["php",str(site/"cli/worker.php")],
                cwd=site,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        for p in workers:
            out,err=p.communicate(timeout=6)
            require(p.returncode!=0 and "维护锁" in (out+err),
                    "concurrent worker did not fail closed on bounded global lock")
        require(time.monotonic()-start<5.5,
                "scheduler worker group waited excessively behind EX")
        print("P01_247500_FOUR_CONCURRENT_WORKERS_BOUNDED_DENIAL=PASS",flush=True)
    finally:
        for p in workers:
            if p.poll() is None:p.terminate()
        terminate(holder)
    post=run("php",str(site/"cli/worker.php"),cwd=site,timeout=10)
    require("WORKER_HANDLED=" in post.stdout,"worker did not recover after EX release")
    print("P01_247500_CONCURRENT_WORKERS_POST_EX_RECOVERY=PASS",flush=True)

def owner_chromium_ui(site,port):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait

    chrome=shutil.which("google-chrome") or shutil.which("chromium")
    driver_bin=shutil.which("chromedriver")
    require(chrome is not None and driver_bin is not None,"hosted Chromium dependencies missing")
    server,url=http_server(site,port)
    opts=Options()
    opts.binary_location=chrome
    for flag in ("--headless=new","--no-sandbox","--disable-dev-shm-usage",
                 "--window-size=1440,900"):
        opts.add_argument(flag)
    driver=None
    try:
        driver=webdriver.Chrome(service=Service(driver_bin),options=opts)
        driver.set_page_load_timeout(22)
        driver.get(url+"/")
        w=WebDriverWait(driver,12)
        w.until(lambda d:bool(d.find_elements(By.CSS_SELECTOR,"[data-vf-auth-login]")))
        driver.find_element(By.CSS_SELECTOR,"[data-vf-auth-login]").click()
        w.until(lambda d:any(e.is_displayed() for e in d.find_elements(By.CSS_SELECTOR,
                                             "[data-vf-auth-dialog] input[name=password]")))
        driver.find_element(By.CSS_SELECTOR,"[data-vf-auth-dialog] input[name=password]").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR,"[data-vf-auth-dialog] [data-vf-auth-submit]").click()
        w.until(lambda d:bool(d.find_elements(By.CSS_SELECTOR,"[data-vf-global-manage-open]")))
        print("P01_247500_REAL_CHROMIUM_OWNER_LOGIN_AFTER_UPGRADE=PASS",flush=True)

        driver.find_element(By.CSS_SELECTOR,"[data-vf-global-manage-open]").click()
        w.until(lambda d:d.find_element(By.CSS_SELECTOR,"#vf-local-management").get_attribute("open") is not None)
        update=driver.find_element(By.CSS_SELECTOR,'[data-vf-global-group="update"]')
        update.click()
        panel=driver.find_element(By.CSS_SELECTOR,"#updatePanel")
        w.until(lambda d:panel.is_displayed())
        w.until(lambda d:"2.47.500" in d.find_element(By.CSS_SELECTOR,"#updateCurrent").text)
        c=driver.find_element(By.CSS_SELECTOR,"#updateCurrent").text
        require("2.47.500" in c,"owner UI current version wrong")
        # Still-live channel is 499; the installed 500 must never offer a
        # duplicate Atomic install. The Owner may manually check after formal
        # distribution, but this synthetic pre-release browser does not.
        install=driver.find_element(By.CSS_SELECTOR,"#installUpdate")
        require(bool(driver.execute_script("return arguments[0].hidden || arguments[0].disabled",install)),
                "pre-release owner UI offers duplicate Atomic install")
        print("P01_247500_CHROME_OWNER_UPDATE_PANEL_500_AND_NO_STALE_INSTALL=PASS",flush=True)

        # Authenticated Owner POST without CSRF must not create an update
        # journal. A UI login alone does not authorize an unsafe write.
        result=driver.execute_async_script(
            'var cb=arguments[arguments.length-1];'
            'fetch("api.php?action=update_prepare",{method:"POST",'
            'headers:{"Content-Type":"application/json"},'
            'body:"{}",credentials:"same-origin"})'
            '.then(r=>cb({status:r.status})).catch(e=>cb({error:String(e)}));')
        require(result.get("status") in (400,401,403,419,422,429),
                "CSRF-less Owner update_prepare was accepted: "+str(result))
        print("P01_247500_AUTHENTICATED_OWNER_NO_CSRF_PREPARE_DENIED=PASS",flush=True)
    finally:
        if driver is not None:driver.quit()
        terminate(server)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--work",required=True)
    ap.add_argument("--source-full",required=True)
    ap.add_argument("--candidate-full",required=True)
    ap.add_argument("--candidate-update",required=True)
    args=ap.parse_args()
    work=Path(args.work).resolve()
    from importlib.util import module_from_spec,spec_from_file_location
    helper=Path(__file__).with_name("p01-v247500-formal-synthetic-helper.py")
    spec=spec_from_file_location("synthetic_p01",helper)
    t=module_from_spec(spec);spec.loader.exec_module(t)
    src=work/"source-extracted"
    tar=work/"target-extracted"
    upd=work/"update-extracted"
    for arc,dest in [(args.source_full,src),(args.candidate_full,tar),
                     (args.candidate_update,upd)]:
        t.unpack_bundle(Path(arc),dest)
    repair=upd/"repair-v2.47.500.php"
    require(repair.is_file(),"target Atomic missing")
    site=work/"focused-upgraded-site"
    shutil.copytree(src,site)
    t.synthetic_setup(site,18941)
    sent=t.sentinel(site,"Owner browser security synthetic private sentinel")
    done=run("php",str(repair),"--run="+str(site),cwd=site,timeout=120)
    d=json.loads(done.stdout)
    require(d["ok"] is True and (site/"VERSION.txt").read_text().strip()=="2.47.500",
            "cannot establish source upgraded fixture")
    t.check_sentinel(site,sent,"Owner browser security synthetic private sentinel")
    sql_check(locate_db(site))
    # Only the new tests below are evidence for this lane. Upgrade above is
    # prerequisite setup, not claimed as a new FULL/Atomic Gate.
    installed_reentry_and_guest_denials(site,18942)
    concurrent_worker_lock_and_recovery(site)
    owner_chromium_ui(site,18943)
    t.check_sentinel(site,sent,"Owner browser security synthetic private sentinel")
    sql_check(locate_db(site))
    print("P01_247500_PRIVATE_SQLITE_INTEGRITY_POST_BROWSER_NEGATIVES=PASS",flush=True)
    print("P01_247500_FOCUSED_NEGATIVE_AND_REAL_OWNER_BROWSER=PASS",flush=True)
    print("P01_247500_FORMAL_RELEASE=NOT_EXECUTED",flush=True)
    print("P01_247500_PRODUCTION=UNCHANGED",flush=True)

if __name__=="__main__":main()
