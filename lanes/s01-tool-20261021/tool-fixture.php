<?php
// Request-local synthetic Provider failure. No database writes, never packaged.
add_filter('pre_do_shortcode_tag', static function ($output, $tag) {
    if (($_GET['vf_tool_review'] ?? '') === 'missing' && $tag === 'vf_m3u8_player') { return ' '; }
    return $output;
}, PHP_INT_MAX, 2);
