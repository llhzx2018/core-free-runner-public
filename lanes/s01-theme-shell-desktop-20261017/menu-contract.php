<?php
declare(strict_types=1);
define('ABSPATH',true);
$checks=[];$active=true;$language='en';$legacy=[];
$physical=['header'=>202,'mobile'=>202,'footer_tools'=>203,'footer_resources'=>204,'footer_company'=>205,'footer_partners'=>245];
$menus=[];$pll=(object)['options'=>['nav_menus'=>[]]];
function sanitize_key($v){return preg_replace('/[^a-z0-9_-]/','',strtolower($v));}
function get_stylesheet(){return 'vf-tools-theme';}
function get_option($key,$default=[]){global $physical;if($key==='theme_mods_vf-tools-theme')return ['nav_menu_locations'=>$physical];throw new Exception('Unexpected option access '.$key);}
function get_nav_menu_locations(){throw new Exception('Recursive filtered menu API must never be called');}
function vf_theme_navigation_polylang_active(){global $active;return $active;}
function vf_theme_navigation_preview_normalize_language($l){return str_replace('_','-',strtolower($l));}
function vf_theme_navigation_default_language_code(){return 'en';}
function vf_theme_current_language_code(){global $language;return $language;}
function PLL(){global $pll;return $pll;}
function pll_get_term($id,$language){global $legacy;return $legacy[$id][$language]??0;}
function pll_get_term_translations($id){global $legacy;return $legacy[$id]??[];}
function pll_get_term_language($id,$mode){return '';}
function exact_function(string $name):void{
 $s=file_get_contents('target/src/inc/services/navigation-service.php');$start=strpos($s,'function '.$name.'(');if($start===false)throw new Exception('Missing exact source function '.$name);$end=strpos($s,"\nfunction ",$start+1);eval(substr($s,$start,$end===false?null:$end-$start));
}
foreach(['vf_theme_navigation_menu_field_map','vf_theme_navigation_locations_raw','vf_theme_navigation_location_base_menu_id','vf_theme_navigation_resolve_menu_translation_id','vf_theme_navigation_location_menu_id'] as $fn)exact_function($fn);
function check_case(string $name,string $location,string $language,int $expected):void{
 global $checks,$physical,$pll,$legacy;
 $before=serialize([$physical,$pll,$legacy]);$actual=vf_theme_navigation_location_menu_id($location,$language);
 $pass=$actual===$expected&&$before===serialize([$physical,$pll,$legacy]);$checks[]=['name'=>$name,'pass'=>$pass,'expected'=>$expected,'actual'=>$actual];if(!$pass)throw new Exception($name);
}
try{
 $active=false;check_case('no Polylang preserves physical menu','header','zh',202);$active=true;
 check_case('legacy default-language fallback preserved','header','en',202);
 check_case('unbound secondary language stays empty','header','zh',0);
 $legacy=[202=>['en'=>202,'zh'=>201]];check_case('legacy translated-term compatibility preserved','header','zh',201);$legacy=[];
 $configured=['header'=>['en'=>202,'zh'=>201],'mobile'=>['en'=>202,'zh'=>201],'footer_tools'=>['en'=>203,'zh'=>206],'footer_resources'=>['en'=>204,'zh'=>207],'footer_company'=>['en'=>205,'zh'=>208],'footer_partners'=>['en'=>245,'zh'=>244]];
 $pll->options=['nav_menus'=>['vf-tools-theme'=>$configured]];
 foreach($configured as $location=>$localized)foreach($localized as $lang=>$id)check_case('native '.$location.' '.$lang,$location,$lang,$id);
 check_case('native primary alias consumes header location','primary','zh',201);
 check_case('regional language selects existing short-language binding','header','zh-CN',201);
 $language='zh';check_case('omitted language uses current request','header','',201);
 $pll->options['nav_menus']['vf-tools-theme']['header']['zh']=0;$legacy=[202=>['zh'=>201]];
 check_case('explicit zero does not borrow default or legacy menu','header','zh',0);
 unset($pll->options['nav_menus']['vf-tools-theme']['header']['zh']);
 check_case('missing governed language stays unbound','header','zh',0);
 $legacy=[];$pll->options=['nav_menus'=>['old-theme'=>$configured]];
 check_case('another theme mapping is never borrowed','header','zh',0);
 $pll->options=new ArrayObject(['nav_menus'=>['vf-tools-theme'=>$configured]]);
 check_case('native ArrayAccess options supported','header','zh',201);
 $native=$pll->options['nav_menus'];$native['vf-tools-theme']['not-a-location']=['zh'=>999];$pll->options['nav_menus']=$native;
 check_case('unknown unregistered location stays empty','not-a-location','zh',0);
 foreach(['src/inc/theme-navigation.php'=>'vf_theme_navigation_location_menu_id($base_location, $language)','src/inc/services/navigation-footer-output-service.php'=>'vf_theme_navigation_location_menu_id($base, $language)'] as $path=>$call){$pass=str_contains(file_get_contents('target/'.$path),$call);$checks[]=['name'=>'consumer shares canonical resolver '.$path,'pass'=>$pass];if(!$pass)throw new Exception($path);}
 file_put_contents('proof/menu-contract.json',json_encode(['status'=>'PASS','checks'=>$checks,'source_sha'=>getenv('TARGET_SHA'),'source_tree'=>getenv('TARGET_TREE'),'state'=>'BYTE_IDENTICAL','native_filtered_api'=>'NEVER_CALLED','production'=>'READ_ONLY_CONFIGURATION_REMAINS_UNBOUND'],JSON_PRETTY_PRINT));
}catch(Throwable $e){file_put_contents('proof/menu-contract.json',json_encode(['status'=>'FAIL','checks'=>$checks,'error'=>$e->getMessage()],JSON_PRETTY_PRINT));throw $e;}
