<?php
// Synthetic canonical tool pages only; no extra duplicate tool-page fixtures.
if (!defined('ABSPATH')) { exit(1); }
$out = [];
foreach (['m3u8-test-links','m3u8-browser-stream-test','m3u8-player'] as $route) {
    $pair = [];
    foreach (['en','zh'] as $lang) {
        $posts = array_values(array_filter(get_posts(['post_type'=>'page','post_status'=>'publish','numberposts'=>-1,'lang'=>'','suppress_filters'=>true]), static fn($p): bool => $p->post_name === $route && pll_get_post_language($p->ID, 'slug') === $lang));
        if (count($posts) !== 1) { throw new RuntimeException('CANONICAL_FIXTURE_NOT_UNIQUE:' . $route . ':' . $lang); }
        $post = $posts[0];
        $body = '<p>Authorized public diagnostic reference, synthetic authored page.</p>' . $post->post_content . '<h2>Usage</h2><p>Inspect an authorized manifest and review the result.</p>';
        wp_update_post(['ID'=>$post->ID,'post_content'=>$body]);
        $pair[$lang] = (int)$post->ID;
    }
    if ($pair['en'] === $pair['zh']) { throw new RuntimeException('DISTINCT_TRANSLATIONS_REQUIRED'); }
    pll_save_post_translations($pair);
    foreach ($pair as $lang => $id) { if (pll_get_post_translations($id) !== $pair) { $actual = pll_get_post_translations($id); ksort($actual); $expected = $pair; ksort($expected); if ($actual !== $expected) { throw new RuntimeException('NATIVE_PAIR_READBACK_FAILED'); } } }
    $out[$route] = $pair;
}
update_option('vf_theme_seo', ['searchIndexability'=>'noindex_follow','previewIndexability'=>'noindex_follow','notFoundRobots'=>'noindex_follow','virtualRoutePolicy'=>[['routeId'=>'tool_hub','pageFamily'=>'tool_hub','pathPattern'=>'tools','resolver'=>'vf_theme_url_resolver','canonicalPolicy'=>'self','hreflangPolicy'=>'paired','indexability'=>'index_follow','staticPathPolicy'=>'required']],'schemaVersion'=>'1.0.0'], false);
echo wp_json_encode(['status'=>'PASS','canonical_pairs'=>$out,'seo_fixture'=>'production-equivalent registered tool-hub policy; no tool override','production'=>'UNTOUCHED']);
