#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()

def p(path): return ROOT/path
def read(path): return p(path).read_text(encoding='utf-8')
def write(path,text): p(path).parent.mkdir(parents=True,exist_ok=True);p(path).write_text(text,encoding='utf-8',newline='\n')
def replace_once(path,old,new):
    s=read(path);n=s.count(old)
    if n!=1: raise SystemExit(f'{path}: expected exact fragment once, found {n}')
    write(path,s.replace(old,new,1))
def sub_once(path,pattern,repl):
    s=read(path);out,n=re.subn(pattern,repl,s,count=1,flags=re.S)
    if n!=1: raise SystemExit(f'{path}: regex fragment not unique/found: {pattern[:100]}')
    write(path,out)

baseline='''<?php
declare(strict_types=1);
if (isset($_SERVER['SCRIPT_FILENAME']) && realpath((string)$_SERVER['SCRIPT_FILENAME']) === __FILE__) { http_response_code(404); exit; }

final class VfCommonBaseline
{
    public const BASELINE_ID='VF-COMMON-PRODUCT-BASELINE@2.0';
    public const PROFILE='PERSONAL_SINGLE_ADMIN';
    public const INSTANT_STORAGE_TIMEZONE='UTC';
    public const SYSTEM_TIMEZONE_DEFAULT='Asia/Shanghai';
    public const AUTH_IDLE_TIMEOUT_SECONDS=604800;
    public const AUTH_ABSOLUTE_TIMEOUT_SECONDS=2592000;
    public const AUTH_COOKIE_MAX_AGE_SECONDS=2592000;
    public const AUTH_SERVER_SESSION_FLOOR_SECONDS=2592000;
    public const STEP_UP_WINDOW_SECONDS=900;
    public const JOB_GENERAL_TIMEOUT_SECONDS=300;
    public const JOB_SYNC_TIMEOUT_SECONDS=900;
    public const JOB_MAINTENANCE_TIMEOUT_SECONDS=1800;
    public const JOB_LOCK_GRACE_SECONDS=60;
    public const JOB_MAX_RETRY_COUNT=3;
    public const TOAST_SUCCESS_MS=2500;
    public const TOAST_INFO_MS=4000;
    public const TOAST_WARNING_MS=6000;
    public const TOAST_ERROR_MS=6000;
    public const HEALTH_TIMEOUT_SECONDS=10;
    public const HEALTH_STALE_AFTER_SECONDS=300;
    public const ADMIN_LOCALE='zh-CN';

    private static function setting(PDO $db,string $key,string $default=''): string
    {
        $q=$db->prepare('SELECT setting_value FROM settings WHERE setting_key=? LIMIT 1');$q->execute([$key]);$v=$q->fetchColumn();return $v===false?$default:(string)$v;
    }
    private static function add(array &$rows,string $domain,string $parameter,mixed $expected,mixed $effective,string $source,string $result='PASS',string $exception='',string $reason=''): void
    {
        $rows[]=['domain'=>$domain,'parameter'=>$parameter,'expected'=>$expected,'effective'=>$effective,'source'=>$source,'exception'=>$exception,'reason'=>$reason,'result'=>$result];
    }
    public static function resolve(PDO $db): array
    {
        $rows=[];$tz=self::setting($db,'timezone',self::SYSTEM_TIMEZONE_DEFAULT);$tzValid=in_array($tz,DateTimeZone::listIdentifiers(),true)||$tz==='UTC';
        self::add($rows,'TIME','instant_storage_timezone','UTC',self::INSTANT_STORAGE_TIMEZONE,'runtime gmdate()/RFC3339 UTC contract');
        self::add($rows,'TIME','system_timezone_required',true,$tzValid,'settings.timezone',$tzValid?'PASS':'DRIFT');
        self::add($rows,'TIME','clean_install_default_timezone','Asia/Shanghai',self::SYSTEM_TIMEZONE_DEFAULT,'bootstrap install defaults');
        $keep=max(1,min(30,(int)self::setting($db,'session_keep_days','30')));
        self::add($rows,'AUTH','idle_timeout_seconds',self::AUTH_IDLE_TIMEOUT_SECONDS,self::AUTH_IDLE_TIMEOUT_SECONDS,'VfCommonBaseline + Auth.php');
        self::add($rows,'AUTH','absolute_timeout_seconds',self::AUTH_ABSOLUTE_TIMEOUT_SECONDS,self::AUTH_ABSOLUTE_TIMEOUT_SECONDS,'VfCommonBaseline + Auth.php');
        if($keep===30)self::add($rows,'AUTH','cookie_max_age_seconds',self::AUTH_COOKIE_MAX_AGE_SECONDS,$keep*86400,'settings.session_keep_days + Auth.php');
        else self::add($rows,'AUTH','cookie_max_age_seconds',self::AUTH_COOKIE_MAX_AGE_SECONDS,$keep*86400,'settings.session_keep_days + Auth.php','EXCEPTION','P03-PRESERVE-OWNER-SESSION-KEEP-DAYS','既有 Owner 显式保持登录天数按 V2 migration guard 保留；新安装默认 30 天。');
        $serverFloor=(int)ini_get('session.gc_maxlifetime');self::add($rows,'AUTH','server_session_lifetime_floor_seconds',self::AUTH_SERVER_SESSION_FLOOR_SECONDS,$serverFloor,'PHP session.gc_maxlifetime',$serverFloor>=self::AUTH_SERVER_SESSION_FLOOR_SECONDS?'PASS':'DRIFT');
        self::add($rows,'AUTH','session_rotation','ON_LOGIN_AND_CREDENTIAL_OR_PRIVILEGE_CHANGE','ON_LOGIN_AND_CREDENTIAL_CHANGE','Auth.php');
        self::add($rows,'AUTH','step_up_recent_auth_window_seconds',self::STEP_UP_WINDOW_SECONDS,self::STEP_UP_WINDOW_SECONDS,'Auth.php');
        require_once __DIR__.'/CoreUpdates/GitHubClient.php';
        self::add($rows,'API','connect_timeout_seconds',5,\CoreUpdates\GitHubClient::CONNECT_TIMEOUT_SECONDS,'CoreUpdates/GitHubClient.php',\CoreUpdates\GitHubClient::CONNECT_TIMEOUT_SECONDS<=5?'PASS':'DRIFT');
        self::add($rows,'API','request_timeout_seconds',15,\CoreUpdates\GitHubClient::REQUEST_TIMEOUT_SECONDS,'CoreUpdates/GitHubClient.php',\CoreUpdates\GitHubClient::REQUEST_TIMEOUT_SECONDS<=15?'PASS':'DRIFT');
        self::add($rows,'API','max_retry_count',3,\CoreUpdates\GitHubClient::MAX_RETRY_COUNT,'CoreUpdates/GitHubClient.php',\CoreUpdates\GitHubClient::MAX_RETRY_COUNT<=3?'PASS':'DRIFT');
        self::add($rows,'API','retry_after_header_respected',true,true,'CoreUpdates/GitHubClient.php');
        self::add($rows,'JOB','GENERAL.timeout_seconds',300,function_exists('vfab_job_timeout_seconds')?vfab_job_timeout_seconds('GENERAL'):0,'Repository.php',function_exists('vfab_job_timeout_seconds')&&vfab_job_timeout_seconds('GENERAL')===300?'PASS':'DRIFT');
        self::add($rows,'JOB','SYNC.timeout_seconds',900,function_exists('vfab_job_timeout_seconds')?vfab_job_timeout_seconds('SYNC'):0,'Repository.php',function_exists('vfab_job_timeout_seconds')&&vfab_job_timeout_seconds('SYNC')===900?'PASS':'DRIFT');
        self::add($rows,'JOB','MAINTENANCE.timeout_seconds',1800,function_exists('vfab_job_timeout_seconds')?vfab_job_timeout_seconds('MAINTENANCE'):0,'Repository.php',function_exists('vfab_job_timeout_seconds')&&vfab_job_timeout_seconds('MAINTENANCE')===1800?'PASS':'DRIFT');
        $js=@file_get_contents(VFAB_ROOT.'/assets/experience.js')?:'';
        self::add($rows,'NOTIFICATION','toast_success_duration_ms',self::TOAST_SUCCESS_MS,str_contains($js,'TOAST_SUCCESS_MS=2500')?2500:0,'assets/experience.js',str_contains($js,'TOAST_SUCCESS_MS=2500')?'PASS':'DRIFT');
        self::add($rows,'NOTIFICATION','toast_error_duration_ms',self::TOAST_ERROR_MS,str_contains($js,'TOAST_ERROR_MS=6000')?6000:0,'assets/experience.js',str_contains($js,'TOAST_ERROR_MS=6000')?'PASS':'DRIFT');
        self::add($rows,'NOTIFICATION','toast_max_visible',2,1,'single global toast + persistent inline error banner','EXCEPTION','P03-SINGLE-TOAST-ANTI-STACK','P03 使用单一替换式 Toast，天然满足不无限堆叠且不遮挡连续操作。');
        self::add($rows,'LOGGING','utc_timestamp_storage',true,class_exists('VfForgeRuntimeLogger'),'Logging.php',class_exists('VfForgeRuntimeLogger')?'PASS':'DRIFT');
        self::add($rows,'LOGGING','secret_redaction_required',true,class_exists('VfForgeRuntimeLogger'),'Logging.php',class_exists('VfForgeRuntimeLogger')?'PASS':'DRIFT');
        self::add($rows,'LOGGING','rotation_required',true,class_exists('VfForgeRuntimeLogger'),'Logging.php',class_exists('VfForgeRuntimeLogger')?'PASS':'DRIFT');
        self::add($rows,'UPDATE','single_primary_action',true,true,'UpdateService.php + settings update center');
        self::add($rows,'UPDATE','owner_manual_repair_download_required',false,false,'UpdateService.php; maintenance.php is advanced fallback');
        self::add($rows,'BACKUP','backup_verify_required',true,true,'BackupService.php + current regression');
        self::add($rows,'BACKUP','restore_preview_required',true,true,'BackupService restore preflight');
        self::add($rows,'DATA','app_version_separate_from_schema_version',true,VFAB_VERSION!==(string)VFAB_SCHEMA_VERSION,'VERSION + SCHEMA_VERSION');
        self::add($rows,'DATA','sqlite_foreign_keys','ON','ON','bootstrap SQLite contract');self::add($rows,'DATA','sqlite_busy_timeout_ms',5000,5000,'bootstrap SQLite contract');
        self::add($rows,'FILE_UPLOAD','project_asset_upload','N_A','RETIRED','P03 Zero Project Asset Storage Contract','N_A','','PROJECT-ASSET STORAGE = NONE；普通项目文件上传永久退休。');
        self::add($rows,'FILE_UPLOAD','brand_logo_max_bytes',20971520,1048576,'Repository::saveBrandLogoUpload','EXCEPTION','P03-BRAND-LOGO-1MB','仅品牌 Logo 的受控图片上传，1MB 更严格且符合产品用途。');
        $healthFile=is_file(VFAB_ROOT.'/diagnose.php');self::add($rows,'HEALTH','health_surface_required',true,$healthFile,'diagnose.php',$healthFile?'PASS':'DRIFT');self::add($rows,'HEALTH','health_check_default_timeout_seconds',10,self::HEALTH_TIMEOUT_SECONDS,'VfCommonBaseline');
        self::add($rows,'VERSION','app_version',VFAB_VERSION,VFAB_VERSION,'VERSION/bootstrap.php');self::add($rows,'VERSION','schema_version',VFAB_SCHEMA_VERSION,VFAB_SCHEMA_VERSION,'database/schema/SCHEMA_VERSION/bootstrap.php');self::add($rows,'VERSION','baseline_version','2.0','2.0','VfCommonBaseline');
        self::add($rows,'CACHE','authenticated_private_html_cache','NO_STORE','NO_STORE','vfab_security_headers');$index=@file_get_contents(VFAB_ROOT.'/index.php')?:'';self::add($rows,'CACHE','versioned_static_asset_identity',true,str_contains($index,'hash_file'),'index.php',str_contains($index,'hash_file')?'PASS':'DRIFT');self::add($rows,'CACHE','versioned_static_asset_cache_seconds',31536000,'WEB_SERVER_OWNED','HTTP server configuration','EXCEPTION','P03-WEB-SERVER-CACHE-TTL','应用提供内容哈希资产身份；静态 TTL 由部署层 Web Server Authority 控制。');
        self::add($rows,'LOCALE','vf_admin_default_locale','zh-CN',self::ADMIN_LOCALE,'index.php/html lang');self::add($rows,'UI_COMMON_STATES','system_baseline_page_mode','READ_ONLY','READ_ONLY','system-baseline.php');
        $counts=['PASS'=>0,'EXCEPTION'=>0,'DRIFT'=>0,'UNKNOWN'=>0,'N_A'=>0];foreach($rows as $row){$state=(string)$row['result'];if(isset($counts[$state]))$counts[$state]++;}$overall=($counts['DRIFT']===0&&$counts['UNKNOWN']===0)?'PASS':'DRIFT';return ['baseline'=>self::BASELINE_ID,'profile'=>self::PROFILE,'overall'=>$overall,'counts'=>$counts,'rules'=>$rows];
    }
}
'''
write('src/app/CommonBaseline.php',baseline)

