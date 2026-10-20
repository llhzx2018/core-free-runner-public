<?php
// Isolated synthetic menu, shaped like the OWNER's long tools footer.
$poly=get_option('polylang',[]);$menus=$poly['nav_menus'][get_stylesheet()]??[];$out=[];
$labels=['M3U8 Player','M3U8 Download URL','M3U8 to MP4 Converter for HLS Playlists','M3U8 Embed Code Generator','HLS Playback','Playlist Checker','Segment URL Viewer','Encryption Detector','Browser Stream Test','IPTV Manager','M3U Playlist to XMLTV EPG','Stream Library','Backup and Restore'];
foreach(['en','zh']as $lang){
 $menu=(int)($menus['footer_tools'][$lang]??0);if(!$menu)throw new Exception('missing footer menu');
 foreach($labels as $i=>$label){wp_update_nav_menu_item($menu,0,['menu-item-title'=>$lang==='zh'?'工具 '.($i+1).' · '.$label:$label,'menu-item-url'=>home_url(($lang==='zh'?'/zh':'').'/m3u8-player/?footer_fixture='.$i),'menu-item-status'=>'publish','menu-item-type'=>'custom']);}
 $items=wp_get_nav_menu_items($menu);$out[$lang]=array_map(static fn($x)=>['title'=>$x->title,'url'=>$x->url],$items);
 if(count($items)!==15)throw new Exception('wrong menu denominator');
}
echo wp_json_encode(['menus'=>$out,'production'=>'NOT_MODIFIED']);
