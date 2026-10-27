<?php
/**
 * One-shot isolated WordPress smoke for Theme PR #346 exact candidate.
 * No Production credentials, network actions or Provider domain mutation.
 */
if (!defined('ABSPATH')) { throw new RuntimeException('WORDPRESS_BOOTSTRAP_REQUIRED'); }

$checks = [];
function s01_theme346_gate(bool $ok, string $name): void {
    if (!$ok) { throw new RuntimeException('THEME346_GATE_FAILED: '.$name); }
    $GLOBALS['checks'][] = ['name' => $name, 'pass' => true];
}
$theme = wp_get_theme();
s01_theme346_gate($theme->get_stylesheet() === 'vf-tools-theme', 'activated_exact_theme_slug');
s01_theme346_gate($theme->get('Version') === '1.35.212', 'actual_wordpress_theme_version');
s01_theme346_gate(function_exists('vf_theme_module_render_tool_hero'), 'actual_theme_tool_hero_renderer_loaded');
s01_theme346_gate(function_exists('pll_set_post_language'), 'polylang_loaded');
$runtime = get_stylesheet_directory().'/assets/css/public/vf-theme-public-runtime.css';
s01_theme346_gate(is_file($runtime), 'runtime_css_present_in_installed_theme');
s01_theme346_gate(hash_file('sha256', $runtime) === '302555de59d3219f3a55e3b761826975d2638089618300f2b8a4a3840aec7117', 'installed_runtime_css_exact_hash');

foreach (['m3u8-downloader', 'm3u8-to-mp4'] as $route) {
    $context = ['route' => $route, 'title' => 'Synthetic authorized task',
        'description' => 'Synthetic safe media task.',
        'field_data' => ['eyebrow' => $route === 'm3u8-downloader' ? 'Downloader' : 'Converter']];
    ob_start();
    vf_theme_module_render_tool_hero($context);
    $html = (string)ob_get_clean();
    s01_theme346_gate(str_contains($html, 'data-vf-tool-route="'.$route.'"'), $route.'_route');
    s01_theme346_gate(substr_count($html, '<h1>') === 1, $route.'_single_h1');
    s01_theme346_gate(!str_contains($html, 'vf-tool-breadcrumb'), $route.'_no_duplicate_breadcrumb');
    s01_theme346_gate(!str_contains($html, 'vf-tool-hero-actions'), $route.'_no_duplicate_action');
    s01_theme346_gate(str_contains($html, 'vf-tool-hero-meta'), $route.'_trust_facts');
}
ob_start();
vf_theme_module_render_tool_hero(['route' => 'm3u8-playlist-checker', 'title' => 'Synthetic neighbor tool']);
$neighbor = (string)ob_get_clean();
s01_theme346_gate(str_contains($neighbor, 'vf-tool-breadcrumb'), 'other_tool_breadcrumb_preserved');
s01_theme346_gate(str_contains($neighbor, 'vf-tool-hero-actions'), 'other_tool_actions_preserved');
foreach (['en', 'zh'] as $language) {
    $id = wp_insert_post([
        'post_type' => 'page', 'post_status' => 'publish',
        'post_title' => 'Synthetic S01 #346 '.$language,
        'post_content' => 'Isolated synthetic WordPress page.',
        'post_name' => 's01-theme346-'.$language,
    ], true);
    s01_theme346_gate(!is_wp_error($id) && (int)$id > 0, 'synthetic_page_created_'.$language);
    pll_set_post_language((int)$id, $language);
    s01_theme346_gate(pll_get_post_language((int)$id) === $language, 'synthetic_page_language_'.$language);
}
echo wp_json_encode([
    'status' => 'PASS', 'checks' => $checks, 'count' => count($checks),
    'version' => '1.35.212', 'source_sha' => '353241c626b2ff549c848e61fd48fed5c7ef15d9',
    'production' => 'NOT_EXECUTED',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
