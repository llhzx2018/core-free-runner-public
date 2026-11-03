<?php
/**
 * S01 R8 real WordPress/MariaDB migration historical option-value proof.
 * This fixture is used only by disposable wp-cli. It does not contain user data.
 * Phase: baseline (after prior main installation) or verify (after each code change).
 */
if (!defined('ABSPATH')) { throw new RuntimeException('WORDPRESS_REQUIRED'); }
$phase = (string)getenv('S01_R8_SKIN_PHASE');
$receipt = '/tmp/s01-r8-skin-raw-option-hashes.json';
if (!in_array($phase, ['baseline', 'verify', 'guard'], true)) {
    throw new RuntimeException('UNSUPPORTED_FIXTURE_PHASE');
}
$keys = [
    'vf_tool_m3u8_settings',
    'vf_m3u8_skin_seasonal_migration_snapshot',
    'vf_m3u8_skin_seasonal_migration_evidence',
    'vf_m3u8_skin_seasonal_migration_version',
];
global $wpdb;
$read = static function() use ($wpdb, $keys): array {
    $rows = [];
    foreach ($keys as $key) {
        $raw = $wpdb->get_var($wpdb->prepare(
            "SELECT option_value FROM {$wpdb->options} WHERE option_name = %s LIMIT 1", $key
        ));
        $rows[$key] = [
            'present' => $raw !== null,
            'length' => $raw === null ? null : strlen((string)$raw),
            'sha256' => $raw === null ? null : hash('sha256', (string)$raw),
        ];
    }
    return $rows;
};
$must = static function(bool $ok, string $message): void {
    if (!$ok) { throw new RuntimeException('S01_R8_SKIN_DB_' . $message); }
};
if (!function_exists('vf_m3u8_skin_seasonal_migrate_from_legacy_v12216')) {
    throw new RuntimeException('SKIN_MIGRATION_RUNTIME_MISSING');
}
if ($phase === 'baseline') {
    $first = vf_m3u8_skin_seasonal_migrate_from_legacy_v12216();
    $must(($first['status'] ?? '') === 'PASS', 'BASELINE_MIGRATION_NOT_PASS');
    $snapshot = get_option('vf_m3u8_skin_seasonal_migration_snapshot', null);
    $evidence = get_option('vf_m3u8_skin_seasonal_migration_evidence', null);
    $must(is_array($snapshot) && $snapshot['artifactType'] === 'skin-seasonal-legacy-migration-snapshot', 'SNAPSHOT_MISSING');
    $must(is_array($evidence) && ($evidence['status'] ?? '') === 'PASS', 'EVIDENCE_MISSING');
    $must(((int)($evidence['legacyFoundCount'] ?? 0)) > 0, 'NONEMPTY_LEGACY_REQUIRED');
    $must(((int)($snapshot['legacy']['legacyFoundCount'] ?? 0)) > 0, 'SNAPSHOT_NONEMPTY_REQUIRED');
    $rows = $read();
    foreach ($rows as $key => $row) { $must($row['present'], 'BASELINE_KEY_ABSENT_' . $key); }
    if (file_put_contents($receipt, json_encode($rows, JSON_PRETTY_PRINT|JSON_THROW_ON_ERROR)) === false) {
        throw new RuntimeException('RECEIPT_WRITE_FAILED');
    }
    echo "S01_R8_SKIN_DB_NONEMPTY_HISTORICAL_BASELINE=PASS\n";
} elseif ($phase === 'verify') {
    $must(is_file($receipt), 'BASELINE_RECEIPT_MISSING');
    $expected = json_decode((string)file_get_contents($receipt), true, 512, JSON_THROW_ON_ERROR);
    $actual = $read();
    foreach ($expected as $key => $value) {
        $must($value === ($actual[$key] ?? null), 'RAW_BYTE_MISMATCH_' . $key);
    }
    $snapshot = get_option('vf_m3u8_skin_seasonal_migration_snapshot', null);
    $evidence = get_option('vf_m3u8_skin_seasonal_migration_evidence', null);
    $must(is_array($snapshot) && is_array($evidence), 'HISTORICAL_DATA_NOT_ARRAY');
    $must(($evidence['legacyHashes'] ?? null) === ($snapshot['legacy']['legacyHashes'] ?? null), 'EVIDENCE_SNAPSHOT_HASH_MISMATCH');
    echo "S01_R8_SKIN_DB_MIGRATION_RAW_OPTION_VALUE_BYTES=PASS 4/4\n";
} else {
    // The historical baseline is protected even when a later legacy setting
    // changes or the snapshot becomes malformed. The test mutates an isolated
    // WordPress DB only; all changes are restored inside this fixture.
    $expected = json_decode((string)file_get_contents($receipt), true, 512, JSON_THROW_ON_ERROR);
    $before = $read();
    foreach ($expected as $key => $value) { $must($value === ($before[$key] ?? null), 'PRE_GUARD_DRIFT_' . $key); }
    $legacy = get_option('vf_tool_m3u8_settings', []);
    $must(is_array($legacy), 'LEGACY_NOT_ARRAY');
    $legacyBefore = $legacy;
    try {
        $legacy['frontend_base_skin'] = 'r8_changed_after_baseline';
        update_option('vf_tool_m3u8_settings', $legacy, false);
        $protected = $read();
        $attempt = vf_m3u8_skin_seasonal_migrate_from_legacy_v12216();
        $must(($attempt['status'] ?? '') === 'FAIL'
            && ($attempt['code'] ?? '') === 'MIGRATION_LEGACY_CHANGED_REVIEW_REQUIRED', 'CHANGED_LEGACY_NOT_BLOCKED');
        $after = $read();
        $must($after === $protected, 'CHANGED_LEGACY_WROTE_MIGRATION_OPTIONS');
        echo "S01_R8_SKIN_DB_CHANGED_LEGACY_FAIL_CLOSED=PASS\n";
    } finally {
        // Restore this isolated fixture's actual pre-test value, not a guessed constant.
        update_option('vf_tool_m3u8_settings', $legacyBefore, false);
    }
    $after = $read();
    foreach ($expected as $key => $value) { $must($after[$key] === $value, 'AFTER_GUARD_RAW_DRIFT_' . $key); }
    echo "S01_R8_SKIN_DB_POST_GUARD_RAW_BYTES=PASS\n";
}
