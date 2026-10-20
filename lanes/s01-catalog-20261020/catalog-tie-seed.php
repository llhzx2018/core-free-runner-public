<?php
// Deterministic equal-date regression data, isolated Runner only.
global $wpdb;
$ids=get_posts(['post_type'=>['vf_guide','vf_problem','vf_glossary'],'post_status'=>'publish','posts_per_page'=>-1,'fields'=>'ids','suppress_filters'=>true,'lang'=>'']);
foreach($ids as $id){$wpdb->update($wpdb->posts,['post_date'=>'2024-03-01 12:00:00','post_date_gmt'=>'2024-03-01 12:00:00','post_modified'=>'2024-03-01 12:00:00','post_modified_gmt'=>'2024-03-01 12:00:00'],['ID'=>(int)$id]);clean_post_cache((int)$id);}
echo wp_json_encode(['status'=>'SEEDED','same_timestamp_public_records'=>count($ids),'production'=>'NOT_EXECUTED']);
