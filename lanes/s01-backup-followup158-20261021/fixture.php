<?php
// Synthetic, request-local Theme settings. Never persisted or packaged.
$backup_copy_fixture = static function ($raw) {
    $variant = (string)($_GET['vf_backup_review'] ?? '');
    if (!in_array($variant, ['legacy', 'custom'], true)) { return $raw; }
    $raw = is_array($raw) ? $raw : [];
    $rows = [
        'related_tools' => ['Switch tools when the task changes', 'Move to another focused tool when the task changes.'],
        'cta' => ['Turn the answer into action.', 'Open the checker or player to test the issue described on this page.'],
        'faq' => ['Questions worth checking before you retry', 'Check the most common access, format, and browser limits before switching to a diagnostic tool.'],
    ];
    foreach ($rows as $module => $copy) {
        $raw['moduleSettings']['tool'][$module]['override'] = true;
        $raw['moduleSettings']['tool'][$module]['title'] = $variant === 'custom' ? 'Owner '.$module.' title' : $copy[0];
        $raw['moduleSettings']['tool'][$module]['description'] = $variant === 'custom' ? 'Owner '.$module.' description' : $copy[1];
    }
    return $raw;
};
add_filter('option_vf_theme_layout', $backup_copy_fixture, 10003);
add_filter('default_option_vf_theme_layout', $backup_copy_fixture, 10003);
