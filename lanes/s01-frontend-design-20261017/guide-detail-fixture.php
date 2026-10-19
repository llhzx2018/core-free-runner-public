<?php
// Synthetic guide data: isolated WordPress only. Runs before protected-state snapshots.
foreach (['en','zh'] as $lang) {
  $ids=get_posts(['post_type'=>'vf_guide','post_status'=>'publish','fields'=>'ids','posts_per_page'=>2,'orderby'=>'ID','order'=>'ASC','lang'=>$lang]);
  if(count($ids)<2)throw new RuntimeException('Missing isolated guide fixture '.$lang);
  $zh=$lang==='zh';
  $sections=$zh
    ? [['概念与用途','理解播放列表和浏览器播放的基本条件。'],['检查步骤','先检查清单权限，再验证媒体分片。'],['实践与下一步','使用本站工具检查已授权的地址。']]
    : [['Concept and purpose','Understand the playlist and browser access first.'],['Inspection steps','Verify the manifest, segment access, and codecs.'],['Practice and next steps','Use an authorized test URL with our tool.']];
  $content='<p>'.($zh?'本文是隔离环境里的真实阅读交互测试。':'This is synthetic authored content used only for browser tests.').'</p>';
  foreach($sections as $section)$content.='<h2>'.esc_html($section[0]).'</h2><p>'.esc_html($section[1]).'</p><p>'.esc_html($section[1]).'</p>';
  $content.='<h3>'.($zh?'常见问题':'Frequently asked question').'</h3><p>'.($zh?'不能绕过服务器访问限制。':'Browser access does not override server restrictions.').'</p>';
  $content.='<p><a href="/m3u8-checker/">'.($zh?'打开检查工具':'Open checker tool').'</a></p>';
  $saved=wp_update_post(['ID'=>(int)$ids[0],'post_content'=>$content],true);
  if(is_wp_error($saved)||$saved!==(int)$ids[0])throw new RuntimeException('Synthetic guide update failed');
}
echo "GUIDE_DETAIL_FIXTURE=PASS languages=2 isolated_only=yes\n";
