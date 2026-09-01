from pathlib import Path

ROOT = Path('p05')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, got {count}')
    return text.replace(old, new, 1)

# 1) Single canonical root app: ProductApp only.
main = ROOT / 'src/client/main.tsx'
main.write_text("""import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const ProductApp = lazy(async () => {
  const module = await import('./ProductApp');
  return { default: module.ProductApp };
});

const CommonSystemCenter = lazy(async () => {
  const module = await import('./CommonSystemCenter');
  return { default: module.CommonSystemCenter };
});

const UpdateShortcut = lazy(async () => {
  const module = await import('./UpdateShortcut');
  return { default: module.UpdateShortcut };
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Suspense fallback={<main className=\"app-shell\"><p>正在加载 VF SEO…</p></main>}><ProductApp /></Suspense>
    <Suspense fallback={null}><CommonSystemCenter /></Suspense>
    <Suspense fallback={null}><UpdateShortcut /></Suspense>
  </StrictMode>,
);
""", encoding='utf-8')

# 2) ProductApp is no longer a preview.
product = ROOT / 'src/client/ProductApp.tsx'
text = product.read_text(encoding='utf-8')
text = replace_once(text, '<span>Product Optimization Preview</span>', '<span>Owner SEO / AEO Workspace</span>', 'product login preview label')
text = replace_once(text, '<p>使用现有管理员账户登录。新版工作区不会创建第二套认证体系。</p>', '<p>使用现有管理员账户登录。这里是 P05 唯一正式工作区。</p>', 'product login preview copy')
product.write_text(text, encoding='utf-8')

# 3) Mount Common System Center into Product v2 Global navigation.
common = ROOT / 'src/client/CommonSystemCenter.tsx'
text = common.read_text(encoding='utf-8')
text = replace_once(text, "import { useEffect, useMemo, useState } from 'react';", "import { useEffect, useMemo, useState } from 'react';\nimport { createPortal } from 'react-dom';", 'common import')
text = replace_once(text, "  const [open, setOpen] = useState(false);\n  const [tab, setTab] = useState<SystemTab>('info');", "  const [open, setOpen] = useState(false);\n  const [portalHost, setPortalHost] = useState<Element | null>(null);\n  const [tab, setTab] = useState<SystemTab>('info');", 'common portal state')
text = replace_once(text, "    const row = document.querySelector<HTMLElement>('.brand-row');\n    if (!row) return;\n    const mark = row.querySelector<HTMLElement>('.brand-mark-small');", "    const row = document.querySelector<HTMLElement>('.brand-row, .p05v2-brand');\n    if (!row) return;\n    const mark = row.querySelector<HTMLElement>('.brand-mark-small, span');", 'common branding shell compatibility')
anchor = """  useEffect(() => {
    if (ready) applyBranding(branding);
  }, [ready, branding]);

  const canApply"""
insert = """  useEffect(() => {
    const findHost = () => {
      const next = document.querySelector('.p05v2-secondary');
      setPortalHost(current => current === next ? current : next);
    };
    findHost();
    const observer = new MutationObserver(findHost);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (ready) applyBranding(branding);
  }, [ready, branding]);

  const canApply"""
text = replace_once(text, anchor, insert, 'common portal effect')
old_button = """    <button className=\"vf-common-launch\" onClick={() => { setOpen(true); setNotice(''); setError(''); void loadInfo(); }} aria-label=\"系统维护\">系统</button>"""
new_button = """    {portalHost && createPortal(<button type=\"button\" className={`vf-common-nav-button ${open ? 'active' : ''}`} onClick={() => { setOpen(true); setNotice(''); setError(''); void loadInfo(); }} aria-label=\"系统维护\">系统维护</button>, portalHost)}"""
text = replace_once(text, old_button, new_button, 'common launch portal')
text = replace_once(text, "      .vf-common-launch{position:fixed;left:18px;bottom:18px;z-index:70;border:1px solid #d7e2e7;background:#fff;border-radius:999px;padding:8px 13px;box-shadow:0 8px 24px rgba(15,23,42,.12);cursor:pointer}", "      .vf-common-nav-button{width:100%;min-height:40px;border-radius:10px;padding:9px 14px;border:1px solid transparent;background:transparent;color:#c6dce0;text-align:left;font:inherit;font-weight:750}.vf-common-nav-button:hover,.vf-common-nav-button.active{background:rgba(255,255,255,.06);color:#fff}.vf-common-nav-button.active{background:rgba(19,167,183,.18);border-color:rgba(66,213,226,.22);color:#83eef4}", 'common nav css')
common.write_text(text, encoding='utf-8')

# 4) Regression contract for single-product shell.
test_path = ROOT / 'tests/contract/single-product-shell.test.ts'
test_path.write_text("""import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';

const main = readFileSync(new URL('../../src/client/main.tsx', import.meta.url), 'utf8');
const product = readFileSync(new URL('../../src/client/ProductApp.tsx', import.meta.url), 'utf8');
const common = readFileSync(new URL('../../src/client/CommonSystemCenter.tsx', import.meta.url), 'utf8');

test('ProductApp is the only runtime root workspace', () => {
  assert.ok(main.includes('<ProductApp />'));
  assert.equal(main.includes("from './App'"), false);
  assert.equal(main.includes('productPreview'), false);
  assert.equal(main.includes("location.hash.startsWith('#/product-v2')"), false);
  assert.equal(main.includes('ProductWorkspaceShortcut'), false);
  assert.equal(main.includes('DemoDatasetShortcut'), false);
});

test('classic workspace remains only as unreachable migration code in phase 1', () => {
  assert.equal(existsSync(new URL('../../src/client/App.tsx', import.meta.url)), true);
  assert.equal(existsSync(new URL('../../src/client/ProductWorkspaceShortcut.tsx', import.meta.url)), true);
});

test('formal Product shell contains no preview or classic-toggle copy', () => {
  assert.equal(product.includes('Product Optimization Preview'), false);
  assert.equal(product.includes('新版工作区不会创建第二套认证体系'), false);
  assert.ok(product.includes('这里是 P05 唯一正式工作区'));
  assert.equal(main.includes('返回经典工作区'), false);
  assert.equal(main.includes('新版工作区 Preview'), false);
});

test('common system maintenance is mounted into Product Global navigation', () => {
  assert.ok(common.includes("import { createPortal } from 'react-dom'"));
  assert.ok(common.includes("document.querySelector('.p05v2-secondary')"));
  assert.ok(common.includes('vf-common-nav-button'));
  assert.ok(common.includes('>系统维护</button>'));
  assert.ok(common.includes("'.brand-row, .p05v2-brand'"));
});
""", encoding='utf-8')

print('P05_SINGLE_PRODUCT_PHASE1_WRITER=PASS')
