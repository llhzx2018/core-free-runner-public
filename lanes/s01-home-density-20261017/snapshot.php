<?php
// Only digests and row identities; never expose protected values or credentials.
global $wpdb;
$rows=[];$parts=[];
$rows['theme_mods']=get_theme_mods();
foreach(['vf_theme_layout','vf_theme_brand','vf_theme_tokens','vf_theme_navigation','vf_theme_ads','vf_theme_seo','polylang']as $key)$rows[$key]=get_option($key);
$rows['provider_mounts']=function_exists('vf_m3u8_mounts_data')?vf_m3u8_mounts_data(true):null;
$rows['translations']=$wpdb->get_results("SELECT object_id,term_taxonomy_id,term_order FROM {$wpdb->term_relationships} ORDER BY object_id,term_taxonomy_id",ARRAY_A);
$rows['terms']=$wpdb->get_results("SELECT term_id,name,slug,term_group FROM {$wpdb->terms} ORDER BY term_id",ARRAY_A);
$rows['term_taxonomy']=$wpdb->get_results("SELECT term_taxonomy_id,term_id,taxonomy,description,parent,count FROM {$wpdb->term_taxonomy} ORDER BY term_taxonomy_id",ARRAY_A);
$rows['frontend_review']=$wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options} WHERE option_name LIKE 'vf_theme_frontend_review_%' ORDER BY option_name",ARRAY_A);
$rows['content']=$wpdb->get_results("SELECT ID,post_type,post_status,post_name,post_title,post_content,post_excerpt FROM {$wpdb->posts} ORDER BY ID",ARRAY_A);
$rows['postmeta']=$wpdb->get_results("SELECT post_id,meta_key,meta_value FROM {$wpdb->postmeta} WHERE meta_key NOT LIKE '\\_edit\\_%' ORDER BY meta_id",ARRAY_A);
foreach($rows as $key=>$value){$parts[$key]=hash('sha256',wp_json_encode($value));}
$details=[];foreach($rows as $key=>$value){
 if($key==='content')foreach($value as $row)$details[$key][$row['ID']]=['sha256'=>hash('sha256',wp_json_encode($row)),'post_type'=>$row['post_type'],'post_status'=>$row['post_status']];
 elseif($key==='postmeta')foreach($value as $row)$details[$key][$row['post_id'].'|'.$row['meta_key']][]=hash('sha256',$row['meta_value']);
 elseif(is_array($value))foreach($value as $k=>$v)$details[$key][$k]=hash('sha256',wp_json_encode($v));
}
$presence=[];foreach(['vf_theme_layout','vf_theme_brand','vf_theme_tokens','vf_theme_navigation','vf_theme_ads','vf_theme_seo','polylang']as $key)$presence[$key]=(bool)$wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->options} WHERE option_name=%s",$key));
echo wp_json_encode(['option_presence'=>$presence,'protected_sha256'=>hash('sha256',wp_json_encode($rows)),'sections'=>$parts,'details'=>$details]);
