<?php
// Synthetic owner-authored problem documents. No Production data.
$layout=get_option('vf_theme_layout',[]);
$layout['modules']['problem_detail']=['hero','content_block','problems','related_tools','faq','related_posts','cta'];
$layout['problemReading']['reading_width']='balanced';$layout['problemReading']['sidebarMode']='off';$layout['problemReading']['tocPosition']='inline';
update_option('vf_theme_layout',$layout);
$out=[];$pairs=[];
foreach(['en','zh']as$lang){
 $zh=$lang==='zh';$body=$zh?'<p>音画同步需要在同一播放器和同一段内容中比较。</p>':'<p>Compare audio and video timing in the same player and the same content segment.</p>';
 foreach(($zh?['确认现象','记录检查结果','复验当前来源','下一步']:['Confirm the symptom','Record the checks','Retest the current source','Next steps'])as$i=>$h){
  $body.='<h2>'.$h.'</h2><p>'.str_repeat($zh?'记录已授权来源中的实际播放现象，保留正文及元数据。':'Record the observed playback symptom from an authorized source. Preserve document content and metadata. ',12).'</p>';
  if($i===1)$body.='<ol><li>Record the same playback interval.</li><li>Compare before and after the change.</li></ol><table><thead><tr><th>Check</th><th>Observed result</th></tr></thead><tbody><tr><td>Playback</td><td>Owner-authored synthetic evidence</td></tr></tbody></table>';
 }
 foreach(['main','short','authored']as$i=>$kind){
  $content=$kind==='short'?'<p>Short owner-authored problem document.</p><h2>Observation</h2><p>Record the actual symptom.</p><h2>Verify</h2><p>Retest the authorized source.</p>':$body;
  $id=wp_insert_post(['post_type'=>'vf_problem','post_status'=>'publish','post_name'=>'hls-audio-out-of-sync-'.$kind.'-'.$lang,'post_title'=>$zh?'HLS 音画不同步：桌面合成验收 '.$kind:'HLS Audio Out of Sync: Synthetic Desktop Check '.$kind,'post_excerpt'=>$zh?'作者填写的问题摘要，保留真实排查范围。':'An authored problem excerpt with a specific troubleshooting scope.','post_content'=>$content,'post_date'=>'2026-10-'.(20+$i).' 10:00:00'],true);
  if(is_wp_error($id))throw new RuntimeException('PROBLEM_FIXTURE_FAILED');pll_set_post_language($id,$lang);
  update_post_meta($id,'rank_math_title','Owner problem SEO '.$kind.' '.$lang);update_post_meta($id,'rank_math_description','Owner problem description '.$kind.' '.$lang);
  if($kind==='authored'){
   update_post_meta($id,'_vf_problem_diagnostic_steps',"Owner step one\nOwner step two");update_post_meta($id,'_vf_problem_root_cause','Owner root <script>window.problemInjected=true</script>');update_post_meta($id,'_vf_problem_fix','Owner fix retained');update_post_meta($id,'_vf_problem_verification','Owner verification retained');
  }
  $out[$lang][$kind]=get_permalink($id);$pairs[$kind][$lang]=$id;
 }
}
foreach($pairs as$pair)pll_save_post_translations($pair);
echo wp_json_encode($out);
