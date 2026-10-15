<?php
$options=get_option('polylang',[]);$options['post_types']=['vf_guide','vf_problem','vf_glossary','vf_tool_note'];update_option('polylang',$options);
for($i=1;$i<=26;$i++){
    $id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'publish','post_title'=>'Directory Fixture English '.sprintf('%02d',$i),'post_name'=>'directory-fixture-en-'.$i,'post_content'=>'<p>Original synthetic guide body '.$i.'</p>','post_excerpt'=>'Original excerpt '.$i]);
    if(is_wp_error($id)||!$id){throw new RuntimeException('seed failed');}pll_set_post_language($id,'en');
}
for($i=1;$i<=3;$i++){
    $id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'publish','post_title'=>'Directory Fixture 中文 '.$i,'post_name'=>'directory-fixture-zh-'.$i,'post_content'=>'<p>中文原文 '.$i.'</p>','post_excerpt'=>'中文摘要 '.$i]);pll_set_post_language($id,'zh');
}
foreach(['draft','private'] as $status){$id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>$status,'post_title'=>'Directory Fixture HIDDEN '.$status,'post_content'=>'Must not appear']);pll_set_post_language($id,'en');}
$pair=[];foreach(['en','zh'] as $lang){$id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>$lang==='en'?'About Directory Fixture':'关于目录示例','post_name'=>'about','post_content'=>'<p>Original about body</p>']);pll_set_post_language($id,$lang);$pair[$lang]=$id;}
pll_save_post_translations($pair);
$id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_title'=>'Directory Literal <b>Title</b>','post_content'=>'<p>Original article</p>']);pll_set_post_language($id,'en');
$id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_title'=>'Tool Fixture','post_name'=>'m3u8-player','post_content'=>'<p>Tool page fixture</p>']);pll_set_post_language($id,'en');
if(!get_user_by('login','subscriber')){wp_insert_user(['user_login'=>'subscriber','user_pass'=>'Synthetic-Subscriber-47!','user_email'=>'subscriber@example.invalid','role'=>'subscriber']);}
echo wp_json_encode(['status'=>'SEEDED','englishGuides'=>26,'chineseGuides'=>3]);
