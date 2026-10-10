<?php
update_option('permalink_structure','/%postname%/');
foreach(['vf_ops_preservation_sentinel'=>['keep'=>'ops'],'vf_m3u8_preservation_sentinel'=>['keep'=>'provider']] as $key=>$value) update_option($key,$value,false);
set_theme_mod('vf_public104_preservation','keep-me');
// Reproduce the owner's three-column, stacked-mobile configuration only here.
$nav=get_option('vf_theme_navigation',[]);$nav=is_array($nav)?$nav:[];$nav['footerColumns']=3;$nav['shell']['footer']['variant']='columns';$nav['shell']['footer']['mobileMode']='stacked';update_option('vf_theme_navigation',$nav,false);
flush_rewrite_rules(true);
echo wp_json_encode(['status'=>'PASS','environment'=>'SYNTHETIC_DISPOSABLE_WORDPRESS']);
