from pathlib import Path
import json
import re
from playwright.sync_api import sync_playwright

PRODUCT = Path('p01/src/assets/update-core.js')
EVID = Path('/tmp/p01-update-terminal-runtime-confirm')
EVID.mkdir(parents=True, exist_ok=True)
js = PRODUCT.read_text(encoding='utf-8')

required = [
    "vf_runtime_probe=",
    "cache:'no-store'",
    "Date.now()+8000",
    "compareVersions(status.current_version,targetVersion)>=0",
    "confirmRuntimeThenReload(toVersion)",
]
for token in required:
    assert token in js, token
assert "hardReload();" not in js

html = '''<!doctype html><html><head>
<meta name="csrf-token" content="gate-csrf"><meta name="vf-asset-version" content="2.36.3">
</head><body>
<div class="vf-rail-footer">VF Start · V2.36.3</div>
<section id="updatePanel">
<button id="checkUpdate">检查更新</button><button id="installUpdate" hidden>立即更新</button>
<strong id="updateCurrent">—</strong><strong id="updateLatest">—</strong><strong id="updateLastCheck">—</strong>
<span id="updateDot"></span><span id="updateState"></span><p id="updateNotes"></p><div id="updateMeta"></div>
<div id="updateSteps" hidden></div><div id="updateError"></div><div id="updateHistory"></div>
</section>
<script>window.vfAdminToast=function(){};</script>
<script>''' + js.replace('</script>', '<\\/script>') + '''</script></body></html>'''

state = {
    'document_requests': 0,
    'probe_count': 0,
    'stale_probe_count': 0,
    'confirmed': False,
    'navigation_before_confirm': False,
    'prepare_count': 0,
    'install_count': 0,
}

def status_payload(current, available):
    return {
        'ok': True,
        'status': {
            'current_version': current,
            'latest_version': '2.36.4',
            'available': available,
            'can_update': available,
            'reason': '可以更新。' if available else '已是最新版本。',
            'current_withdrawn': False,
            'release_notes': {'summary': 'terminal gate'},
            'released_at': '2026-09-01T15:17:48Z',
            'update_priority': 'normal',
            'last_check_at': '2026-09-01T15:42:40Z',
            'next_check_at': '2026-09-02T04:35:12Z',
            'repository': 'core-updates + GitHub Release',
            'history': [{'from_version': '2.36.3', 'to_version': '2.36.4', 'result': 'success', 'completed_at': '2026-09-01T15:42:45Z'}] if not available else [],
        }
    }

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1319, 'height': 641})

    def route_handler(route, request):
        url = request.url
        if request.resource_type == 'document':
            state['document_requests'] += 1
            if state['document_requests'] > 1 and not state['confirmed']:
                state['navigation_before_confirm'] = True
            route.fulfill(status=200, content_type='text/html; charset=utf-8', body=html)
            return
        if '/api.php?' in url:
            if 'action=update_status' in url:
                if 'vf_runtime_probe=' in url:
                    state['probe_count'] += 1
                    if state['probe_count'] <= 3:
                        state['stale_probe_count'] += 1
                        body = status_payload('2.36.3', True)
                    else:
                        state['confirmed'] = True
                        body = status_payload('2.36.4', False)
                else:
                    body = status_payload('2.36.4', False) if state['confirmed'] else status_payload('2.36.3', True)
                route.fulfill(status=200, content_type='application/json', body=json.dumps(body))
                return
            if 'action=update_prepare' in url:
                state['prepare_count'] += 1
                route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'result': {'operation_id': '20260901154240-0123456789abcdef'}}))
                return
            if 'action=update_install' in url:
                state['install_count'] += 1
                route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True, 'result': {'to_version': '2.36.4'}}))
                return
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'ok': True}))
            return
        route.fulfill(status=404, body='not found')

    page.route('http://vf.test/**', route_handler)
    page.goto('http://vf.test/update.php')
    page.wait_for_function("document.getElementById('updateCurrent').textContent==='V2.36.3' && !document.getElementById('installUpdate').hidden")
    page.click('#installUpdate')

    page.wait_for_function("document.getElementById('updateState').textContent.indexOf('正在确认新版本状态')>=0")
    page.wait_for_timeout(1200)
    assert state['stale_probe_count'] >= 2, state
    assert state['document_requests'] == 1, state
    assert not state['navigation_before_confirm'], state

    page.wait_for_url(re.compile(r'vf_refresh='), timeout=10000)
    page.wait_for_function("document.getElementById('updateCurrent').textContent==='V2.36.4' && document.getElementById('updateLatest').textContent==='V2.36.4'")
    page.wait_for_function("document.querySelector('.vf-rail-footer').textContent==='VF Start · V2.36.4'")
    page.wait_for_function("document.getElementById('installUpdate').hidden === true")
    page.wait_for_function("document.getElementById('updateState').textContent==='已是最新版本。'")

    assert state['probe_count'] >= 4, state
    assert state['stale_probe_count'] == 3, state
    assert state['confirmed'] is True, state
    assert state['navigation_before_confirm'] is False, state
    assert state['document_requests'] >= 2, state
    assert state['prepare_count'] == 1, state
    assert state['install_count'] == 1, state

    page.screenshot(path=str(EVID / 'terminal-after-auto-reload.png'), full_page=True)
    browser.close()

(EVID / 'state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
(EVID / 'verdict.txt').write_text(
    'P01_UPDATE_TERMINAL_RUNTIME_CONFIRM=PASS\n'
    'STALE_STATUS_BEFORE_CONFIRM=PASS\n'
    'NO_RELOAD_WHILE_RUNTIME_STALE=PASS\n'
    'AUTO_RELOAD_AFTER_RUNTIME_CONFIRM=PASS\n'
    'TERMINAL_CURRENT_LATEST_FOOTER=PASS\n'
    'MANUAL_REFRESH_REQUIRED=NO\n',
    encoding='utf-8'
)
print('P01_UPDATE_TERMINAL_RUNTIME_CONFIRM=PASS')
