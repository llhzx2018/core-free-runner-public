<?php
// Disposable WordPress fixture for Theme PR #343. Synthetic accounts and content only.
if (!defined('ABSPATH')) { throw new RuntimeException('WORDPRESS_BOOTSTRAP_REQUIRED'); }
if (!post_type_exists('vf_guide') || !function_exists('pll_set_post_language')) {
    throw new RuntimeException('GUIDE_OR_POLYLANG_FIXTURE_MISSING');
}
$existing = get_user_by('login', 'subscriber');
if (!$existing) {
    $id = wp_create_user('subscriber', 'Synthetic-Only-Not-For-Login', 'subscriber@example.invalid');
    if (is_wp_error($id)) { throw new RuntimeException('SYNTHETIC_SUBSCRIBER_CREATE_FAILED'); }
    $existing = get_user_by('id', (int) $id);
}
$existing->set_role('subscriber');
$counts = ['en' => 26, 'zh' => 3];
foreach ($counts as $language => $total) {
    for ($i = 1; $i <= $total; $i++) {
        $id = wp_insert_post([
            'post_type' => 'vf_guide',
            'post_status' => 'publish',
            'post_title' => sprintf('Directory Fixture %s %02d', strtoupper($language), $i),
            'post_content' => 'Synthetic guide content; isolated machine proof only.',
            'post_excerpt' => 'Synthetic guide excerpt.',
        ], true);
        if (is_wp_error($id) || !$id) { throw new RuntimeException('GUIDE_SEED_FAILED'); }
        pll_set_post_language((int) $id, $language);
    }
}
foreach ($counts as $language => $expected) {
    $q = new WP_Query(['post_type' => 'vf_guide', 'post_status' => 'publish',
        'posts_per_page' => 50, 's' => 'Directory Fixture', 'lang' => $language]);
    if ((int) $q->found_posts !== $expected) {
        throw new RuntimeException('SYNTHETIC_GUIDE_QUERY_COUNT_'.strtoupper($language).'_'.(int)$q->found_posts.'_EXPECTED_'.$expected);
    }
}
echo wp_json_encode(['status' => 'PASS', 'synthetic_guides' => $counts,
    'synthetic_subscriber' => true, 'production' => 'UNTOUCHED'], JSON_UNESCAPED_UNICODE);
