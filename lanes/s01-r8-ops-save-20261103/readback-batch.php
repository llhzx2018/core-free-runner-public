<?php
if (!defined('ABSPATH')||!defined('WP_CLI')||!WP_CLI){throw new RuntimeException('Isolated WordPress CLI only');}
$host=(string)wp_parse_url(home_url('/'),PHP_URL_HOST);
if(!in_array($host,['localhost','127.0.0.1'],true))throw new RuntimeException('Nonlocal WordPress prohibited');
$dir='/tmp/s01-r8-ops-save-evidence';
$fixture=json_decode((string)file_get_contents($dir.'/fixture.json'),true);
$browser=json_decode((string)file_get_contents($dir.'/batch-browser-results.json'),true);
if(!is_array($browser)||($browser['passed']??0)!==6||($browser['failed']??99)!==0)throw new RuntimeException('Actual batch Chromium not PASS');
$ids=(array)($fixture['ids']??[]);
if(count($ids)!==3)throw new RuntimeException('Fixture scope drift');
$audit=get_option('vf_ops_content_lifecycle_audit_v13',[]);
if(!is_array($audit))throw new RuntimeException('Lifecycle audit unavailable');
$report=[];
foreach($ids as $suffix=>$id){
 $id=(int)$id;
 $post=get_post($id);
 if(!$post||(string)$post->post_title!=='R8 Ops Core Save Fixture '.$suffix)throw new RuntimeException('Wrong post identity');
 if((string)$post->post_status!=='draft')throw new RuntimeException('Draft rollback failed '.$suffix);
 if((string)get_post_meta($id,'_vf_ops_workflow_status',true)!=='draft')throw new RuntimeException('Workflow rollback failed '.$suffix);
 if((string)get_post_meta($id,'_vf_ops_is_core',true)!=='')throw new RuntimeException('Core mutated unexpectedly '.$suffix);
 $actions=array_values(array_filter($audit,static fn($a)=>is_array($a)&&(int)($a['post_id']??0)===$id));
 if($suffix==='peer'){
  if($actions!==[])throw new RuntimeException('Peer lifecycle mutated');
  $report[$suffix]='UNCHANGED';
  continue;
 }
 $passes=array_values(array_filter($actions,static fn($a)=>($a['result']??'')==='PASS'));
 $fails=array_values(array_filter($actions,static fn($a)=>($a['result']??'')==='FAIL'));
 if(count($passes)!==2||count($fails)!==1){
  throw new RuntimeException('Unexpected lifecycle receipt count '.$suffix.': '.wp_json_encode($actions));
 }
 if((string)($passes[0]['action']??'')!=='transition_draft'
   ||(string)($passes[1]['action']??'')!=='transition_refining'){
  throw new RuntimeException('Incorrect lifecycle transition audit '.$suffix);
 }
 if(!str_starts_with((string)($fails[0]['action']??''),'revision_conflict_')){
  throw new RuntimeException('Concurrent stale form was not rejected '.$suffix);
 }
 $report[$suffix]='BULK_SAVED_CONFLICT_BLOCKED_ROLLBACK_PASS';
}
echo 'S01_R8_OPS_BATCH_INDEPENDENT_DB_READBACK_PASS '.wp_json_encode($report,JSON_UNESCAPED_SLASHES).PHP_EOL;
file_put_contents($dir.'/batch-wpcli-readback.json',wp_json_encode(['status'=>'PASS','readback'=>$report],JSON_PRETTY_PRINT));
