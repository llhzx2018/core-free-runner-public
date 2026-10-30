<?php
// WordPress-only synthetic fixture; no production data or network access.
$keys = ['vf_tool_m3u8_settings','vf_m3u8_skin_seasonal_settings','vf_m3u8_custom_skin_registry','vf_m3u8_custom_seasonal_registry','vf_m3u8_skin_seasonal_migration_evidence','vf_m3u8_skin_seasonal_migration_snapshot','vf_m3u8_skin_seasonal_migration_version'];
$missing = '__VF_ABSENT_91__';
$before=[]; foreach($keys as $k) $before[$k]=get_option($k,$missing);
try {
  $inventory=vf_m3u8_skin_seasonal_legacy_inventory();
  if ((int)$inventory['legacyFoundCount']!==0) throw new Exception('fixture requires empty legacy inventory');
  $e=vf_m3u8_skin_seasonal_migration_state();
  if (($e['code']??'')!=='NOT_APPLICABLE_WITH_PROOF'||!empty($e['canRetireLegacy'])) throw new Exception('fixture must retain failed retirement evidence');
  $snapshot=get_option(vf_m3u8_skin_seasonal_migration_snapshot_option_name(),null);
  $state=serialize($e); $snapshotState=serialize($snapshot);
  for($i=0;$i<3;$i++) {
    $r=vf_m3u8_skin_seasonal_migrate_from_legacy_v12216();
    if (($r['code']??'')!=='RETRY_DEFERRED_NO_LEGACY'||!empty($r['canRetireLegacy'])) throw new Exception('unchanged empty input must defer while keeping retirement false');
    if (serialize(vf_m3u8_skin_seasonal_migration_state())!==$state || serialize(get_option(vf_m3u8_skin_seasonal_migration_snapshot_option_name(),null))!==$snapshotState) throw new Exception('repeated request changed recovery evidence');
  }
  $legacy=get_option('vf_tool_m3u8_settings',[]); if(!is_array($legacy)) $legacy=[];
  $legacy['frontend_base_skin']='clean_utility'; update_option('vf_tool_m3u8_settings',$legacy);
  $changed=vf_m3u8_skin_seasonal_migrate_from_legacy_v12216();
  if (($changed['code']??'')==='RETRY_DEFERRED_NO_LEGACY' || (int)($changed['legacyFoundCount']??0)<1) throw new Exception('new legacy data must reach existing migration');
  if (!empty($changed['canRetireLegacy'])) throw new Exception('failed preview contract must not authorize legacy retirement');
  echo wp_json_encode(['status'=>'PASS','scope'=>'empty retry, recovery snapshot, changed legacy and fail-closed retirement']);
} finally {
  foreach($before as $k=>$v) { if($v===$missing) delete_option($k); else update_option($k,$v); }
}
