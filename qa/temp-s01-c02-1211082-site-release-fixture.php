<?php
// Isolated GitHub Actions ephemeral WordPress fixture only. Never Production.
if (!defined('ABSPATH')) { exit(1); }
$base=WP_PLUGIN_DIR.'/vf-ops/includes/site-release/';
foreach (['contract.php','validation.php','audit.php','manifest.php','repository.php','service.php'] as $file) {
    require_once $base.$file;
}
wp_set_current_user(1);
$before=vf_ops_site_release_readback_v121453();
$raw=vf_ops_site_release_defaults_v121453();
$raw['publicBaseUrl']='https://example.com';
$raw['inputMode']='zip';
$raw['requiredPaths']=['/','/tools/'];
$result=vf_ops_save_site_release_transaction($raw,(int)$before['revision'],'isolated-publish-goldenpath');
if (empty($result['ok'])) {
    throw new RuntimeException('Isolated site-release save failed: '.wp_json_encode($result));
}
$after=vf_ops_site_release_readback_v121453();
if ((int)$after['revision']<=0 || !$after['configHash'] || $after['publicBaseUrl']!=='https://example.com') {
    throw new RuntimeException('Isolated site-release readback mismatch');
}
echo "ISOLATED_CONFIG_CANONICAL_SAVE_READBACK=PASS\n";