logging='''<?php
declare(strict_types=1);
if (isset($_SERVER['SCRIPT_FILENAME']) && realpath((string)$_SERVER['SCRIPT_FILENAME']) === __FILE__) { http_response_code(404); exit; }
final class VfForgeRuntimeLogger
{
    public const MAX_FILE_BYTES=10485760;public const MAX_TOTAL_BYTES=268435456;public const RETENTION_DAYS=['APP_INFO'=>30,'ERROR'=>90,'SECURITY_AUDIT'=>180,'JOB'=>30,'INTEGRATION'=>30,'UPDATE_RESTORE_SUMMARY'=>365];
    public static function log(string $channel,string $level,string $message,array $context=[]): void
    {
        if(!defined('VFAB_LOG_DIR'))return;$channel=strtoupper(preg_replace('/[^A-Z0-9_]/i','_',trim($channel))?:'APP_INFO');if($channel==='DEBUG'&&getenv('VF_DEBUG_PERSIST')!=='1')return;
        try{if(!is_dir(VFAB_LOG_DIR)&&!mkdir(VFAB_LOG_DIR,0750,true)&&!is_dir(VFAB_LOG_DIR))return;$path=VFAB_LOG_DIR.'/'.strtolower($channel).'.log';self::rotate($path);$row=['timestamp'=>gmdate('c'),'channel'=>$channel,'level'=>strtoupper($level),'message'=>self::clean($message),'context'=>self::redact($context)];@file_put_contents($path,json_encode($row,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_INVALID_UTF8_SUBSTITUTE)."\n",FILE_APPEND|LOCK_EX);@chmod($path,0640);self::prune();}catch(Throwable $ignore){}
    }
    private static function clean(string $value): string{return mb_substr(preg_replace('/[\r\n]+/u',' ',trim($value))?:'',0,2000,'UTF-8');}
    private static function redact(mixed $value,string $key=''): mixed{if(preg_match('/password|passwd|token|secret|authorization|cookie|api[_-]?key/i',$key))return '[REDACTED]';if(is_array($value)){foreach($value as $k=>$v)$value[$k]=self::redact($v,(string)$k);return $value;}if(is_string($value)&&strlen($value)>4000)return substr($value,0,4000).'…';return $value;}
    private static function rotate(string $path): void{if(is_file($path)&&filesize($path)>=self::MAX_FILE_BYTES){@rename($path,$path.'.'.gmdate('YmdHis'));}}
    private static function prune(): void{$files=glob(VFAB_LOG_DIR.'/*.log*')?:[];$total=0;$now=time();foreach($files as $file){if(!is_file($file))continue;$base=strtoupper((string)preg_replace('/\.LOG.*$/i','',basename($file)));$days=self::RETENTION_DAYS[$base]??30;if((int)@filemtime($file)<$now-$days*86400){@unlink($file);continue;}$total+=(int)@filesize($file);}if($total<=self::MAX_TOTAL_BYTES)return;usort($files,static fn($a,$b)=>(int)@filemtime($a)<=>(int)@filemtime($b));foreach($files as $file){if($total<=self::MAX_TOTAL_BYTES)break;if(!is_file($file))continue;$size=(int)@filesize($file);@unlink($file);$total-=$size;}}
}
'''
write('src/app/Logging.php',logging)

