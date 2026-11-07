#!/usr/bin/env python3
"""P01 v2.47.501 test-only official 500->candidate maintenance Atomic and real Chromium UX.
All installed SQLite, credentials and state are disposable local synthetic data.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

PASSWORD="SyntheticOnly!Passw0rd"

def require(ok,msg):
    if not ok: raise AssertionError(msg)

def run(*args,cwd=None,expect=0,env=None,timeout=140):
    p=subprocess.run(args,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,timeout=timeout)
    if expect is not None:
        require(p.returncode==expect,"COMMAND_EXIT="+str(p.returncode)+": "+p.stderr[-500:])
    return p

def load_helper():
    p=Path(__file__).with_name("p01-v247501-synthetic-helper-temp.py")
    spec=importlib.util.spec_from_file_location("p01_synthetic_501",p)
    require(spec is not None and spec.loader is not None,"synthetic helper missing")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def start_server(root,port):
    p=subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(root)],
        cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f"http://127.0.0.1:{port}"
    for _ in range(65):
        try:
            with urllib.request.urlopen(url+"/VERSION.txt",timeout=1) as r:
                if r.status==200:return p,url
        except Exception: time.sleep(.12)
    p.terminate();p.wait(timeout=5)
    raise AssertionError("PHP test origin failed startup")

def stop(p):
    p.terminate()
    try:p.wait(timeout=6)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)

def browser_options():
    from selenium.webdriver.chrome.options import Options
    opts=Options()
    binary=shutil.which("google-chrome") or shutil.which("chromium")
    require(binary,"Chromium unavailable on runner")
    opts.binary_location=binary
    for flag in ("--headless=new","--no-sandbox","--disable-dev-shm-usage",
                 "--window-size=1440,900"):
        opts.add_argument(flag)
    return opts

def chrome_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    require(shutil.which("chromedriver"),"Chromedriver absent")
    driver=webdriver.Chrome(service=Service(shutil.which("chromedriver")),
                            options=browser_options())
    driver.set_page_load_timeout(25)
    driver.set_script_timeout(12)
    return driver

def login_owner(driver,url):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    w=WebDriverWait(driver,18)
    driver.get(url+"/")
    w.until(lambda d:bool(d.find_elements(By.CSS_SELECTOR,"[data-vf-auth-login]")))
    driver.find_element(By.CSS_SELECTOR,"[data-vf-auth-login]").click()
    w.until(lambda d:bool(d.find_elements(By.CSS_SELECTOR,
                                         "[data-vf-auth-dialog] input[name=password]")))
    driver.find_element(By.CSS_SELECTOR,
                        "[data-vf-auth-dialog] input[name=password]").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR,
                        "[data-vf-auth-dialog] [data-vf-auth-submit]").click()
    w.until(lambda d:bool(d.find_elements(By.CSS_SELECTOR,"[data-vf-global-manage-open]")))
    return w

def first_full_chromium(root,port,helper):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    server,url=start_server(root,port)
    driver=None
    try:
        driver=chrome_driver()
        driver.get(url+"/")
        w=WebDriverWait(driver,20)
        w.until(lambda d:bool(d.find_elements(By.CSS_SELECTOR,'input[name="setup_csrf"]')))
        require("/setup.php" in driver.current_url,"first browser did not reach setup")
        driver.find_element(By.CSS_SELECTOR,'input[name="admin_password"]').send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR,'input[name="admin_password_confirm"]').send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR,'form button[type=submit]').click()
        w.until(lambda d:"VF Start 安装完成" in d.page_source)
        driver.find_element(By.CSS_SELECTOR,'a[href="/"]').click()
        login_owner(driver,url)
        driver.get(url+"/setup.php")
        w.until(lambda d:"/setup.php" not in d.current_url)
        verify=run("php",str(root/"cli/verify.php"),cwd=root,timeout=40)
        require("VERIFY_PASS=YES" in verify.stdout,"clean FULL first install verify failed")
        print("P01_247501_FULL_REAL_CHROMIUM_FIRST_SETUP_OWNER_LOGIN_REVISIT=PASS",flush=True)
    finally:
        if driver is not None:driver.quit()
        stop(server)

def owner_chromium_ui(site,port):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    server,url=start_server(site,port)
    driver=None
    try:
        driver=chrome_driver()
        w=login_owner(driver,url)
        driver.find_element(By.CSS_SELECTOR,"[data-vf-global-manage-open]").click()
        w.until(lambda d:d.find_element(By.CSS_SELECTOR,"#vf-local-management").get_attribute("open") is not None)
        auth=driver.find_element(By.CSS_SELECTOR,"[data-vf-frontstage-reauth-root]")
        require(driver.execute_script("return arguments[0].hidden;",auth),
                "password rail occupies ordinary management dialog")
        driver.find_element(By.CSS_SELECTOR,'[data-vf-management-tab="global"]').click()
        require(driver.execute_script("return arguments[0].hidden;",auth),
                "global tab unexpectedly exposes password step-up")
        print("P01_247501_OWNER_BROWSER_ALL_TABS_DORMANT_STEPUP=PASS",flush=True)

        # A simulated existing server 428 challenge shows same inline step-up,
        # never executes a risky action, and returns to the current task.
        result=driver.execute_script(
            "window.__reAuthPosts=0;"
            "const orig=window.fetch.bind(window);"
            "window.fetch=(u,o)=>{if(String(u).includes('reauth.php'))window.__reAuthPosts++;"
            "return orig(u,o);};"
            "window.VFFrontstageReauth.show();"
            "return {hidden:document.querySelector('[data-vf-frontstage-reauth-root]').hidden,"
            "open:document.querySelector('[data-vf-frontstage-reauth-root]').open};")
        require(result=={"hidden":False,"open":True},"step-up not shown upon explicit challenge")
        driver.find_element(By.CSS_SELECTOR,"[data-vf-frontstage-reauth-dismiss]").click()
        require(driver.execute_script(
            "return document.querySelector('[data-vf-frontstage-reauth-root]').hidden&&window.__reAuthPosts===0;"),
            "return from step-up either leaked prompt or sent unexpected auth POST")
        print("P01_247501_OWNER_BROWSER_STEPUP_428_SHOW_SAFE_RETURN_NO_AUTO_POST=PASS",flush=True)

        # Observe real fetch calls. Entering the Channels tab must NOT load its
        # inventory. Only an explicit click may do so.
        driver.execute_script(
            "window.__channelReads=0;const prev=window.fetch.bind(window);"
            "window.fetch=(u,o)=>{const s=String(u);"
            "if(s.includes('action=resource_inventory')&&s.includes('surface=channels'))"
            "window.__channelReads++;return prev(u,o);};")
        driver.find_element(By.CSS_SELECTOR,'[data-vf-management-tab="channels"]').click()
        channel=driver.find_element(By.CSS_SELECTOR,"[data-vf-remote-channels-root]")
        w.until(lambda d:channel.is_displayed())
        require(driver.execute_script("return window.__channelReads;")==0,
                "Channels task auto-read on tab entry")
        require(driver.execute_script("return arguments[0].hidden;",auth),
                "channel management still shows permanent password rail")
        button=driver.find_element(By.CSS_SELECTOR,"[data-vf-remote-channels-load]")
        require(button.is_displayed() and button.is_enabled(),
                "manual channel read not available")
        print("P01_247501_OWNER_BROWSER_CHANNEL_TAB_ZERO_AUTO_FETCH=PASS",flush=True)

        button.click()
        w.until(lambda d:d.execute_script("return window.__channelReads;")==1)
        feedback=driver.find_element(By.CSS_SELECTOR,"[data-vf-remote-channels-feedback]")
        w.until(lambda d:"清单已读取" in feedback.text or "读取失败" in feedback.text)
        require("清单已读取" in feedback.text,"real manual resource_inventory read failed: "+feedback.text[:150])
        print("P01_247501_OWNER_BROWSER_CHANNEL_EXPLICIT_SINGLE_INVENTORY_GET=PASS",flush=True)

        # A hung GET may never trap the Owner. We deliberately mock only
        # the read-only inventory request, then safely abort via requestDismiss.
        driver.execute_script(
            "const real=window.fetch.bind(window);"
            "window.fetch=(u,o)=>{const s=String(u);"
            "if(s.includes('action=resource_inventory')&&s.includes('surface=channels'))"
            "return new Promise((_resolve,reject)=>{"
            "o?.signal?.addEventListener('abort',()=>reject(new Error('aborted')));});"
            "return real(u,o);};")
        driver.find_element(By.CSS_SELECTOR,"[data-vf-remote-channels-reload]").click()
        w.until(lambda d:not d.find_element(By.CSS_SELECTOR,"[data-vf-remote-channels-reload]").is_enabled())
        allowed=driver.execute_script(
            "const ok=window.VFRemoteChannelsManagement.requestDismiss();"
            "window.VFRemoteChannelsManagement.hide();"
            "return {ok,hidden:document.querySelector('[data-vf-remote-channels-root]').hidden};")
        require(allowed=={"ok":True,"hidden":True},"hung read cannot safely dismiss")
        print("P01_247501_OWNER_BROWSER_HUNG_INVENTORY_ABORTS_NO_TRAP=PASS",flush=True)
    finally:
        if driver is not None:driver.quit()
        stop(server)

def atomic_and_rollback(work,source,full,update,helper):
    with zipfile.ZipFile(update) as z:
        require(z.namelist()==["repair-v2.47.501.php"],"Atomic not a single repair")
        repair=work/"repair-v2.47.501.php"
        repair.write_bytes(z.read(z.namelist()[0]))
    lint=run("php","-l",str(repair))
    test=run("php",str(repair),"--self-test")
    require(json.loads(test.stdout)["ok"] is True,"Atomic self-test mismatch")
    u=work/"installed-500-upgrade"
    shutil.copytree(source,u)
    helper.synthetic_setup(u,19501)
    sid=helper.sentinel(u,"V501 synthetic private persisted")
    result=json.loads(run("php",str(repair),"--run="+str(u),cwd=u).stdout)
    require(result.get("ok") is True and (u/"VERSION.txt").read_text().strip()=="2.47.501",
            "actual official500->candidate501 Atomic not successful")
    helper.check_sentinel(u,sid,"V501 synthetic private persisted")
    again=json.loads(run("php",str(repair),"--run="+str(u),cwd=u).stdout)
    require(again.get("ok") is True and again.get("already_current") is True,
            "second Atomic should be safely idempotent")
    print("P01_247501_ATOMIC_500_501_PRIVATE_DATA_AND_IDEMPOTENCE=PASS",flush=True)

    failedsite=work/"rollback-500"
    shutil.copytree(source,failedsite)
    helper.synthetic_setup(failedsite,19502)
    fid=helper.sentinel(failedsite,"V501 rollback private persisted")
    env=os.environ.copy();env["VF_ATOMIC_TEST_FAIL_AFTER_APPLY"]="1"
    failed=run("php",str(repair),"--run="+str(failedsite),
               cwd=failedsite,env=env,expect=None,timeout=145)
    require(failed.returncode!=0,"rollback fault unexpectedly successful")
    require((failedsite/"VERSION.txt").read_text().strip()=="2.47.500",
            "rollback must restore exactly official500")
    helper.check_sentinel(failedsite,fid,"V501 rollback private persisted")
    check=run("php",str(failedsite/"cli/verify.php"),cwd=failedsite)
    require("VERIFY_PASS=YES" in check.stdout,"rollback SQLite integrity unavailable")
    print("P01_247501_FAULT_INJECTION_ROLLBACK_500_SQLITE_PRESERVED=PASS",flush=True)

    interrupted=work/"interrupted-500"
    shutil.copytree(source,interrupted)
    helper.synthetic_setup(interrupted,19503)
    iid=helper.sentinel(interrupted,"V501 hard exit private persisted")
    env=os.environ.copy();env["VF_ATOMIC_TEST_HARD_EXIT_AFTER_APPLY"]="1"
    aborted=run("php",str(repair),"--run="+str(interrupted),cwd=interrupted,
                env=env,expect=None,timeout=145)
    require(aborted.returncode!=0,"simulated abrupt exit did not interrupt")
    resumed=json.loads(run("php",str(repair),"--run="+str(interrupted),
                           cwd=interrupted,timeout=145).stdout)
    require(resumed.get("ok") is True and (interrupted/"VERSION.txt").read_text().strip()=="2.47.501",
            "hard interruption recovery did not finish")
    helper.check_sentinel(interrupted,iid,"V501 hard exit private persisted")
    check=run("php",str(interrupted/"cli/verify.php"),cwd=interrupted)
    require("VERIFY_PASS=YES" in check.stdout,"recovered database not verified")
    print("P01_247501_HARD_EXIT_RECOVERY_REAPPLY_SQLITE_PRESERVED=PASS",flush=True)
    return u

def main():
    ap=argparse.ArgumentParser()
    for x in ("work","source-full","candidate-full","candidate-update"):ap.add_argument("--"+x,required=True)
    a=ap.parse_args()
    helper=load_helper()
    wk=Path(a.work).resolve()
    source=wk/"official500";candidate=wk/"clean501"
    helper.unpack_bundle(Path(a.source_full),source)
    helper.unpack_bundle(Path(a.candidate_full),candidate)
    require((source/"VERSION.txt").read_text().strip()=="2.47.500","official source identity absent")
    require((candidate/"VERSION.txt").read_text().strip()=="2.47.501","target identity mismatch")
    require(b"define('VF_VERSION', '2.47.501');" in (candidate/"app/bootstrap.php").read_bytes(),
            "candidate bootstrap identity drift")
    manifest=json.loads((candidate/"release-manifest.json").read_text())
    require(manifest["version"]=="2.47.501" and manifest["source_version"]=="2.47.500"
            and manifest["schema_version"]=="2026102201"
            and manifest["maintenance_release"]["updater_mechanism_unchanged"] is True,
            "candidate not same-schema maintenance formal package")
    for p in candidate.rglob("*"):
        if p.is_file():require(not p.name.endswith((".sqlite",".db",".log",".env")),
                               "private file in candidate")
    print("P01_247501_CANDIDATE_ASSET_NO_SCHEMA_NO_PRIVATE_DATA=PASS",flush=True)
    first_full_chromium(candidate,19504,helper)
    upgraded=atomic_and_rollback(wk,source,candidate,Path(a.candidate_update),helper)
    owner_chromium_ui(upgraded,19505)
    check=run("php",str(upgraded/"cli/verify.php"),cwd=upgraded)
    require("VERIFY_PASS=YES" in check.stdout,"post browser installed SQLite corrupt")
    print("P01_247501_CANDIDATE_FULL_ATOMIC_BROWSER_RECOVERY_COMPLETE=PASS",flush=True)
    print("P01_247501_RELEASE=NOT_EXECUTED",flush=True)
    print("P01_247501_PRODUCTION=UNCHANGED",flush=True)

if __name__=="__main__":main()
