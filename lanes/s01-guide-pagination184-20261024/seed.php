<?php
// Synthetic isolated review fixtures, before the protected-state snapshot.
// Retain the established existing-installation marker without unrelated pages.
$layout=get_option('vf_theme_layout',[]);$layout['s01_authored_keep']='retained';$layout['moduleSettings']['home']['tool_grid']['override']=true;$layout['moduleSettings']['home']['tool_grid']['count']=6;$layout['moduleSettings']['home']['tool_grid']['featured_count']=0;update_option('vf_theme_layout',$layout);set_theme_mod('s01_authored_keep','retained');
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




// Synthetic guide content and editorial facts, never Production data.
$layout=get_option('vf_theme_layout',[]);
$layout['moduleSettings']['guide_index']['post_list']=['override'=>true,'source'=>'registered_type','content_type'=>'vf_guide','count'=>9,'sort'=>'title_asc','show_date'=>true,'show_read_time'=>true,'show_guide_task'=>true,'show_guide_difficulty'=>true,'show_guide_duration'=>true,'show_guide_steps'=>true,'show_guide_filters'=>true];
update_option('vf_theme_layout',$layout);
$names=[
 ['A01','Inspect a master playlist before embedding playback with long titles and browser access restrictions','嵌入播放前检查主播放列表、浏览器访问限制与长标题示例'],
 ['B02','Start with HLS playback basics','从 HLS 播放基础开始'],
 ['C03','Play an authorized HLS stream in a browser','在浏览器播放已授权的 HLS 流'],
 ['D04','Export an authored playlist','导出已整理的播放列表'],
 ['E05','Inspect stream access and segment responses','检查流访问与分片响应'],
 ['F06','Understand master and media playlists','理解主播放列表与媒体播放列表'],
 ['G07','Embed playback in your website','在网站中嵌入播放'],
 ['H08','Manage playlist backups','管理播放列表备份'],
 ['I09','How HLS streaming and M3U8 playlists work in a browser','HLS 流媒体指南：M3U8 播放列表如何在浏览器中工作'],
 ['J10','Inspect a playlist before sharing a support request','提交支持请求之前检查播放列表'],
 ['K11','Compare playback workflows for a site','比较站点播放工作流'],
 ['L12','Plan a local media export','规划本地媒体导出'],
];
foreach($names as $n=>$nameset){
 $pair=[];foreach(['en','zh']as$lang){$zh=$lang==='zh';$i=$n+1;
  $title=$nameset[0].' '.$nameset[$zh?2:1];$task=['inspect','start','play','export'][$n%4];
  $body='<h2>Context, not an operational step</h2><p>Retain authored content and inspect source access.</p><h2>Background</h2><p>Headings must not become invented steps.</p>';
  $excerpt=$zh?'阅读真实的播放列表结构、浏览器访问条件与任务说明。此条合成摘要用于核对正文间距，标题和内容在升级回退后保持。':'Read the playlist structure, browser access conditions and practical task guidance. This synthetic excerpt checks readable spacing and survives upgrade and rollback.';
  if($task==='inspect')$excerpt.=' retainedneedle';
  $id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'publish','post_name'=>'guide-spacing-'.$i.'-'.$lang,'post_title'=>$title,'post_excerpt'=>$excerpt,'post_content'=>$body,'post_date'=>'2026-10-01 10:00:00'],true);if(is_wp_error($id))throw new RuntimeException('GUIDE_SEED_FAILED');pll_set_post_language($id,$lang);$pair[$lang]=(int)$id;
  update_post_meta($id,'_vf_guide_task',$task);$case=$i===1?'authored':($i===3?'malformed':($i===4?'alias':'missing'));update_post_meta($id,'_s01_guide_fact_case',$case);
  if($case==='authored'){update_post_meta($id,'_vf_guide_steps','4');update_post_meta($id,'_vf_guide_duration','12');update_post_meta($id,'_vf_guide_difficulty','intermediate');}
  if($case==='alias'){update_post_meta($id,'guide_steps','2');update_post_meta($id,'guide_minutes','7');update_post_meta($id,'guide_difficulty','easy');}
  if($case==='malformed'){update_post_meta($id,'_vf_guide_steps','-4');update_post_meta($id,'_vf_guide_duration','999');update_post_meta($id,'_vf_guide_difficulty','<script>alert(1)</script>');}
 }pll_save_post_translations($pair);
}