replace_once('src/app/bootstrap.php',"require_once __DIR__ . '/Foundation.php';","require_once __DIR__ . '/Foundation.php';\nrequire_once __DIR__ . '/CommonBaseline.php';\nrequire_once __DIR__ . '/Logging.php';")
replace_once('src/app/bootstrap.php',"'timezone'=>'UTC','date_format'=>'ymd_hm','page_size'=>'30','default_density'=>'comfortable',","'timezone'=>VfCommonBaseline::SYSTEM_TIMEZONE_DEFAULT,'date_format'=>'ymd_hm','page_size'=>'30','default_density'=>'comfortable',")
replace_once('src/app/bootstrap.php',"'allowed_extensions'=>'*','inbox_default_project_id'=>'0','session_timeout_minutes'=>'120','session_keep_days'=>'14',","'allowed_extensions'=>'*','inbox_default_project_id'=>'0','session_timeout_minutes'=>'10080','session_keep_days'=>'30',")
replace_once('src/app/bootstrap.php',"session_set_cookie_params(['lifetime'=>60*60*24*14,'path'=>'/','secure'=>vfab_is_https(),'httponly'=>true,'samesite'=>'Lax']);","session_set_cookie_params(['lifetime'=>VfCommonBaseline::AUTH_COOKIE_MAX_AGE_SECONDS,'path'=>'/','secure'=>vfab_is_https(),'httponly'=>true,'samesite'=>'Lax']);")
replace_once('src/app/bootstrap.php',"ini_set('session.gc_maxlifetime',(string)(60*60*24*14));","ini_set('session.gc_maxlifetime',(string)VfCommonBaseline::AUTH_SERVER_SESSION_FLOOR_SECONDS);")

