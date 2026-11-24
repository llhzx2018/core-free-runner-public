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
            # DO NOT CLICK or submit: capture only bounded boolean/enum
            # interaction evidence for a synthetic local CloudPanel form.
            phase = "TERMS_SNAPSHOT"
            summary = browser.execute_script(r"""
              const form = arguments[0];
              const checkboxes = Array.from(form.querySelectorAll('input[type=checkbox]'));
              const legal = text => /\b(terms|privacy|consent|agree|license|conditions)\b/i.test(text || '');
              const safeTag = e => {
                if (!e || !e.tagName) return 'none';
                const tag = e.tagName.toLowerCase();
                return ['input','label','span','div','svg','path','a','button','p'].includes(tag)
                    ? tag : 'other';
              };
              const visible = el => {
                if(!el) return false;
                const cs=getComputedStyle(el),rect=el.getBoundingClientRect();
                return cs.display!=='none'&&cs.visibility!=='hidden'&&
                    Number(cs.opacity)>0&&rect.width>0&&rect.height>0;
              };
              const center = el => {
                if(!el) return null;
                const r=el.getBoundingClientRect();
                if(r.width<1||r.height<1) return null;
                const x=Math.min(innerWidth-1,Math.max(0,r.left+r.width/2));
                const y=Math.min(innerHeight-1,Math.max(0,r.top+r.height/2));
                if(x<0||y<0||x>=innerWidth||y>=innerHeight) return null;
                return document.elementFromPoint(x,y);
              };
              const card = e => {
                const associated=Array.from(e.labels||[]);
                const parentLabel=e.closest('label');
                const marker=((e.name||'')+' '+(e.id||'')).toLowerCase();
                const relevant=e.required||legal(marker);
                const hit=center(e);
                const cs=getComputedStyle(e);
                const label=associated.find(visible)||parentLabel||associated[0]||null;
                const labelHit=center(label);
                return {
                  relevant:!!relevant,
                  required:!!e.required,checked:!!e.checked,disabled:!!e.disabled,
                  input_visible:visible(e),
                  input_nonzero_rect:!!(e.getBoundingClientRect().width>0&&e.getBoundingClientRect().height>0),
                  input_pointer_events_none:cs.pointerEvents==='none',
                  input_opacity_zero:Number(cs.opacity)===0,
                  input_display_none:cs.display==='none',
                  input_visibility_hidden:cs.visibility==='hidden',
                  input_center_hit_tag:safeTag(hit),
                  input_center_hit_self:hit===e,
                  input_center_hit_inside_label:associated.some(l=>hit&&(l===hit||l.contains(hit))),
                  associated_label_count:associated.length,
                  label_by_for:associated.some(l=>!!e.id&&l.htmlFor===e.id),
                  wrapping_label:!!parentLabel,
                  associated_label_visible:visible(label),
                  label_center_hit_tag:safeTag(labelHit),
                  label_center_hit_self:labelHit===label,
                  label_center_hit_descendant:!!(label&&labelHit&&label.contains(labelHit)),
                  label_legal_keyword:associated.some(l=>legal(l.textContent||'')),
                  label_has_link:associated.some(l=>!!l.querySelector('a')),
                  viewport_input_center_in_bounds:!!center(e),
                  viewport_label_center_in_bounds:!!center(label)
                };
              };
              return {
                checkbox_total:checkboxes.length,
                checkbox_summaries:checkboxes.slice(0,6).map(card),
                form_has_native_submit:!!form.querySelector('button[type=submit],input[type=submit],button:not([type])'),
                form_post:(form.method||'').toLowerCase()==='post',
                timezone_native_select_selected:!!form.querySelector('select[name=timezone] option:checked')
              };
            """,form)
            if not isinstance(summary,dict):
                die("TERMS_SNAPSHOT_RESULT_MISSING")
            if summary.get("checkbox_total",0) > 12:
                die("TERMS_SNAPSHOT_UNEXPECTED_CHECKBOX_COUNT")
            # Fixed keys and booleans/enumerated tags only; never raw HTML,
            # label strings, input names/values or exception messages.
            import json
            print("P07_D04_BROWSER_CHECKBOX_SNAPSHOT=" + json.dumps(summary,sort_keys=True,separators=(",",":")))
            print("P07_D04_BROWSER_READONLY_INSPECTION=PASS")
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
