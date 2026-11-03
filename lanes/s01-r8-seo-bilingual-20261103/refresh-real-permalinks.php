<?php
/**
 * Separate-process WP & Polylang permalink readback, not constructed URLs.
 * This compensates for transient permalink caches during REST language setup.
 */
if (!defined('ABSPATH')||!defined('WP_CLI')||!WP_CLI)throw new RuntimeException('WP CLI only');
if(!in_array((string)wp_parse_url(home_url('/'),PHP_URL_HOST),['127.0.0.1','localhost'],true))throw new RuntimeException('Nonlocal prohibited');
$path='/tmp/s01-r8-seo-live/fixture.json';
$data=json_decode((string)file_get_contents($path),true);
if(!is_array($data)||($data['status']??'')!=='PASS')throw new RuntimeException('Fixture identity missing');
flush_rewrite_rules(false);
foreach(['en','zh','single'] as $key){
    $id=(int)($data['post_ids'][$key]??0);
    $p=get_post($id);
    if(!$p||(string)$p->post_status!=='publish')throw new RuntimeException('Published fixture missing '.$key);
    $lang=(string)pll_get_post_language($id,'slug');
    if($lang!==($key==='zh'?'zh':'en'))throw new RuntimeException('Wrong actual Polylang language '.$key);
    $url=(string)get_permalink($id);
    if((string)wp_parse_url($url,PHP_URL_HOST)!=='127.0.0.1')throw new RuntimeException('Nonlocal permalink');
    $data['urls'][$key]=$url;
    if(trim((string)get_post_meta($id,'rank_math_description',true))==='')throw new RuntimeException('Rank Math description fixture was not saved');
}
$relations=(array)pll_get_post_translations((int)$data['post_ids']['en']);
if($relations!==$data['translations'])throw new RuntimeException('Real Polylang relationship changed across processes');
$data['urlReadback']='FRESH_WP_CLI';
$flags=['rank_math_version'=>defined('RANK_MATH_VERSION')?RANK_MATH_VERSION:'MISSING',
    'rank_math_setup_option'=>get_option('rank_math_setup_complete','NOT_SET'),
    'rank_math_modules'=>get_option('rank_math_modules','NOT_SET')];
$data['seoPluginDiagnostic']=$flags;
if(!file_put_contents($path,wp_json_encode($data,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE)))throw new RuntimeException('Readback write failed');
echo 'S01_R8_SEO_FRESH_REAL_POLYLANG_PERMALINK_READBACK '.wp_json_encode([
   'urls'=>$data['urls'],'relation'=>$relations,'rankMath'=>$flags
],JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE).PHP_EOL;