replace_once('src/app/Auth.php',"return max(1,min(30,(int)($q->fetchColumn()?:14)));\n    }catch(Throwable $e){return 14;}","return max(1,min(30,(int)($q->fetchColumn()?:30)));\n    }catch(Throwable $e){return 30;}")
sub_once('src/app/Auth.php',r"function vfab_session_timeout_minutes\(\?PDO \$db=null\): int\n\{.*?\n\}","function vfab_session_timeout_minutes(?PDO $db=null): int\n{\n    return intdiv(VfCommonBaseline::AUTH_IDLE_TIMEOUT_SECONDS,60);\n}")
replace_once('src/app/Auth.php','function vfab_refresh_session_cookie(int $keepDays=14,bool $force=false): void','function vfab_refresh_session_cookie(int $keepDays=30,bool $force=false): void')
sub_once('src/app/Auth.php',r"function vfab_register_current_session\(PDO \$db\): void\n\{.*?\n\}",'''function vfab_register_current_session(PDO $db): void
{
    vfab_start_session();$hash=vfab_current_session_hash();if($hash==='')return;$keepDays=vfab_session_keep_days($db);$nowTs=time();$now=gmdate('c',$nowTs);$loginAt=(int)($_SESSION['vfab_login_at']??$nowTs);$expires=gmdate('c',$loginAt+VfCommonBaseline::AUTH_ABSOLUTE_TIMEOUT_SECONDS);
    $stmt=$db->prepare('INSERT INTO admin_sessions(session_hash,created_at,last_seen_at,expires_at,revoked_at,ip_hash,user_agent_hash) VALUES (?,?,?,?,NULL,?,?) ON CONFLICT(session_hash) DO UPDATE SET last_seen_at=excluded.last_seen_at,expires_at=excluded.expires_at,revoked_at=NULL,ip_hash=excluded.ip_hash,user_agent_hash=excluded.user_agent_hash');$stmt->execute([$hash,$now,$now,$expires,vfab_session_fingerprint((string)($_SERVER['REMOTE_ADDR']??'')),vfab_session_fingerprint((string)($_SERVER['HTTP_USER_AGENT']??''))]);$_SESSION['vfab_last_seen_sync']=$nowTs;$_SESSION['vfab_last_db_validation_at']=$nowTs;$_SESSION['vfab_last_activity_at']=$nowTs;vfab_refresh_session_cookie($keepDays,true);
}''')
sub_once('src/app/Auth.php',r"function vfab_is_admin\(\): bool\n\{.*?\n\}\nfunction vfab_login",'''function vfab_is_admin(): bool
{
    vfab_start_session();if(empty($_SESSION['vfab_admin']))return false;if(!vfab_session_epoch_valid()){$_SESSION=[];return false;}$now=time();$loginAt=(int)($_SESSION['vfab_login_at']??0);$lastActivity=(int)($_SESSION['vfab_last_activity_at']??$loginAt);
    if($loginAt<=0||$now-$loginAt>VfCommonBaseline::AUTH_ABSOLUTE_TIMEOUT_SECONDS||($lastActivity>0&&$now-$lastActivity>VfCommonBaseline::AUTH_IDLE_TIMEOUT_SECONDS)){if(vfab_is_installed())vfab_revoke_current_session();$_SESSION=[];return false;}if(!vfab_is_installed())return true;
    try{$db=vfab_db();$keepDays=vfab_session_keep_days($db);$hash=vfab_current_session_hash();if($hash==='')return false;$q=$db->prepare('SELECT * FROM admin_sessions WHERE session_hash=? LIMIT 1');$q->execute([$hash]);$row=$q->fetch();if(!$row){if(!vfab_session_epoch_valid()){$_SESSION=[];return false;}vfab_register_current_session($db);return true;}if(!empty($row['revoked_at'])){$_SESSION=[];return false;}$expiresAt=strtotime((string)($row['expires_at']??''))?:0;if($expiresAt>0&&$expiresAt<=$now){$db->prepare('UPDATE admin_sessions SET revoked_at=? WHERE id=?')->execute([gmdate('c'),(int)$row['id']]);$_SESSION=[];return false;}if($now-(int)($_SESSION['vfab_last_seen_sync']??0)>=300){$seen=gmdate('c');$db->prepare('UPDATE admin_sessions SET last_seen_at=? WHERE id=? AND revoked_at IS NULL')->execute([$seen,(int)$row['id']]);$_SESSION['vfab_last_seen_sync']=$now;}$_SESSION['vfab_last_db_validation_at']=$now;$_SESSION['vfab_last_activity_at']=$now;vfab_refresh_session_cookie($keepDays);return true;
    }catch(Throwable $e){$validated=(int)($_SESSION['vfab_last_db_validation_at']??0);return vfab_session_epoch_valid()&&$validated>0&&$now-$validated<=120&&$now-$loginAt<=VfCommonBaseline::AUTH_ABSOLUTE_TIMEOUT_SECONDS&&($lastActivity===0||$now-$lastActivity<=VfCommonBaseline::AUTH_IDLE_TIMEOUT_SECONDS);}
}
function vfab_login''')
replace_once('src/app/Auth.php',"$_SESSION['vfab_admin']=true; $_SESSION['vfab_auth_epoch']=vfab_auth_epoch(); $_SESSION['vfab_csrf']=bin2hex(random_bytes(24)); $_SESSION['vfab_login_at']=time(); $_SESSION['vfab_last_activity_at']=time(); $_SESSION['vfab_last_db_validation_at']=0;","$_SESSION['vfab_admin']=true; $_SESSION['vfab_auth_epoch']=vfab_auth_epoch(); $_SESSION['vfab_csrf']=bin2hex(random_bytes(24)); $_SESSION['vfab_login_at']=time(); $_SESSION['vfab_recent_auth_at']=time(); $_SESSION['vfab_last_activity_at']=time(); $_SESSION['vfab_last_db_validation_at']=0;")
s=read('src/app/Auth.php');marker="function vfab_logout(): void\n{";stepup="""function vfab_recent_auth_valid(): bool\n{\n    vfab_start_session();$at=(int)($_SESSION['vfab_recent_auth_at']??0);return $at>0&&time()-$at<=VfCommonBaseline::STEP_UP_WINDOW_SECONDS;\n}\nfunction vfab_mark_recent_auth(): void { vfab_start_session();$_SESSION['vfab_recent_auth_at']=time(); }\nfunction vfab_reauthenticate(string $password): bool\n{\n    $hash=(string)(vfab_config()['admin_password_hash']??'');if($hash===''||!password_verify($password,$hash))return false;vfab_mark_recent_auth();return true;\n}\nfunction vfab_require_recent_auth(): void\n{\n    vfab_require_admin();if(!vfab_recent_auth_valid())vfab_json(['ok'=>false,'code'=>'STEP_UP_REQUIRED','error'=>'此高风险操作需要重新验证管理员密码。','step_up_window_seconds'=>VfCommonBaseline::STEP_UP_WINDOW_SECONDS],428);\n}\n"""
if s.count(marker)!=1: raise SystemExit('Auth logout marker mismatch')
write('src/app/Auth.php',s.replace(marker,stepup+marker,1))
replace_once('src/app/Auth.php',"error_log('[VF Forge][password-change] 配置补偿恢复失败：'.$restore->getMessage());","if(class_exists('VfForgeRuntimeLogger'))VfForgeRuntimeLogger::log('SECURITY_AUDIT','ERROR','password-change compensation restore failed',['error'=>$restore->getMessage()]);")

