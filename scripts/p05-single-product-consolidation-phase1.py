from pathlib import Path

root = Path('p05')

main = root / 'src/client/main.tsx'
text = main.read_text()
text = text.replace("import { App } from './App';\n", '')
text = text.replace("\nconst DemoDatasetShortcut = lazy(async () => {\n  const module = await import('./DemoDatasetShortcut');\n  return { default: module.DemoDatasetShortcut };\n});\n\nconst ProductWorkspaceShortcut = lazy(async () => {\n  const module = await import('./ProductWorkspaceShortcut');\n  return { default: module.ProductWorkspaceShortcut };\n});\n\nconst productPreview = location.hash.startsWith('#/product-v2');\n", "\n")
old = '''    {productPreview ? <Suspense fallback={<main className="app-shell"><p>正在加载 Product Preview…</p></main>}><ProductApp /></Suspense> : <App />}\n    <Suspense fallback={null}><CommonSystemCenter /></Suspense>\n    <Suspense fallback={null}><UpdateShortcut /></Suspense>\n    <Suspense fallback={null}><DemoDatasetShortcut /></Suspense>\n    <Suspense fallback={null}><ProductWorkspaceShortcut /></Suspense>'''
new = '''    <Suspense fallback={<main className="app-shell"><p>正在加载 VF SEO…</p></main>}><ProductApp /></Suspense>\n    <Suspense fallback={null}><CommonSystemCenter /></Suspense>\n    <Suspense fallback={null}><UpdateShortcut /></Suspense>'''
assert old in text, 'main root switch anchor missing'
text = text.replace(old, new)
assert "from './App'" not in text
assert 'productPreview' not in text
assert 'ProductWorkspaceShortcut' not in text
assert 'DemoDatasetShortcut' not in text
main.write_text(text)

product = root / 'src/client/ProductApp.tsx'
text = product.read_text()
assert 'Product Optimization Preview' in text
assert '新版工作区不会创建第二套认证体系。' in text
text = text.replace('Product Optimization Preview', 'Owner SEO / AEO Workspace')
text = text.replace('使用现有管理员账户登录。新版工作区不会创建第二套认证体系。', '使用现有管理员账户登录。所有 SEO / AEO 工作都在这一套工作区完成。')
product.write_text(text)

common = root / 'src/client/CommonSystemCenter.tsx'
text = common.read_text()
assert "import { useEffect, useMemo, useState } from 'react';" in text
text = text.replace("import { useEffect, useMemo, useState } from 'react';", "import { useEffect, useMemo, useState } from 'react';\nimport { createPortal } from 'react-dom';")
anchor = "  const [ready, setReady] = useState(false);\n"
assert anchor in text
text = text.replace(anchor, anchor + "  const [portalHost, setPortalHost] = useState<Element | null>(null);\n")
auth_effect = """  useEffect(() => {\n    api('/api/auth/me')\n"""
assert auth_effect in text
host_effect = """  useEffect(() => {\n    const findHost = () => {\n      const next = document.querySelector('.p05v2-secondary');\n      setPortalHost(current => current === next ? current : next);\n    };\n    findHost();\n    const observer = new MutationObserver(findHost);\n    observer.observe(document.body, { childList: true, subtree: true });\n    return () => observer.disconnect();\n  }, []);\n\n"""
text = text.replace(auth_effect, host_effect + auth_effect)
old_button = '    <button className="vf-common-launch" onClick={() => { setOpen(true); setNotice(\'\'); setError(\'\'); void loadInfo(); }} aria-label="系统维护">系统</button>'
new_button = '    {portalHost && createPortal(<button className={`vf-common-nav-button ${open ? \'active\' : \'\'}`} onClick={() => { setOpen(true); setNotice(\'\'); setError(\'\'); void loadInfo(); }} aria-label="系统维护">系统维护</button>, portalHost)}'
assert old_button in text
text = text.replace(old_button, new_button)
style_anchor = "      .vf-common-launch{position:fixed;left:18px;bottom:18px;z-index:70;border:1px solid #d7e2e7;background:#fff;border-radius:999px;padding:8px 13px;box-shadow:0 8px 24px rgba(15,23,42,.12);cursor:pointer}"
assert style_anchor in text
style_new = "      .vf-common-nav-button{width:100%;min-height:40px;border-radius:10px;padding:9px 14px;border:1px solid transparent;background:transparent;color:#c6dce0;text-align:left;font:inherit;font-weight:750}.vf-common-nav-button:hover,.vf-common-nav-button.active{background:rgba(255,255,255,.06);color:#fff}.vf-common-nav-button.active{background:rgba(19,167,183,.18);border-color:rgba(66,213,226,.22);color:#83eef4}"
text = text.replace(style_anchor, style_new)
common.write_text(text)

test = root / 'tests/contract/single-product-shell.test.ts'
test.write_text("""import assert from 'node:assert/strict';\nimport { readFileSync } from 'node:fs';\nimport test from 'node:test';\n\nconst main = readFileSync(new URL('../../src/client/main.tsx', import.meta.url), 'utf8');\nconst product = readFileSync(new URL('../../src/client/ProductApp.tsx', import.meta.url), 'utf8');\nconst common = readFileSync(new URL('../../src/client/CommonSystemCenter.tsx', import.meta.url), 'utf8');\n\ntest('ProductApp is the only runtime product root', () => {\n  assert.ok(main.includes('<ProductApp />'));\n  assert.equal(main.includes("from './App'"), false);\n  assert.equal(main.includes('productPreview'), false);\n  assert.equal(main.includes('ProductWorkspaceShortcut'), false);\n  assert.equal(main.includes('DemoDatasetShortcut'), false);\n});\n\ntest('runtime no longer presents product preview or classic workspace language', () => {\n  assert.equal(product.includes('Product Optimization Preview'), false);\n  assert.equal(product.includes('新版工作区'), false);\n  assert.ok(product.includes('Owner SEO / AEO Workspace'));\n});\n\ntest('common system maintenance belongs to Product global navigation', () => {\n  assert.ok(common.includes("document.querySelector('.p05v2-secondary')"));\n  assert.ok(common.includes('createPortal(<button'));\n  assert.ok(common.includes('>系统维护</button>'));\n  for (const label of ['系统信息', '系统基线', '在线升级', '备份与恢复', '运行健康']) {\n    assert.ok(common.includes(`>${label}</button>`), `missing system capability: ${label}`);\n  }\n});\n""")

print('P05_SINGLE_PRODUCT_CONSOLIDATION_PHASE1=PASS')
