<?php
foreach(['en'=>26,'zh'=>3] as $language=>$count){
 for($i=1;$i<=$count;$i++){
  $id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'publish','post_title'=>'Directory Fixture '.$language.' '.$i,'post_name'=>'directory-fixture-'.$language.'-'.$i,'post_content'=>'<h2>Fixture</h2><p>Isolated directory content.</p>'],true);
  if(is_wp_error($id)){throw new RuntimeException('DIRECTORY_FIXTURE_FAILED');}
  pll_set_post_language($id,$language);
 }
}
echo wp_json_encode(['status'=>'PASS','purpose'=>'synthetic admin content navigation','production'=>'NOT_EXECUTED']);