api=read('public/api.php');csrf="""if($method==='POST'){\n    if($action==='login'){\n        if(!vfab_request_origin_is_same_host()) vfab_json(['ok'=>false,'code'=>'ORIGIN_FAILED','error'=>'请求来源与当前站点不一致。','request_id'=>$requestId],403);\n    }else{\n        vfab_require_csrf();\n    }\n}\n"""
if api.count(csrf)!=1: raise SystemExit('api csrf block mismatch')
api=api.replace(csrf,csrf+"\n$stepUpActions=['restore_execute','trash_delete','trash_purge_expired'];\nif($method==='POST'&&in_array($action,$stepUpActions,true))vfab_require_recent_auth();\n",1)
login_case="""        case 'login':\n            vfab_post_only($method);$b=vfab_body();$guard=vfab_login_guard($db);"""
if api.count(login_case)!=1: raise SystemExit('api login case mismatch')
api=api.replace(login_case,"""        case 'reauth':\n            vfab_post_only($method);$b=vfab_body();if(!vfab_reauthenticate((string)($b['password']??'')))vfab_json(['ok'=>false,'code'=>'REAUTH_FAILED','error'=>'管理员密码不正确。'],401);vfab_json(['ok'=>true,'csrf'=>vfab_csrf_token(),'recent_auth_window_seconds'=>VfCommonBaseline::STEP_UP_WINDOW_SECONDS]);\n\n"""+login_case,1)
old="'session_timeout_minutes'=>$authenticated?vfab_session_timeout_minutes($db):0,'session_keep_days'=>$authenticated?vfab_session_keep_days($db):0]"
new="'session_timeout_minutes'=>$authenticated?vfab_session_timeout_minutes($db):0,'session_keep_days'=>$authenticated?vfab_session_keep_days($db):0,'baseline_id'=>VfCommonBaseline::BASELINE_ID,'profile'=>VfCommonBaseline::PROFILE,'absolute_timeout_seconds'=>VfCommonBaseline::AUTH_ABSOLUTE_TIMEOUT_SECONDS,'recent_auth_valid'=>$authenticated?vfab_recent_auth_valid():false]"
if api.count(old)!=1: raise SystemExit('api session payload mismatch')
write('public/api.php',api.replace(old,new,1))

