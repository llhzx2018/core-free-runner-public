#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()

p = root / 'src/app/SystemDiagnosticsService.php'
s = p.read_text(encoding='utf-8')
needle = """        $pdo = Database::connection();
        $checks = [];
        $add = static function (string $key, string $label, string $status, string $detail, string $next = '') use (&$checks): void {
"""
repl = """        $checks = [];
        $cron = [];
        $add = static function (string $key, string $label, string $status, string $detail, string $next = '') use (&$checks): void {
"""
if s.count(needle) != 1:
    raise SystemExit('DIAGNOSTICS_OPEN_DRIFT')
s = s.replace(needle, repl, 1)
marker = "        $add('php', 'PHP 运行环境',"
if s.count(marker) != 1:
    raise SystemExit('DIAGNOSTICS_TRY_DRIFT')
s = s.replace(marker, "        try {\n            $pdo = Database::connection();\n\n" + marker, 1)
summary = "        $summary = ['ok' => 0, 'warning' => 0, 'blocked' => 0];"
if s.count(summary) != 1:
    raise SystemExit('DIAGNOSTICS_SUMMARY_DRIFT')
catch = """        } catch (Throwable $e) {
            $reference = Support::randomHex(6);
            error_log('[VF Infra][' . $reference . '] diagnostics: ' . Support::sanitizeError($e->getMessage()));
            $add(
                'diagnostics_internal',
                '诊断执行完整性',
                'blocked',
                '部分检查未完成 · 参考 ' . $reference,
                '请先处理已显示检查项；如持续出现，请使用参考编号定位服务器日志。'
            );
        }

"""
s = s.replace(summary, catch + summary, 1)
p.write_text(s, encoding='utf-8')

p = root / 'public/assets/v284-long-action-feedback.js'
s = p.read_text(encoding='utf-8')
block = """    domain_check: {
      title: '正在检查域名',
      detail: '正在查询 RDAP，请勿重复点击。',
      selectors: ['[data-action=\"check-domain\"]'],
      clickedOnly: true,
    },
"""
if s.count(block) != 1:
    raise SystemExit('FEEDBACK_KNOWN_DRIFT')
s = s.replace(block, block + """    diagnostics_run: {
      title: '正在检查系统',
      detail: '正在执行完整诊断，请稍候，不要重复点击。',
      selectors: ['[data-v271-action=\"diagnostics-run\"]'],
      clickedOnly: true,
    },
""", 1)
needle = "    'check-domain': 'domain_check',\n"
if s.count(needle) != 1:
    raise SystemExit('FEEDBACK_MAP_DRIFT')
s = s.replace(needle, needle + "    'diagnostics-run': 'diagnostics_run',\n", 1)
needle = "event.target.closest('[data-action]')"
if s.count(needle) != 1:
    raise SystemExit('FEEDBACK_SELECTOR_DRIFT')
s = s.replace(needle, "event.target.closest('[data-action], [data-v271-action=\"diagnostics-run\"]')", 1)
needle = "String(button.dataset.action || '')"
if s.count(needle) != 1:
    raise SystemExit('FEEDBACK_DATASET_DRIFT')
s = s.replace(needle, "String(button.dataset.action || button.dataset.v271Action || '')", 1)
p.write_text(s, encoding='utf-8')

(root / 'VERSION').write_text('2.8.6\n', encoding='utf-8')

p = root / 'CHANGELOG.md'
s = p.read_text(encoding='utf-8')
p.write_text("""## V2.8.6

- 修复“重新检查系统”在诊断异常时看起来没有反应：单项异常不再让整块诊断退化为“未知 / 0”，已完成检查继续显示，并给出安全参考编号。
- “重新检查系统”接入统一长耗时反馈：立即显示正在检查、等待秒数、Indeterminate Progress，并阻止重复点击。
- Schema 14，无 Migration，无 Provider 写权限变化。

""" + s, encoding='utf-8')

p = root / 'docs/operations/package/RELEASE_NOTES.md'
s = p.read_text(encoding='utf-8')
p.write_text("""# VF Infra V2.8.6

- 修复系统诊断手工重检无明显反馈与异常时整块结果被吞掉的问题。
- 诊断异常改为 fail-partial：保留已完成检查，追加“诊断执行完整性”阻断项与安全参考编号。
- 手工诊断接入 V2.8.4 Busy / 等待秒数 / Indeterminate Progress / 防重复提交合同。
- 保留 V2.8.5 设置左侧主分栏、无右侧二级 TAB、数据管理与系统信息单页连续内容。
- Schema 14，无 Migration，无 Provider 写权限变化。

""" + s, encoding='utf-8')

p = root / 'scripts/build-release-tree.py'
s = p.read_text(encoding='utf-8')
needle = "'2.8.3','2.8.4','2.8.5'}"
if s.count(needle) != 1:
    raise SystemExit('RELEASE_TREE_SET_DRIFT')
s = s.replace(needle, "'2.8.3','2.8.4','2.8.5','2.8.6'}", 1)
needle = """if version=='2.8.5':
    version_note='V2.8.5 retains the primary Settings sidebar, removes only nested content tabs, combines Data Management and System Information subcontent into one continuous page per primary section, and resets async top-level routes after render so Provider opens at the page top without disrupting same-page refresh position.'
"""
if s.count(needle) != 1:
    raise SystemExit('RELEASE_TREE_NOTE_DRIFT')
s = s.replace(needle, """if version=='2.8.6':
    version_note='V2.8.6 makes System Diagnostics fail-partial instead of fail-silent and connects the manual diagnostics action to the established long-running-operation feedback contract; Schema remains 14 and Provider authority remains read-only first.'
elif version=='2.8.5':
    version_note='V2.8.5 retains the primary Settings sidebar, removes only nested content tabs, combines Data Management and System Information subcontent into one continuous page per primary section, and resets async top-level routes after render so Provider opens at the page top without disrupting same-page refresh position.'
""", 1)
p.write_text(s, encoding='utf-8')
