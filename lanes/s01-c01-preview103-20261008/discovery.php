<?php
if (wp_get_theme()->get('Version') !== getenv('SOURCE_VERSION')) { throw new Exception('native source theme version mismatch'); }
VF_Theme_Update_Source_V1::clear_cache();
$source = new VF_Theme_Update_Source_V1(getenv('SOURCE_VERSION'));
$manifest = $source->manifest(true);
if (is_wp_error($manifest)) { throw new Exception('manifest discovery failed: '.$manifest->get_error_code()); }
$expected = json_decode(file_get_contents('/tmp/channel.json'),true);
if ($manifest !== $expected || $manifest['target_version'] !== getenv('TARGET_VERSION') || !in_array(getenv('SOURCE_VERSION'),$manifest['from_versions'],true)) { throw new Exception('live channel identity mismatch'); }
$release = $source->release($manifest);
if (is_wp_error($release)) { throw new Exception('release discovery failed: '.$release->get_error_code()); }
$client = new VF_Theme_Update_Client_V1(getenv('SOURCE_VERSION'));
$t = $client->inject_theme_update((object)['response'=>[]]);
if (($t->response['vf-tools-theme']['new_version']??'') !== getenv('TARGET_VERSION') || VF_Theme_Update_Client_V1::status()['state'] !== 'UPDATE_AVAILABLE') { throw new Exception('native updater did not discover update'); }
$zip = $source->download($release);
if (is_wp_error($zip)) { throw new Exception('actual native asset download failed: '.$zip->get_error_code()); }
$bytes = filesize($zip);$sha=hash_file('sha256',$zip);unlink($zip);
if ($bytes !== (int)$manifest['asset_bytes'] || $sha !== $manifest['asset_sha256']) { throw new Exception('actual asset integrity mismatch'); }
putenv('VF_PRIVATE_READ_TOKEN');VF_Theme_Update_Source_V1::clear_cache();
$missing = $source->manifest(true);
if (!is_wp_error($missing) || $missing->get_error_code() !== 'vf_private_update_token_missing') { throw new Exception('credential missing did not fail closed'); }
echo wp_json_encode(['status'=>'PASS','source_version'=>getenv('SOURCE_VERSION'),'target_version'=>$manifest['target_version'],'channel_sha'=>getenv('CHANNEL_SHA'),'source_sha'=>getenv('TARGET_SHA'),'source_tree'=>getenv('TARGET_TREE'),'native_discovery'=>'UPDATE_AVAILABLE','asset_name'=>$manifest['asset_name'],'asset_bytes'=>$bytes,'asset_sha256'=>$sha,'runtime_files'=>$manifest['runtime_files'],'runtime_fingerprint'=>$manifest['runtime_fingerprint'],'missing_credential'=>'FAIL_CLOSED_PRESERVED','production'=>'NOT_EXECUTED']);
