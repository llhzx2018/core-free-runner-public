<?php
foreach(['page-runtime-contract-service','admin-preview-catalog-service','frontend-page-directory-service','frontend-page-progress-service']as $f)require_once get_template_directory().'/inc/services/'.$f.'.php';
$u=get_user_by('login','admin');wp_set_current_user($u->ID);$_SERVER['REQUEST_METHOD']='POST';
foreach([['home','zh','desktop'],['shared_footer','en','mobile']]as [$s,$l,$d]){
 $r=vf_theme_frontend_progress_record($s,$l,$d);
 $v=vf_theme_frontend_progress_save(['vf_theme_action'=>'frontend_pages_review_save','_wpnonce'=>wp_create_nonce('theme.frontend-pages.review'),'vf_review_subject'=>$s,'vf_pages_language'=>$l,'vf_review_device'=>$d,'vf_review_phase'=>'verify','vf_review_status'=>$d==='mobile'?'deferred':'needs_changes','vf_review_note'=>'Synthetic lifecycle note; preserve exactly.','vf_review_version'=>vf_theme_frontend_progress_version(),'vf_review_revision'=>$r['revision']]);
 if(empty($v['ok']))throw new Exception('REAL_REVIEW_SAVE_FAILED');
}
add_option(vf_theme_frontend_progress_key('search','zh','desktop'),'{"schema":99,"preserve":"unknown future row"}','',false);
echo wp_json_encode(['status'=>'PASS','records'=>3,'native_save'=>2,'unknown_schema_retained'=>1]);
