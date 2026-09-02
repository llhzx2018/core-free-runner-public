#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get('P05_BASE_URL', 'http://127.0.0.1:18189').rstrip('/')
DRIVER_PORT = int(os.environ.get('P05_DRIVER_PORT', '9516'))
USERNAME = os.environ.get('P05_BROWSER_USERNAME', 'phase3-owner')
PASSWORD = os.environ.get('P05_BROWSER_PASSWORD', 'Phase3BrowserPass-2026!')
EXPECTED_SITE_VIEWS = ['概览', '机会', '搜索表现', '关键词', '页面', '网站检查', 'AI / AEO', '变更', '数据源', '设置']


def fail(message: str) -> None:
    print(f'P05_PHASE3_BROWSER_JOURNEY=FAIL {message}', file=sys.stderr)
    raise SystemExit(1)


def http_json(method: str, url: str, payload=None, timeout: float = 20):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        raw = error.read().decode(errors='replace')
        fail(f'webdriver http {error.code}: {raw[:500]}')
    return json.loads(raw) if raw else {}


def wait_http(url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.2)
    fail(f'server did not become ready: {url}')


def wd(method: str, path: str, payload=None):
    response = http_json(method, f'http://127.0.0.1:{DRIVER_PORT}{path}', payload)
    value = response.get('value')
    if isinstance(value, dict) and value.get('error'):
        fail(f"webdriver {value.get('error')}: {value.get('message')}")
    return response


def session_value(session: str, method: str, path: str, payload=None):
    return wd(method, f'/session/{session}{path}', payload).get('value')


def element_id(value) -> str:
    if not isinstance(value, dict):
        fail(f'element response invalid: {value!r}')
    key = 'element-6066-11e4-a52e-4f735466cecf'
    if key not in value:
        fail(f'element id missing: {value!r}')
    return str(value[key])


def find(session: str, using: str, value: str) -> str:
    return element_id(session_value(session, 'POST', '/element', {'using': using, 'value': value}))


def find_all(session: str, using: str, value: str):
    rows = session_value(session, 'POST', '/elements', {'using': using, 'value': value}) or []
    return [element_id(row) for row in rows]


def text(session: str, element: str) -> str:
    return str(session_value(session, 'GET', f'/element/{element}/text') or '')


def body_text(session: str) -> str:
    return text(session, find(session, 'css selector', 'body'))


def click(session: str, element: str) -> None:
    session_value(session, 'POST', f'/element/{element}/click', {})


def send_keys(session: str, element: str, value: str) -> None:
    session_value(session, 'POST', f'/element/{element}/value', {'text': value, 'value': list(value)})


def execute(session: str, script: str):
    return session_value(session, 'POST', '/execute/sync', {'script': script, 'args': []})


def wait_until(label: str, callback, timeout: float = 20):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = callback()
            if last:
                return last
        except Exception as error:
            last = repr(error)
        time.sleep(0.2)
    fail(f'timeout waiting for {label}: {last!r}')


def button_with_text(session: str, label: str, scope: str = '') -> str:
    root = scope if scope else ''
    xpath = f"{root}//button[normalize-space(.)={json.dumps(label)}]" if root else f"//button[normalize-space(.)={json.dumps(label)}]"
    return find(session, 'xpath', xpath)


def button_contains(session: str, label: str, scope: str = '') -> str:
    root = scope if scope else ''
    xpath = f"{root}//button[contains(normalize-space(.), {json.dumps(label)})]" if root else f"//button[contains(normalize-space(.), {json.dumps(label)})]"
    return find(session, 'xpath', xpath)


def assert_no_overflow(session: str, label: str) -> None:
    value = execute(session, "return {w:window.innerWidth,doc:document.documentElement.scrollWidth,body:document.body.scrollWidth};")
    width = int(value.get('w', 0))
    scroll = max(int(value.get('doc', 0)), int(value.get('body', 0)))
    if scroll > width + 1:
        fail(f'{label} horizontal overflow viewport={width} scroll={scroll}')


