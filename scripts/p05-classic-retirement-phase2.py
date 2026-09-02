from pathlib import Path

root = Path('p05')

# Shared Product truth: preserve UNKNOWN != 0 and comparable-history semantics without retaining Classic UI.
truth = root / 'src/client/product-metric-truth.ts'
truth.write_text("""export function observedNumber(value: unknown): number | null {\n  if (value === null || value === undefined) return null;\n  if (typeof value === 'string' && value.trim() === '') return null;\n  const number = Number(value);\n  return Number.isFinite(number) ? number : null;\n}\n\nexport function keywordTrendCoverage(rows: Array<{ movement?: unknown }>) {\n  return {\n    observed: rows.length,\n    comparable: rows.filter(row => observedNumber(row.movement) != null).length,\n  };\n}\n\nexport function formatObservedNumber(value: unknown, digits = 0): string {\n  const number = observedNumber(value);\n  return number == null ? '—' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(number);\n}\n\nexport function formatRatioPercent(value: unknown, digits = 1): string {\n  const number = observedNumber(value);\n  return number == null ? '—' : `${(number * 100).toFixed(digits)}%`;\n}\n\nexport function movementText(value: unknown): string {\n  const number = observedNumber(value);\n  if (number == null) return '暂无对比';\n  if (number === 0) return '→ 0';\n  return number > 0 ? `↑ ${Math.abs(number)}` : `↓ ${Math.abs(number)}`;\n}\n""")

product = root / 'src/client/ProductApp.tsx'
text = product.read_text()
import_anchor = "import type { FormEvent, ReactNode } from 'react';\n"
assert import_anchor in text
text = text.replace(import_anchor, import_anchor + "import { observedNumber } from './product-metric-truth';\n", 1)
old = "function numberOrNull(value: unknown): number | null { if (value === null || value === undefined || value === '') return null; const n = Number(value); return Number.isFinite(n) ? n : null; }\nfunction fmt(value: unknown, digits = 0) { const n = numberOrNull(value); return n == null ? '—' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(n); }\nfunction pct(value: unknown) { const n = numberOrNull(value); return n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`; }"
new = "function fmt(value: unknown, digits = 0) { const n = observedNumber(value); return n == null ? '—' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(n); }\nfunction pct(value: unknown) { const n = observedNumber(value); return n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`; }"
assert old in text, 'Product numeric parser anchor missing'
text = text.replace(old, new, 1)
assert 'numberOrNull(' not in text
product.write_text(text)

# Upgrade single-product contract from migration state to physical retirement.
shell = root / 'tests/contract/single-product-shell.test.ts'
text = shell.read_text()
old_block = """test('classic workspace remains only as unreachable migration code in phase 1', () => {\n  assert.equal(existsSync(new URL('../../src/client/App.tsx', import.meta.url)), true);\n  assert.equal(existsSync(new URL('../../src/client/ProductWorkspaceShortcut.tsx', import.meta.url)), true);\n});\n"""
new_block = """test('Classic product surfaces are physically retired after parity migration', () => {\n  for (const path of [\n    '../../src/client/App.tsx',\n    '../../src/client/ProductWorkspaceShortcut.tsx',\n    '../../src/client/DemoDatasetShortcut.tsx',\n  ]) assert.equal(existsSync(new URL(path, import.meta.url)), false, `retired surface still exists: ${path}`);\n});\n"""
assert old_block in text, 'phase1 migration contract anchor missing'
text = text.replace(old_block, new_block)
shell.write_text(text)

# Replace Classic-bound unit contracts with Product/shared truth contracts.
for path in [
    root / 'tests/unit/classic-keyword-trend-coverage.test.ts',
    root / 'tests/unit/classic-nullable-metric-truth.test.ts',
]:
    path.unlink()

metric_test = root / 'tests/unit/product-metric-truth.test.ts'
metric_test.write_text("""import assert from 'node:assert/strict';\nimport { readFileSync } from 'node:fs';\nimport test from 'node:test';\nimport {\n  formatObservedNumber,\n  formatRatioPercent,\n  keywordTrendCoverage,\n  movementText,\n  observedNumber,\n} from '../../src/client/product-metric-truth.ts';\n\nconst productServer = readFileSync(new URL('../../src/server/product-optimization.ts', import.meta.url), 'utf8');\n\ntest('missing and whitespace observations remain UNKNOWN instead of becoming zero', () => {\n  for (const value of [null, undefined, '', '   ']) {\n    assert.equal(observedNumber(value), null);\n    assert.equal(formatObservedNumber(value), '—');\n    assert.equal(formatRatioPercent(value), '—');\n    assert.equal(movementText(value), '暂无对比');\n  }\n});\n\ntest('real zero and observed values remain distinguishable from UNKNOWN', () => {\n  assert.equal(observedNumber(0), 0);\n  assert.equal(observedNumber('0'), 0);\n  assert.equal(formatObservedNumber(0), '0');\n  assert.equal(formatObservedNumber(12.34, 1), '12.3');\n  assert.equal(formatRatioPercent(0), '0.0%');\n  assert.equal(formatRatioPercent(0.125), '12.5%');\n  assert.equal(movementText(0), '→ 0');\n  assert.equal(movementText(-1.2), '↓ 1.2');\n});\n\ntest('keyword coverage separates current observations from comparable history', () => {\n  assert.deepEqual(keywordTrendCoverage([\n    { movement: null },\n    { movement: undefined },\n    { movement: 0 },\n    { movement: 1.2 },\n    { movement: -0.8 },\n  ]), { observed: 5, comparable: 3 });\n  assert.match(productServer, /movement: position != null && previousPosition != null \\? previousPosition - position : null/);\n});\n""")

# Physically remove dead Classic / transition runtime sources.
for path in [
    root / 'src/client/App.tsx',
    root / 'src/client/ProductWorkspaceShortcut.tsx',
    root / 'src/client/DemoDatasetShortcut.tsx',
]:
    path.unlink()

print('P05_CLASSIC_RETIREMENT_PHASE2_WRITER=PASS')
