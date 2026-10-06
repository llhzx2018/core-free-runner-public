<?php
wp_set_current_user(1);
vf_theme_bootstrap_require_many(require get_template_directory().'/inc/bootstrap/manifests/admin-tabs/recovery.php');
$before=vf_theme_recovery_current_stores();$raw=vf_theme_recovery_store_raw_state();
$document=vf_theme_export_config()['payload'];$document['stores']['brand']['siteName']='Synthetic isolated readback probe';
$errors=[];$candidate=vf_theme_recovery_sanitize_stores($document['stores'],$errors);
$diff=[];
function synthetic_readback_diff($expected,$actual,$path,array &$diff):void {
 if(is_array($expected)&&is_array($actual)) {
  if(array_keys($expected)!==array_keys($actual))$diff[]=['path'=>$path,'kind'=>'ARRAY_KEYS_OR_ORDER','expectedKeys'=>array_keys($expected),'actualKeys'=>array_keys($actual)];
  foreach(array_unique(array_merge(array_keys($expected),array_keys($actual))) as $key)synthetic_readback_diff($expected[$key]??null,$actual[$key]??null,$path.'.'.$key,$diff);
 } elseif($expected!==$actual)$diff[]=['path'=>$path,'kind'=>'VALUE','expected'=>$expected,'actual'=>$actual];
}
try {vf_theme_recovery_write_stores($candidate);$actual=vf_theme_recovery_current_stores();synthetic_readback_diff($candidate,$actual,'stores',$diff);}
finally {$restored=vf_theme_recovery_restore_raw_state($raw);}
$after=vf_theme_recovery_current_stores();
$restore_ok=$restored&&hash_equals(vf_theme_recovery_hash($before),vf_theme_recovery_hash($after));
echo wp_json_encode(['status'=>$diff?'MISMATCH_OBSERVED':'MATCH_OBSERVED','validationErrors'=>$errors,'diff'=>$diff,'restore_ok'=>$restore_ok]);
if(!$restore_ok)throw new Exception('isolated diagnostic restore failed');

