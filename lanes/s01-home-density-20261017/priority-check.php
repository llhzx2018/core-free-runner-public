<?php
require_once get_template_directory().'/inc/renderers/family-render-core.php';
require_once get_template_directory().'/inc/modules/module-tool-grid.php';
$checks=[];
foreach(['en','zh']as $lang){
 $prefix=$lang==='zh'?'/zh/':'/';$cards=[];
 foreach(['m3u8-downloader','m3u8-playlist-checker','m3u8-player','m3u8-browser-stream-test','owner-extra']as $slug)$cards[]=['href'=>'https://example.invalid'.$prefix.$slug.'/?x=1#result','title'=>$slug];
 $out=vf_theme_home_priority_tool_cards($cards);$expected=['m3u8-player','m3u8-browser-stream-test','m3u8-playlist-checker','m3u8-downloader','owner-extra'];
 $checks[]=['name'=>'canonical priority across localized absolute URLs','lang'=>$lang,'pass'=>array_column($out,'title')===$expected];
 $checks[]=['name'=>'original card URLs retained','lang'=>$lang,'pass'=>array_column($out,'href')===array_map(static fn($slug)=>'https://example.invalid'.$prefix.$slug.'/?x=1#result',$expected)];
}
$out=vf_theme_home_priority_tool_cards([null,'bad',['slug'=>'m3u8-downloader','href'=>'/owner-download/','title'=>'download'],['slug'=>'m3u8-player','href'=>'/owner-play/','title'=>'play']]);
$checks[]=['name'=>'canonical slug metadata respected and malformed cards ignored','pass'=>array_column($out,'title')===['play','download']];
if(array_filter($checks,static fn($c)=>!$c['pass'])){echo wp_json_encode(['status'=>'FAIL','checks'=>$checks]);exit(1);}echo wp_json_encode(['status'=>'PASS','checks'=>$checks]);
