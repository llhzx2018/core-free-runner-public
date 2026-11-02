<?php
// Executed in a disposable synthetic WordPress instance via WP-CLI.
if (!defined('ABSPATH')) { exit(3); }
$names = [
    'vf_tool_m3u8_settings',
    'vf_m3u8_skin_seasonal_settings',
    'vf_m3u8_custom_skin_registry',
    'vf_m3u8_custom_seasonal_registry',
    'vf_m3u8_skin_seasonal_migration_evidence',
    'vf_m3u8_skin_seasonal_migration_snapshot',
    'vf_m3u8_skin_seasonal_migration_version',
    'vf_m3u8_fixture_user_setting'
];
$result = [];
$sentinel = '__S01_R2_ABSENT__';
foreach ($names as $name) {
    $value = get_option($name, $sentinel);
    $result[$name] = [
        'present' => ($value !== $sentinel),
        'sha256' => hash('sha256', serialize($value)),
    ];
}
if (empty($result['vf_m3u8_skin_seasonal_migration_snapshot']['present'])
    || empty($result['vf_m3u8_skin_seasonal_migration_evidence']['present'])
    || empty($result['vf_m3u8_fixture_user_setting']['present'])) {
    throw new RuntimeException('Required synthetic protected options not present');
}
if (!class_exists('VF_M3U8_Update_State_V1')) { throw new RuntimeException('Provider state class missing'); }
$state = VF_M3U8_Update_State_V1::snapshot();
if (is_wp_error($state)) { throw new RuntimeException('Provider snapshot failed: '.$state->get_error_code()); }
ksort($result);
echo wp_json_encode([
    'status' => 'PASS',
    'protected_options' => $result,
    'provider_state_sha256' => $state['fingerprint_sha256'],
    'provider_table_count' => count($state['tables'] ?? [])
], JSON_UNESCAPED_SLASHES), "\n";
