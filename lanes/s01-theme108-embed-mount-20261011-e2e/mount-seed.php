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
    if ($toolId === 'segment-list-viewer') {
        // Theme current public route contract: src/inc/routes/static-routes-core.php.
        // This is a synthetic Page Mount choice, not an alternate product resolver.
        $route = 'm3u8-segment-viewer';
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
// Two existing WordPress Page Mount languages, both consuming the same
// canonical plugin shortcode. This is synthetic fixture data only.
$embed_en = get_page_by_path('m3u8-embed-generator', OBJECT, 'page');
if (!$embed_en instanceof WP_Post) {
    $embed_en = wp_insert_post([
        'post_type' => 'page', 'post_status' => 'publish',
        'post_name' => 'm3u8-embed-generator', 'post_title' => 'Synthetic Embed Generator',
        'post_content' => '[vf_m3u8_embed]',
    ], true);
    if (is_wp_error($embed_en)) { throw new RuntimeException('SYNTHETIC_EMBED_EN_CREATE_FAILED'); }
    $embed_en = get_post((int)$embed_en);
}
pll_set_post_language((int)$embed_en->ID, 'en');
// Create translation as draft, assign Polylang ownership and pair both
// pages BEFORE publishing; otherwise WordPress reserves a "-2" slug while the
// new page still has no locale (unlike the real Production Page Mount).
$embed_zh_id = wp_insert_post([
    'post_type' => 'page', 'post_status' => 'draft',
    'post_name' => 'm3u8-embed-generator', 'post_title' => 'Synthetic ZH Embed Generator',
    'post_content' => '[vf_m3u8_embed]',
], true);
if (is_wp_error($embed_zh_id)) { throw new RuntimeException('SYNTHETIC_EMBED_ZH_CREATE_FAILED'); }
pll_set_post_language((int)$embed_zh_id, 'zh');
pll_save_post_translations(['en' => (int)$embed_en->ID, 'zh' => (int)$embed_zh_id]);
$published_zh = wp_update_post([
    'ID' => (int)$embed_zh_id, 'post_status' => 'publish',
    'post_name' => 'm3u8-embed-generator',
], true);
if (is_wp_error($published_zh)) {
    throw new RuntimeException('SYNTHETIC_EMBED_ZH_PUBLISH_FAILED');
}
// The isolated runner has Polylang Free; Production uses Polylang Pro, which
// permits paired EN/ZH pages to share their translated slug. Mirror that
// already-observed Production fixture state directly in the throwaway DB.
// NEVER use this workaround on a real site or for product migration.
if (get_post_field('post_name', (int)$embed_zh_id) !== 'm3u8-embed-generator') {
    global $wpdb;
    $changed = $wpdb->update($wpdb->posts, ['post_name' => 'm3u8-embed-generator'], ['ID' => (int)$embed_zh_id], ['%s'], ['%d']);
    if ($changed !== 1) { throw new RuntimeException('SYNTHETIC_POLYLANG_PRO_SLUG_MIRROR_FAILED'); }
    clean_post_cache((int)$embed_zh_id);
}
if (get_post_field('post_name', (int)$embed_zh_id) !== 'm3u8-embed-generator') {
    throw new RuntimeException('SYNTHETIC_EMBED_ZH_CANONICAL_SLUG_MISMATCH');
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
