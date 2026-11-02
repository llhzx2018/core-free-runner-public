<?php
// Evaluated only inside a disposable WordPress/MariaDB container.
// Include real pinned product source, but do not activate the complete plugin.
if (!defined('VF_TOOL_M3U8_DIR')) { define('VF_TOOL_M3U8_DIR', '/tmp/r2-empty-assets/'); }
if (!function_exists('vf_m3u8_read_json_manifest')) {
    function vf_m3u8_read_json_manifest(string $path): array { return []; }
}
require '/tmp/r2-skin-seasonal.php';
$result = vf_m3u8_skin_seasonal_migrate_from_legacy_v12216();
if (($result['status'] ?? '') !== 'PASS' || ($result['code'] ?? '') !== 'NOT_APPLICABLE_WITH_PROOF' || !empty($result['canRetireLegacy'])) {
    throw new RuntimeException('isolated initial migration failed to establish protected empty legacy baseline');
}
require '/tmp/r2-wordpress-fixture.php';
echo PHP_EOL . 'S01_R2_ISOLATED_WORDPRESS=PASS' . PHP_EOL;
