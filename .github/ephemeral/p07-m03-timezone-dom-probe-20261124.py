#!/usr/bin/env python3
"""Synthetic CloudPanel CE 8443 first-run DOM read-only audit.

Only loops back to the one ephemeral Debian13 VM. No account creation, no
clicks, no secret, no private source, no screenshot or raw HTML in public output.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

BASE = "https://127.0.0.1:22443"
ALLOWED_LIBS = ("select2", "choices", "tom-select", "selectize", "jquery", "bootstrap")
FIELDS = ("username", "password", "email", "firstname", "lastname", "timezone", "role")
TIME_KEYS = ("time", "zone", "tz")
# All strings returned by browser JavaScript are first converted to fixed
# booleans, counts, supported keywords, or SHA256; never the DOM or values.

def emit(k: str, value: object) -> None:
    print(f"P07_DOM_{k}=" + json.dumps(value, separators=(",", ":"), sort_keys=True))

def fail(code: str) -> None:
    emit("READONLY_STATUS", code)
    raise SystemExit(42)

def main() -> None:
    exe = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    drv = shutil.which("chromedriver")
    if not exe or not drv:
        fail("CHROME_OR_DRIVER_NOT_PRESENT")
    with tempfile.TemporaryDirectory(prefix="p07-dom-onevm-") as profile:
        o = Options()
        o.binary_location = exe
        for option in ("--headless=new","--no-sandbox","--disable-dev-shm-usage",
                       "--disable-extensions","--disable-background-networking",
                       "--no-first-run","--ignore-certificate-errors",
                       "--allow-insecure-localhost"):
            o.add_argument(option)
        o.add_argument("--user-data-dir=" + profile)
        driver = None
        try:
            driver = webdriver.Chrome(
                service=Service(executable_path=drv, log_output="/dev/null"),
                options=o,
            )
            driver.set_page_load_timeout(35)
            driver.get(BASE + "/")
            if driver.current_url.split("/")[0:3] != BASE.split("/")[0:3]:
                fail("NON_LOOPBACK_NAVIGATION")
            data = driver.execute_script(r"""
            const forms=Array.from(document.forms);
            const norm=v=>String(v||'').toLowerCase();
            const kind=s=>{
              const z=norm(s).replace(/[^a-z0-9]/g,'');
              return ['username','email','password','firstname','lastname',
                      'timezone','role'].find(k=>z.includes(k)) || 'other';
            };
            const word=x=>/(time|zone|tz)/i.test(x||'');
            const seen=new Set();
            const out=[];
            const known=['select2','choices','tom-select','selectize','jquery','bootstrap'];
            function attributes(e) {
              const tokens=[
                  e.getAttribute('name'),e.id,e.getAttribute('aria-label'),
                  e.getAttribute('aria-labelledby'),e.getAttribute('placeholder'),
                  e.getAttribute('data-placeholder'),e.getAttribute('role')
              ].map(norm);
              const p=e.closest('label')?.textContent || '';
              const isTZ=tokens.some(word) || word(p) ||
                  (e.tagName==='SELECT' && Array.from(e.options).some(o=>word(o.textContent)));
              return {
                  e, isTZ, tokens, p
              };
            }
            const nodes=Array.from(document.querySelectorAll(
                'select,input,[role=combobox],.select2-container,.choices,.ts-wrapper,.selectize-control'));
            const all=nodes.map(attributes);
            const opts=a=>Array.from(a?.options||[]);
            const candidates=all.filter(a=>a.isTZ || a.e.matches('select,[role=combobox]'));
            for (const c of candidates.slice(0,32)) {
                const e=c.e, parent=e.parentElement, grand=parent?.parentElement;
                const classes=(x)=>known.filter(k=>norm(x?.className).includes(k));
                const values=opts(e);
                out.push({
                    tag:e.tagName.toLowerCase(),
                    id_kind:kind(e.id),
                    name_kind:kind(e.getAttribute('name')),
                    role: ['combobox','listbox','option','textbox'].includes(e.getAttribute('role')) ? e.getAttribute('role') : 'other',
                    input_type: ['text','hidden','search','password'].includes(e.getAttribute('type')) ? e.getAttribute('type') : 'other',
                    visible:!!(e.getClientRects().length),
                    disabled:!!e.disabled,
                    is_time_candidate:c.isTZ,
                    element_libs:classes(e),
                    parent_tag:parent?.tagName.toLowerCase()||'none',
                    parent_libs:classes(parent),
                    grand_libs:classes(grand),
                    native_option_count:values.length,
                    native_nonempty_value_count:values.filter(o=>o.value).length,
                    native_nonempty_label_count:values.filter(o=>o.textContent.trim()).length,
                    common_iana_options:values.filter(o=>/^(UTC|Etc\/UTC|Europe\/London|Asia\/Shanghai|America\/Los_Angeles)$/.test(o.value||o.textContent.trim())).length,
                    label_present:!!c.p.trim(),
                    aria_expanded:e.getAttribute('aria-expanded') === 'true',
                    autocomplete: e.getAttribute('autocomplete') === 'off' ? 'off':'other'
                });
            }
            const form_fields=forms.map(f=>({
                post:norm(f.method)==='post',
                recognized:Array.from(f.querySelectorAll('input[name]'))
                    .map(x=>kind(x.name)).filter(x=>x!=='other').sort(),
                input_total:f.querySelectorAll('input').length,
                select_total:f.querySelectorAll('select').length
            }));
            return {
                form_count:forms.length,
                form_fields:form_fields.slice(0,5),
                timezone_candidates:out,
                detected_libraries:known.filter(x=>
                    Array.from(document.querySelectorAll('script[src],link[href]')).some(e=>
                        norm(e.getAttribute('src')||e.getAttribute('href')).includes(x)) ||
                    Array.from(document.querySelectorAll('[class]')).some(e=>norm(e.className).includes(x))
                ),
                timezone_label_count:Array.from(document.querySelectorAll('label'))
                    .filter(e=>word(e.textContent)).length,
                timezone_text_nodes:Array.from(document.querySelectorAll('input,select,[role=combobox]'))
                    .filter(e=>word(e.name)||word(e.id)||word(e.getAttribute('aria-label'))).length,
                native_select_count:document.querySelectorAll('select').length
            };
            """)
            if not isinstance(data, dict):
                fail("DOM_SUMMARY_NOT_OBJECT")
            # Output contains only constrained metadata, never field values.
            emit("READONLY_FINGERPRINT", hashlib.sha256(
                json.dumps(data,sort_keys=True).encode()).hexdigest())
            for key in ("form_count","form_fields","timezone_candidates",
                        "detected_libraries","timezone_label_count",
                        "timezone_text_nodes","native_select_count"):
                emit(key.upper(),data.get(key))
            emit("READONLY_STATUS","PASS")
        except SystemExit:
            raise
        except Exception:
            fail("BROWSER_DOM_ACCESS_FAILED")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

if __name__ == "__main__":
    main()
