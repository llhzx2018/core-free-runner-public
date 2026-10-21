<?php
// Request-local copy fixture; no persistent changes and never packaged.
$copy_fixture = static function ($raw) {
    $variant = (string)($_GET['vf_tool_review'] ?? '');
    if (!in_array($variant, ['legacycopy', 'customcopy'], true)) { return $raw; }
    $raw = is_array($raw) ? $raw : [];
    $raw['moduleSettings']['tool']['related_tools']['override'] = true;
    $raw['moduleSettings']['tool']['related_tools']['description'] = $variant === 'legacycopy' ? 'Move to another focused tool when the task changes.' : 'Owner custom next-tool description';
    return $raw;
};
add_filter('option_vf_theme_layout', $copy_fixture, 10003);
add_filter('default_option_vf_theme_layout', $copy_fixture, 10003);
