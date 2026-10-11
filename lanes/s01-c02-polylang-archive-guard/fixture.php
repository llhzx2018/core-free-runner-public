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
// The actual guard must reject a one-call reassignment while the former
// Chinese page still has an incoming membership in the old translation group.
$naiveGuard=vf_ops_multilingual_slug_cleaner_archive_relation_block_reason(
    (int)$duplicate,(int)$official,'zh',(int)$en
);
if ($naiveGuard==='') {
    throw new Exception('Naive reassignment unexpectedly allowed duplicate archive');
}
echo 'S01_C02_POLYLANG_NAIVE_RELATION_BLOCK_PASS '.wp_json_encode([
    'blocked'=>true,'formerChineseProtected'=>true,'production'=>'NOT_EXECUTED'
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
// Archive guard must read the source and canonical target bidirectionally;
// detached old post alone cannot justify making a published page unavailable.
$verifiedGuard=vf_ops_multilingual_slug_cleaner_archive_relation_block_reason(
    (int)$duplicate, (int)$official, 'zh', (int)$en
);
if ($verifiedGuard !== '') {
    throw new Exception('Real reciprocal Polylang maps were rejected: '.$verifiedGuard);
}
echo 'S01_C02_POLYLANG_RECIPROCAL_RELATION_PASS '.wp_json_encode([
    'sourceToOfficial'=>true,'officialToSource'=>true,'duplicateNoIncoming'=>true,'production'=>'NOT_EXECUTED'
])."\n";
if (get_post_status((int)$duplicate)!=='publish' || get_post_status((int)$official)!=='publish') {
    throw new Exception('Translation-only rehearsal must not alter page statuses');
}
echo 'S01_C02_POLYLANG_LINK_REHEARSAL_PASS '.wp_json_encode([
    'correctedEnglish'=> (int)$en,'correctedChinese'=>(int)$official,
    'oldDuplicateUnlinked'=>true,'oldDuplicatePublished'=>true,'production'=>'NOT_EXECUTED'
])."\n";
// Even if the three real Polylang members have been corrected, an old
// caller lacking source ID is not allowed to skip the reciprocal map gate.
$noSource=vf_ops_multilingual_slug_cleaner_archive_duplicate_conflict([
    'id'=>(int)$duplicate,'same_language_conflict_id'=>(int)$official,
]);
if (($noSource['status']??'')!=='BLOCKED' || get_post_status((int)$duplicate)!=='publish') {
    throw new Exception('Missing source ID bypassed the archive guard');
}
echo 'S01_C02_MISSING_SOURCE_GUARD_PASS '.wp_json_encode([
    'missingSourceBlocked'=>true,'oldDuplicateStillPublished'=>true,'production'=>'NOT_EXECUTED'
])."\n";
$preflight=vf_ops_multilingual_slug_cleaner_archive_duplicate_conflict([
    'id'=>(int)$duplicate, 'same_language_conflict_id'=>(int)$official,
    'source_post_id'=>(int)$en,
]);
if (($preflight['status']??'')!=='BLOCKED' || get_post_status((int)$duplicate)!=='publish') {
    throw new Exception('Unlinked page was archived without a verified live 301');
}
echo 'S01_C02_NO_301_NO_ARCHIVE_PASS '.wp_json_encode([
    'status'=>$preflight['status'],'oldDuplicateStillPublished'=>true,'production'=>'NOT_EXECUTED'
])."\n";
// Install a REAL public HTTP 301 handler inside this disposable WordPress
// container, then let the actual Ops helper perform its own live GET.
// This is a synthetic MU-plugin handler, NOT a claim of Rank Math / CF Pages.
$oldUrl = get_permalink((int)$duplicate);
$newUrl = get_permalink((int)$official);
$isolatedHost = (string)wp_parse_url($oldUrl, PHP_URL_HOST);
add_filter('http_request_host_is_external', static function($external,$candidateHost) use ($isolatedHost) {
    return (string)$candidateHost === $isolatedHost ? true : $external;
}, 10, 2);
$redirectPlugin=<<<'PHP'
<?php
add_action('init', static function() {
    $path=(string)parse_url((string)($_SERVER['REQUEST_URI']??''), PHP_URL_PATH);
    if (!str_ends_with(rtrim($path, '/'), '/checker-zh-2')) { return; }
    wp_redirect('S01_SYNTHETIC_TARGET_URL',301);
    exit;
}, 0);
PHP;
$redirectPlugin=str_replace('S01_SYNTHETIC_TARGET_URL',$newUrl,$redirectPlugin);
if (!is_dir(WPMU_PLUGIN_DIR)) {wp_mkdir_p(WPMU_PLUGIN_DIR);}
$redirectPluginPath=WPMU_PLUGIN_DIR.'/s01-isolated-playlist-301.php';
if (file_put_contents($redirectPluginPath,$redirectPlugin)===false) {
    throw new Exception('Unable to install disposable WordPress redirect fixture');
}
$httpProbe=wp_safe_remote_get($oldUrl,['redirection'=>0,'timeout'=>10,'sslverify'=>true]);
if (is_wp_error($httpProbe)) {
    throw new Exception('Actual isolated HTTP 301 probe failed: '.$httpProbe->get_error_message());
}
$code=(int)wp_remote_retrieve_response_code($httpProbe);
$location=(string)wp_remote_retrieve_header($httpProbe,'location');
if ($code!==301 || rtrim($location,'/')!==rtrim($newUrl,'/')) {
    throw new Exception('Expected installed isolated 301 to official URL, got '.wp_json_encode(['code'=>$code,'location'=>$location,'expected'=>$newUrl]));
}
$canArchive=vf_ops_multilingual_slug_cleaner_archive_duplicate_conflict([
    'id'=>(int)$duplicate,'same_language_conflict_id'=>(int)$official,'source_post_id'=>(int)$en
]);
if (($canArchive['status']??'')!=='PASS' || get_post_status((int)$duplicate)!=='draft') {
    throw new Exception('Verified real 301 did not permit guarded isolated draft: '.wp_json_encode($canArchive));
}
echo 'S01_C02_REAL_HTTP_301_ARCHIVE_PASS '.wp_json_encode([
    'httpStatus'=>$code,'toOfficial'=>true,'guardedDraft'=>true,'production'=>'NOT_EXECUTED'
])."\n";
unlink($redirectPluginPath);
wp_update_post(['ID'=>(int)$duplicate,'post_status'=>'publish']);
if (get_post_status((int)$duplicate)!=='publish') {
    throw new Exception('Synthetic duplicate status could not be restored');
}


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

