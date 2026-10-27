<?php
// Isolated synthetic fixtures, before all protected-state baselines.
$layout=get_option('vf_theme_layout',[]);
foreach(['search'=>3,'blog_index'=>9] as $key=>$count){$layout['moduleSettings'][$key]['post_list']=array_merge($layout['moduleSettings'][$key]['post_list']??[],['override'=>true,'count'=>$count,'show_pagination'=>true,'sort'=>'title_asc','excerpt_words'=>28]);}
update_option('vf_theme_layout',$layout);update_option('posts_per_page',3);update_option('vf_summary_probe_executed','not-executed');
$out=[];$pairs=[];
foreach(['en','zh'] as $lang){
 $zh=$lang==='zh';$prefix=$zh?'/zh':'';
 $plain=$zh?'先找到实际失败的请求，再分别核对服务器响应与浏览器跨域提示。保留测试时间、使用环境和经过脱敏的播放地址，避免把不同时间的结果直接比较。修改配置前先记录这次观察，检查后还可以用相同条件复测。':'First identify the request that actually failed, then compare the server response with the browser cross-origin message. Record the observation time, environment and a redacted source reference so another person can repeat the same task without guessing which conditions changed between the two attempts.';
 $body=$zh?str_repeat('这是未填写专属摘要时需要读取的正文回退内容，应该保留足够信息帮助访客选择正确结果。',8):str_repeat('This fallback body explains the task, the input and the expected result before asking the reader to continue. ',8);
 for($i=1;$i<=10;$i++){
  $excerpt=$i===10?'':'<strong>'.$plain.'</strong> [vf_summary_probe]';
  $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_title'=>'Search206 '.sprintf('%02d',$i).' '.$lang,'post_name'=>'search206-'.$lang.'-'.$i,'post_excerpt'=>$excerpt,'post_content'=>'<p>'.$body.'</p> [vf_summary_probe]'],true);
  if(is_wp_error($id))throw new RuntimeException('SEED_FAILED');pll_set_post_language($id,$lang);$pairs[$i][$lang]=$id;
 }
 $out[$lang]=['search'=>home_url($prefix.'/?s=Search206&type=article'),'entry'=>home_url($prefix.'/search/?q=Search206&type=article'),'home'=>home_url($prefix.'/'),'tools'=>home_url($prefix.'/tools/'),'blog'=>home_url($prefix.'/blog/?q=Search206'),'authored'=>$plain];
}
foreach($pairs as $pair)pll_save_post_translations($pair);
global $wpdb;
$ids=$wpdb->get_col("SELECT ID FROM {$wpdb->posts} WHERE post_type IN ('post','vf_guide','vf_problem','vf_glossary') AND post_status='publish' ORDER BY ID");
foreach($ids as $i=>$id){$stamp=gmdate('Y-m-d H:i:s',1577836800+$i*3600);$wpdb->update($wpdb->posts,['post_modified'=>$stamp,'post_modified_gmt'=>$stamp],['ID'=>(int)$id]);clean_post_cache((int)$id);}
echo wp_json_encode($out);
