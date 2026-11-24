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
from selenium.common.exceptions import NoSuchElementException
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
    """Use the real native dropdown, not guessed IANA option syntax.

    Actual first-run CloudPanel DOM proof: one visible <select name=timezone>
    with 419 enabled-looking options and 419 nonempty option values.
    The app's option values are authoritative for this synthetic test.
    """
    fields = [
        e for e in form.find_elements(By.CSS_SELECTOR, "select[name]")
        if kind(e.get_attribute("name") or "") == "timezone"
    ]
    if len(fields) != 1:
        die("TIMEZONE_NATIVE_SELECT_AMBIGUOUS")
    field = fields[0]
    if not field.is_displayed() or not field.is_enabled():
        die("TIMEZONE_NATIVE_SELECT_NOT_INTERACTIVE")
    selector = Select(field)
    options = selector.options
    if not 3 <= len(options) <= 800:
        die("TIMEZONE_NATIVE_OPTION_COUNT_UNEXPECTED")
    try:
        current = (selector.first_selected_option.get_attribute("value") or "").strip()
    except NoSuchElementException:
        current = ""
    for i, option in enumerate(options):
        value = (option.get_attribute("value") or "").strip()
        if (not option.is_enabled() or not value or
            value == current or len(value) > 120 or
            value.lower() in ("choose", "select", "timezone", "none", "null")):
            continue
        selector.select_by_index(i)
        if (Select(field).first_selected_option.get_attribute("value") or "").strip() != value:
            die("TIMEZONE_NATIVE_SELECTION_NOT_CONFIRMED")
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
        phase = "BROWSER_CREATE"
        try:
            browser = webdriver.Chrome(
                service=Service(executable_path=driver_path, log_output=subprocess.DEVNULL),
                options=options,
            )
            phase = "BROWSER_SETUP"
            browser.set_page_load_timeout(35)
            phase = "PAGE_LOAD"
            browser.get(f"https://127.0.0.1:{port}/")
            if not is_local(browser.current_url, port):
                die("NONLOCAL_NAVIGATION_REJECTED")
            phase = "FORM_DISCOVERY"
            form = WebDriverWait(browser, 20).until(lambda d: find_form(d))
            if form is None:
                die("FIRST_ADMIN_FORM_NOT_FOUND")
            if not is_local(form.get_attribute("action") or browser.current_url, port):
                die("NONLOCAL_FORM_ACTION_REJECTED")
            phase = "FILL_FIELDS"
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
            phase = "TIMEZONE_SELECT"
            if not select_timezone(browser, form):
                die("TIMEZONE_BROWSER_SELECTION_UNSUPPORTED")
            # A timezone onchange handler may refresh the form, invalidating
            # Selenium element handles; re-acquire without losing browser state.
            phase = "TERMS_REACQUIRE_FORM"
            form = WebDriverWait(browser, 10).until(lambda d: find_form(d))
            # Only a required, form-local synthetic account checkbox is eligible.
            # Never print its label/name/value or blindly click a consent widget.
            phase = "TERMS_DISCOVER"
            boxes = form.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            phase = "TERMS_INSPECT"
            legal = []
            for c in boxes:
                marker = ((c.get_attribute("name") or "") + " " +
                          (c.get_attribute("id") or "")).lower()
                if c.get_attribute("required") is not None or any(
                        word in marker for word in ("terms", "privacy", "license", "agree")):
                    legal.append(c)
            phase = "TERMS_EVALUATE"
            if len(legal) > 1:
                die("FIRST_RUN_TERMS_CHECKBOX_AMBIGUOUS")
            for c in legal:
                phase = "TERMS_INTERACTABLE"
                if not c.is_displayed() or not c.is_enabled():
                    die("FIRST_RUN_TERMS_CHECKBOX_NOT_INTERACTIVE")
                phase = "TERMS_CLICK"
                if not c.is_selected():
                    c.click()
                phase = "TERMS_VERIFY"
                if not c.is_selected():
                    die("FIRST_RUN_TERMS_CHECKBOX_NOT_SELECTED")
            phase = "ROLE_SELECTION"
            for e in form.find_elements(By.CSS_SELECTOR, "select[name]"):
                if kind(e.get_attribute("name") or "") == "role":
                    s = Select(e)
                    allowed = [o.get_attribute("value") for o in s.options
                               if (o.get_attribute("value") or "").lower() == "admin"]
                    if not allowed:
                        die("ADMIN_ROLE_UNVERIFIED")
                    s.select_by_value(allowed[0])
            phase = "SUBMIT_BUTTON_DISCOVERY"
            buttons = form.find_elements(
                By.CSS_SELECTOR,
                "button[type='submit'],input[type='submit'],button:not([type])",
            )
            button = next((b for b in buttons if b.is_displayed() and b.is_enabled()), None)
            if button is None:
                die("CREATE_USER_SUBMIT_MISSING")
            phase = "SUBMIT_CLICK"
            button.click()
            phase = "POST_SUBMIT"
            time.sleep(3)
            if not is_local(browser.current_url, port):
                die("NONLOCAL_REDIRECT_REJECTED")
            # Click is not proof of creation. Guest SQLite + database_server gate follows.
            print("P07_D04_BROWSER_FIRST_RUN_CLICKED=YES")
        except SystemExit:
            raise
        except Exception:
            # Fixed, branch-owned phase only. Never print Selenium tracebacks,
            # private HTML, form values or exception messages to public logs.
            die("FIRST_RUN_" + phase + "_UNHANDLED")
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
