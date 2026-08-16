from pathlib import Path

p = Path('scripts/p04-v254-browser-e2e.mjs')
s = p.read_text(encoding='utf-8')

replacements = [
    (
        "const errors = [];\nconst browser = await chromium.launch({ headless: true });",
        "const errors = [];\nlet expectedFailureInjection = false;\nconst browser = await chromium.launch({ headless: true });",
    ),
    (
        "page.on('pageerror', (e) => errors.push(`PAGEERROR ${e.message}`));\npage.on('console', (msg) => { if (msg.type() === 'error') errors.push(`CONSOLE ${msg.text()}`); });\npage.on('response', (res) => { if (res.status() >= 500) errors.push(`HTTP${res.status()} ${res.url()}`); });",
        "page.on('pageerror', (e) => { if (!expectedFailureInjection) errors.push(`PAGEERROR ${e.message}`); });\npage.on('console', (msg) => { if (msg.type() === 'error' && !expectedFailureInjection) errors.push(`CONSOLE ${msg.text()}`); });\npage.on('response', (res) => { if (res.status() >= 500 && !expectedFailureInjection) errors.push(`HTTP${res.status()} ${res.url()}`); });",
    ),
    (
        "// Synthetic full error and real retry recovery.\nawait page.route('**/api.php?action=dashboard*', async (route) => {",
        "// Synthetic full error and real retry recovery.\nexpectedFailureInjection = true;\nawait page.route('**/api.php?action=dashboard*', async (route) => {",
    ),
    (
        "await page.unroute('**/api.php?action=dashboard*');\nawait page.locator('#view-dashboard [data-action=\"reload-view\"]').click();",
        "await page.unroute('**/api.php?action=dashboard*');\nexpectedFailureInjection = false;\nawait page.locator('#view-dashboard [data-action=\"reload-view\"]').click();",
    ),
]

for old, new in replacements:
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'expected-error sentinel mismatch: {old[:70]!r} -> {count}')
    s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('EXPECTED_ERROR_E2E_PATCH=PASS')
