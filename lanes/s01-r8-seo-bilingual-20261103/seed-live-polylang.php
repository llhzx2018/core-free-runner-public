<?php
/**
 * S01 R8: real Polylang + Rank Math fixture on disposable localhost WP only.
 * No mocking of pll_* APIs or SEO head. One strictly isolated EN/ZH pair and
 * one unpaired EN page, with real translated WordPress permalinks.
 */
if (!defined('ABSPATH') || !defined('WP_CLI') || !WP_CLI) {
    throw new RuntimeException('Disposable WordPress CLI context required');
}
$host=(string)wp_parse_url((string)get_option('home'),PHP_URL_HOST);
if(!in_array($host,['127.0.0.1','localhost'],true))throw new RuntimeException('Refusing non-local WP SEO fixture');
wp_set_current_user(1);
if(!current_user_can('manage_options'))throw new RuntimeException('Expected synthetic WP admin required');
if(!function_exists('pll_set_post_language')||!function_exists('pll_save_post_translations')){
    throw new RuntimeException('Actual Polylang APIs not loaded (no simulated language service)');
}
if(!defined('RANK_MATH_VERSION'))throw new RuntimeException('Actual Rank Math plugin not loaded');

$createLanguage=static function(string $locale,string $slug,string $name):void{
    $langs=function_exists('pll_languages_list') ? (array)pll_languages_list(['fields'=>'slug']) : [];
    if(in_array($slug,$langs,true))return;
    $request=new WP_REST_Request('POST','/pll/v1/languages');
    $request->set_param('locale',$locale);
    $request->set_param('name',$name);
    $request->set_param('slug',$slug);
    $response=rest_do_request($request);
    if(!$response instanceof WP_REST_Response || $response->get_status()<200 || $response->get_status()>=300){
        throw new RuntimeException('Actual Polylang language REST create failed: '.$slug.' '.wp_json_encode($response->get_data()));
    }
};
$createLanguage('en_US','en','English');
$createLanguage('zh_CN','zh','中文');
$settings=new WP_REST_Request('POST','/pll/v1/settings');
foreach(['default_lang'=>'en','hide_default'=>true,'force_lang'=>1,'rewrite'=>true,'browser'=>false] as $key=>$val){$settings->set_param($key,$val);}
$settingResult=rest_do_request($settings);
if($settingResult->get_status()<200 || $settingResult->get_status()>=300){
    throw new RuntimeException('Actual Polylang language settings failed: '.wp_json_encode($settingResult->get_data()));
}
$languages=(array)pll_languages_list(['fields'=>'slug']);
sort($languages);
if($languages!==['en','zh'])throw new RuntimeException('Polylang EN/ZH languages not available: '.wp_json_encode($languages));
if(function_exists('pll_default_language') && pll_default_language('slug')!=='en'){
    throw new RuntimeException('Polylang default EN setting unreadable');
}
$makePost=static function(string $slug,string $title,string $lang):int{
    $id=wp_insert_post([
        'post_type'=>'page','post_status'=>'publish','post_author'=>1,
        'post_name'=>$slug,'post_title'=>$title,
        'post_content'=> 'S01 R8 isolated bilingual search fixture for '.$lang.'. This published test page verifies actual SEO metadata and language links.'
    ],true);
    if(is_wp_error($id)|| (int)$id<1)throw new RuntimeException('Unable to create genuine WP SEO test page');
    pll_set_post_language((int)$id,$lang);
    if((string)pll_get_post_language((int)$id,'slug')!==$lang)throw new RuntimeException('Actual Polylang post language not saved: '.$slug);
    update_post_meta((int)$id,'rank_math_title',$title.' | S01 SEO');
    update_post_meta((int)$id,'rank_math_description','Isolated '.$lang.' authoritative bilingual SEO output probe.');
    return (int)$id;
};
$en=$makePost('s01-r8-seo-en','S01 R8 English SEO Fixture','en');
$zh=$makePost('s01-r8-seo-zh','S01 R8 中文 SEO 验证','zh');
$single=$makePost('s01-r8-seo-single','S01 R8 English Unpaired SEO','en');
pll_save_post_translations(['en'=>$en,'zh'=>$zh]);
$pairs=(array)pll_get_post_translations($en);
if((int)($pairs['en']??0)!==$en || (int)($pairs['zh']??0)!==$zh){
    throw new RuntimeException('Actual Polylang EN/ZH relation not saved');
}
flush_rewrite_rules(false);
$urls=['en'=>(string)get_permalink($en),'zh'=>(string)get_permalink($zh),'single'=>(string)get_permalink($single)];
foreach($urls as $name=>$url){
    if((string)wp_parse_url($url,PHP_URL_HOST)!==$host)throw new RuntimeException('Nonlocal SEO target: '.$name);
    if(!str_starts_with((string)wp_parse_url($url,PHP_URL_PATH),'/'))throw new RuntimeException('Unexpected SEO permalink '.$name);
    if(str_contains($url,'?page_id='))throw new RuntimeException('SEO permalink not pretty '.$name);
}
if($urls['en']===$urls['zh'] || $urls['en']===$urls['single'] || $urls['zh']===$urls['single']) {
    throw new RuntimeException('Polylang URLs collapsed to same canonical');
}
$directory='/tmp/s01-r8-seo-live';
if(!is_dir($directory)&&!mkdir($directory,0755,true)&&!is_dir($directory))throw new RuntimeException('SEO evidence dir unavailable');
$proof=['status'=>'PASS','polylang'=>'REAL_PLUGIN','rank_math'=>'REAL_PLUGIN',
    'languages'=>$languages,'post_ids'=>['en'=>$en,'zh'=>$zh,'single'=>$single],
    'translations'=>$pairs,'urls'=>$urls];
file_put_contents($directory.'/fixture.json',wp_json_encode($proof,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE));
echo 'S01_R8_SEO_REAL_POLYLANG_RANKMATH_FIXTURE_PASS '.wp_json_encode([
    'languages'=>$languages,'urls'=>$urls,'translationCount'=>count($pairs)
],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE).PHP_EOL;
