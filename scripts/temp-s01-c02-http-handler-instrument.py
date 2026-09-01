#!/usr/bin/env python3
from pathlib import Path
import os

wp_path = Path(os.environ["WP_PATH"])
path = wp_path / "wp-content/plugins/vf-ops/includes/s01/tool-workbench.php"
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "function vf_ops_s01_tool_workbench_handle_initialize_v1(): void {\n    if (!current_user_can('manage_options'))",
        "function vf_ops_s01_tool_workbench_handle_initialize_v1(): void {\n    error_log('S01_HTTP_REPAIR:ENTER:' . sprintf('%.6f', microtime(true)));\n    if (!current_user_can('manage_options'))"
    ),
    (
        "    $nonceName = vf_ops_s01_tool_workbench_nonce_name_v1();",
        "    error_log('S01_HTTP_REPAIR:PERMISSION_PASS:' . sprintf('%.6f', microtime(true)));\n    $nonceName = vf_ops_s01_tool_workbench_nonce_name_v1();"
    ),
    (
        "    if (!function_exists('vf_m3u8_first_run_initialize')) {",
        "    error_log('S01_HTTP_REPAIR:NONCE_PASS:' . sprintf('%.6f', microtime(true)));\n    if (!function_exists('vf_m3u8_first_run_initialize')) {"
    ),
    (
        "    try {\n        $result = vf_m3u8_first_run_initialize((int)get_current_user_id(), 'vf_ops_owner_workbench');",
        "    try {\n        $vfS01Started = microtime(true);\n        error_log('S01_HTTP_REPAIR:BEFORE_INIT:' . sprintf('%.6f', $vfS01Started));\n        $result = vf_m3u8_first_run_initialize((int)get_current_user_id(), 'vf_ops_owner_workbench');\n        error_log('S01_HTTP_REPAIR:AFTER_INIT:' . sprintf('%.6f', microtime(true)) . ':MS=' . (string)((int)round((microtime(true) - $vfS01Started) * 1000)) . ':STATUS=' . (string)(is_array($result) ? ($result['status'] ?? '') : 'NON_ARRAY'));"
    ),
    (
        "    wp_safe_redirect(vf_ops_s01_tool_workbench_url_v1(['vf_s01_action'=>$status]));\n    exit;",
        "    $vfS01RedirectUrl = vf_ops_s01_tool_workbench_url_v1(['vf_s01_action'=>$status]);\n    error_log('S01_HTTP_REPAIR:BEFORE_REDIRECT:' . sprintf('%.6f', microtime(true)) . ':URL=' . $vfS01RedirectUrl);\n    $vfS01RedirectResult = wp_safe_redirect($vfS01RedirectUrl);\n    error_log('S01_HTTP_REPAIR:AFTER_REDIRECT:' . sprintf('%.6f', microtime(true)) . ':RESULT=' . ($vfS01RedirectResult ? 'TRUE' : 'FALSE'));\n    exit;"
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"instrumentation anchor missing: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("S01_HTTP_HANDLER_INSTRUMENTATION=PASS")
print(path)
