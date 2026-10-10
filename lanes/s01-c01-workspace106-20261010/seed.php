<?php
update_option('permalink_structure','/%postname%/');
foreach(['vf_ops_preservation_sentinel'=>['keep'=>'ops'],'vf_m3u8_preservation_sentinel'=>['keep'=>'provider']] as $key=>$value) update_option($key,$value,false);
set_theme_mod('vf_public104_preservation','keep-me');
// Reproduce the owner's three-column, stacked-mobile configuration only here.
$nav=get_option('vf_theme_navigation',[]);$nav=is_array($nav)?$nav:[];$nav['footerColumns']=3;$nav['shell']['footer']['variant']='columns';$nav['shell']['footer']['mobileMode']='stacked';update_option('vf_theme_navigation',$nav,false);
// Real Core menu bindings, not fabricated footer markup: empty clean WordPress
// has no configured footer groups, while the owner's site has all three.
$groups=[
 'footer_tools'=>['m3u8-player'=>'M3U8 Player','embed'=>'Embed Generator','m3u8-browser-stream-test'=>'Browser Stream Test','m3u8-playlist-checker'=>'Playlist Checker','m3u8-segment-viewer'=>'Segment List Viewer','m3u8-encryption-detector'=>'Encryption Detector','m3u8-downloader'=>'M3U8 Downloader','m3u8-to-mp4'=>'M3U8 to MP4','iptv-manager'=>'IPTV Manager','m3u8-test-links'=>'Test Links','m3u8-backup-restore'=>'Backup and Restore'],
 'footer_resources'=>['tools'=>'Tools Directory','guides'=>'Guides','faq'=>'FAQ'],
 'footer_company'=>['about'=>'About','contact'=>'Contact','privacy-policy'=>'Privacy','terms'=>'Terms'],
];
$locations=get_theme_mod('nav_menu_locations',[]);
foreach($groups as $location=>$items){$menu=wp_create_nav_menu('Synthetic '.$location);if(is_wp_error($menu))throw new Exception($menu->get_error_message());foreach($items as $route=>$label){$result=wp_update_nav_menu_item($menu,0,['menu-item-title'=>$label,'menu-item-url'=>home_url('/'.$route.'/'),'menu-item-type'=>'custom','menu-item-status'=>'publish']);if(is_wp_error($result))throw new Exception($result->get_error_message());}$locations[$location]=$menu;}
set_theme_mod('nav_menu_locations',$locations);
flush_rewrite_rules(true);
echo wp_json_encode(['status'=>'PASS','environment'=>'SYNTHETIC_DISPOSABLE_WORDPRESS']);