gh='''<?php
declare(strict_types=1);
namespace CoreUpdates;
use RuntimeException;
final class GitHubClient
{
    public const CONNECT_TIMEOUT_SECONDS=5;public const REQUEST_TIMEOUT_SECONDS=15;public const DOWNLOAD_TIMEOUT_SECONDS=300;public const MAX_RETRY_COUNT=3;public const BACKOFF_BASE_MS=1000;public const BACKOFF_MAX_MS=30000;private const RETRYABLE_STATUS=[429,502,503,504];
    public function __construct(private readonly string $token,private readonly string $userAgent='vf-forge-core-updates-v2'){}
    public function fetchProjectManifest(string $coreRepository,string $projectFile,string $ref='main'): array{if(!preg_match('/^[A-Z0-9-]+\.json$/',$projectFile))throw new RuntimeException('非法项目清单文件名。');$url=sprintf('https://api.github.com/repos/%s/contents/projects/%s?ref=%s',$coreRepository,rawurlencode($projectFile),rawurlencode($ref));$data=json_decode($this->request($url,'application/vnd.github.raw+json'),true,512,JSON_THROW_ON_ERROR);if(!is_array($data))throw new RuntimeException('更新清单不是有效 JSON 对象。');return $data;}
    public function releaseAssetMetadata(string $repository,string $releaseTag,string $assetName): array{$url=sprintf('https://api.github.com/repos/%s/releases/tags/%s',$repository,rawurlencode($releaseTag));$release=json_decode($this->request($url,'application/vnd.github+json'),true,512,JSON_THROW_ON_ERROR);if(!is_array($release)||!isset($release['assets'])||!is_array($release['assets']))throw new RuntimeException('无法读取 GitHub Release Asset 列表。');if(($release['tag_name']??null)!==$releaseTag)throw new RuntimeException('GitHub Release Tag 与更新清单不一致。');if(($release['draft']??true)===true)throw new RuntimeException('更新目标仍是 Draft Release。');if(($release['prerelease']??true)===true)throw new RuntimeException('stable 通道不能消费 Prerelease。');$asset=null;foreach($release['assets'] as $candidate){if(is_array($candidate)&&($candidate['name']??null)===$assetName){if($asset!==null)throw new RuntimeException('GitHub Release 存在重复同名 Asset。');$asset=$candidate;}}if($asset===null||!isset($asset['url']))throw new RuntimeException('指定 Release Asset 不存在。');return ['release'=>$release,'asset'=>$asset];}
    public function downloadReleaseAsset(string $repository,string $releaseTag,string $assetName,string $destination): array{$resolved=$this->releaseAssetMetadata($repository,$releaseTag,$assetName);$dir=dirname($destination);if(!is_dir($dir)&&!mkdir($dir,0700,true)&&!is_dir($dir))throw new RuntimeException('无法创建 staging 目录。');$this->download((string)$resolved['asset']['url'],$destination);return $resolved['asset'];}
    private function request(string $url,string $accept): string{if($this->token==='')throw new RuntimeException('缺少 VF_PRIVATE_READ_TOKEN，在线更新读取已安全停止。');$last='';for($attempt=0;$attempt<=self::MAX_RETRY_COUNT;$attempt++){$headers=[];$ch=curl_init($url);if($ch===false)throw new RuntimeException('无法初始化 cURL。');curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>true,CURLOPT_MAXREDIRS=>3,CURLOPT_CONNECTTIMEOUT=>self::CONNECT_TIMEOUT_SECONDS,CURLOPT_TIMEOUT=>self::REQUEST_TIMEOUT_SECONDS,CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,CURLOPT_REDIR_PROTOCOLS=>CURLPROTO_HTTPS,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_HTTPHEADER=>$this->headers($accept),CURLOPT_HEADERFUNCTION=>static function($ch,$line)use(&$headers){$len=strlen($line);$q=strpos($line,':');if($q!==false)$headers[strtolower(trim(substr($line,0,$q)))]=trim(substr($line,$q+1));return $len;}]);$body=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_RESPONSE_CODE);$error=curl_error($ch);curl_close($ch);if(is_string($body)&&$status>=200&&$status<300)return $body;$last='HTTP '.$status.($error!==''?' / '.$error:'');if($attempt>=self::MAX_RETRY_COUNT||!in_array($status,self::RETRYABLE_STATUS,true))break;$this->sleepBeforeRetry($headers,$attempt);}throw new RuntimeException('GitHub 读取失败：'.$last);}
    private function download(string $url,string $destination): void{if($this->token==='')throw new RuntimeException('缺少 VF_PRIVATE_READ_TOKEN，Release Asset 下载已安全停止。');$last='';for($attempt=0;$attempt<=self::MAX_RETRY_COUNT;$attempt++){$headers=[];$fp=fopen($destination,'wb');if($fp===false)throw new RuntimeException('无法创建下载文件。');@chmod($destination,0600);$ch=curl_init($url);if($ch===false){fclose($fp);@unlink($destination);throw new RuntimeException('无法初始化下载 cURL。');}curl_setopt_array($ch,[CURLOPT_FILE=>$fp,CURLOPT_FOLLOWLOCATION=>true,CURLOPT_MAXREDIRS=>3,CURLOPT_CONNECTTIMEOUT=>self::CONNECT_TIMEOUT_SECONDS,CURLOPT_TIMEOUT=>self::DOWNLOAD_TIMEOUT_SECONDS,CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,CURLOPT_REDIR_PROTOCOLS=>CURLPROTO_HTTPS,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_HTTPHEADER=>$this->headers('application/octet-stream'),CURLOPT_HEADERFUNCTION=>static function($ch,$line)use(&$headers){$len=strlen($line);$q=strpos($line,':');if($q!==false)$headers[strtolower(trim(substr($line,0,$q)))]=trim(substr($line,$q+1));return $len;}]);$ok=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_RESPONSE_CODE);$error=curl_error($ch);curl_close($ch);fclose($fp);if($ok===true&&$status>=200&&$status<300)return;$last='HTTP '.$status.($error!==''?' / '.$error:'');@unlink($destination);if($attempt>=self::MAX_RETRY_COUNT||!in_array($status,self::RETRYABLE_STATUS,true))break;$this->sleepBeforeRetry($headers,$attempt);}throw new RuntimeException('Release Asset 下载失败：'.$last);}
    public function retryDelaySeconds(array $headers,int $attempt): float{$retry=trim((string)($headers['retry-after']??''));if(ctype_digit($retry))return(float)min(self::BACKOFF_MAX_MS/1000,max(0,(int)$retry));$ms=min(self::BACKOFF_MAX_MS,self::BACKOFF_BASE_MS*(2**max(0,$attempt)))+random_int(0,250);return $ms/1000;}
    private function sleepBeforeRetry(array $headers,int $attempt): void{usleep((int)round($this->retryDelaySeconds($headers,$attempt)*1000000));}
    private function headers(string $accept): array{return ['Accept: '.$accept,'X-GitHub-Api-Version: 2022-11-28','User-Agent: '.$this->userAgent,'Authorization: Bearer '.$this->token];}
}
'''
write('src/app/CoreUpdates/GitHubClient.php',gh)

sub_once('src/app/Repository.php',r"function vfab_job_stale_seconds\(\): int\n\{\n    return 900;\n\}",'''function vfab_job_class_for_type(string $type): string
{
    $type=strtoupper(trim($type));if(str_contains($type,'BACKUP')||str_contains($type,'RESTORE')||str_contains($type,'UPDATE')||str_contains($type,'MAINTENANCE'))return 'MAINTENANCE';if(str_contains($type,'SYNC')||str_contains($type,'IMPORT')||str_contains($type,'EXPORT'))return 'SYNC';return 'GENERAL';
}
function vfab_job_timeout_seconds(string $classOrType='GENERAL'): int
{
    $class=strtoupper(trim($classOrType));if(!in_array($class,['GENERAL','SYNC','MAINTENANCE'],true))$class=vfab_job_class_for_type($class);return match($class){'MAINTENANCE'=>VfCommonBaseline::JOB_MAINTENANCE_TIMEOUT_SECONDS,'SYNC'=>VfCommonBaseline::JOB_SYNC_TIMEOUT_SECONDS,default=>VfCommonBaseline::JOB_GENERAL_TIMEOUT_SECONDS};
}
function vfab_job_stale_seconds(): int{return VfCommonBaseline::JOB_MAINTENANCE_TIMEOUT_SECONDS;}''')
sub_once('src/app/Repository.php',r"public function start\(string \$type,string \$stage='queued',\?int \$projectId=null,array \$context=\[\]\): array\n    \{.*?\n    \}",'''public function start(string $type,string $stage='queued',?int $projectId=null,array $context=[]): array
    {
        $class=vfab_job_class_for_type($type);$context=['baseline_job_class'=>$class,'baseline_timeout_seconds'=>vfab_job_timeout_seconds($class)]+$context;$uuid=vfab_uuid();$now=gmdate('c');$s=$this->db->prepare("INSERT INTO jobs(uuid,project_id,job_type,status,stage,current,total,context_json,heartbeat_at,started_at,created_at,updated_at) VALUES (?,?,?,'running',?,0,0,?,?,?,?,?)");$s->execute([$uuid,$projectId,$type,$stage,json_encode($context,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES),$now,$now,$now,$now]);return $this->get((int)$this->db->lastInsertId());
    }''')
