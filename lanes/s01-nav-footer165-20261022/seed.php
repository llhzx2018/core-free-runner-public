<?php
// Synthetic isolated review fixtures, before the protected-state snapshot.
$base=['schema'=>1,'phase'=>'complete','status'=>'accepted','note'=>'Synthetic existing owner record preserved','version'=>'1.35.162','updated'=>'2026-10-21 12:00:00','user'=>1,'token'=>'synthetic-record-162'];
foreach ([['home','en','desktop'],['contact_page','en','desktop']] as [$subject,$language,$device]) {
    $value=array_merge($base,compact('subject','language','device'));
    if ($subject==='contact_page') {$value['status']='needs_changes';$value['note']='Synthetic contact note preserved';}
    update_option('vf_theme_frontend_review_'.hash('sha256',$subject.'|'.$language.'|'.$device),wp_json_encode($value),false);
}
update_option('vf_theme_frontend_review_'.hash('sha256','about_page|zh|mobile'),'{"schema":99,"keep":"unknown-schema-must-not-change"}',false);



// Synthetic content only, before the protected-state baseline.
foreach (['en','zh'] as $lang) {
    for ($i=1;$i<=25;$i++) {
        $id=wp_insert_post(['post_type'=>'post','post_status'=>'publish','post_title'=>'Directory coverage fixture '.$lang.' '.$i,'post_name'=>'directory-coverage-fixture-'.$lang.'-'.$i,'post_content'=>'<p>Synthetic directory pagination fixture.</p>']);
        if (is_wp_error($id) || !$id) { throw new Exception('SYNTHETIC_SEED_FAILED'); }
        pll_set_post_language($id,$lang);
    }
}
echo 'SYNTHETIC_DIRECTORY_SEED_PASS';