def assert_absent_text(session: str, labels) -> None:
    page = body_text(session)
    for label in labels:
        if label in page:
            fail(f'forbidden owner-visible term present: {label}')


def main() -> None:
    chrome = shutil.which('google-chrome') or shutil.which('google-chrome-stable')
    driver = shutil.which('chromedriver')
    if not chrome or not driver:
        fail('Google Chrome / ChromeDriver unavailable')

    wait_http(f'{BASE}/api/health')
    driver_log = open('/tmp/p05-phase3-chromedriver.log', 'wb')
    proc = subprocess.Popen([driver, f'--port={DRIVER_PORT}', '--allowed-ips=127.0.0.1'], stdout=driver_log, stderr=subprocess.STDOUT)
    session = None
    try:
        wait_http(f'http://127.0.0.1:{DRIVER_PORT}/status')
        response = wd('POST', '/session', {'capabilities': {'alwaysMatch': {'browserName': 'chrome', 'goog:chromeOptions': {'binary': chrome, 'args': ['--headless=new', '--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--window-size=1440,1000']}}}})
        value = response.get('value') or {}
        session = str(value.get('sessionId') or response.get('sessionId') or '')
        if not session:
            fail('webdriver session missing')
        session_value(session, 'POST', '/window/rect', {'width': 1440, 'height': 1000, 'x': 0, 'y': 0})
        session_value(session, 'POST', '/url', {'url': BASE + '/'})

        wait_until('Product login', lambda: '使用现有管理员账户登录' in body_text(session))
        username = find(session, 'css selector', '.p05v2-login input[autocomplete="username"]')
        password = find(session, 'css selector', '.p05v2-login input[autocomplete="current-password"]')
        send_keys(session, username, USERNAME)
        send_keys(session, password, PASSWORD)
        click(session, button_with_text(session, '登录'))
        wait_until('Site Portfolio', lambda: 'Site Portfolio' in body_text(session) and '今天先看谁' in body_text(session) or 'Portfolio 还没有网站' in body_text(session))

        load_button = wait_until('Demo load action', lambda: button_contains(session, '载入 Demo Dataset'))
        click(session, load_button)
        wait_until('P05_DEMO_V1 sites', lambda: 'Kewaro Tools' in body_text(session) and 'Kewaro Start' in body_text(session) and 'WordPress Lab' in body_text(session), 30)
        if len(find_all(session, 'css selector', '.p05v2-portfolio-list article')) < 5:
            fail('Demo Portfolio did not render five websites')
        assert_absent_text(session, ['Product Optimization', 'Product Workspace', '唯一正式工作区', 'Product Site Authority', '新版工作区 Preview', '返回经典工作区'])
        assert_no_overflow(session, 'portfolio-desktop')

        nav_labels = [text(session, el).strip() for el in find_all(session, 'css selector', '.p05v2-nav button')]
        if nav_labels != EXPECTED_SITE_VIEWS:
            fail(f'canonical site navigation mismatch: {nav_labels!r}')

        for label in EXPECTED_SITE_VIEWS:
            click(session, button_with_text(session, label, "//nav[contains(@class,'p05v2-nav')]") )
            wait_until(f'{label} surface', lambda label=label: label in text(session, find(session, 'css selector', '.p05v2-header h1')))
            assert_no_overflow(session, f'{label}-desktop')
            page = body_text(session)
            if label == '变更' and '不自动宣称因果' not in page:
                fail('Changes surface lost non-causality owner copy')
            if label == '搜索表现' and '不等于 0 流量' in page and '暂无 Search Observation' not in page:
                fail('unexpected Search zero/unknown presentation state')

        click(session, button_with_text(session, '全局搜索', "//nav[contains(@class,'p05v2-secondary')]") )
        wait_until('Global Search', lambda: text(session, find(session, 'css selector', '.p05v2-header h1')).strip() == '全局搜索')
        search_box = find(session, 'css selector', '.p05v2-search input[placeholder="网站、关键词或页面…"]')
        send_keys(session, search_box, 'kewaro')
        click(session, button_with_text(session, '搜索', "//form[contains(@class,'p05v2-search')]") )
        wait_until('Global Search results', lambda: len(find_all(session, 'css selector', '.p05v2-table-wrap tbody tr')) > 0)
        assert_no_overflow(session, 'global-search-desktop')

        maintenance_buttons = find_all(session, 'xpath', "//nav[contains(@class,'p05v2-secondary')]//button[normalize-space(.)='系统维护']")
        update_buttons = find_all(session, 'xpath', "//nav[contains(@class,'p05v2-secondary')]//button[.//span[normalize-space(.)='系统更新']]")
        if len(maintenance_buttons) != 1 or len(update_buttons) != 1:
            fail(f'system owner surfaces are not unique maintenance={len(maintenance_buttons)} update={len(update_buttons)}')

        click(session, maintenance_buttons[0])
        wait_until('System Maintenance dialog', lambda: len(find_all(session, 'css selector', '.vf-common-modal[aria-label="系统维护"]')) == 1)
        maintenance_text = text(session, find(session, 'css selector', '.vf-common-modal'))
        for required in ['系统信息', '系统基线', '备份', '运行健康', '品牌', '导入 / 导出']:
            if required not in maintenance_text:
                fail(f'System Maintenance missing owner job: {required}')
        if '在线升级' in maintenance_text or '系统更新' in maintenance_text:
            fail('System Maintenance still exposes second update job')
        click(session, button_with_text(session, '关闭', "//section[contains(@class,'vf-common-modal')]") )
        wait_until('System Maintenance close', lambda: len(find_all(session, 'css selector', '.vf-common-modal')) == 0)

        click(session, update_buttons[0])
        wait_until('System Update dialog', lambda: len(find_all(session, 'css selector', '.vf-update-dialog')) == 1)
        update_text = text(session, find(session, 'css selector', '.vf-update-dialog'))
        for required in ['系统更新', '当前版本', '最新版本', '状态']:
            if required not in update_text:
                fail(f'System Update missing owner copy: {required}')
        for forbidden in ['GitHub', 'core-updates', 'runtime.env', 'Atomic', 'Schema']:
            if forbidden in update_text:
                fail(f'update infrastructure leaked to Owner UI: {forbidden}')
        click(session, find(session, 'css selector', '.vf-update-close'))
        wait_until('System Update close', lambda: len(find_all(session, 'css selector', '.vf-update-dialog')) == 0)

        session_value(session, 'POST', '/window/rect', {'width': 390, 'height': 844, 'x': 0, 'y': 0})
        click(session, find(session, 'css selector', '.p05v2-portfolio'))
        wait_until('mobile Portfolio', lambda: 'Site Portfolio' in text(session, find(session, 'css selector', '.p05v2-header h1')))
        assert_no_overflow(session, 'portfolio-mobile-390')
        for label in EXPECTED_SITE_VIEWS:
            click(session, button_with_text(session, label, "//nav[contains(@class,'p05v2-nav')]") )
            wait_until(f'mobile {label}', lambda label=label: label in text(session, find(session, 'css selector', '.p05v2-header h1')))
            assert_no_overflow(session, f'{label}-mobile-390')

        print('P05_PHASE3_BROWSER_JOURNEY=PASS')
        print('P05_PHASE3_DEMO_DATASET=P05_DEMO_V1')
        print('P05_PHASE3_DEMO_WEBSITES=5')
        print('P05_PHASE3_SITE_SURFACES=10')
        print('P05_PHASE3_GLOBAL_SEARCH=PASS')
        print('P05_PHASE3_SYSTEM_MAINTENANCE_UNIQUE=PASS')
        print('P05_PHASE3_SYSTEM_UPDATE_UNIQUE=PASS')
        print('P05_PHASE3_CAUSALITY_GUARD=PASS')
        print('P05_PHASE3_MOBILE_390_OVERFLOW=0')
    finally:
        if session:
            try:
                wd('DELETE', f'/session/{session}')
            except Exception:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        driver_log.close()


if __name__ == '__main__':
    main()
