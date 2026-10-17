<?php
// Hash only protected persistent records, never expose user/session/credentials.
global $wpdb;
$rows=[];
$rows['theme_mods']=get_theme_mods();
foreach(['vf_theme_layout','vf_theme_brand','vf_theme_tokens','vf_theme_navigation','polylang']as $key)$rows[$key]=get_option($key);
$rows['content']=$wpdb->get_results("SELECT ID,post_type,post_status,post_name,post_title,post_content,post_excerpt FROM {$wpdb->posts} ORDER BY ID",ARRAY_A);
$rows['postmeta']=$wpdb->get_results("SELECT post_id,meta_key,meta_value FROM {$wpdb->postmeta} WHERE meta_key NOT LIKE '\\_edit\\_%' ORDER BY meta_id",ARRAY_A);
echo hash('sha256',wp_json_encode($rows));
