<?php
// Synthetic content only, before the protected-state baseline.
foreach (['en','zh'] as $lang) {
    for ($i=1;$i<=25;$i++) {
        $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_title'=>'Directory coverage fixture '.$lang.' '.$i,'post_name'=>'directory-coverage-fixture-'.$lang.'-'.$i,'post_content'=>'<p>Synthetic directory pagination fixture.</p>']);
        if (is_wp_error($id) || !$id) { throw new Exception('SYNTHETIC_SEED_FAILED'); }
        pll_set_post_language($id,$lang);
    }
}
echo 'SYNTHETIC_DIRECTORY_SEED_PASS';
