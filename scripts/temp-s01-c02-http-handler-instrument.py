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

mu_dir = wp_path / "wp-content/mu-plugins"
mu_dir.mkdir(parents=True, exist_ok=True)
mu_path = mu_dir / "s01-admin-post-phase-tracer.php"
mu_path.write_text(r'''<?php
if (!defined('ABSPATH')) { exit; }
$vfS01Uri = (string)($_SERVER['REQUEST_URI'] ?? '');
if (strpos($vfS01Uri, '/wp-admin/admin-post.php') === false) { return; }
$vfS01Log = static function(string $phase): void {
    $method = (string)($_SERVER['REQUEST_METHOD'] ?? '');
    $postAction = isset($_POST['action']) && !is_array($_POST['action']) ? (string)$_POST['action'] : '';
    $requestAction = isset($_REQUEST['action']) && !is_array($_REQUEST['action']) ? (string)$_REQUEST['action'] : '';
    error_log('S01_HTTP_PHASE:' . $phase . ':' . sprintf('%.6f', microtime(true)) . ':METHOD=' . $method . ':POST_ACTION=' . $postAction . ':REQUEST_ACTION=' . $requestAction);
};
$vfS01Log('MU_FILE');
add_filter('option_active_plugins', static function($plugins) use ($vfS01Log) {
    $vfS01Log('ACTIVE_PLUGINS=' . implode(',', array_map('strval', (array)$plugins)));
    return $plugins;
}, -99999);
foreach (['muplugins_loaded','plugins_loaded','setup_theme','after_setup_theme','init','wp_loaded','admin_init','shutdown'] as $vfS01Hook) {
    add_action($vfS01Hook, static function() use ($vfS01Log, $vfS01Hook): void { $vfS01Log(strtoupper($vfS01Hook)); }, -99999);
}
add_action('admin_post_vf_ops_s01_m3u8_initialize', static function() use ($vfS01Log): void { $vfS01Log('ADMIN_POST_PRE_DISPATCH'); }, -99999);
register_shutdown_function(static function() use ($vfS01Log): void {
    $last = error_get_last();
    $vfS01Log('PHP_SHUTDOWN_LAST_ERROR=' . ($last ? json_encode($last, JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE) : 'NONE'));
    $pluginFiles = [];
    foreach (get_included_files() as $file) {
        if (strpos($file, '/wp-content/plugins/') !== false || strpos($file, '/wp-content/mu-plugins/') !== false) {
            $pluginFiles[] = $file;
        }
    }
    $vfS01Log('PHP_SHUTDOWN_INCLUDED_PLUGINS=' . implode('|', $pluginFiles));
});
''', encoding="utf-8")

print("S01_HTTP_HANDLER_INSTRUMENTATION=PASS")
print(path)
print("S01_HTTP_BOOTSTRAP_PHASE_TRACER=PASS")
print(mu_path)
