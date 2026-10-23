<?php
// Synthetic canonical tool pages only; no extra duplicate tool-page fixtures.
if (!defined('ABSPATH')) { exit(1); }
$out = [];
$bindings = (array)(vf_m3u8_mounts_data(true)['bindings'] ?? []);
foreach (['m3u8-test-links'=>'test-links','m3u8-browser-stream-test'=>'browser-stream-test','m3u8-player'=>'player'] as $route => $tool) {
    $pair = [];
    foreach (['en','zh'] as $lang) {
        $rows = array_values(array_filter($bindings, static fn($row): bool => ($row['toolId'] ?? '') === $tool && ($row['language'] ?? '') === $lang));
        if (count($rows) !== 1) { throw new RuntimeException('OWNER_BINDING_NOT_UNIQUE:' . $tool . ':' . $lang); }
        $id = (int)$rows[0]['pageId'];
        $post = get_post($id);
        if (!$post || $post->post_status !== 'publish' || pll_get_post_language($id, 'slug') !== $lang) { throw new RuntimeException('OWNER_BINDING_LANGUAGE_OR_STATUS_INVALID'); }
        $body = '<p>Authorized public diagnostic reference, synthetic authored page.</p>' . $post->post_content . '<h2>Usage</h2><p>Inspect an authorized manifest and review the result.</p>';
        wp_update_post(['ID'=>$id,'post_content'=>$body]);
        // Mirror the established Pro same-slug fixture after the Provider write.
        // Only this throwaway database is adjusted; no production data is used.
        global $wpdb;
        $wpdb->update($wpdb->posts, ['post_name'=>$route], ['ID'=>$id], ['%s'], ['%d']);
        clean_post_cache($id);
        if (get_post_field('post_name',$id) !== $route) { throw new RuntimeException('FINAL_CANONICAL_SLUG_MISMATCH'); }
        $url = 'http://127.0.0.1:18880/' . ($lang === 'zh' ? 'zh/' : '') . $route . '/';
        update_post_meta($id, 'rank_math_title', 'Synthetic public diagnostic ' . $lang);
        update_post_meta($id, 'rank_math_description', 'Synthetic authorized tool guidance.');
        update_post_meta($id, 'rank_math_canonical_url', $url);
        $pair[$lang] = $id;
    }
    if ($pair['en'] === $pair['zh']) { throw new RuntimeException('DISTINCT_TRANSLATIONS_REQUIRED'); }
    pll_save_post_translations($pair);
    foreach ($pair as $lang => $id) {
        $actual = pll_get_post_translations($id); ksort($actual); $expected = $pair; ksort($expected);
        if ($actual !== $expected) { throw new RuntimeException('NATIVE_PAIR_READBACK_FAILED'); }
    }
    $out[$route] = $pair;
}
// A real published WordPress Page exercises the page-type fallback without
// depending on the unproven Production tool-route trigger. No SEO API is mocked.
$route = 'public-stream-test-reference';
$pair = [];
foreach (['en','zh'] as $lang) {
    $id = wp_insert_post(['post_type'=>'page','post_status'=>'draft','post_name'=>$route,'post_title'=>'Public stream test reference '.$lang,'post_content'=>'<h2>Published reference</h2><p>Authored public reference retained across upgrade and rollback.</p>'], true);
    if (is_wp_error($id) || !$id) { throw new RuntimeException('PUBLIC_REFERENCE_INSERT_FAILED'); }
    pll_set_post_language($id, $lang);
    update_post_meta($id, '_wp_page_template', 'page-basic.php');
    wp_update_post(['ID'=>$id,'post_status'=>'publish','post_name'=>$route]);
    global $wpdb;
    $wpdb->update($wpdb->posts, ['post_name'=>$route], ['ID'=>$id], ['%s'], ['%d']);
    clean_post_cache($id);
    $url = 'http://127.0.0.1:18880/' . ($lang === 'zh' ? 'zh/' : '') . $route . '/';
    update_post_meta($id, 'rank_math_title', 'Public stream test reference '.$lang);
    update_post_meta($id, 'rank_math_description', 'A published diagnostic reference.');
    update_post_meta($id, 'rank_math_canonical_url', $url);
    $pair[$lang] = (int)$id;
}
pll_save_post_translations($pair);
foreach ($pair as $lang=>$id) {
    $actual = pll_get_post_translations($id); ksort($actual); $expected = $pair; ksort($expected);
    if ($actual !== $expected || pll_get_post_language($id,'slug') !== $lang || get_post_status($id) !== 'publish') { throw new RuntimeException('PUBLIC_REFERENCE_NATIVE_RELATION_INVALID'); }
}
$out[$route] = $pair;
// Real unpublished content remains inaccessible and must never emit hreflang.
$draft = wp_insert_post(['post_type'=>'page','post_status'=>'draft','post_name'=>'unpublished-test-reference','post_title'=>'Unpublished reference','post_content'=>'This draft must not become public.'], true);
if (is_wp_error($draft) || !$draft) { throw new RuntimeException('DRAFT_REFERENCE_INSERT_FAILED'); }
pll_set_post_language($draft, 'en');
update_option('vf_s01_canonical_head_fixture', $out, false);
update_option('vf_theme_seo', ['searchIndexability'=>'noindex_follow','previewIndexability'=>'noindex_follow','notFoundRobots'=>'noindex_follow','virtualRoutePolicy'=>[['routeId'=>'tool_hub','pageFamily'=>'tool_hub','pathPattern'=>'tools','resolver'=>'vf_theme_url_resolver','canonicalPolicy'=>'self','hreflangPolicy'=>'paired','indexability'=>'index_follow','staticPathPolicy'=>'required']],'schemaVersion'=>'1.0.0'], false);
echo wp_json_encode(['status'=>'PASS','canonical_pairs'=>$out,'seo_fixture'=>'production-equivalent registered tool-hub policy; no tool override','production'=>'UNTOUCHED']);
