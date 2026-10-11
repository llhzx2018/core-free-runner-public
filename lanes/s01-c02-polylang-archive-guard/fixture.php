<?php
if (!function_exists('pll_save_post_translations') || !function_exists('pll_set_post_language')) {
    throw new Exception('Official Polylang runtime not available');
}
wp_set_current_user((int)get_user_by('login','admin')->ID);
foreach ([['en_US','English','en'],['zh_CN','Chinese','zh']] as $language) {
    $request = new WP_REST_Request('POST','/pll/v1/languages');
    $request->set_param('locale',$language[0]);
    $request->set_param('name',$language[1]);
    $request->set_param('slug',$language[2]);
    $response=rest_do_request($request);
    if ((int)$response->get_status() >= 400) {
        throw new Exception('Polylang language registration failed for '.$language[2].': '.wp_json_encode($response->get_data()));
    }
}
$en=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'English','post_name'=>'checker-en','post_content'=>'EN']);
$official=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Official Chinese','post_name'=>'checker-zh','post_content'=>'ZH']);
$duplicate=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Duplicate Chinese','post_name'=>'checker-zh-2','post_content'=>'OLD']);
foreach ([$en,$official,$duplicate] as $id) {if (is_wp_error($id) || (int)$id<=0) {throw new Exception('Synthetic page insertion failed');}}
pll_set_post_language((int)$en,'en');
pll_set_post_language((int)$official,'zh');
pll_set_post_language((int)$duplicate,'zh');
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$duplicate]);
$map=pll_get_post_translations((int)$duplicate);
if (!is_array($map) || (int)($map['en']??0)!==(int)$en || (int)($map['zh']??0)!==(int)$duplicate) {
    throw new Exception('Polylang real translation setup failed: '.wp_json_encode($map));
}
require_once '/tmp/01-common.php';
require_once '/tmp/02-scan.php';
require_once '/tmp/03-repair-helpers.php';
$reason=vf_ops_multilingual_slug_cleaner_archive_relation_block_reason((int)$duplicate,(int)$official,'zh');
if ($reason==='' || !str_contains($reason,'翻译关系')) {throw new Exception('Real Polylang membership did not block archive');}
$archive=vf_ops_multilingual_slug_cleaner_archive_duplicate_conflict([
    'id'=>(int)$duplicate, 'same_language_conflict_id'=>(int)$official
]);
if (($archive['status']??'')!=='BLOCKED' || get_post_status((int)$duplicate)!=='publish') {
    throw new Exception('Real WordPress duplicate status was modified');
}
$after=pll_get_post_translations((int)$duplicate);
if ($map!==$after) {throw new Exception('Translation membership changed unexpectedly');}
echo 'S01_C02_POLYLANG_WORDPRESS_PASS '.wp_json_encode(['linkedMemberBlocked'=>true,'translationPreserved'=>true,'draftWrites'=>0,'production'=>'NOT_EXECUTED'])."\n";
