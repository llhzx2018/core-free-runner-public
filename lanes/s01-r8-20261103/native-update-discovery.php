<?php
// S01 R8 isolated WP native update_plugins offer discovery; synthetic HTTP only.
// Executed via wp-cli eval-file inside transient WordPress fixture (not Production).
if (!defined('ABSPATH')) { exit(2); }
if (!class_exists('VF_M3U8_Update_Client_V1')) { throw new RuntimeException('M3U8_UPDATER_NOT_BOOTED'); }
if ((string)VF_TOOL_M3U8_VERSION !== '99.99.999') { throw new RuntimeException('SYNTHETIC_CANDIDATE_VERSION_EXPECTED'); }
$schema = VF_M3U8_Update_Contract_V1::schema_version();
if (!$schema) { throw new RuntimeException('PROVIDER_SCHEMA_IDENTITY_MISSING'); }
$manifest = [
  'schema_version' => 'wp-component-1.0', 'project_id' => 'S01',
  'component_id' => 'S01-C03', 'component_type' => 'PLUGIN',
  'package_slug' => 'vf-tool-m3u8', 'enabled' => true,
  'target_version' => '100.0.0', 'from_versions' => ['99.99.999'],
  'repository' => 'llhzx2018/vf-tools-m3u8',
  'release_tag' => 'v100.0.0-r8-isolated-fixture',
  'asset_name' => 'vf-tools-m3u8_V100.0.0-fixture.zip',
  'asset_bytes' => 1234, 'asset_sha256' => str_repeat('a', 64),
  'schema_from' => $schema, 'schema_to' => $schema,
  'minimum_wordpress' => '6.5', 'minimum_php' => '8.2',
  'backup_required' => true, 'rollback_supported' => true,
  'runtime_contract' => 'VF_WP_COMPONENT_RUNTIME_AUTHORITY_V1',
  'released_at' => '2026-11-03T00:00:00Z'
];
$release = ['tag_name' => $manifest['release_tag'],
  'assets' => [[ 'name' => $manifest['asset_name'],
    'size' => $manifest['asset_bytes'],
    'url' => 'https://api.github.com/repos/llhzx2018/vf-tools-m3u8/releases/assets/9876' ]]];
$httpLog = [];
$mode = 'valid';
add_filter('pre_http_request', function($pre, $args, $url) use (&$manifest, &$release, &$httpLog, &$mode) {
  if (str_contains($url, 'api.github.com/repos/llhzx2018/core-updates/contents/projects/S01-C03.json')) {
    $httpLog[] = ['manifest', $mode];
    return ['response' => ['code' => 200, 'message' => 'OK'],
      'headers' => [], 'body' => wp_json_encode($manifest), 'cookies' => []];
  }
  if (str_contains($url, 'api.github.com/repos/llhzx2018/vf-tools-m3u8/releases/tags/')) {
    $httpLog[] = ['release', $mode];
    return ['response' => ['code' => 200, 'message' => 'OK'],
      'headers' => [], 'body' => wp_json_encode($release), 'cookies' => []];
  }
  if (str_contains($url, 'api.wordpress.org')) {
    return new WP_Error('synthetic_wp_org_disabled', 'No external update service in fixture');
  }
  return $pre;
}, 1, 3);
update_option('vf_private_update_credential_v1', 'S01-R8-SYNTHETIC-NOT-A-REAL-TOKEN', false);
VF_M3U8_Update_Source_V1::clear_cache();
delete_site_transient('update_plugins');
wp_update_plugins();
$t = get_site_transient('update_plugins');
$plugin = VF_M3U8_Update_Contract_V1::PLUGIN_BASENAME;
$offer = is_object($t) && isset($t->response[$plugin]) ? $t->response[$plugin] : null;
if (!is_object($offer) || ($offer->new_version ?? '') !== $manifest['target_version'] ||
    ($offer->package ?? '') !== $release['assets'][0]['url']) {
  throw new RuntimeException('NATIVE_UPDATE_PLUGINS_OFFER_NOT_VISIBLE');
}
if (count($httpLog) < 2) { throw new RuntimeException('FIXTURE_DID_NOT_READ_MANIFEST_AND_RELEASE'); }
echo "S01_R8_WP_NATIVE_UPDATE_PLUGINS_DISCOVERY=PASS\n";

$mode = 'unsupported';
$manifest['from_versions'] = ['1.0.0'];
VF_M3U8_Update_Source_V1::clear_cache();
$client = new VF_M3U8_Update_Client_V1(VF_TOOL_M3U8_VERSION);
$bad = $client->inject_plugin_update(new stdClass());
if (!empty($bad->response[$plugin])) { throw new RuntimeException('UNSUPPORTED_SOURCE_FALSE_UPDATE'); }
echo "S01_R8_WP_UPDATE_FROM_VERSION_FAIL_CLOSED=PASS\n";

$mode = 'invalid';
$manifest['from_versions'] = ['99.99.999'];
$release['assets'][0]['size'] = 1233;
VF_M3U8_Update_Source_V1::clear_cache();
$client = new VF_M3U8_Update_Client_V1(VF_TOOL_M3U8_VERSION);
$bad = $client->inject_plugin_update(new stdClass());
if (!empty($bad->response[$plugin])) { throw new RuntimeException('MISMATCHED_ASSET_FALSE_UPDATE'); }
echo "S01_R8_WP_UPDATE_RELEASE_BYTES_FAIL_CLOSED=PASS\n";

$mode = 'no-credential';
delete_option('vf_private_update_credential_v1');
$release['assets'][0]['size'] = 1234;
VF_M3U8_Update_Source_V1::clear_cache();
$client = new VF_M3U8_Update_Client_V1(VF_TOOL_M3U8_VERSION);
$bad = $client->inject_plugin_update(new stdClass());
if (!empty($bad->response[$plugin])) { throw new RuntimeException('MISSING_TOKEN_FALSE_UPDATE'); }
echo "S01_R8_WP_UPDATE_NO_CREDENTIAL_FAIL_CLOSED=PASS\n";
echo "S01_R8_WP_NATIVE_DISCOVERY_SYNTHETIC_NOT_RELEASE=YES\n";
