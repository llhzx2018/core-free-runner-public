<?php
define('ABSPATH', '/tmp/');
class VfReply extends Exception {
    public function __construct(public bool $success, public array $data, public int $http) { parent::__construct('reply'); }
}
$GLOBALS['allowed']=true; $GLOBALS['nonceOk']=true; $GLOBALS['stored']=true;
$GLOBALS['runtimeOk']=true; $GLOBALS['fieldsOk']=true; $GLOBALS['writes']=0;
function add_action($hook,$callable){}
function current_user_can($name){return $GLOBALS['allowed'] && $name==='vf_manage_theme_profile';}
function sanitize_text_field($s){return $s;}
function wp_unslash($s){return $s;}
function wp_verify_nonce($value,$action){return $GLOBALS['nonceOk'] && $value==='test-token' && $action==='theme.seo.save';}
function esc_html__($s){return $s;}
function wp_die($message,$title='', $args=[]){throw new VfReply(false,['failureCode'=>'BLOCKED','message'=>$message],403);}
function wp_send_json_success($data,$code=200){throw new VfReply(true,$data,$code);}
function wp_send_json_error($data,$code=200){throw new VfReply(false,$data,$code);}
function update_option(){ $GLOBALS['writes']++; throw new Exception('WRITE FORBIDDEN'); }
function delete_option(){ $GLOBALS['writes']++; throw new Exception('DELETE FORBIDDEN'); }
function theme_seo_save(){ $GLOBALS['writes']++; throw new Exception('SAVE FORBIDDEN'); }
function get_current_user_id(){return 1;}
function theme_seo_readback(){return ['stored'=>$GLOBALS['stored'], 'source'=>$GLOBALS['stored']?'vf_theme_seo':'registered_defaults_without_write', 'revision'=>str_repeat('a',64),'seo'=>['searchIndexability'=>'noindex_follow','virtualRoutePolicy'=>[]],'errors'=>$GLOBALS['fieldsOk']?[]:['bad'=>'stored invalid']];}
function vf_theme_seo_runtime_verification($state){return ['ok'=>$GLOBALS['runtimeOk'],'manifest'=>vf_theme_seo_runtime_manifest($state['seo'])];}
function vf_theme_seo_runtime_manifest($seo){return ['schemaVersion'=>'1.0.0','owner'=>'vf-theme','revision'=>str_repeat('a',64),'robots'=>[],'virtualRoutePolicy'=>[],'ownerBoundary'=>[],'previewLinks'=>[]];}
require getcwd().'/target/src/inc/admin/admin-seo-actions.php';
function exercise(string $id, callable $setup, bool $success, int $http, string $code=''): void {
    $GLOBALS['allowed']=true;$GLOBALS['nonceOk']=true;$GLOBALS['stored']=true;
    $GLOBALS['runtimeOk']=true;$GLOBALS['fieldsOk']=true;
    $_POST=['nonce'=>'test-token','revision'=>str_repeat('a',64),'seo'=>['malicious'=>'write']];
    $setup();
    try { vf_theme_seo_ajax_verify();throw new Exception('NO_RESPONSE:'.$id); }
    catch(VfReply $r){
        if($r->success!==$success||$r->http!==$http||($code!==''&&($r->data['failureCode']??'')!==$code))throw new Exception('BAD_'. $id .':'.json_encode($r->data));
        if($success && ($r->data['stages']['execute']??null)!=='skipped')throw new Exception('VERIFY_EXECUTED_WRITE');
        echo 'PASS_'.$id."\n";
    }
}
exercise('readback',fn()=>null,true,200);
exercise('permission',fn()=> $GLOBALS['allowed']=false,false,403,'PERMISSION_DENIED');
exercise('csrf',fn()=> $GLOBALS['nonceOk']=false,false,403,'NONCE_INVALID');
exercise('defaults',fn()=> $GLOBALS['stored']=false,false,422,'DEFAULT_NOT_STORED');
exercise('revision',fn()=> $_POST['revision']=str_repeat('b',64),false,409,'REVISION_CONFLICT');
exercise('empty_revision',fn()=> $_POST['revision']='',false,409,'REVISION_CONFLICT');
exercise('stored_validation',fn()=> $GLOBALS['fieldsOk']=false,false,422,'VALIDATION_FAILED');
exercise('runtime_failure',fn()=> $GLOBALS['runtimeOk']=false,false,422,'RUNTIME_CONSUMER_MISMATCH');
if($GLOBALS['writes']!==0)throw new Exception('UNEXPECTED_WRITE_COUNT='.$GLOBALS['writes']);
echo 'PASS_ZERO_WRITES_EIGHT_PATHS'."\n";
