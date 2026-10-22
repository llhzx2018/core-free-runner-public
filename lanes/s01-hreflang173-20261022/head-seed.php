<?php
// Synthetic canonical tool pages only; no extra duplicate tool-page fixtures.
if (!defined('ABSPATH')) { exit(1); }
$out = [];
foreach (['m3u8-test-links','m3u8-browser-stream-test','m3u8-player'] as $route) {
    $pair = [];
    foreach (['en','zh'] as $lang) {
        $posts = get_posts(['post_type'=>'page','post_status'=>'publish','name'=>$route,'lang'=>$lang,'numberposts'=>3,'suppress_filters'=>false]);
        if (count($posts) !== 1) { throw new RuntimeException('CANONICAL_FIXTURE_NOT_UNIQUE:' . $route . ':' . $lang); }
        $post = $posts[0];
        $body = '<p>Authorized public diagnostic reference, synthetic authored page.</p>' . $post->post_content . '<h2>Usage</h2><p>Inspect an authorized manifest and review the result.</p>';
        wp_update_post(['ID'=>$post->ID,'post_content'=>$body]);
        $pair[$lang] = (int)$post->ID;
    }
    pll_save_post_translations($pair);
    $out[$route] = $pair;
}
update_option('vf_theme_seo', ['searchIndexability'=>'noindex_follow','previewIndexability'=>'noindex_follow','notFoundRobots'=>'noindex_follow','virtualRoutePolicy'=>[['routeId'=>'tool_hub','pageFamily'=>'tool_hub','pathPattern'=>'tools','resolver'=>'vf_theme_url_resolver','canonicalPolicy'=>'self','hreflangPolicy'=>'paired','indexability'=>'index_follow','staticPathPolicy'=>'required']],'schemaVersion'=>'1.0.0'], false);
echo wp_json_encode(['status'=>'PASS','canonical_pairs'=>$out,'seo_fixture'=>'production-equivalent registered tool-hub policy; no tool override','production'=>'UNTOUCHED']);
