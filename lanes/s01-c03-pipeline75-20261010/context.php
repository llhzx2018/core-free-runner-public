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

// Capability-only controlled failures. None of these hooks ship in the plugin ZIP.
$capabilityFailureFlags=[];foreach(['read','save','pointer','seal','archive','begin'] as $f)$capabilityFailureFlags[$f]=(bool)get_option('vf_runner_capability_fail-'.$f);
add_filter('query',function($sql)use($capabilityFailureFlags){
 $t=function_exists('vf_tools_m3u8_v6_table_names')?vf_tools_m3u8_v6_table_names():[];if(!$t)return $sql;
 if($capabilityFailureFlags['read']&&str_contains($sql,'FROM '.$t['capabilities'].' c LEFT JOIN'))return 'SELECT * FROM vf_synthetic_missing_table';
 if($capabilityFailureFlags['save']&&str_starts_with($sql,'UPDATE '.$t['capability_contracts'].' SET definition='))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if($capabilityFailureFlags['pointer']&&str_starts_with($sql,'UPDATE `'.$t['capabilities'].'`'))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if($capabilityFailureFlags['seal']&&str_starts_with($sql,'UPDATE '.$t['capability_contracts']." SET revision_state='SEALED'"))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if($capabilityFailureFlags['archive']&&str_starts_with($sql,'UPDATE `'.$t['capabilities'].'`'))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if($capabilityFailureFlags['begin']&&str_starts_with($sql,'INSERT INTO `'.$t['capability_contracts'].'`'))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 return $sql;
},999);
$capabilityImpact=get_option('vf_runner_capability_impact','unknown');
add_filter('vf_tools_m3u8_capability_archive_impact',function($v)use($capabilityImpact){return $capabilityImpact==='none'?['known'=>true,'production_usage'=>false,'dependents'=>[]]:['known'=>false,'production_usage'=>null,'dependents'=>[]];},999);

// Runtime failure flags are read before registering the filter to avoid recursive SQL.
$runtimeFailureFlags=[(bool)get_option('vf_runner_runtime_fail-read'),(bool)get_option('vf_runner_runtime_fail-begin'),(bool)get_option('vf_runner_runtime_fail-save'),(bool)get_option('vf_runner_runtime_fail-assets')];
add_filter('query',function($sql)use($runtimeFailureFlags){
 if(!defined('VF_WP_UPDATE_TEST_MODE')||VF_WP_UPDATE_TEST_MODE!==true)return $sql;
 $t=function_exists('vf_tools_m3u8_v6_table_names')?vf_tools_m3u8_v6_table_names():[];
 if($runtimeFailureFlags[0]&&isset($t['runtime_bundles'])&&str_contains($sql,'SELECT * FROM '.$t['runtime_bundles'].' WHERE provider_key='))return 'SELECT * FROM vf_synthetic_missing_table';
 if($runtimeFailureFlags[1]&&isset($t['runtime_bundles'])&&str_starts_with($sql,'INSERT INTO `'.$t['runtime_bundles'].'`'))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 if($runtimeFailureFlags[2]&&isset($t['runtime_bundles'])&&str_starts_with($sql,'UPDATE `'.$t['runtime_bundles'].'`'))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if($runtimeFailureFlags[3]&&isset($t['runtime_bundle_assets'])&&str_starts_with($sql,'INSERT INTO `'.$t['runtime_bundle_assets'].'`'))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 return $sql;
},999);

// Pipeline-only controlled failures. These hooks never ship in the plugin ZIP.
$pipelineFailureFlags=[];foreach(['read','save','pointer','seal','archive','begin','steps','edges','empty'] as $f)$pipelineFailureFlags[$f]=(bool)get_option('vf_runner_pipeline_fail-'.$f);
add_filter('query',function($sql)use($pipelineFailureFlags){
 $t=function_exists('vf_tools_m3u8_v6_table_names')?vf_tools_m3u8_v6_table_names():[];if(!$t)return $sql;
 if($pipelineFailureFlags['empty']&&str_contains($sql,'FROM '.$t['pipelines'].' p LEFT JOIN'))return str_replace(' ORDER BY p.semantic_key ASC',' AND 1=0 ORDER BY p.semantic_key ASC',$sql);
 if($pipelineFailureFlags['read']&&str_contains($sql,'FROM '.$t['pipelines'].' p LEFT JOIN'))return 'SELECT * FROM vf_synthetic_missing_table';
 if($pipelineFailureFlags['save']&&str_starts_with($sql,'UPDATE '.$t['pipeline_revisions'].' SET definition='))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if(($pipelineFailureFlags['pointer']||$pipelineFailureFlags['archive'])&&str_starts_with($sql,'UPDATE '.chr(96).$t['pipelines'].chr(96)))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if($pipelineFailureFlags['seal']&&str_starts_with($sql,'UPDATE '.$t['pipeline_revisions']." SET revision_state='SEALED'"))return 'UPDATE vf_synthetic_missing_table SET id=1';
 if($pipelineFailureFlags['begin']&&str_starts_with($sql,'INSERT INTO '.chr(96).$t['pipeline_revisions'].chr(96)))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 foreach(['steps','edges'] as $part)if($pipelineFailureFlags[$part]&&str_starts_with($sql,'INSERT INTO '.chr(96).$t['pipeline_'.$part].chr(96)))return 'INSERT INTO vf_synthetic_missing_table (id) VALUES (1)';
 return $sql;
},999);
$pipelineImpact=get_option('vf_runner_pipeline_impact','unknown');
add_filter('vf_tools_m3u8_pipeline_archive_impact',function($v)use($pipelineImpact){return $pipelineImpact==='none'?['known'=>true,'production_usage'=>false,'dependents'=>[]]:['known'=>false,'production_usage'=>null,'dependents'=>[]];},999);
