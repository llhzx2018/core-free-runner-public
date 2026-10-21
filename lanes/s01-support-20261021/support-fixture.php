<?php
// Request-local synthetic content states; never installed on Production or packaged.
add_filter('the_content', static function ($html) {
    if (($_GET['vf_support_review'] ?? '') !== '1') { return $html; }
    $state = isset($_GET['review_state']) && is_scalar($_GET['review_state']) ? (string)$_GET['review_state'] : '';
    if (!is_page(['contact', 'privacy-policy'])) { return $html; }
    if ($state === 'empty') { return ''; }
    if ($state === 'information' && is_page('contact')) { return '<p>Owner informational guidance only</p>'; }
    return $html;
}, PHP_INT_MAX);

$description = static function ($raw) {
    if (($_GET['vf_support_review'] ?? '') !== '1') { return $raw; }
    $state = isset($_GET['review_state']) && is_scalar($_GET['review_state']) ? (string)$_GET['review_state'] : '';
    if (!in_array($state, ['stale-description', 'authored-description'], true)) { return $raw; }
    $raw = is_array($raw) ? $raw : [];
    $raw['moduleSettings']['problem_index']['post_list']['override'] = true;
    $raw['moduleSettings']['problem_index']['post_list']['description'] = $state === 'stale-description'
        ? 'List error explanations as a real recovery center.' : 'Owner authored diagnostic description retained.';
    return $raw;
};
add_filter('option_vf_theme_layout', $description, 10003);
add_filter('default_option_vf_theme_layout', $description, 10003);
