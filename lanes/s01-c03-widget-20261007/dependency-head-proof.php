<?php
wp_set_current_user(1);
vf_theme_bootstrap_require_many(require get_template_directory().'/inc/bootstrap/manifests/admin-tabs/preview.php');
$rows=[];
foreach(['tool'=>'/m3u8-player/','guide_detail'=>'/guides/how-to-check-if-m3u8-is-encrypted/','problem_detail'=>'/problems/m3u8-403-forbidden-fix/','article_detail'=>'/tool-notes/m3u8-player/'] as $type=>$route){
    $request=vf_theme_preview_workbench_resolve_candidate_request('page_type:'.$type,'en');
    $expected=vf_theme_seo_inspector_expected($request);$fetch=vf_theme_seo_inspector_fetch(home_url($route));
    $issues=vf_theme_seo_inspector_compare($request,$expected,$fetch);
    $row=['type'=>$type,'route'=>$route,'resolved_url'=>$request['url'],'post_id'=>$request['postId']??0,'expected'=>$expected,'actual'=>$fetch['actual'],'issues'=>$issues,'http'=>$fetch['code']??0];
    $rows[]=$row;
}
// Hreflang's canonical contract emits nothing for a single-language published
// object. Do not manufacture an EN/ZH pair in this WordPress-owned test content.
echo wp_json_encode(['scope'=>'ACTUAL_PUBLIC_HEAD_VS_CANONICAL_OBJECT_EXPECTATIONS','rows'=>$rows,'production'=>'NOT_EXECUTED'],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES);
