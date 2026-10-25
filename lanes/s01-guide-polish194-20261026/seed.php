<?php
// Synthetic isolated review fixtures, before the protected-state snapshot.
// Retain the established existing-installation marker without unrelated pages.
$layout=get_option('vf_theme_layout',[]);$layout['moduleSettings']['home']['tool_grid']['override']=true;$layout['moduleSettings']['home']['tool_grid']['count']=6;$layout['moduleSettings']['home']['tool_grid']['featured_count']=0;update_option('vf_theme_layout',$layout);set_theme_mod('s01_authored_keep','retained');
// Representative native configured menus, not Production data.
$tools=['m3u8-player'=>['M3U8 Player and HLS playback testing','M3U8 在线播放器与 HLS 播放测试'],'m3u8-downloader'=>['M3U8 Downloader Lite','M3U8 轻量下载器'],'m3u8-to-mp4'=>['M3U8 to MP4 Converter for HLS Playlists','M3U8 转 MP4 与 HLS 转换规划'],'embed'=>['M3U8 Embed Code Generator for HLS Playback','M3U8 嵌入代码生成器与 HLS 播放器'],'m3u8-playlist-checker'=>['Playlist Checker','播放列表检查器'],'m3u8-segment-viewer'=>['Segment List Viewer','M3U8 分片查看器'],'m3u8-encryption-detector'=>['Encryption Detector','加密检测器'],'m3u8-browser-stream-test'=>['Browser Stream Test','浏览器流检测'],'iptv-manager'=>['IPTV Manager','IPTV 管理器'],'m3u8-test-links'=>['M3U8 Test Links and Sample Stream Library','M3U8 测试链接与示例流库'],'m3u8-backup-restore'=>['Backup and Restore','备份与恢复']];
$resources=['tools'=>['Tools Directory','工具集合'],'guides'=>['Guides','指南'],'blog'=>['Blog','博客'],'problems'=>['Problems','问题库'],'faq'=>['FAQ','常见问题'],'glossary'=>['Glossary','术语表'],'sitemap'=>['Sitemap','站点地图']];
$company=['contact'=>['Contact','联系'],'privacy-policy'=>['Privacy','隐私政策'],'terms'=>['Terms','使用条款']];
$menus=[];
foreach(['en','zh'] as $lang){
 $idx=$lang==='zh'?1:0;$prefix=$idx?'zh/':'';
 foreach(['header','mobile','footer_tools','footer_resources','footer_company','footer_partners'] as $location){
  $menu=wp_create_nav_menu('Synthetic operational '.$location.' '.$lang);if(is_wp_error($menu))throw new RuntimeException('MENU_CREATE_FAILED');
  $add=static function(string $title,string $url,int $parent=0)use($menu):int{$id=wp_update_nav_menu_item($menu,0,['menu-item-title'=>$title,'menu-item-url'=>$url,'menu-item-parent-id'=>$parent,'menu-item-status'=>'publish','menu-item-type'=>'custom']);if(is_wp_error($id))throw new RuntimeException('MENU_ITEM_FAILED');return(int)$id;};
  $url=static fn(string $route):string=>home_url('/'.$prefix.($route!==''?$route.'/':''));
  if(in_array($location,['header','mobile'],true)){
   $add($idx?'首页':'Home',$url(''));$parent=$add($idx?'工具':'Tools',$url('tools'));foreach($tools as $route=>$labels)$add($labels[$idx],$url($route),$parent);
   $add($idx?'指南':'Guides',$url('guides'));$add($idx?'博客':'Blog',$url('blog'));$parent=$add($idx?'支持':'Support',$url('contact'));$add($idx?'常见问题':'FAQ',$url('faq'),$parent);
  }elseif($location==='footer_partners'){$add($idx?'示例合作入口':'Synthetic partner directory','https://example.invalid/partner/');}
  else{$items=$location==='footer_tools'?$tools:($location==='footer_resources'?$resources:$company);foreach($items as $route=>$labels)$add($labels[$idx],$url($route));}
  $menus[$location][$lang]=(int)$menu;
 }
}
$options=get_option('polylang',[]);$options['nav_menus'][get_stylesheet()]=$menus;update_option('polylang',$options);
$locations=[];foreach($menus as $location=>$langs)$locations[$location]=$langs['en'];set_theme_mod('nav_menu_locations',$locations);
$base=['schema'=>1,'phase'=>'complete','status'=>'accepted','note'=>'Synthetic existing owner record preserved','version'=>'1.35.162','updated'=>'2026-10-21 12:00:00','user'=>1,'token'=>'synthetic-record-162'];
foreach ([['home','en','desktop'],['contact_page','en','desktop']] as [$subject,$language,$device]) {
    $value=array_merge($base,compact('subject','language','device'));
    if ($subject==='contact_page') {$value['status']='needs_changes';$value['note']='Synthetic contact note preserved';}
    update_option('vf_theme_frontend_review_'.hash('sha256',$subject.'|'.$language.'|'.$device),wp_json_encode($value),false);
}
update_option('vf_theme_frontend_review_'.hash('sha256','about_page|zh|mobile'),'{"schema":99,"keep":"unknown-schema-must-not-change"}',false);




