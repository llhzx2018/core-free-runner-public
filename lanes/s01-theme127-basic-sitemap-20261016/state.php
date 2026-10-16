<?php
global $wpdb;
$keys=['vf_theme_brand','vf_theme_tokens','vf_theme_layout','vf_theme_navigation','vf_theme_ads','vf_theme_seo','theme_mods_vf-tools-theme'];$rows=[];
foreach($keys as $key){$rows[$key]=get_option($key);}
$rows['provider_mounts']=function_exists('vf_m3u8_mounts_data')?vf_m3u8_mounts_data(true):null;
$rows['content']=$wpdb->get_results("SELECT ID,post_title,post_content,post_excerpt,post_status FROM {$wpdb->posts} ORDER BY ID",ARRAY_A);
$rows['postmeta']=$wpdb->get_results("SELECT meta_id,post_id,meta_key,meta_value FROM {$wpdb->postmeta} ORDER BY meta_id",ARRAY_A);
$rows['translations']=$wpdb->get_results("SELECT object_id,term_taxonomy_id,term_order FROM {$wpdb->term_relationships} ORDER BY object_id,term_taxonomy_id",ARRAY_A);
$hashes=[];foreach($rows as $key=>$value){$hashes[$key]=hash('sha256',wp_json_encode($value));}
$types=[];foreach($wpdb->get_results("SELECT ID,post_type,post_status,post_title,post_content,post_excerpt FROM {$wpdb->posts} ORDER BY ID",ARRAY_A) as $post){$types[$post['post_type']][$post['ID']]=['status'=>$post['post_status'],'sha256'=>hash('sha256',wp_json_encode($post))];}
$mods=[];foreach((array)$rows['theme_mods_vf-tools-theme'] as $key=>$value){$mods[$key]=hash('sha256',wp_json_encode($value));}
echo wp_json_encode(['status'=>'SNAPSHOT','sha256'=>hash('sha256',wp_json_encode($rows)),'stores'=>$hashes,'postTypes'=>$types,'themeModFields'=>$mods]);
