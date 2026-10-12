<?php
// Licensed Polylang Pro acceptance (disposable WordPress/MariaDB only).
// This must never be run on Production or with a Production database.
if (!defined('ABSPATH') || !function_exists('pll_save_post_translations')) {
    throw new RuntimeException('Required WordPress + Polylang APIs are unavailable');
}
require_once ABSPATH.'wp-admin/includes/plugin.php';
$proActive = is_plugin_active('polylang-pro/polylang.php');
$installedPro = WP_PLUGIN_DIR.'/polylang-pro/polylang.php';
$proVersion = file_exists($installedPro) ? (string)(get_plugin_data($installedPro, false, false)['Version']??'') : '';
if (!$proActive || $proVersion === '') {
    throw new RuntimeException('Actual licensed Polylang Pro plugin is not active');
}
// Require the version observed on Production, not a different free/older build.
if ($proVersion !== '3.8.2') {
    throw new RuntimeException('POLYLANG_PRO_VERSION_MISMATCH: expected 3.8.2, actual '.$proVersion);
}
wp_set_current_user((int)get_user_by('login', 'admin')->ID);
if (!function_exists('vf_ops_multilingual_slug_cleaner_archive_relation_block_reason')) {
    require_once '/tmp/01-common.php';
    require_once '/tmp/02-scan.php';
    require_once '/tmp/03-repair-helpers.php';
}
$slug='pro-shared-slug-gate';
$en=wp_insert_post([
    'post_type'=>'page','post_status'=>'publish','post_title'=>'Pro EN canonical',
    'post_name'=>$slug, 'post_content'=>'SYNTHETIC EN'
]);
$zh=wp_insert_post([
    'post_type'=>'page','post_status'=>'publish','post_title'=>'Pro ZH canonical',
    'post_name'=>$slug, 'post_content'=>'SYNTHETIC ZH'
]);
$old=wp_insert_post([
    'post_type'=>'page','post_status'=>'publish','post_title'=>'Pro ZH duplicate',
    'post_name'=>$slug.'-2','post_content'=>'SYNTHETIC OLD'
]);
foreach ([$en,$zh,$old] as $id) {
    if (is_wp_error($id) || (int)$id<=0) { throw new RuntimeException('Failed to create disposable Pro pages'); }
}
pll_set_post_language((int)$en,'en');
pll_set_post_language((int)$zh,'zh');
pll_set_post_language((int)$old,'zh');
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$old]);
// Polylang Pro may assign a temporary suffix before languages are linked.
// Explicitly request the shared slug for the canonical ZH page.
wp_update_post(['ID'=>(int)$zh,'post_name'=>$slug]);
$enSlug=(string)get_post_field('post_name',(int)$en);
$zhSlug=(string)get_post_field('post_name',(int)$zh);
if ($enSlug!==$slug || $zhSlug!==$slug) {
    throw new RuntimeException('POLYLANG_PRO_SHARE_SLUGS_NOT_CONFIRMED: canonical language slugs differ');
}
echo 'S01_C02_POLYLANG_PRO_SHARE_SLUGS_PASS '.wp_json_encode(['sameSlug'=>true,'production'=>'NOT_EXECUTED'])."\n";
// Snapshot every affected member, including the formerly independent ZH page.
function s01_pro_complete_snapshot(array $ids): array {
    $rows=[];
    foreach ($ids as $id) {
        clean_post_cache((int)$id);
        $post=get_post((int)$id);
        if (!$post instanceof WP_Post) { throw new RuntimeException('Pro fixture page disappeared'); }
        $map=pll_get_post_translations((int)$id);ksort($map,SORT_STRING);
        $rows[(int)$id]=[
            'status'=>$post->post_status,'slug'=>$post->post_name,
            'title'=>$post->post_title,'content'=>$post->post_content,
            'language'=>pll_get_post_language((int)$id),'translations'=>$map,
        ];
    }
    ksort($rows,SORT_NUMERIC);
    return $rows;
}
$fixtureIds=[(int)$en,(int)$zh,(int)$old];
$originalSnapshot=s01_pro_complete_snapshot($fixtureIds);
$before=pll_get_post_translations((int)$en);
if (!is_array($before) || (int)($before['zh']??0)!==(int)$old) {
    throw new RuntimeException('Failed to reproduce wrong translated duplicate');
}
$blocked=vf_ops_multilingual_slug_cleaner_archive_relation_block_reason((int)$old,(int)$zh,'zh',(int)$en);
if ($blocked==='') {throw new RuntimeException('Linked old page should fail closed on real Pro');}
$linkedArchive=vf_ops_multilingual_slug_cleaner_archive_duplicate_conflict([
    'id'=>(int)$old,'source_post_id'=>(int)$en,'same_language_conflict_id'=>(int)$zh,
]);
if (($linkedArchive['status']??'')!=='BLOCKED'
    || s01_pro_complete_snapshot($fixtureIds)!==$originalSnapshot) {
    throw new RuntimeException('Actual Pro linked duplicate archive changed affected content or relations');
}
echo 'S01_C02_POLYLANG_PRO_LINKED_ARCHIVE_BLOCK_PASS '.wp_json_encode(['allThreePagesPreserved'=>true,'production'=>'NOT_EXECUTED'])."\n";
pll_save_post_translations(['zh'=>(int)$old]);
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$zh]);
$enMap=pll_get_post_translations((int)$en);
$zhMap=pll_get_post_translations((int)$zh);
$oldMap=pll_get_post_translations((int)$old);
if ((int)($enMap['zh']??0)!==(int)$zh || (int)($zhMap['en']??0)!==(int)$en
    || (int)($oldMap['en']??0)===(int)$en
    || vf_ops_multilingual_slug_cleaner_archive_relation_block_reason((int)$old,(int)$zh,'zh',(int)$en)!=='') {
    throw new RuntimeException('Pro three-member translation correction failed readback');
}
echo 'S01_C02_POLYLANG_PRO_TRANSLATION_PASS '.wp_json_encode(['reciprocal'=>true,'oldUnlinked'=>true,'production'=>'NOT_EXECUTED'])."\n";
// Reversible mutation in disposable staging only. No archive occurs without
// a real 301; this is verified elsewhere against official Rank Math engine.
$correctedSnapshot=s01_pro_complete_snapshot($fixtureIds);
$notRedirected=vf_ops_multilingual_slug_cleaner_archive_duplicate_conflict([
    'id'=>(int)$old,'source_post_id'=>(int)$en,'same_language_conflict_id'=>(int)$zh,
]);
if (($notRedirected['status']??'')!=='BLOCKED' || get_post_status((int)$old)!=='publish'
    || s01_pro_complete_snapshot($fixtureIds)!==$correctedSnapshot) {
    throw new RuntimeException('Pro old URL was wrongly archived without a live 301');
}
pll_save_post_translations(['zh'=>(int)$zh]);
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$old]);
$restored=pll_get_post_translations((int)$en);
if ((int)($restored['zh']??0)!==(int)$old
    || get_post_status((int)$old)!=='publish'
    || get_post_status((int)$zh)!=='publish'
    || s01_pro_complete_snapshot($fixtureIds)!==$originalSnapshot) {
    throw new RuntimeException('Pro restoration failed');
}
echo 'S01_C02_POLYLANG_PRO_ROLLBACK_PASS '.wp_json_encode(['originalRelationRestored'=>true,'allThreeRelationsAndContentRestored'=>true,'oldPublished'=>true,'production'=>'NOT_EXECUTED'])."\n";
echo 'S01_C02_POLYLANG_PRO_LICENSED_STAGING_PASS '.wp_json_encode([
    'pluginVersion'=>$proVersion,'sharedSlug'=>true,'translationCorrection'=>true,
    'safetyNo301'=>true,'rollback'=>true,'production'=>'NOT_EXECUTED'
])."\n";
