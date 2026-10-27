<?php
// Public-safe synthetic descriptor: proves a workspace link is shown without a pending update.
add_filter('vf_wp_update_components_v1', static function ($components): array {
    $components = is_array($components) ? $components : [];
    $components['S01-C03'] = [
        'component_id' => 'S01-C03',
        'name' => 'Synthetic VF Component',
        'type' => 'PLUGIN',
        'current_version' => '1.0.0',
        'target_version' => '1.0.0',
        'state' => 'UP_TO_DATE',
        'manage_url' => admin_url('admin.php?page=vf-toolsite-ops'),
    ];
    return $components;
}, 20);
