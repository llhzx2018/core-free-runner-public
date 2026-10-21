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
