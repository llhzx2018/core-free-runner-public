<?php
// Synthetic WordPress only. Exercise the existing canonical M3U8 Page Mounts
// transaction; never write a second URL registry or Production state.
if (!function_exists('vf_m3u8_save_mount_transaction') || !function_exists('pll_set_post_language')) {
    throw new RuntimeException('CANONICAL_MOUNT_AND_POLYLANG_NOT_AVAILABLE');
}
$registry = vf_m3u8_mounts_tool_registry();
$bindings = [];
$routes = [];
foreach ($registry as $toolId => $def) {
    $route = trim((string)($def['public_route'] ?? ''), '/');
    // Consume the installed Theme's existing public route rather than inventing
    // a second slug for the same canonical M3U8 segment viewer tool.
    if ($toolId === 'segment-list-viewer' && function_exists('vf_toolsite_static_routes')) {
        $realRoutes = vf_toolsite_static_routes();
        if (isset($realRoutes['m3u8-segment-viewer'])) { $route = 'm3u8-segment-viewer'; }
    }
    $shortcode = trim((string)($def['shortcode'] ?? ''));
    if ($route === '' || $shortcode === '') {
        throw new RuntimeException('MISSING_CANONICAL_TOOL_ROUTE_OR_SHORTCODE:' . $toolId);
    }
    $existing = get_page_by_path($route, OBJECT, 'page');
    if ($existing instanceof WP_Post && $existing->post_status === 'publish') {
        $id = (int)$existing->ID;
    } else {
        $id = wp_insert_post([
            'post_type' => 'page',
            'post_status' => 'publish',
            'post_name' => $route,
            'post_title' => 'Synthetic ' . (string)($def['label'] ?? $toolId),
            'post_content' => '[' . $shortcode . ']',
        ], true);
    }
    if (is_wp_error($id) || (int)$id <= 0) {
        throw new RuntimeException('CANONICAL_PAGE_RESOLUTION_FAILED:' . $toolId);
    }
    if (get_post_field('post_name', (int)$id) !== $route) {
        throw new RuntimeException('DUPLICATE_ROUTE_SUFFIX_REJECTED:' . $toolId);
    }
    pll_set_post_language((int)$id, 'en');
    $bindings[] = ['toolId' => $toolId, 'language' => 'en', 'pageId' => (int)$id];
    $routes[$toolId] = get_permalink((int)$id);
}
$before = vf_m3u8_mounts_data();
$result = vf_m3u8_save_mount_transaction($bindings, 'shortcode', (int)$before['revision'], 1);
if (($result['status'] ?? '') !== 'PASS' || ($result['stages']['verify'] ?? '') !== 'PASS') {
    throw new RuntimeException('CANONICAL_MOUNT_TRANSACTION_FAILED:' . wp_json_encode([
        'code' => $result['code'] ?? 'UNKNOWN',
        'stages' => $result['stages'] ?? [],
        'issues' => $result['issues'] ?? [],
        'pageResult' => $result['pageResult']['code'] ?? '',
    ]));
}
$readback = vf_m3u8_mounts_data(true);
if (count($readback['bindings']) !== count($bindings)) {
    throw new RuntimeException('MOUNT_READBACK_INCOMPLETE');
}
foreach (['player','segment-list-viewer','playlist-checker','browser-stream-test'] as $id) {
    $found = false;
    foreach ($readback['bindings'] as $binding) {
        if (($binding['toolId'] ?? '') === $id && ($binding['language'] ?? '') === 'en' && !empty($binding['pageId']) && get_permalink((int)$binding['pageId']) === $routes[$id]) { $found = true; break; }
    }
    if (empty($routes[$id]) || !$found) {
        throw new RuntimeException('MOUNT_URL_NOT_CANONICAL:' . $id);
    }
}
echo wp_json_encode([
    'status' => 'PASS',
    'configured_through' => 'vf_m3u8_save_mount_transaction',
    'binding_count' => count($bindings),
    'revision' => (int)$readback['revision'],
    'player_path' => wp_parse_url($routes['player'], PHP_URL_PATH),
    'segment_path' => wp_parse_url($routes['segment-list-viewer'], PHP_URL_PATH),
    'production' => 'NOT_EXECUTED',
]);
