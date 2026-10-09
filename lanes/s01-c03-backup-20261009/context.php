<?php
// Only a declared synthetic context, never Production integration evidence.
if(!defined('VF_WP_UPDATE_TEST_MODE')||VF_WP_UPDATE_TEST_MODE!==true)return;
add_filter('vf_tools_m3u8_platform_compatibility_context',function($v){return get_option('vf_runner_overview_context')==='known'?['known'=>true,'production_usage'=>'SYNTHETIC_ISOLATED_CONTEXT','dependents'=>[]]:['known'=>false,'production_usage'=>'SYNTHETIC_UNKNOWN_EXTERNAL_OWNER','dependents'=>[]];},999);
add_filter('vf_tools_m3u8_provider_production_dependents',function($v){return get_option('vf_runner_overview_context')==='known'?['known'=>true,'dependents'=>[],'meaning'=>'SYNTHETIC_NOT_PRODUCTION']:['known'=>false,'dependents'=>[]];},999);

// Controlled database failure injection only in this disposable WordPress instance.
$backupFailureFlags=[(bool)get_option('vf_runner_backup_fail-run'),(bool)get_option('vf_runner_backup_fail-read'),(bool)get_option('vf_runner_backup_fail-create'),(bool)get_option('vf_runner_backup_fail-restore')];
add_filter('query',function($sql)use($backupFailureFlags){
 if(!defined('VF_WP_UPDATE_TEST_MODE')||VF_WP_UPDATE_TEST_MODE!==true)return $sql;
 $t=function_exists('vf_tools_m3u8_v6_table_names')?vf_tools_m3u8_v6_table_names():[];
 if($backupFailureFlags[0]&&isset($t['operation_runs'])&&str_starts_with($sql,'INSERT INTO `'.$t['operation_runs'].'`'))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 if($backupFailureFlags[1]&&isset($t['snapshots'])&&str_contains($sql,'SELECT * FROM '.$t['snapshots'].' WHERE'))return 'SELECT * FROM vf_synthetic_missing_table';
 if($backupFailureFlags[2]&&isset($t['snapshots'])&&str_starts_with($sql,'INSERT INTO `'.$t['snapshots'].'`'))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 if($backupFailureFlags[3]&&isset($t['runtime_bundles'])&&str_starts_with($sql,'INSERT INTO `'.$t['runtime_bundles'].'`'))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 return $sql;
},999);
