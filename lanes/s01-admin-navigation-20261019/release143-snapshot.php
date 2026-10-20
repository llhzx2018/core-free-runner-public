<?php
global $wpdb;
$sections=[];
$sections['theme_options']=$wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options} WHERE option_name LIKE 'vf_theme_%' OR option_name LIKE 'theme_mods_%' OR option_name LIKE 's01_preserve_%' ORDER BY option_name",ARRAY_A);
foreach(['posts'=>'ID','postmeta'=>'meta_id','terms'=>'term_id','term_taxonomy'=>'term_taxonomy_id','term_relationships'=>'object_id,term_taxonomy_id'] as $table=>$order){$sections[$table]=$wpdb->get_results("SELECT * FROM {$wpdb->$table} ORDER BY $order",ARRAY_A);}
foreach($sections as $name=>$rows){$sections[$name]=hash('sha256',wp_json_encode($rows,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));}
echo wp_json_encode($sections,JSON_PRETTY_PRINT);
