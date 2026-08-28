#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'p06')

version_path = root / 'VERSION'
if version_path.read_text(encoding='utf-8').strip() != '0.1.14':
    raise SystemExit('unexpected starting VERSION')
version_path.write_text('0.1.15\n', encoding='utf-8')

project_path = root / 'VF_PROJECT.json'
project = json.loads(project_path.read_text(encoding='utf-8'))
project['version'] = '0.1.15'
project['lifecycle'] = 'CANDIDATE'
project['current_phase'] = 'V0_1_15_HUMAN_BASELINE_UI_CANDIDATE'
project['next_gate'] = 'EXACT_SOURCE_MACHINE_GATE_V0_1_15'
project['human_ui_exposure_v0_1_15'] = {
    'state': 'CANDIDATE',
    'scope': 'SYSTEM_INFO_BASELINE_HEALTH_PRESENTATION_ONLY',
    'baseline_resolver_change': False,
    'schema_change': False,
    'production_change': False,
    'owner_first_conclusion': True,
    'attention_summary': True,
    'domain_translation_count': 15,
    'technical_details_default_collapsed': True,
    'explicit_exceptions_preserved': [
        'P06-TIME-DISPLAY-CONVERSION-LEGACY-SURFACES',
        'P06-API-RETRY-PROVIDER-SPECIFIC',
    ],
}
project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

changelog_path = root / 'CHANGELOG.md'
changelog = changelog_path.read_text(encoding='utf-8')
heading = '## 0.1.15 · Human-readable System Baseline UI（2026-08-28）'
if heading not in changelog:
    block = '''## 0.1.15 · Human-readable System Baseline UI（2026-08-28）

- 系统信息、系统基线、运行健康改为管理员优先：先显示“管理员结论 / 你需要关注”，不再要求 OWNER 先读 Runtime 枚举和秒数。
- Common Product Baseline V2 的 15 个 Domain 全部提供中文业务名称；PASS / EXCEPTION / DRIFT / UNKNOWN / N_A 分别展示为正常、已知限制、需要处理、待确认、当前不适用。
- 两个正式显式例外继续保留：旧后台时间显示尚未全部转换、外部 API 尚无统一 Retry Wrapper；不把 EXCEPTION 美化成 PASS。
- 原始 Domain / State / Reason / Details、Profile 与 Runtime 参数继续存在于默认折叠的“技术详情（开发 / 排障使用）”，Resolver 不变、Schema 保持 `3`。
- 本版本不修改书稿、Reader、AI、Schema、CommonBaselineV2 Resolver 或 Production；Production 升级必须使用独立 Gate。

'''
    marker = '# 变更记录\n\n'
    if marker not in changelog:
        raise SystemExit('CHANGELOG marker missing')
    changelog_path.write_text(changelog.replace(marker, marker + block, 1), encoding='utf-8')

css_path = root / 'public/assets/maintenance.css'
css = css_path.read_text(encoding='utf-8')
css_marker = '/* V0.1.15 human-readable baseline UI */'
if css_marker not in css:
    css += r'''

/* V0.1.15 human-readable baseline UI */
.maintenance-owner-summary,
.maintenance-attention,
.maintenance-baseline-group,
.maintenance-tech-details {
    margin-bottom: 16px;
    border: 1px solid #dbe4e7;
    border-radius: 10px;
    background: #fff;
}
.maintenance-owner-summary { padding: 20px 22px; border-left-width: 4px; }
.maintenance-owner-summary > span,
.maintenance-attention > div > span {
    display: block;
    color: #667a82;
    font-size: 10px;
    font-weight: 750;
    letter-spacing: .08em;
}
.maintenance-owner-summary h2 { margin: 5px 0 6px; font-size: 22px; line-height: 1.3; }
.maintenance-owner-summary p,
.maintenance-attention p,
.maintenance-attention li,
.maintenance-known-limits li,
.maintenance-baseline-item p { color: #526970; font-size: 12px; line-height: 1.65; }
.maintenance-owner-summary-ok { border-left-color: #21866d; background: #fbfefd; }
.maintenance-owner-summary-warn { border-left-color: #c98226; background: #fffdf8; }
.maintenance-attention { padding: 16px 18px; }
.maintenance-attention > div:first-child {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}
.maintenance-attention > div > strong { font-size: 13px; }
.maintenance-attention ul { margin: 10px 0 0; padding-left: 20px; }
.maintenance-attention-ok { border-color: #cfe3dc; background: #f8fcfa; }
.maintenance-attention-warn { border-color: #ead6b5; background: #fffaf1; }
.maintenance-known-limits { margin-top: 12px; padding-top: 12px; border-top: 1px solid #dfe8ea; }
.maintenance-known-limits > strong { font-size: 12px; }
.maintenance-metrics-human { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.maintenance-baseline-groups {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}
.maintenance-baseline-group { margin: 0; padding: 16px; }
.maintenance-baseline-list { display: grid; }
.maintenance-baseline-item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 14px;
    align-items: start;
    padding: 12px 0;
    border-top: 1px solid #e6edef;
}
.maintenance-baseline-item:first-child { border-top: 0; }
.maintenance-baseline-item strong { font-size: 13px; }
.maintenance-baseline-item p { margin: 4px 0 0; }
.maintenance-state {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    padding: 3px 8px;
    border: 1px solid #cbdadd;
    border-radius: 999px;
    background: #f5f9fa;
    color: #415b62;
    font-size: 10px;
    font-weight: 700;
    white-space: nowrap;
}
.maintenance-state-pass { border-color: #bdddcf; background: #f1faf6; color: #27735f; }
.maintenance-state-exception { border-color: #ead2aa; background: #fff9ee; color: #9a6422; }
.maintenance-state-drift,
.maintenance-state-unknown { border-color: #e6c0c0; background: #fff5f5; color: #a73d3d; }
.maintenance-state-n-a { color: #687b81; background: #f4f7f8; }
.maintenance-tech-details { padding: 0; overflow: hidden; }
.maintenance-tech-details > summary {
    padding: 13px 16px;
    color: #536970;
    background: #f8fafb;
    cursor: pointer;
    font-size: 11px;
    font-weight: 700;
}
.maintenance-tech-details[open] > summary { border-bottom: 1px solid #dfe7e9; }
.maintenance-tech-details > .maintenance-definition,
.maintenance-tech-details > .maintenance-table-wrap,
.maintenance-tech-meta { margin: 14px 16px; }
.maintenance-tech-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    color: #667a82;
    font-size: 10px;
}
.maintenance-definition-human dd { font-weight: 650; }
@media (max-width: 980px) {
    .maintenance-metrics-human { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .maintenance-baseline-groups { grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
    .maintenance-metrics-human { grid-template-columns: 1fr 1fr; }
    .maintenance-owner-summary { padding: 17px; }
    .maintenance-baseline-item { grid-template-columns: 1fr; gap: 7px; }
    .maintenance-state { justify-self: start; }
}
'''
    css_path.write_text(css, encoding='utf-8')

