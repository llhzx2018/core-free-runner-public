<?php
// Isolated synthetic content only; no tied modified-desc timestamps in parity fixtures.
global $wpdb;
foreach($wpdb->get_col("SELECT ID FROM {$wpdb->posts} WHERE post_status='publish' AND post_type<>'nav_menu_item' ORDER BY ID") as $id){
 $stamp=gmdate('Y-m-d H:i:s',strtotime('2026-10-20 00:00:00 UTC')+(int)$id);
 $wpdb->update($wpdb->posts,['post_date'=>$stamp,'post_date_gmt'=>$stamp,'post_modified'=>$stamp,'post_modified_gmt'=>$stamp],['ID'=>(int)$id]);clean_post_cache((int)$id);
}
wp_cache_flush();echo "SYNTHETIC_DISTINCT_CONTENT_DATES\n";
