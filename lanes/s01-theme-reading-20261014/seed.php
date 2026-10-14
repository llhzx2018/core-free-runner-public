<?php
require_once ABSPATH.'wp-admin/includes/template.php';
$model = new PLL_Admin_Model(PLL()->options);
foreach ([['en','en_US','English','us'],['zh','zh_CN','中文','cn']] as $l) {
    if (!$model->get_language($l[0])) { $model->add_language(['slug'=>$l[0],'locale'=>$l[1],'name'=>$l[2],'flag'=>$l[3],'rtl'=>0,'term_group'=>0]); }
}
$o=get_option('polylang',[]); $o['default_lang']='en'; $o['hide_default']=1; $o['force_lang']=1; update_option('polylang',$o);
$layout=['articleReading'=>['sidebarMode'=>'off'],'guideReading'=>['sidebarMode'=>'off']];
update_option('vf_theme_layout',$layout);
$urls=[];
foreach (['guide_detail','article_detail','problem_detail','glossary_detail'] as $kind) foreach (['en','zh'] as $lang) {
    $body=$lang==='zh' ? '<h2 id="answer">核心结论</h2><p>保留真实正文与 <a href="/zh/tools/">工具目录链接</a>。</p><h2>检查顺序</h2><p>先确认输入，再检查结果。</p><h3>检查顺序</h3><p>保留代码 <code>EXT-X-KEY</code>。</p><h2>安全边界</h2><p>只处理已授权的内容。</p>' : '<h2 id="answer">Core answer</h2><p>Keep actual body and <a href="/tools/">tool directory link</a>.</p><h2>Check order</h2><p>Check input before the result.</p><h3>Check order</h3><p>Keep code <code>EXT-X-KEY</code>.</p><h2>Safety limits</h2><p>Use authorized content.</p>';
    $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_name'=>'s01-template-'.$kind.'-'.$lang,'post_title'=>'Synthetic Content Owner '.$kind,'post_excerpt'=>'Synthetic document summary.','post_content'=>$body],true);
    if (is_wp_error($id)) { throw new RuntimeException('SYNTHETIC_INSERT_FAILED'); }
    pll_set_post_language($id,$lang);
    $urls[$lang][$kind]=get_permalink($id);
}
echo wp_json_encode(['status'=>'PASS','data'=>'synthetic_only','urls'=>$urls]);
