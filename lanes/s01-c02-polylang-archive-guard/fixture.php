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
// Rehearse the proposed *content-owner* correction on synthetic pages only.
// No source product code has been granted permission to run this against Production.
$before=pll_get_post_translations((int)$en);
if ((int)($before['en']??0)!==(int)$en || (int)($before['zh']??0)!==(int)$duplicate) {
    throw new Exception('Initial link snapshot is not exact');
}
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$official]);
$corrected=pll_get_post_translations((int)$en);
$officialLinks=pll_get_post_translations((int)$official);
$duplicateLinks=pll_get_post_translations((int)$duplicate);
echo 'S01_POLYLANG_NAIVE_LINK_READBACK '.wp_json_encode([
    'english'=>$corrected, 'official'=>$officialLinks, 'oldDuplicate'=>$duplicateLinks
])."\n";
// Polylang may keep the former Chinese page in the original translation group
// when the EN post is re-associated. Explicitly detach the old Chinese member,
// then bind the intended pair. This is isolated rehearsal, not production code.
if ((int)($duplicateLinks['en']??0)===(int)$en) {
    pll_save_post_translations(['zh'=>(int)$duplicate]);
    pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$official]);
    $corrected=pll_get_post_translations((int)$en);
    $officialLinks=pll_get_post_translations((int)$official);
    $duplicateLinks=pll_get_post_translations((int)$duplicate);
    echo 'S01_POLYLANG_DETACH_REBIND_READBACK '.wp_json_encode([
        'english'=>$corrected, 'official'=>$officialLinks, 'oldDuplicate'=>$duplicateLinks
    ])."\n";
}
if ((int)($corrected['zh']??0)!==(int)$official || (int)($officialLinks['en']??0)!==(int)$en) {
    throw new Exception('Synthetic corrected translation family has not converged');
}
if ((int)($duplicateLinks['en']??0)===(int)$en) {
    throw new Exception('Old duplicate is still linked to English');
}
if (get_post_status((int)$duplicate)!=='publish' || get_post_status((int)$official)!=='publish') {
    throw new Exception('Translation-only rehearsal must not alter page statuses');
}
echo 'S01_C02_POLYLANG_LINK_REHEARSAL_PASS '.wp_json_encode([
    'correctedEnglish'=> (int)$en,'correctedChinese'=>(int)$official,
    'oldDuplicateUnlinked'=>true,'oldDuplicatePublished'=>true,'production'=>'NOT_EXECUTED'
])."\n";
// Restore the snapshot with explicit displacement of the newly linked page.
pll_save_post_translations(['zh'=>(int)$official]);
pll_save_post_translations($before);
$restored=pll_get_post_translations((int)$en);
$oldRestored=pll_get_post_translations((int)$duplicate);
$officialRestored=pll_get_post_translations((int)$official);
echo 'S01_POLYLANG_ROLLBACK_READBACK '.wp_json_encode([
    'english'=>$restored,'oldDuplicate'=>$oldRestored,'official'=>$officialRestored
])."\n";
if ((int)($officialRestored['en']??0)===(int)$en || (int)($oldRestored['en']??0)!==(int)$en) {
    throw new Exception('Rollback left stray translations on noncanonical member');
}
if ((int)($restored['en']??0)!==(int)$en || (int)($restored['zh']??0)!==(int)$duplicate) {
    throw new Exception('Translation rollback did not restore original mapping');
}
if (get_post_status((int)$duplicate)!=='publish') {
    throw new Exception('Rollback unexpectedly changed old duplicate status');
}
echo 'S01_C02_POLYLANG_LINK_ROLLBACK_PASS '.wp_json_encode([
    'originalFamilyRestored'=>true,'duplicateRetained'=>true,'production'=>'NOT_EXECUTED'
])."\n";

