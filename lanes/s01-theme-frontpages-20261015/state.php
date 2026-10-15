<?php
global $wpdb;
$keys=['vf_theme_brand','vf_theme_tokens','vf_theme_layout','vf_theme_navigation','vf_theme_ads','vf_theme_seo','theme_mods_vf-tools-theme'];$rows=[];
foreach($keys as $key){$rows[$key]=get_option($key);}
$rows['content']=$wpdb->get_results("SELECT ID,post_title,post_content,post_excerpt,post_status FROM {$wpdb->posts} ORDER BY ID",ARRAY_A);
$rows['translations']=$wpdb->get_results("SELECT object_id,term_taxonomy_id,term_order FROM {$wpdb->term_relationships} ORDER BY object_id,term_taxonomy_id",ARRAY_A);
echo wp_json_encode(['status'=>'SNAPSHOT','sha256'=>hash('sha256',wp_json_encode($rows))]);
