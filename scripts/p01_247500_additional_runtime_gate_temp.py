#!/usr/bin/env python3
"""P01 #1935: focused extra gates against transient exact V2.47.500 candidate.
Run only inside the registered Public Runner's disposable, synthetic workspace.
Not a published preview, not an official release, not a Production read.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import select
import shutil
import subprocess
import time
import urllib.request

def check(ok, message):
    if not ok:
        raise AssertionError(message)

def run_worker(site):
    start=time.monotonic()
    p=subprocess.run(["php",str(site/"cli/worker.php")],cwd=site,text=True,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    return p,time.monotonic()-start

def check_worker_barrier(site):
    check((site/"VERSION.txt").read_text().strip()=="2.47.500","wrong installed target")
    hold_code=(
        'require $argv[1]."/app/bootstrap.php";'
        '$lease=VfMaintenanceBarrier::globalExclusive();'
        'echo "HELD\\n";fflush(STDOUT);sleep(7);'
    )
    holder=subprocess.Popen(["php","-r",hold_code,str(site)],cwd=site,text=True,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    try:
        ready,_,_=select.select([holder.stdout],[],[],4)
        check(bool(ready) and holder.stdout.readline().strip()=="HELD",
              "cannot prove global EX holder acquired the lock")
        blocked,seconds=run_worker(site)
        check(blocked.returncode!=0,"worker unexpectedly crossed global exclusive lock")
        check(seconds<4.5,"worker stalled under global EX instead of bounded failure")
        check("维护锁" in (blocked.stderr+blocked.stdout),
              "worker lock denial has no maintenance error classification")
        print("P01_247500_REAL_CLI_WORKER_GLOBAL_EX_BOUNDED_DENY=PASS",flush=True)
    finally:
        holder.terminate()
        try: holder.communicate(timeout=5)
        except subprocess.TimeoutExpired: holder.kill();holder.communicate(timeout=5)
    accepted,seconds=run_worker(site)
    check(accepted.returncode==0 and "WORKER_HANDLED=" in accepted.stdout,
          "worker did not resume safely after global EX was released")
    check(seconds<8,"worker remained starved after EX release")
    print("P01_247500_REAL_CLI_WORKER_POST_LOCK_RECOVERY=PASS",flush=True)

def check_browser(site,port):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait

    browser=shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    check(browser is not None,"BROWSER_INFRA_NO_CHROME")
    driver_path=shutil.which("chromedriver")
    check(driver_path is not None,"BROWSER_INFRA_NO_CHROMEDRIVER")
    base=f"http://127.0.0.1:{port}"
    server=subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(site)],cwd=site,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    driver=None
    try:
        up=False
        for _ in range(70):
            try:
                with urllib.request.urlopen(base+"/VERSION.txt",timeout=1) as result:
                    up=(result.read().decode().strip()=="2.47.500")
                if up:break
            except Exception:time.sleep(0.1)
        check(up,"test-only PHP HTTP origin did not start")
        options=Options()
        options.binary_location=browser
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1440,900")
        driver=webdriver.Chrome(service=Service(driver_path),options=options)
        driver.set_page_load_timeout(20)
        driver.get(base+"/")
        WebDriverWait(driver,12).until(lambda d: "常用资源" in d.page_source)
        check(driver.find_elements(By.CSS_SELECTOR,"[data-vf-auth-login]"),
              "guest Owner login entry is missing")
        check("2.47.500"==urllib.request.urlopen(base+"/VERSION.txt",timeout=2).read().decode().strip(),
              "browser site identity drifted")
        print("P01_247500_POST_ATOMIC_CHROME_GUEST_HOME=PASS",flush=True)
        driver.find_element(By.CSS_SELECTOR,"[data-vf-auth-login]").click()
        WebDriverWait(driver,10).until(
            lambda d:any(x.is_displayed() for x in d.find_elements(By.CSS_SELECTOR,"input[type=password]"))
        )
        print("P01_247500_POST_ATOMIC_CHROME_LOGIN_DIALOG=PASS",flush=True)
    finally:
        if driver is not None: driver.quit()
        server.terminate()
        try:server.wait(timeout=4)
        except subprocess.TimeoutExpired:server.kill();server.wait(timeout=4)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--work",required=True)
    args=ap.parse_args()
    work=Path(args.work).resolve()
    site=work/"atomic-success"
    check((site/"cli/worker.php").is_file(),"candidate asset suite must run first")
    check_worker_barrier(site)
    check_browser(site,18921)
    print("P01_247500_FOCUSED_NEW_MACHINE_GATES=PASS",flush=True)
    print("P01_247500_HOSTED_OWNER_PREVIEW=NOT_PROVEN",flush=True)
    print("P01_247500_PRODUCTION_READONLY_INTEGRITY=NOT_PROVEN",flush=True)

if __name__=="__main__":main()
