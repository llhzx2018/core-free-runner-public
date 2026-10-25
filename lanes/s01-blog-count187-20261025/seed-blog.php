<?php
// Isolated synthetic articles only, before the protected-state baseline.
foreach (get_posts(['post_type'=>'post','post_status'=>'any','numberposts'=>-1,'suppress_filters'=>true,'fields'=>'ids']) as $id) { wp_delete_post($id,true); }
$layout=get_option('vf_theme_layout',[]);
$layout['moduleSettings']['blog_index']['post_list']=['override'=>true,'source'=>'latest_posts','content_type'=>'post','count'=>9,'sort'=>'published_desc','excerpt_words'=>28,'show_image'=>true,'show_date'=>true,'show_category'=>true,'show_read_time'=>true,'show_search'=>true,'show_pagination'=>true];
update_option('vf_theme_layout',$layout);
$names=[['Checking playlists before playback','播放前如何检查播放列表'],['Browser access and response headers','浏览器访问与响应头'],['Master playlists and media playlists','主播放列表与媒体播放列表'],['Finding an HLS playback issue with a deliberately long title about access restrictions and browser limitations','使用较长标题说明如何查找 HLS 播放、访问限制与浏览器兼容问题'],['Understanding segment responses','理解分片响应'],['A published workflow note','已发布的工作流笔记'],['Working with authorized HLS streams','使用已授权的 HLS 流'],['Inspecting an authored manifest','检查已整理的媒体清单'],['Backup decisions','备份前的选择'],['Keeping URLs private','保护链接隐私'],['Live and VOD','直播与点播'],['A short note','简短笔记']];
$expected=[];
foreach($names as $n=>$labels){$pair=[];foreach(['en','zh'] as $lang){$zh=$lang==='zh';$i=$n+1;
 $excerpt=$zh?'本文介绍播放列表结构、浏览器访问条件和排查流程，帮助你在操作之前理解现有工具的用途与限制。保留编辑填写的完整摘要，避免按英文单词数量截断中文说明。摘要末尾标记。':'Understand playlist structure, browser access conditions and the existing tools before starting a workflow. Preserve the complete editor-authored summary rather than clipping it to an arbitrary word budget. Authored summary tail.';
 $body='<h2>Article context</h2><p>poolneedle187</p><p>'.str_repeat('Read authorized streaming documentation and keep the original source. ',55).'</p>';
 if($i===2)$body.='<p>bodyonlyneedle186</p>';
 if($i===3)$body.='<p>A legitimate article about redirect headers and location hints, without executable redirection.</p>';
 if($i===8)$excerpt='';
 if($i===9)$excerpt.=' [vf_summary_probe] <img src=x onerror="window.summaryUnsafe=true">';
 $id=wp_insert_post(['post_type'=>'post','post_author'=>1,'post_status'=>'publish','post_name'=>'blog-reference-'.$i.'-'.$lang,'post_title'=>sprintf('%02d ',$i).$labels[$zh?1:0],'post_excerpt'=>$excerpt,'post_content'=>$body,'post_date'=>sprintf('2026-10-%02d 10:00:00',20-$n)],true);
 if(is_wp_error($id))throw new RuntimeException('BLOG_SEED_FAILED');pll_set_post_language($id,$lang);$pair[$lang]=(int)$id;
 $cat=term_exists($i===3?('Editorial '.$lang):('M3U8 Blog'),'category');if(!$cat)$cat=wp_insert_term($i===3?('Editorial '.$lang):('M3U8 Blog'),'category');wp_set_post_categories($id,[(int)$cat['term_id']]);
 $expected[$lang][]=['id'=>(int)$id,'title'=>get_the_title($id),'href'=>get_permalink($id),'excerpt'=>$excerpt,'case'=>$i];
 }pll_save_post_translations($pair);
}
$draft=wp_insert_post(['post_type'=>'post','post_status'=>'draft','post_title'=>'DRAFT MUST NOT APPEAR','post_content'=>'bodyonlyneedle186']);pll_set_post_language($draft,'en');
// A genuine authored attachment, not a replacement cover in product source.
$upload=wp_upload_bits('synthetic-blog-cover.png',null,base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1sAAAAASUVORK5CYII='));
$attachment=wp_insert_attachment(['post_title'=>'Synthetic authored cover','post_mime_type'=>'image/png','post_status'=>'inherit'], $upload['file']);
foreach(['en','zh'] as $lang)set_post_thumbnail($expected[$lang][0]['id'],$attachment);
// One Guide is a scoped regression witness; its accepted page is not re-audited.
$pair=[];foreach(['en','zh'] as $lang){$id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'publish','post_name'=>'blog-guide-witness-'.$lang,'post_title'=>'Guide compatibility witness '.$lang,'post_excerpt'=>'Authored Guide text retained beyond a short preview budget. '.str_repeat('Retain this editorial guide excerpt. ',8),'post_content'=>'<p>Guide body.</p>']);pll_set_post_language($id,$lang);$pair[$lang]=$id;}pll_save_post_translations($pair);
$expected['excluded']=[];
foreach(['en','zh'] as $lang){foreach(['text','refresh'] as $kind){
 $body=$kind==='text'?'<p>Redirecting...</p>':'<meta http-equiv="refresh" content="0;url=/tools/">';
 $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_author'=>1,'post_name'=>'retired-shell-187-'.$kind.'-'.$lang,'post_title'=>'Legacy public handoff '.$kind.' '.$lang,'post_content'=>$body.'<p>poolneedle187 bodyonlyneedle186 invalidonly187</p>','post_date'=>'2026-10-24 11:00:00']);pll_set_post_language($id,$lang);$expected['excluded'][$lang][]=$id;
}}
echo wp_json_encode($expected);
