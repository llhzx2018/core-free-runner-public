<?php
define('ABSPATH', __DIR__ . '/');
function esc_html($s){return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
function esc_attr($s){return esc_html($s);}
function vf_theme_public_is_zh(){return $GLOBALS['test_zh'];}
function vf_toolsite_static_current_route(){return $GLOBALS['test_route'];}
function vf_theme_module_description($id,$default,$context){return $GLOBALS['test_description'];}
function vf_theme_seo_route_faq_items($context,$name){return [['q'=>'Synthetic question','a'=>'Synthetic answer']];}
require 'target/src/inc/modules/module-faq.php';
$cases=[
 ['m3u8-downloader',false,'Short answers that keep the tool page useful for search and real users.','Review access requirements, browser limits, and common download questions.'],
 ['m3u8-downloader',true,'用简短答案让工具页同时服务搜索和真实用户。','了解下载前的访问条件、浏览器限制和常见问题。'],
 ['m3u8-downloader',false,'Owner authored guidance remains unchanged.','Owner authored guidance remains unchanged.'],
 ['m3u8-downloader',true,'运营人员自定义说明。','运营人员自定义说明。'],
 ['m3u8-to-mp4',false,'Short answers that keep the tool page useful for search and real users.','Short answers that keep the tool page useful for search and real users.'],
 ['m3u8-player',false,'Short answers that keep the tool page useful for search and real users.','Understand CORS, stream formats, and browser limits before troubleshooting playback.'],
];
foreach($cases as [$route,$zh,$source,$expected]){
 $GLOBALS['test_route']=$route;$GLOBALS['test_zh']=$zh;$GLOBALS['test_description']=$source;
 ob_start();vf_theme_module_render_faq([],'tool');$out=ob_get_clean();
 if(strpos($out,esc_html($expected))===false)throw new RuntimeException('FAQ_BOUNDARY_FAILED: '.$route.' '.($zh?'zh':'en'));
}
echo json_encode(['status'=>'PASS','cases'=>count($cases),'authored_copy'=>'PRESERVED','other_route'=>'PRESERVED']);
