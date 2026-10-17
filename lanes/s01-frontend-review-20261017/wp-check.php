<?php
// Synthetic-only exact-source behavioral tests, executed inside real WordPress.
foreach (['page-runtime-contract-service','admin-preview-catalog-service','frontend-page-directory-service','frontend-page-progress-service'] as $file) { require_once get_template_directory().'/inc/services/'.$file.'.php'; }
$checks=[];
function check_progress($condition,$name): void { global $checks; $checks[]=['name'=>$name,'pass'=>(bool)$condition]; if(!$condition){throw new RuntimeException('CHECK_FAILED:'.$name);} }
$admin=get_user_by('login','admin');$admin->add_cap('vf_manage_theme_profile');wp_set_current_user($admin->ID);
$subscriber=wp_insert_user(['user_login'=>'subscriber','user_pass'=>'Synthetic-Subscriber-47!','user_email'=>'subscriber@example.invalid','role'=>'subscriber']);
update_option('vf_progress_protected_sentinel',['keep'=>'untouched']);
$protected=['sentinel'=>get_option('vf_progress_protected_sentinel'),'mods'=>get_theme_mods(),'polylang'=>get_option('polylang')];
function input_progress(string $subject='home',string $language='en',string $device='desktop'): array {
    return ['vf_theme_action'=>'frontend_pages_review_save','_wpnonce'=>wp_create_nonce('theme.frontend-pages.review'),'vf_review_subject'=>$subject,'vf_pages_language'=>$language,
        'vf_review_device'=>$device,'vf_review_phase'=>'verify','vf_review_status'=>'needs_changes','vf_review_note'=>'Synthetic reviewed home; needs alignment.',
        'vf_review_version'=>vf_theme_frontend_progress_version(),'vf_review_revision'=>vf_theme_frontend_progress_record($subject,$language,$device)['revision']];
}
function save_progress(array $input): array { $_SERVER['REQUEST_METHOD']='POST';return vf_theme_frontend_progress_save($input); }
try {
 $raw_before=$GLOBALS['wpdb']->get_var("SELECT COUNT(*) FROM {$GLOBALS['wpdb']->options} WHERE option_name LIKE 'vf_theme_frontend_review_%'");
 $record=vf_theme_frontend_progress_record('home','en','desktop');
 check_progress($record['status']==='pending'&&$record['phase']==='prototype','unwritten desktop is not accepted');
 check_progress(vf_theme_frontend_progress_record('home','en','mobile')['status']==='deferred','mobile defaults deferred');
 $_SERVER['REQUEST_METHOD']='GET';check_progress(!vf_theme_frontend_progress_save(input_progress())['attempted'],'GET cannot write');
 check_progress($raw_before===$GLOBALS['wpdb']->get_var("SELECT COUNT(*) FROM {$GLOBALS['wpdb']->options} WHERE option_name LIKE 'vf_theme_frontend_review_%'"),'reading does not initialize rows');
 $input=input_progress();wp_set_current_user(0);check_progress(!save_progress($input)['ok'],'anonymous write denied');
 wp_set_current_user((int)$subscriber);check_progress(!save_progress($input)['ok'],'subscriber write denied');wp_set_current_user($admin->ID);
 $bad=input_progress();$bad['_wpnonce']='invalid';$failure=save_progress($bad);check_progress(!$failure['ok']&&$failure['draft']['note']===$bad['vf_review_note'],'nonce failure preserves valid draft');
 foreach (['vf_review_subject'=>'unknown','vf_pages_language'=>'xx','vf_review_device'=>'tablet','vf_review_phase'=>'PASS','vf_review_status'=>'PASS','vf_review_revision'=>'junk','vf_review_note'=>['bad'],'vf_review_version'=>'older'] as $field=>$value) { $bad=input_progress();$bad[$field]=$value;check_progress(!save_progress($bad)['ok'],'reject invalid '.$field); }
 $bad=input_progress();$bad['vf_review_note']=str_repeat('x',6001);check_progress(!save_progress($bad)['ok'],'reject oversize note');
 $bad=input_progress();$bad['vf_review_status']='accepted';check_progress(!save_progress($bad)['ok'],'acceptance requires completed development');
 $bad=input_progress();$bad['vf_review_phase']='complete';$bad['vf_review_status']='accepted';$bad['vf_review_note']='';check_progress(!save_progress($bad)['ok'],'acceptance requires checked-page note');
 $input=input_progress();$input['vf_review_note']="Synthetic line one\n<script>alert(1)</script><b>safe</b>";
 check_progress(save_progress($input)['ok'],'create and actual database readback');
 $saved=vf_theme_frontend_progress_record('home','en','desktop');check_progress(!str_contains($saved['note'],'<script>')&&str_contains($saved['note'],"\n"),'sanitize stored text and preserve paragraphs');
 check_progress(vf_theme_frontend_progress_record('home','zh','desktop')['status']==='pending'&&vf_theme_frontend_progress_record('home','en','mobile')['status']==='deferred','language and device isolation');
 $stale=save_progress($input);check_progress(!$stale['ok']&&$stale['draft']['revision']===$input['vf_review_revision'],'stale save retains old revision and draft');
 check_progress(vf_theme_frontend_progress_record('home','en','desktop')['revision']===$saved['revision'],'stale save cannot overwrite newer note');
 $input=input_progress();$input['vf_review_phase']='complete';$input['vf_review_status']='accepted';check_progress(save_progress($input)['ok'],'explicit human confirmation saved');
 $vm=['language'=>'en'];$model=vf_theme_frontend_progress_model($vm,[],['ok'=>false,'subject'=>'','draft'=>[]]);check_progress($model['accepted']===1&&count($model['subjects'])===22,'20 types plus two separately tracked shared subjects');
 $key=vf_theme_frontend_progress_key('home','en','desktop');$history=json_decode(vf_theme_frontend_progress_raw($key),true);$history['version']='older';update_option($key,wp_json_encode($history),false);
 $model=vf_theme_frontend_progress_model($vm,[],['ok'=>false,'subject'=>'','draft'=>[]]);check_progress($model['accepted']===0&&!$model['records']['home']['current'],'older version confirmation never counts as current');
 $corrupt=vf_theme_frontend_progress_key('search','en','desktop');add_option($corrupt,'{"schema":99,"phase":[]}', '',false);$before=vf_theme_frontend_progress_raw($corrupt);$bad=input_progress('search');check_progress(!save_progress($bad)['ok']&&vf_theme_frontend_progress_raw($corrupt)===$before,'unknown schema and malformed legacy protected');
 $race=input_progress('guide_index');$race_key=vf_theme_frontend_progress_key('guide_index','en','desktop');check_progress(save_progress($race)['ok'],'race setup');$race=input_progress('guide_index');
 $hook=static function($sql)use($race_key){if(str_starts_with($sql,'UPDATE')&&str_contains($sql,$race_key)&&str_contains($sql,'BINARY option_value')){remove_filter('query',$GLOBALS['progress_race_hook']);$new=json_decode(vf_theme_frontend_progress_raw($race_key),true);$new['note']='Concurrent winner';update_option($race_key,wp_json_encode($new),false);}return $sql;};$GLOBALS['progress_race_hook']=$hook;add_filter('query',$hook);
 check_progress(!save_progress($race)['ok']&&vf_theme_frontend_progress_record('guide_index','en','desktop')['note']==='Concurrent winner','real SQL compare-and-swap rejects race between read and write');
 $failure_input=input_progress('about_page');$hook=static function($sql){if(str_starts_with($sql,'INSERT')&&str_contains($sql,'vf_theme_frontend_review_'))return "UPDATE {$GLOBALS['wpdb']->options} SET option_value=option_value WHERE 1=0";return $sql;};add_filter('query',$hook);$failure=save_progress($failure_input);remove_filter('query',$hook);
 check_progress(!$failure['ok']&&$failure['draft']['note']===$failure_input['vf_review_note']&&vf_theme_frontend_progress_raw(vf_theme_frontend_progress_key('about_page','en','desktop'))===null,'database failure preserves draft and does not claim success');
 check_progress(get_option('vf_progress_protected_sentinel')===$protected['sentinel']&&get_theme_mods()===$protected['mods']&&get_option('polylang')===$protected['polylang'],'protected menu settings and other state unchanged');
 foreach(array_keys(vf_theme_frontend_progress_subjects())as $subject)foreach(['en','zh']as $lang)foreach(['desktop','mobile']as $device)delete_option(vf_theme_frontend_progress_key($subject,$lang,$device));
 echo wp_json_encode(['status'=>'PASS','checks'=>$checks,'environment'=>'real isolated WordPress and MariaDB','production'=>'NOT_EXECUTED']);
}catch(Throwable $error){echo wp_json_encode(['status'=>'FAIL','checks'=>$checks,'error'=>$error->getMessage()]);exit(1);}
