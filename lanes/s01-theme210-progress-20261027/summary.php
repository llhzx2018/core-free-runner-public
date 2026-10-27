<?php
define('ABSPATH','/synthetic/');
$root=$argv[1];$fixed=($argv[2]??'after')==='after';
$keys=['home','tool','tool_hub','blog_index','article_detail','guide_index','guide_detail','problem_index','problem_detail','archive_list','faq_page','glossary_index','glossary_detail','legal','contact_page','about_page','basic_page','search','not_found','html_sitemap'];
function vf_theme_page_runtime_contracts(){global $keys;return array_fill_keys($keys,['label'=>'Synthetic']);}
function get_template(){return 'vf-tools-theme';}
function wp_get_theme($unused){return new class{function get($k){return '1.35.210';}};}
function vf_theme_frontend_pages_input($a,$k){return (string)($a[$k]??'');}
$wpdb=new class{
 public $options='wp_options';public $rows=[];
 function prepare($q,$key){return $key;}
 function get_var($key){return $this->rows[$key]??null;}
 function query(){throw new RuntimeException('READ_MODEL_MUST_NOT_WRITE');}
};
require $root.'/inc/services/frontend-page-progress-service.php';
function check($v,$message){if(!$v)throw new RuntimeException($message);}
$feedback=['ok'=>true,'subject'=>'','draft'=>[]];$rows=[];
foreach(['en','zh','fr']as$lang)foreach(['desktop','mobile']as$device){
 $m=vf_theme_frontend_progress_model(['language'=>$lang],['vf_review_device'=>$device],$feedback);
 check($m['accepted']===0,'history cannot sign off');
 if($fixed){check($m['history_count']===20,'fixed runtime denominator');check($m['reviewed_count']===($device==='desktop'&&in_array($lang,['en','zh'],true)?6:0),'language/device isolation');}
 $rows[]=['language'=>$lang,'device'=>$device,'status'=>'PASS'];
}
if($fixed){
 check(vf_theme_frontend_progress_history_summary([],'en','desktop')===['latest'=>'','reviewed'=>''],'empty history');
 $h=[['version'=>'1.35.200','review_languages'=>['en']],['version'=>'1.35.209'],['version'=>'1.35.208','review_languages'=>['en']]];
 check(vf_theme_frontend_progress_history_summary($h,'en','desktop')===['latest'=>'1.35.209','reviewed'=>'1.35.208'],'history versions independent');
 check(vf_theme_frontend_progress_history_summary($h,'zh','desktop')['reviewed']==='','no borrowed language');
}
$rec=['schema'=>1,'subject'=>'home','language'=>'en','device'=>'desktop','phase'=>'complete','status'=>'accepted','note'=>'Synthetic explicit signoff','version'=>'1.35.210','updated'=>'2026-10-27 12:00:00','user'=>1,'token'=>'synthetic'];
$key=vf_theme_frontend_progress_key('home','en','desktop');$wpdb->rows[$key]=json_encode($rec);$before=$wpdb->rows;
$m=vf_theme_frontend_progress_model(['language'=>'en'],[], $feedback);check($m['accepted']===1,'existing native current signoff retained');check($wpdb->rows===$before,'GET projection wrote state');
$rec['version']='1.35.209';$wpdb->rows[$key]=json_encode($rec);$m=vf_theme_frontend_progress_model(['language'=>'en'],[],$feedback);check($m['accepted']===0,'prior version not current signoff');
$wpdb->rows[$key]='{"schema":99,"keep":"invalid"}';$before=$wpdb->rows;$m=vf_theme_frontend_progress_model(['language'=>'en'],[],$feedback);check($m['records']['home']['blocked']&&$m['accepted']===0&&$wpdb->rows===$before,'invalid state protection');
echo json_encode(['status'=>'PASS','phase'=>$fixed?'after':'before','cases'=>count($rows)+($fixed?6:3),'rows'=>$rows,'production'=>'UNTOUCHED'])."\n";
