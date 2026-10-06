<?php
wp_set_current_user(1);
vf_theme_bootstrap_require_many(require get_template_directory().'/inc/bootstrap/manifests/admin-tabs/recovery.php');
$before=vf_theme_recovery_current_stores();$raw=vf_theme_recovery_store_raw_state();
$candidate=$before;$candidate['navigation']['shell']['header']['height']=78;
try {
 vf_theme_recovery_write_stores($candidate);
 $actual=vf_theme_recovery_current_stores();
 $observed=(int)$actual['navigation']['shell']['header']['height'];
 $defect=$observed!==78;
} finally { $restored=vf_theme_recovery_restore_raw_state($raw); }
$restore_ok=$restored&&hash_equals(vf_theme_recovery_hash($before),vf_theme_recovery_hash(vf_theme_recovery_current_stores()));
if(!$defect||!$restore_ok)throw new RuntimeException('BASELINE_NAVIGATION_COUNTERFACTUAL_FAILED');
echo wp_json_encode(['status'=>'PASS','outcome'=>'BASELINE_DEFECT_REPRODUCED','expected_header_height'=>78,'observed_header_height'=>$observed,'actual_original_state_restored'=>$restore_ok,'production'=>'NOT_EXECUTED']);

