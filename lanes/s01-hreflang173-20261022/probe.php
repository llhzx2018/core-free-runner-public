<?php
if (!defined('ABSPATH')) { exit; }
// Polylang Free cannot route Pro shared slugs after the established SQL fixture.
// Bridge only native request selection for the three declared synthetic pairs;
// do not replace the URL resolver, page-family classifier or SEO Head services.
add_filter('request', static function (array $query): array {
    if (is_admin()) { return $query; }
    $path = (string)parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH);
    if (!preg_match('#^/(zh/)?(m3u8-test-links|m3u8-browser-stream-test|m3u8-player)/$#', $path, $match)) { return $query; }
    $language = !empty($match[1]) ? 'zh' : 'en';
    $pairs = get_option('vf_s01_canonical_head_fixture', []);
    $id = (int)($pairs[$match[2]][$language] ?? 0);
    if ($id <= 0 || get_post_status($id) !== 'publish' || pll_get_post_language($id, 'slug') !== $language) { throw new RuntimeException('SYNTHETIC_SHARED_SLUG_QUERY_TARGET_INVALID'); }
    unset($query['pagename'], $query['name'], $query['p']);
    $query['page_id'] = $id;
    $query['post_type'] = 'page';
    $query['lang'] = $language;
    return $query;
}, 9999);
// Synthetic isolated runtime only: observe after the unchanged request has rendered.
add_action('shutdown', static function () {
    $path = (string)parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH);
    if (!preg_match('#^/(?:zh/)?m3u8-(?:test-links|browser-stream-test)/$#', $path)) { return; }
    if (!function_exists('vf_theme_get_hreflang_state')) { return; }
    $route = preg_replace('#^zh/#', '', trim($path, '/'));
    $lang = str_starts_with($path, '/zh/') ? 'zh' : 'en';
    $selected = vf_theme_url_resolver_resolve(['route'=>$route, 'language'=>$lang, 'purpose'=>'public']);
    $row = ['version'=>wp_get_theme()->get('Version'), 'request'=>$path, 'post_id'=>get_queried_object_id(), 'selected'=>$selected, 'state'=>vf_theme_get_hreflang_state('')];
    file_put_contents('/tmp/href-diagnostics.ndjson', wp_json_encode($row) . "\n", FILE_APPEND);
}, 9999);
