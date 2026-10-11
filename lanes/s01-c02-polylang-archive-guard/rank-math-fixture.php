<?php
// All content is disposable WordPress + MariaDB only; no Production endpoint.
if (!function_exists('pll_save_post_translations') || !class_exists('\RankMath\Redirections\\Redirection')) {
    throw new Exception('Polylang and official Rank Math redirections runtime required');
}
wp_set_current_user((int)get_user_by('login','admin')->ID);
\RankMath\Installer::create_tables(['redirections']);
$en=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'EN redirect lab','post_name'=>'rank-en','post_content'=>'EN']);
$official=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'ZH canonical redirect lab','post_name'=>'rank-zh','post_content'=>'ZH']);
$duplicate=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'ZH duplicate redirect lab','post_name'=>'rank-zh-2','post_content'=>'OLD']);
foreach ([$en,$official,$duplicate] as $id) {
    if (is_wp_error($id) || !$id) {throw new Exception('Failed to seed Rank Math disposable page');}
}
pll_set_post_language((int)$en,'en');
pll_set_post_language((int)$official,'zh');
pll_set_post_language((int)$duplicate,'zh');
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$duplicate]);
pll_save_post_translations(['zh'=>(int)$duplicate]);
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$official]);
$sourceMap=pll_get_post_translations((int)$en);
$targetMap=pll_get_post_translations((int)$official);
$oldMap=pll_get_post_translations((int)$duplicate);
if ((int)($sourceMap['zh']??0)!==(int)$official || (int)($targetMap['en']??0)!==(int)$en
    || (int)($oldMap['en']??0)===(int)$en) {throw new Exception('Polylang family not fully repaired');}
$oldUrl=get_permalink((int)$duplicate);
$newUrl=get_permalink((int)$official);
$sourcePath=(string)wp_parse_url($oldUrl,PHP_URL_PATH);
$redirect=\RankMath\Redirections\Redirection::from([
    'sources'=>[['pattern'=>$sourcePath,'comparison'=>'exact','ignore'=>'']],
    'url_to'=>$newUrl,'header_code'=>'301','status'=>'active',
]);
$recordId=$redirect->save();
if (!is_numeric($recordId) || (int)$recordId<=0) {
    throw new Exception('Rank Math API failed saving redirection record');
}
$rankmathMatch=\RankMath\Redirections\\DB::match_redirections(trim($sourcePath,'/'));
echo 'S01_RANKMATH_SETUP_READBACK '.wp_json_encode([
    'moduleOption'=>get_option('rank_math_modules'),
    'moduleActive'=>\RankMath\Helper::is_module_active('redirections'),
    'sourcePath'=>$sourcePath,
    'matchFound'=>is_array($rankmathMatch),
    'recordFound'=>(bool)\RankMath\Redirections\\DB::get_redirection_by_id((int)$recordId)
])."\\n";
$host=(string)wp_parse_url($oldUrl,PHP_URL_HOST);
add_filter('http_request_host_is_external',static function($external,$candidateHost) use ($host) {
    return $candidateHost===$host ? true : $external;
},10,2);
require_once '/tmp/01-common.php';
require_once '/tmp/02-scan.php';
require_once '/tmp/03-repair-helpers.php';
$http=wp_safe_remote_get($oldUrl,['redirection'=>0,'timeout'=>12,'sslverify'=>true]);
if (is_wp_error($http)) {
    throw new Exception('Rank Math live HTTP request failed: '.$http->get_error_message());
}
$status=(int)wp_remote_retrieve_response_code($http);
$location=(string)wp_remote_retrieve_header($http,'location');
if ($status!==301 || rtrim($location,'/')!==rtrim($newUrl,'/')) {
    throw new Exception('Rank Math engine failed live HTTP 301: '.wp_json_encode([
        'status'=>$status,'location'=>$location,'wanted'=>$newUrl,'record'=>$recordId
    ]));
}
$protected=vf_ops_multilingual_slug_cleaner_archive_duplicate_conflict([
    'id'=>(int)$duplicate,'same_language_conflict_id'=>(int)$official,'source_post_id'=>(int)$en,
]);
if (($protected['status']??'')!=='PASS' || get_post_status((int)$duplicate)!=='draft') {
    throw new Exception('Rank Math redirect did not satisfy Ops guarded archive: '.wp_json_encode($protected));
}
echo 'S01_C02_RANK_MATH_NATIVE_301_PASS '.wp_json_encode([
    'real_rank_math_engine'=>true,'code'=>$status,'exact_target'=>true,
    'guarded_archive'=>true,'production'=>'NOT_EXECUTED'
])."\n";
wp_update_post(['ID'=>(int)$duplicate,'post_status'=>'publish']);
pll_save_post_translations(['zh'=>(int)$official]);
pll_save_post_translations(['en'=>(int)$en,'zh'=>(int)$duplicate]);
if (get_post_status((int)$duplicate)!=='publish'
    || (int)(pll_get_post_translations((int)$en)['zh']??0)!==(int)$duplicate) {
    throw new Exception('Rank Math isolated status/translation rollback failed');
}
echo 'S01_C02_RANK_MATH_ISOLATED_ROLLBACK_PASS '.wp_json_encode([
    'statusRestored'=>true,'translationRestored'=>true,'production'=>'NOT_EXECUTED'
])."\n";