replace_once('src/app/Repository.php','public function acquire(string $key,int $jobId,int $ttlSeconds=900): array','public function acquire(string $key,int $jobId,int $ttlSeconds=1860): array')
replace_once('src/app/Repository.php','public function heartbeat(string $key,string $token,int $ttlSeconds=900): void','public function heartbeat(string $key,string $token,int $ttlSeconds=1860): void')
replace_once('src/app/Repository.php','public function heartbeatForJob(string $key,int $jobId,int $ttlSeconds=900): void','public function heartbeatForJob(string $key,int $jobId,int $ttlSeconds=1860): void')
replace_once('src/app/Repository.php',"$nowTs=time();$now=gmdate('c');$staleCutoff=$nowTs-vfab_job_stale_seconds();","$nowTs=time();$now=gmdate('c');")
replace_once('src/app/Repository.php',"$heartbeat=strtotime((string)($row['job_heartbeat']??$row['job_updated']??$row['heartbeat_at']??''))?:0;$expires=strtotime((string)($row['expires_at']??''))?:0;\n            $fresh=$jobStatus==='running'&&$heartbeat>=$staleCutoff;","$heartbeat=strtotime((string)($row['job_heartbeat']??$row['job_updated']??$row['heartbeat_at']??''))?:0;$expires=strtotime((string)($row['expires_at']??''))?:0;$ctx=json_decode((string)($row['context_json']??'{}'),true);$timeout=is_array($ctx)?(int)($ctx['baseline_timeout_seconds']??0):0;if($timeout<=0)$timeout=vfab_job_timeout_seconds($jobType);$staleCutoff=$nowTs-$timeout;\n            $fresh=$jobStatus==='running'&&$heartbeat>=$staleCutoff;")
replace_once('src/app/UpdateService.php',"$lock=$jobs->acquire('ONLINE_UPDATE_PREPARE',$jobId,900);","$lock=$jobs->acquire('ONLINE_UPDATE_PREPARE',$jobId,VfCommonBaseline::JOB_MAINTENANCE_TIMEOUT_SECONDS+VfCommonBaseline::JOB_LOCK_GRACE_SECONDS);")

old="function toast(m,bad=false){const n=$('#toast');n.textContent=m;n.className='toast show'+(bad?' error':'');n.setAttribute('role',bad?'alert':'status');n.setAttribute('aria-atomic','true');const old=$('#inlineFeedback');if(!bad&&old)old.remove();if(bad&&$('#view')){let b=old;if(!b){b=document.createElement('div');b.id='inlineFeedback';b.className='feedback-banner error';$('#view').prepend(b)}b.innerHTML=`<strong>操作未完成</strong><span>${esc(m)}</span>`}clearTimeout(toast.t);toast.t=setTimeout(()=>n.className='toast',bad?9000:4200)}"
new="const TOAST_SUCCESS_MS=2500,TOAST_ERROR_MS=6000;function toast(m,bad=false){const n=$('#toast');n.textContent=m;n.className='toast show'+(bad?' error':'');n.setAttribute('role',bad?'alert':'status');n.setAttribute('aria-atomic','true');n.title='点击关闭';n.onclick=()=>{clearTimeout(toast.t);n.className='toast'};const old=$('#inlineFeedback');if(!bad&&old)old.remove();if(bad&&$('#view')){let b=old;if(!b){b=document.createElement('div');b.id='inlineFeedback';b.className='feedback-banner error';$('#view').prepend(b)}b.innerHTML=`<strong>操作未完成</strong><span>${esc(m)}</span>`}clearTimeout(toast.t);toast.t=setTimeout(()=>n.className='toast',bad?TOAST_ERROR_MS:TOAST_SUCCESS_MS)}"
replace_once('public/assets/experience.js',old,new)

replace_once('public/maintenance.php',"vfab_require_csrf();\n        if(!isset($_FILES['atomic_zip'])","vfab_require_csrf();\n        vfab_require_recent_auth();\n        if(!isset($_FILES['atomic_zip'])")
replace_once('public/maintenance.php','<p>管理员 · 高风险维护</p><h1>系统维护</h1><p>正式 Atomic 手工更新与只读 Production Source Manifest。</p>','<p>管理员 · 高级维护 / 灾难恢复</p><h1>系统维护</h1><p>普通升级请使用在线升级；这里保留正式 Atomic 手工恢复与只读 Source Manifest。</p>')
replace_once('public/maintenance.php','<section class="card"><h2>手工原子更新</h2>','<section class="card"><h2>高级手工原子更新（Fallback）</h2>')
replace_once('public/maintenance.php',"<?php if($error!==''):?>","<section class=\"card\"><h2>统一运维入口</h2><div class=\"actions\"><a class=\"button secondary\" href=\"system-info.php\">系统信息</a><a class=\"button secondary\" href=\"system-baseline.php\">系统基线</a><a class=\"button secondary\" href=\"./#settings\">在线升级 / 备份恢复</a><a class=\"button secondary\" href=\"diagnose.php\">运行健康</a></div></section>\n<?php if($error!==''):?>")

