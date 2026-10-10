<?php
update_option('permalink_structure','/%postname%/');
foreach(['vf_ops_preservation_sentinel'=>['keep'=>'ops'],'vf_m3u8_preservation_sentinel'=>['keep'=>'provider']] as $key=>$value) update_option($key,$value,false);
set_theme_mod('vf_public104_preservation','keep-me');
flush_rewrite_rules(true);
echo wp_json_encode(['status'=>'PASS','environment'=>'SYNTHETIC_DISPOSABLE_WORDPRESS']);
