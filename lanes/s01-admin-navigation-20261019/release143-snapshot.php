<?php
global $wpdb;
$sections=[];
$rows=$wpdb->get_results("SELECT option_name,option_value FROM {$wpdb->options} WHERE option_name LIKE 'vf_theme_%' OR option_name LIKE 'theme_mods_%' OR option_name LIKE 's01_preserve_%' ORDER BY option_name",ARRAY_A);
$sections['theme_options']=[];
foreach($rows as $row){if($row['option_name']==='vf_theme_install_migration_state'){continue;}$sections['theme_options'][$row['option_name']]=hash('sha256',$row['option_value']);}
$ledger=get_option('vf_theme_install_migration_state',[]);
if(($ledger['status']??'')!=='PASS'||($ledger['themeVersion']??'')!==vf_theme_runtime_version()||($ledger['writeSet']??null)!==[]){throw new RuntimeException('Existing version validation ledger must PASS at current runtime version without canonical configuration writes');}
foreach(['posts'=>'ID','postmeta'=>'meta_id','terms'=>'term_id','term_taxonomy'=>'term_taxonomy_id','term_relationships'=>'object_id,term_taxonomy_id'] as $table=>$order){$sections[$table]=$wpdb->get_results("SELECT * FROM {$wpdb->$table} ORDER BY $order",ARRAY_A);}
foreach($sections as $name=>$rows){if($name==='theme_options'){continue;}$sections[$name]=hash('sha256',wp_json_encode($rows,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));}
echo wp_json_encode($sections,JSON_PRETTY_PRINT);
