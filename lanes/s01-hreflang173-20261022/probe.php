<?php
if (!defined('ABSPATH')) { exit; }
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
