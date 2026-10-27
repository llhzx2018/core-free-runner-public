<?php
require_once get_template_directory().'/inc/renderers/family-render-data.php';
require_once get_template_directory().'/inc/modules/module-hero.php';
$custom=['title'=>'Custom <heading>','description'=>'Custom <explanation>','eyebrow'=>'Custom label','hero_actions'=>[['href'=>'/tools/','label'=>'Custom action','style'=>'secondary']],'trust_items'=>['Custom trust'],'notice'=>'Custom notice'];
ob_start();vf_theme_module_render_hero(['field_data'=>$custom],'not_found');$html=ob_get_clean();
foreach(['Custom &lt;heading&gt;','Custom &lt;explanation&gt;','Custom label','Custom action','Custom trust','Custom notice'] as $text){if(!str_contains($html,$text)){throw new RuntimeException('Authored 404 hero item lost');}}
foreach(['The route may have changed. Search the site or continue from a verified public route.','链接可能已变化。请搜索站内内容，或从已验证的公开入口继续。'] as $description){
    ob_start();vf_theme_module_render_hero(['field_data'=>['title'=>'Preserved Page title','description'=>$description,'eyebrow'=>'404']],'not_found');$html=ob_get_clean();
    if(!str_contains($html,'Preserved Page title')||str_contains($html,'verified public route')||str_contains($html,'已验证的公开入口')||str_contains($html,'vf-family-eyebrow')){throw new RuntimeException('Stock 404 explanation did not simplify safely');}
}
echo "AUTHORED_HERO_AND_PAGE_TITLE_PRESERVED_PASS\n";
