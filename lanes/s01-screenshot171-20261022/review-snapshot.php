<?php
global $wpdb;
$rows=$wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options} WHERE option_name LIKE 'vf_theme_frontend_review_%' ORDER BY option_name",ARRAY_A);
$out=[];foreach($rows as $row)$out[$row['option_name']]=hash('sha256',$row['option_value']);
echo wp_json_encode($out);
