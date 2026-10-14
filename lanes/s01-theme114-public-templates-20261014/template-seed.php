<?php
foreach(vf_theme_available_contexts() as $kind) {
    $slug='s01-template-'.$kind;
    if (get_page_by_path($slug,OBJECT,'post')) { continue; }
    $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_name'=>$slug,'post_title'=>'Synthetic Content Owner '.$kind,'post_excerpt'=>'Synthetic document summary.','post_content'=>'<h2>First section</h2><p>Synthetic reading fixture with a <a href="/tools/">tool directory link</a>.</p><h2>Second section</h2><p>Browser tasks remain owned by the existing Provider.</p>'],true);
    if(is_wp_error($id)) { throw new RuntimeException('SYNTHETIC_INSERT_FAILED'); }
    if(function_exists('pll_set_post_language'))pll_set_post_language($id,'en');
}
echo wp_json_encode(['status'=>'PASS','contexts'=>vf_theme_available_contexts(),'context_count'=>count(vf_theme_available_contexts()),'data'=>'synthetic_only']);
