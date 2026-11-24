#!/usr/bin/env python3
"""Only synthetic P07 dual-VM CloudPanel first-run via host Chrome 8443."""
from __future__ import annotations
import argparse
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

def die(code: str) -> None:
    print("P07_D04_BROWSER_" + code, flush=True)
    raise SystemExit(1)

def kind(name: str) -> str:
    s = re.sub(r"[^a-z0-9]", "", name.lower())
    for tag in ("username", "firstname", "lastname", "timezone", "email", "password", "passwd", "role"):
        if tag in s:
            return "password" if tag == "passwd" else tag
    return "other"

def is_local(url: str, port: int) -> bool:
    u = urlsplit(url)
    return u.scheme == "https" and u.netloc == f"127.0.0.1:{port}"

def find_form(driver):
    for f in driver.find_elements(By.TAG_NAME, "form"):
        names = {kind(e.get_attribute("name") or "") for e in f.find_elements(By.CSS_SELECTOR, "input[name]")}
        if {"username", "email", "password"}.issubset(names):
            return f
    return None

def select_timezone(driver, form) -> bool:
    for e in form.find_elements(By.CSS_SELECTOR, "select[name]"):
        if kind(e.get_attribute("name") or "") != "timezone":
            continue
        choices = []
        for x in Select(e).options:
            value = (x.get_attribute("value") or x.text or "").strip()
            if (x.is_enabled()
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_+./:-]{0,79}", value)
                and value.lower() not in ("select", "choose", "timezone", "none")):
                choices.append((value, x))
        preferred = ("UTC", "Etc/UTC", "Europe/London", "Europe/Berlin", "Asia/Shanghai")
        item = next(((v, x) for v, x in choices if v in preferred), choices[0] if choices else None)
        if item is None:
            continue
        value, option = item
        if e.is_displayed():
            option.click()
        else:
            driver.execute_script(
                "arguments[0].value=arguments[1];"
                "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                e, value,
            )
        return True
    for e in form.find_elements(By.CSS_SELECTOR, "input[name]"):
        if kind(e.get_attribute("name") or "") == "timezone" and e.is_displayed():
            e.clear()
            e.send_keys("UTC")
            return True
    for trigger in form.find_elements(By.CSS_SELECTOR, ".select2-selection,[role='combobox']"):
        if not trigger.is_displayed():
            continue
        trigger.click()
        for option in driver.find_elements(By.CSS_SELECTOR, ".select2-results__option,[role='option']"):
            label = (option.text or "").strip()
            if (re.search(r"[A-Za-z]+/[A-Za-z_]+", label)
                and option.is_displayed() and option.is_enabled()):
                option.click()
                return True
    return False

def create(port: int) -> None:
    if port not in (22443, 22444):
        die("PORT_NOT_ALLOWED")
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    driver_path = shutil.which("chromedriver")
    if not chrome or not driver_path:
        die("HOST_CHROME_DRIVER_MISSING")
    with tempfile.TemporaryDirectory(prefix="p07-browser-") as profile:
        options = Options()
        options.binary_location = chrome
        for flag in (
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--ignore-certificate-errors",
            "--allow-insecure-localhost",
            "--no-first-run",
            "--disable-extensions",
        ):
            options.add_argument(flag)
        options.add_argument("--user-data-dir=" + profile)
        browser = None
        try:
            browser = webdriver.Chrome(
                service=Service(executable_path=driver_path, log_output=subprocess.DEVNULL),
                options=options,
            )
            browser.set_page_load_timeout(35)
            browser.get(f"https://127.0.0.1:{port}/")
            if not is_local(browser.current_url, port):
                die("NONLOCAL_NAVIGATION_REJECTED")
            form = WebDriverWait(browser, 20).until(lambda d: find_form(d))
            if form is None:
                die("FIRST_ADMIN_FORM_NOT_FOUND")
            if not is_local(form.get_attribute("action") or browser.current_url, port):
                die("NONLOCAL_FORM_ACTION_REJECTED")
            password = secrets.token_urlsafe(36)
            for e in form.find_elements(By.CSS_SELECTOR, "input[name]"):
                tag = kind(e.get_attribute("name") or "")
                value = {
                    "username": "p07-ci-admin",
                    "email": "p07-ci-admin@example.invalid",
                    "firstname": "Synthetic",
                    "lastname": "Admin",
                    "password": password,
                }.get(tag)
                if value is not None:
                    if not e.is_displayed() or not e.is_enabled():
                        die("REQUIRED_INPUT_NOT_INTERACTIVE")
                    e.clear()
                    e.send_keys(value)
            if not select_timezone(browser, form):
                die("TIMEZONE_BROWSER_SELECTION_UNSUPPORTED")
            for e in form.find_elements(By.CSS_SELECTOR, "select[name]"):
                if kind(e.get_attribute("name") or "") == "role":
                    s = Select(e)
                    allowed = [o.get_attribute("value") for o in s.options
                               if (o.get_attribute("value") or "").lower() == "admin"]
                    if not allowed:
                        die("ADMIN_ROLE_UNVERIFIED")
                    s.select_by_value(allowed[0])
            buttons = form.find_elements(
                By.CSS_SELECTOR,
                "button[type='submit'],input[type='submit'],button:not([type])",
            )
            button = next((b for b in buttons if b.is_displayed() and b.is_enabled()), None)
            if button is None:
                die("CREATE_USER_SUBMIT_MISSING")
            button.click()
            time.sleep(3)
            if not is_local(browser.current_url, port):
                die("NONLOCAL_REDIRECT_REJECTED")
            # Click is not proof of creation. Guest SQLite + database_server gate follows.
            print("P07_D04_BROWSER_FIRST_RUN_CLICKED=YES")
        except SystemExit:
            raise
        except Exception:
            die("FIRST_RUN_UI_INTERACTION_FAILED")
        finally:
            if browser is not None:
                try:
                    browser.quit()
                except Exception:
                    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int, choices=[22443, 22444])
    args = parser.parse_args()
    create(args.port)