system_info='''<?php
declare(strict_types=1);require_once __DIR__.'/app/bootstrap.php';vfab_security_headers(true);if(!vfab_is_installed()){http_response_code(404);exit;}vfab_require_admin();$db=vfab_db();$baseline=VfCommonBaseline::resolve($db);$tz=(new VfAssetRepository($db))->setting('timezone',VfCommonBaseline::SYSTEM_TIMEZONE_DEFAULT);
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>VF Forge · 系统信息</title><style>body{font:15px/1.6 system-ui,"Microsoft YaHei";background:#f7fbf9;color:#173029;margin:0;padding:32px}.wrap{max-width:900px;margin:auto}.card{background:#fff;border:1px solid #dfe9e4;border-radius:14px;padding:22px;margin:14px 0}.grid{display:grid;grid-template-columns:220px 1fr;gap:10px 20px}.nav{display:flex;gap:10px;flex-wrap:wrap}a{color:#087a61}.ok{color:#087a61;font-weight:700}@media(max-width:640px){body{padding:16px}.grid{grid-template-columns:1fr}}</style></head><body><main class="wrap"><h1>系统信息</h1><p>只读 Runtime Truth。版本、Schema、Runtime、公共基线与系统时区来自当前运行实现。</p><section class="card grid"><strong>应用版本</strong><span>v<?=htmlspecialchars(VFAB_VERSION)?></span><strong>Schema</strong><span><?=VFAB_SCHEMA_VERSION?></span><strong>PHP Runtime</strong><span><?=htmlspecialchars(PHP_VERSION)?></span><strong>Common Baseline</strong><span><?=htmlspecialchars(VfCommonBaseline::BASELINE_ID)?></span><strong>Project Profile</strong><span><?=htmlspecialchars(VfCommonBaseline::PROFILE)?></span><strong>Release Channel</strong><span>stable</span><strong>System Timezone</strong><span><?=htmlspecialchars($tz)?></span><strong>Baseline Status</strong><span class="ok"><?=htmlspecialchars($baseline['overall'])?></span></section><section class="card nav"><a href="system-baseline.php">系统基线</a><a href="./#settings">在线升级 / 备份恢复</a><a href="diagnose.php">运行健康</a><a href="maintenance.php">高级维护</a><a href="./">返回 VF Forge</a></section></main></body></html>
'''
write('public/system-info.php',system_info)
system_baseline='''<?php
declare(strict_types=1);require_once __DIR__.'/app/bootstrap.php';vfab_security_headers(true);if(!vfab_is_installed()){http_response_code(404);exit;}vfab_require_admin();$r=VfCommonBaseline::resolve(vfab_db());$e=static fn($v)=>htmlspecialchars(is_bool($v)?($v?'true':'false'):(is_scalar($v)?(string)$v:json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)),ENT_QUOTES,'UTF-8');
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>VF Forge · 系统基线</title><style>body{font:14px/1.55 system-ui,"Microsoft YaHei";background:#f7fbf9;color:#173029;margin:0;padding:28px}.wrap{max-width:1180px;margin:auto}.summary,.table{background:#fff;border:1px solid #dfe9e4;border-radius:14px;padding:20px;margin:14px 0}.counts{display:flex;gap:16px;flex-wrap:wrap}.counts b{font-size:20px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;min-width:950px}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #edf2ef}th{color:#687d75}.PASS{color:#087a61;font-weight:700}.EXCEPTION{color:#9a6700;font-weight:700}.DRIFT,.UNKNOWN{color:#b42318;font-weight:700}code{white-space:normal}a{color:#087a61}</style></head><body><main class="wrap"><h1>系统基线</h1><p>Runtime-derived · Read-only · No Shadow Truth。此页不修改公共规范；需要调整时由 AI 修改正式代码/配置并重新机器验证。</p><section class="summary"><strong><?=$e($r['baseline'])?></strong> · <?=$e($r['profile'])?> · Overall <b class="<?=$e($r['overall'])?>"><?=$e($r['overall'])?></b><div class="counts"><?php foreach($r['counts'] as $k=>$v):?><span><?=$e($k)?> <b><?=$e($v)?></b></span><?php endforeach;?></div></section><section class="table scroll"><table><thead><tr><th>Domain</th><th>Rule</th><th>Expected</th><th>Effective</th><th>Result</th><th>Exception / Reason</th><th>Source</th></tr></thead><tbody><?php foreach($r['rules'] as $x):?><tr><td><?=$e($x['domain'])?></td><td><code><?=$e($x['parameter'])?></code></td><td><?=$e($x['expected'])?></td><td><?=$e($x['effective'])?></td><td class="<?=$e($x['result'])?>"><?=$e($x['result'])?></td><td><?=$e(trim((string)$x['exception'].' '.(string)$x['reason']))?></td><td><?=$e($x['source'])?></td></tr><?php endforeach;?></tbody></table></section><p><a href="system-info.php">系统信息</a> · <a href="./#settings">在线升级 / 备份恢复</a> · <a href="diagnose.php">运行健康</a> · <a href="./">返回 VF Forge</a></p></main></body></html>
'''
write('public/system-baseline.php',system_baseline)
cli='''<?php
declare(strict_types=1);require_once dirname(__DIR__).'/app/bootstrap.php';if(!vfab_is_installed()){fwrite(STDERR,"NOT_INSTALLED\n");exit(2);}$r=VfCommonBaseline::resolve(vfab_db());foreach(['PASS','EXCEPTION','DRIFT','UNKNOWN','N_A'] as $k)echo $k.'_COUNT='.(int)($r['counts'][$k]??0)."\n";echo 'BASELINE_FULL_PASS='.(($r['counts']['DRIFT']??0)===0&&($r['counts']['UNKNOWN']??0)===0?'YES':'NO')."\n";exit((($r['counts']['DRIFT']??0)===0&&($r['counts']['UNKNOWN']??0)===0)?0:1);
'''
write('src/cli/baseline-verify.php',cli)
candidate={'schema':'vf-common-product-baseline-adoption/v2','state':'MACHINE_VERIFICATION_PENDING','project_id':'P03','project_name':'VF Forge','repository':'llhzx2018/vf-forge','baseline_id':'VF-COMMON-PRODUCT-BASELINE@2.0','baseline_version':'2.0','profile':'PERSONAL_SINGLE_ADMIN','authority_repository':'llhzx2018/gov-doc','authority_ref':'main','assessed_base_sha':'29580b62a0839ee3453ccf0cf8a4902bdf3cd8ec','runtime_resolver':'src/app/CommonBaseline.php','baseline_surface':'public/system-baseline.php','system_info_surface':'public/system-info.php','machine_verification':{'state':'PENDING','run_id':None,'exact_source_sha':'PENDING'},'explicit_exceptions':['P03-PRESERVE-OWNER-SESSION-KEEP-DAYS','P03-SINGLE-TOAST-ANTI-STACK','P03-BRAND-LOGO-1MB','P03-WEB-SERVER-CACHE-TTL'],'permanent_product_boundary':{'project_asset_storage':'NONE','user_file_upload':'RETIRED','local_asset_repository':'RETIRED'},'version_changed':False,'schema_changed':False,'release_executed':False,'production_changed':False}
write('docs/authority/VF_COMMON_PRODUCT_BASELINE_V2_ADOPTION_CANDIDATE.json',json.dumps(candidate,ensure_ascii=False,indent=2)+'\n')
print('P03_COMMON_BASELINE_V2_PATCH_COMPLETE')
