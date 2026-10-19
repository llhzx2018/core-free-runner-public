<?php
// Synthetic owner-authored WordPress articles; never deployed or written to Production.
$out=[];
foreach(['en','zh'] as $lang){
  $ids=get_posts(['post_type'=>'post','post_status'=>'publish','posts_per_page'=>3,'fields'=>'ids','orderby'=>'ID','order'=>'ASC','lang'=>$lang]);
  if(count($ids)<2)throw new RuntimeException('Insufficient synthetic '. $lang . ' blog articles');
  $zh=$lang==='zh';
  $headings=$zh?['问题背景','实际验证步骤','判断结果','下一步操作']:['Problem context','Practical inspection','Interpreting results','Next steps'];
  $long='<p>'.($zh?'这是一份仅用于自动化验收的长文章。':'This synthetic article tests the real article reading flow.').'</p>';
  foreach($headings as $i=>$heading){
    $long.='<h2>'.esc_html($heading).'</h2>';
    $long.='<p>'.str_repeat($zh?'先收集正确的浏览器证据，再决定是否修改站点。':'Record the browser evidence, inspect the authorized playlist, and use the appropriate tool only when permitted. ',5).'</p>';
  }
  $long.='<h3>'.($zh?'排查提示':'Interpretation tip').'</h3><p>'.($zh?'不要上传敏感链接。':'Do not upload private credentials.').'</p>';
  $long.='<p><a href="/m3u8-checker/">'.($zh?'打开检查工具':'Open checker').'</a></p>';
  $short='<h2>'.($zh?'简短说明':'Short note').'</h2><p>'.($zh?'这是简短文章，不应该被强制插入完整目录。':'Short articles should not get an artificial oversized contents rail.').'</p>';
  foreach([0=>$long,1=>$short] as $i=>$content){
    $save=wp_update_post(['ID'=>(int)$ids[$i],'post_content'=>$content],true);
    if(is_wp_error($save)||$save!==(int)$ids[$i])throw new RuntimeException('fixture write failed '.$lang.' '.$i);
  }
  $out[$lang]=['long'=>get_permalink($ids[0]),'short'=>get_permalink($ids[1]),'title'=>get_the_title($ids[0])];
}
echo json_encode(['status'=>'PASS','fixture'=>'ISOLATED_ONLY','posts'=>$out],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES).PHP_EOL;