self_test = r'''<?php

declare(strict_types=1);

$base = dirname(__DIR__);
$system = (string) file_get_contents($base . '/src/Http/Studio/SystemBaselineController.php');
$shell = (string) file_get_contents($base . '/src/Http/Studio/BackofficeShell.php');
$resolver = (string) file_get_contents($base . '/src/Application/Operations/CommonBaselineV2.php');
$css = (string) file_get_contents($base . '/public/assets/maintenance.css');
$version = trim((string) file_get_contents($base . '/VERSION'));
$failures = [];

foreach ([
    '管理员结论', '你需要关注', '技术详情（开发 / 排障使用）',
    '时间规则', '登录与高风险验证', '在线升级', '备份与恢复', '数据与 Schema',
    '外部接口保护', '后台任务', '外部通知', '操作与安全记录', '后台通用状态',
    '文件上传', '运行健康', '版本身份', '缓存策略', '界面语言',
    "'PASS' => '正常'", "'EXCEPTION' => '已知限制'", "'DRIFT' => '需要处理'",
    "'UNKNOWN' => '待确认'", "'N_A' => '当前不适用'",
] as $needle) {
    if (!str_contains($system, $needle)) {
        $failures[] = 'System UI missing: ' . $needle;
    }
}
foreach (['系统信息', '系统基线', '在线升级', '备份与恢复', '运行健康'] as $entry) {
    if (!str_contains($shell, $entry)) {
        $failures[] = 'Canonical maintenance entry missing: ' . $entry;
    }
}
if (!str_contains($system, '<details class="maintenance-tech-details')) {
    $failures[] = 'Raw evidence is not collapsed in details';
}
if (!str_contains($system, "['DRIFT', 'UNKNOWN']")) {
    $failures[] = 'Attention gate does not prioritize DRIFT/UNKNOWN';
}
foreach (['P06-API-RETRY-PROVIDER-SPECIFIC', 'P06-TIME-DISPLAY-CONVERSION-LEGACY-SURFACES'] as $exception) {
    if (!str_contains($resolver, $exception)) {
        $failures[] = 'Explicit baseline exception disappeared: ' . $exception;
    }
}
if (!str_contains($resolver, "'NOTIFICATION'")) {
    $failures[] = 'NOTIFICATION domain contract disappeared';
}
if (!str_contains($css, 'V0.1.15 human-readable baseline UI')) {
    $failures[] = 'Human UI CSS missing';
}
if ($version !== '0.1.15') {
    $failures[] = 'VERSION is not 0.1.15';
}
if ($failures !== []) {
    foreach ($failures as $failure) {
        fwrite(STDERR, "FAIL: {$failure}\n");
    }
    exit(1);
}
fwrite(STDOUT, "P06_COMMON_BASELINE_HUMAN_UI=PASS\n");
'''
(root / 'bin/common-baseline-human-ui-self-test.php').write_text(self_test, encoding='utf-8')
