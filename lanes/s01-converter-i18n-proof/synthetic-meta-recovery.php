<?php
// Synthetic-only diagnostic. Never invokes production or constitutes a shipped recovery feature.
global $wpdb;
$keys=['vf_m3u8_skin_seasonal_migration_evidence','vf_m3u8_skin_seasonal_migration_snapshot'];
$mode=(string)($args[0]??'');
if($mode==='seed'){
    $s=get_option($keys[1],[]); if(!is_array($s)) WP_CLI::error('snapshot missing');
    $s['currentBefore']['settings']['synthetic_recovery_marker']='original-before-rollback';
    update_option($keys[1],$s,false);
    if((get_option($keys[1])['currentBefore']['settings']['synthetic_recovery_marker']??'')!=='original-before-rollback') WP_CLI::error('seed failed');
    echo "SYNTHETIC_MARKER_SEEDED";
    return;
}
if($mode==='capture'){
    $rows=[];
    foreach($keys as $key){$row=$wpdb->get_row($wpdb->prepare("SELECT option_name,option_value,autoload FROM {$wpdb->options} WHERE option_name=%s",$key),ARRAY_A);if(!is_array($row)) WP_CLI::error('required record absent');$rows[]=$row;}
    $data=wp_json_encode($rows);if(!is_string($data)||file_put_contents('/tmp/s01-synthetic-recovery.json',$data,LOCK_EX)===false) WP_CLI::error('capture failed');
    chmod('/tmp/s01-synthetic-recovery.json',0600);echo hash('sha256',$data);return;
}
if($mode==='restore'){
    $rows=json_decode((string)file_get_contents('/tmp/s01-synthetic-recovery.json'),true);
    if(!is_array($rows)||count($rows)!==2) WP_CLI::error('capture invalid');
    $wpdb->query('START TRANSACTION');
    try {foreach($rows as $row){if(!in_array($row['option_name']??'', $keys,true))throw new Exception('invalid key');if($wpdb->update($wpdb->options,['option_value'=>$row['option_value'],'autoload'=>$row['autoload']],['option_name'=>$row['option_name']])===false)throw new Exception('write failed');} $wpdb->query('COMMIT');}
    catch(Throwable $e){$wpdb->query('ROLLBACK');WP_CLI::error('synthetic recovery failed');}
    foreach($keys as $key)wp_cache_delete($key,'options');wp_cache_delete('alloptions','options');
    foreach($rows as $row){$actual=$wpdb->get_row($wpdb->prepare("SELECT option_name,option_value,autoload FROM {$wpdb->options} WHERE option_name=%s",$row['option_name']),ARRAY_A);if($actual!==$row) WP_CLI::error('recovery readback mismatch');}
    echo "SYNTHETIC_RECOVERY_READBACK_PASS";return;
}
WP_CLI::error('unknown mode');
