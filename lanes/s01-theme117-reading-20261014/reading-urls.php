<?php
$urls=[];
foreach (['en','zh'] as $lang) foreach (['guide_detail','article_detail','problem_detail','glossary_detail'] as $kind) {
    $p=get_page_by_path('s01-reading-'.$kind.'-'.$lang,OBJECT,'post');
    $urls[$lang][$kind]=get_permalink($p);
}
echo wp_json_encode(['status'=>'PASS','data'=>'synthetic_only','urls'=>$urls]);
