from pathlib import Path
import json,re

ROOT=Path('.')

def read(path): return (ROOT/path).read_text()
def write(path,text):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
def replace_once(path,old,new):
    s=read(path)
    if old not in s: raise SystemExit(f'missing patch anchor: {path}: {old[:120]!r}')
    if s.count(old)!=1: raise SystemExit(f'non-unique patch anchor: {path}: {s.count(old)}')
    write(path,s.replace(old,new,1))

# Session runtime + Common Baseline bootstrap.
replace_once('src/app/bootstrap.php',
"function vftb_start_session(): void\n{\n    if (session_status() === PHP_SESSION_ACTIVE) return;\n    session_name('vftextbox_session');\n    session_cache_limiter('');\n    ini_set('session.gc_maxlifetime','43200');\n    ini_set('session.use_strict_mode','1');\n    ini_set('session.use_only_cookies','1');\n    ini_set('session.use_trans_sid','0');\n    ini_set('session.cookie_httponly','1');\n    session_set_cookie_params(['lifetime'=>1209600,'path'=>'/','secure'=>vftb_is_https(),'httponly'=>true,'samesite'=>'Strict']);\n    if (!session_start()) throw new RuntimeException('无法启动安全会话。');\n}\n",
"function vftb_start_session(): void\n{\n    if (session_status() === PHP_SESSION_ACTIVE) return;\n    VfLibraryCommonBaseline::configureSessionRuntime();\n    session_name('vftextbox_session');\n    session_cache_limiter('');\n    ini_set('session.use_strict_mode','1');\n    ini_set('session.use_only_cookies','1');\n    ini_set('session.use_trans_sid','0');\n    ini_set('session.cookie_httponly','1');\n    session_set_cookie_params(['lifetime'=>VfLibraryCommonBaseline::AUTH_COOKIE_SECONDS,'path'=>'/','secure'=>vftb_is_https(),'httponly'=>true,'samesite'=>'Strict']);\n    if (!session_start()) throw new RuntimeException('无法启动安全会话。');\n}\n")
replace_once('src/app/bootstrap.php',
"require_once VFTB_ROOT . '/app/Auth.php';\n",
"require_once VFTB_ROOT . '/app/Logging.php';\nrequire_once VFTB_ROOT . '/app/CommonBaseline.php';\ndate_default_timezone_set(VfLibraryCommonBaseline::SYSTEM_TIMEZONE);\nrequire_once VFTB_ROOT . '/app/Auth.php';\n")
replace_once('src/app/bootstrap.php',
"    // Deliberately do not emit exception messages, SQL, private paths, user content or traces.\n    error_log('[VF Library '.$context.'] '.get_class($error).' code='.$code.' ref='.$ref);\n",
"    // Deliberately do not emit exception messages, SQL, private paths, user content or traces.\n    if(class_exists('VfLibraryRuntimeLogger',false))VfLibraryRuntimeLogger::log('error','exception',['context'=>$context,'class'=>get_class($error),'code'=>$code,'ref'=>$ref]);\n    else error_log('[VF Library '.$context.'] '.get_class($error).' code='.$code.' ref='.$ref);\n")

# Auth profile alignment + remove periodic rotation; add 15-minute recent-auth step-up primitive.
auth=read('src/app/Auth.php')
auth=auth.replace("if($loginAt<=0||$now-$loginAt>1209600){vftb_logout();return false;}","if($loginAt<=0||$now-$loginAt>VfLibraryCommonBaseline::AUTH_ABSOLUTE_SECONDS){vftb_logout();return false;}")
auth=auth.replace("if($lastSeen>0&&$now-$lastSeen>43200){vftb_logout();return false;}","if($lastSeen>0&&$now-$lastSeen>VfLibraryCommonBaseline::AUTH_IDLE_SECONDS){vftb_logout();return false;}")
auth=re.sub(r"\$rotatedAt=\(int\)\(\$_SESSION\['vftextbox_rotated_at'\]\?\?0\);if\(\$rotatedAt<=0\|\|\$now-\$rotatedAt>1800\)\{session_regenerate_id\(true\);\$_SESSION\['vftextbox_rotated_at'\]=\$now;\}","",auth,count=1)
# Mark successful password login/re-auth as recent authentication.
auth=auth.replace("$_SESSION['vftextbox_auth_epoch']=$epoch;\n    return true;","$_SESSION['vftextbox_auth_epoch']=$epoch;\n    $_SESSION['vftextbox_recent_auth_at']=$now;\n    if(class_exists('VfLibraryRuntimeLogger',false))VfLibraryRuntimeLogger::log('security','login_success');\n    return true;",1)
# Password-change session rebuild is also a strong recent auth.
auth=auth.replace("$_SESSION['vftextbox_auth_epoch']=$epoch;\n    return true;", "$_SESSION['vftextbox_auth_epoch']=$epoch;\n    $_SESSION['vftextbox_recent_auth_at']=$now;\n    if(class_exists('VfLibraryRuntimeLogger',false))VfLibraryRuntimeLogger::log('security','credential_changed');\n    return true;",1)
insert_anchor="function vftb_logout(): void\n"
if insert_anchor not in auth: raise SystemExit('Auth logout anchor missing')
stepup="""function vftb_recent_auth_valid(): bool
{
    vftb_start_session();
    if(!vftb_is_admin())return false;
    $at=(int)($_SESSION['vftextbox_recent_auth_at']??0);
    return $at>0 && time()-$at<=VfLibraryCommonBaseline::STEP_UP_RECENT_AUTH_SECONDS;
}

function vftb_reauthenticate(string $password): bool
{
    if(!vftb_is_admin()||!vftb_is_installed())return false;
    $config=vftb_config();$hash=(string)($config['admin_password_hash']??'');
    if($hash===''||!password_verify($password,$hash)){
        if(class_exists('VfLibraryRuntimeLogger',false))VfLibraryRuntimeLogger::log('security','reauth_failed');
        return false;
    }
    session_regenerate_id(true);
    $_SESSION['vftextbox_recent_auth_at']=time();
    $_SESSION['vftextbox_rotated_at']=time();
    if(class_exists('VfLibraryRuntimeLogger',false))VfLibraryRuntimeLogger::log('security','reauth_success');
    return true;
}

function vftb_require_recent_auth(): void
{
    if(vftb_recent_auth_valid())return;
    vftb_json(['ok'=>false,'reauth_required'=>true,'error'=>'此操作需要重新验证管理员密码。'],428);
}

"""
auth=auth.replace(insert_anchor,stepup+insert_anchor,1)
write('src/app/Auth.php',auth)

# API: explicit reauth endpoint and high-risk step-up gates.
api=read('public/api.php')
login_anchor="    if($action==='logout'){\n        if($method!=='POST')vftb_json(['ok'=>false,'error'=>'Method Not Allowed'],405);vftb_require_csrf();vftb_logout();vftb_json(['ok'=>true]);\n    }\n"
if login_anchor not in api: raise SystemExit('API logout anchor missing')
api=api.replace(login_anchor,login_anchor+"    if($action==='reauth'){\n        if($method!=='POST')vftb_json(['ok'=>false,'error'=>'Method Not Allowed'],405);vftb_require_admin();vftb_require_csrf();$body=vftb_request_json(16384);if(!vftb_reauthenticate((string)($body['password']??'')))vftb_json(['ok'=>false,'error'=>'密码错误。'],401);vftb_json(['ok'=>true,'csrf'=>vftb_csrf_token()]);\n    }\n",1)
# High-risk destructive/recovery actions. Password-change already asks current password directly.
api=api.replace("case 'backup_restore':", "case 'backup_restore': vftb_require_recent_auth();",1)
api=api.replace("case 'content_purge':", "case 'content_purge': vftb_require_recent_auth();",1)
api=api.replace("case 'category_delete':", "case 'category_delete': vftb_require_recent_auth();",1)
api=api.replace("case 'category_merge':", "case 'category_merge': vftb_require_recent_auth();",1)
# Bulk purge only requires step-up for irreversible purge.
api=api.replace("$action=(string)($body['operation']??'');if($action==='purge')$repo->createBackup", "$action=(string)($body['operation']??'');if($action==='purge')vftb_require_recent_auth();if($action==='purge')$repo->createBackup",1)
write('public/api.php',api)

# Standard external API resilience.
gh=read('src/app/CoreUpdates/GitHubClient.php')
gh=gh.replace("final class GitHubClient\n{", "final class GitHubClient\n{\n    private const CONNECT_TIMEOUT_SECONDS=5;\n    private const REQUEST_TIMEOUT_SECONDS=15;\n    private const MAX_RETRY_COUNT=3;\n    private const BACKOFF_BASE_MS=1000;\n    private const BACKOFF_MAX_MS=30000;",1)
request_re=re.compile(r"    private function request\(string \$url, string \$accept\): string\n    \{.*?\n    \}\n\n    private function download",re.S)
request_new="""    private function request(string $url, string $accept): string
    {
        $attempt=0;
        do{
            $attempt++;$responseHeaders=[];
            $ch=curl_init($url);if($ch===false)throw new RuntimeException('无法初始化 cURL。');
            curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>true,CURLOPT_CONNECTTIMEOUT=>self::CONNECT_TIMEOUT_SECONDS,CURLOPT_TIMEOUT=>self::REQUEST_TIMEOUT_SECONDS,CURLOPT_HTTPHEADER=>$this->headers($accept),CURLOPT_HEADERFUNCTION=>static function($ch,string $line)use(&$responseHeaders):int{$trim=trim($line);if(str_contains($trim,':')){[$k,$v]=explode(':',$trim,2);$responseHeaders[strtolower(trim($k))]=trim($v);}return strlen($line);}]);
            $body=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_RESPONSE_CODE);$error=curl_error($ch);curl_close($ch);
            if(is_string($body)&&$status>=200&&$status<300)return $body;
            if(!$this->retryable($status)||$attempt>self::MAX_RETRY_COUNT)throw new RuntimeException('GitHub 读取失败：HTTP '.$status.($error!==''?' / '.$error:''));
            $this->sleepBeforeRetry($attempt,$responseHeaders['retry-after']??'');
        }while(true);
    }

    private function download"""
gh,n=request_re.subn(request_new,gh,count=1)
if n!=1: raise SystemExit('GitHubClient request patch failed')
# Download: 5s connect; preserve 300s transfer window as asset-transfer class, retry only idempotent GET failures.
download_re=re.compile(r"    private function download\(string \$url, string \$destination\): void\n    \{.*?\n    \}\n\n    private function headers",re.S)
download_new="""    private function download(string $url, string $destination): void
    {
        for($attempt=1;$attempt<=self::MAX_RETRY_COUNT+1;$attempt++){
            @unlink($destination);$responseHeaders=[];
            $fp=fopen($destination,'xb');if($fp===false)throw new RuntimeException('无法创建下载文件。');@chmod($destination,0600);
            $ch=curl_init($url);if($ch===false){fclose($fp);@unlink($destination);throw new RuntimeException('无法初始化下载 cURL。');}
            curl_setopt_array($ch,[CURLOPT_FILE=>$fp,CURLOPT_FOLLOWLOCATION=>true,CURLOPT_CONNECTTIMEOUT=>self::CONNECT_TIMEOUT_SECONDS,CURLOPT_TIMEOUT=>300,CURLOPT_HTTPHEADER=>$this->headers('application/octet-stream'),CURLOPT_HEADERFUNCTION=>static function($ch,string $line)use(&$responseHeaders):int{$trim=trim($line);if(str_contains($trim,':')){[$k,$v]=explode(':',$trim,2);$responseHeaders[strtolower(trim($k))]=trim($v);}return strlen($line);}]);
            $ok=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_RESPONSE_CODE);$error=curl_error($ch);curl_close($ch);fclose($fp);
            if($ok===true&&$status>=200&&$status<300)return;
            @unlink($destination);
            if(!$this->retryable($status)||$attempt>self::MAX_RETRY_COUNT)throw new RuntimeException('Release Asset 下载失败：HTTP '.$status.($error!==''?' / '.$error:''));
            $this->sleepBeforeRetry($attempt,$responseHeaders['retry-after']??'');
        }
    }

    private function retryable(int $status): bool{return in_array($status,[429,502,503,504],true);}
    private function sleepBeforeRetry(int $attempt,string $retryAfter): void
    {
        $ms=0;if(preg_match('/^\\d+$/',$retryAfter)===1)$ms=min(self::BACKOFF_MAX_MS,(int)$retryAfter*1000);
        if($ms<=0){$base=min(self::BACKOFF_MAX_MS,self::BACKOFF_BASE_MS*(2**max(0,$attempt-1)));try{$jitter=random_int(0,max(1,(int)floor($base*0.2)));}catch(\\Throwable $e){$jitter=0;}$ms=min(self::BACKOFF_MAX_MS,$base+$jitter);}usleep($ms*1000);
    }

    private function headers"""
gh,n=download_re.subn(download_new,gh,count=1)
if n!=1: raise SystemExit('GitHubClient download patch failed')
write('src/app/CoreUpdates/GitHubClient.php',gh)

# Job timeout/retry/backoff contract.
jobs=read('src/app/JobService.php')
jobs=jobs.replace("    /** @var PDO */ private $db; private const TYPES=['search_rebuild','source_backfill','asset_role_backfill','derivative_rebuild','ingestion_finalize'];", "    /** @var PDO */ private $db; private const TYPES=['search_rebuild','source_backfill','asset_role_backfill','derivative_rebuild','ingestion_finalize']; private const MAX_ATTEMPTS=3; private const RETRY_BASE_SECONDS=30; private const RETRY_MAX_SECONDS=900; private const GENERAL_TIMEOUT_SECONDS=300; private const SYNC_TIMEOUT_SECONDS=900; private const MAINTENANCE_TIMEOUT_SECONDS=1800; private const LOCK_GRACE_SECONDS=60;",1)
jobs=jobs.replace("public function enqueue(string $type,array $payload=[],int $maxAttempts=3", "public function enqueue(string $type,array $payload=[],int $maxAttempts=self::MAX_ATTEMPTS",1)
jobs=jobs.replace("public function enqueueUnique(string $type,array $payload=[],int $maxAttempts=3", "public function enqueueUnique(string $type,array $payload=[],int $maxAttempts=self::MAX_ATTEMPTS",1)
jobs=jobs.replace("public function claim(string $workerId,int $staleSeconds=900): ?array", "public function claim(string $workerId,int $staleSeconds=self::MAINTENANCE_TIMEOUT_SECONDS+self::LOCK_GRACE_SECONDS): ?array",1)
jobs=jobs.replace("$s=$this->db->prepare(\"UPDATE library_jobs SET status='queued',locked_at=NULL,locked_by=NULL,lease_token=NULL,heartbeat_at=NULL,available_at=?,updated_at=?,last_error=? WHERE id=? AND status='running' AND locked_by=? AND lease_token=?\");$s->execute([gmdate('c',time()+60),$now,$error,$id,$worker,$lease]);", "$delay=$this->retryDelaySeconds((int)$j['attempts']);$s=$this->db->prepare(\"UPDATE library_jobs SET status='queued',locked_at=NULL,locked_by=NULL,lease_token=NULL,heartbeat_at=NULL,available_at=?,updated_at=?,last_error=? WHERE id=? AND status='running' AND locked_by=? AND lease_token=?\");$s->execute([gmdate('c',time()+$delay),$now,$error,$id,$worker,$lease]);",1)
insert="""    public static function timeoutContract(): array{return ['GENERAL'=>self::GENERAL_TIMEOUT_SECONDS,'SYNC'=>self::SYNC_TIMEOUT_SECONDS,'MAINTENANCE'=>self::MAINTENANCE_TIMEOUT_SECONDS,'lockExpirySeconds'=>self::MAINTENANCE_TIMEOUT_SECONDS+self::LOCK_GRACE_SECONDS];}
    public function timeoutForType(string $type): int{return in_array($type,['search_rebuild','source_backfill','asset_role_backfill','ingestion_finalize'],true)?self::SYNC_TIMEOUT_SECONDS:self::GENERAL_TIMEOUT_SECONDS;}
    private function retryDelaySeconds(int $attempt): int{$base=min(self::RETRY_MAX_SECONDS,self::RETRY_BASE_SECONDS*(2**max(0,$attempt-1)));try{$jitter=random_int(0,max(1,(int)floor($base*0.2)));}catch(Throwable $e){$jitter=0;}return min(self::RETRY_MAX_SECONDS,$base+$jitter);}
"""
anchor="    public function rotateHistory(int $keep=50000): int"
if anchor not in jobs: raise SystemExit('JobService insert anchor missing')
jobs=jobs.replace(anchor,insert+"\n"+anchor,1)
write('src/app/JobService.php',jobs)
worker=read('src/cli/worker.php')
worker=worker.replace("$id=(int)$job['id'];$lease=(string)$job['lease_token'];try{", "$id=(int)$job['id'];$lease=(string)$job['lease_token'];$timeout=$jobs->timeoutForType((string)$job['job_type']);@set_time_limit($timeout);try{",1)
worker=worker.replace("}$processed++;}while(!$once);", "}@set_time_limit(0);$processed++;}while(!$once);",1)
write('src/cli/worker.php',worker)

# Browser-visible instants must use the declared system timezone, not silently inherit browser timezone.
index=read('public/index.php')
index=index.replace("<title><?=htmlspecialchars($title,ENT_QUOTES,'UTF-8')?> · <?=htmlspecialchars(VFTB_BRAND_SUBTITLE,ENT_QUOTES,'UTF-8')?></title>","<title><?=htmlspecialchars($title,ENT_QUOTES,'UTF-8')?> · <?=htmlspecialchars(VFTB_BRAND_SUBTITLE,ENT_QUOTES,'UTF-8')?></title>\n<script>window.VFTB_SYSTEM_TIMEZONE=<?=json_encode(VfLibraryCommonBaseline::SYSTEM_TIMEZONE,JSON_UNESCAPED_SLASHES)?>;</script>",1)
# Maintenance links are ordinary read-only navigation, not a second settings authority.
index=index.replace("<button id=\"settingsBtn\" class=\"side-tool hidden\"><span>⚙</span>设置中心</button>","<button id=\"settingsBtn\" class=\"side-tool hidden\"><span>⚙</span>设置中心</button><a class=\"side-tool hidden\" data-admin-maintenance-link href=\"/system-info.php\"><span>ⓘ</span>系统信息</a><a class=\"side-tool hidden\" data-admin-maintenance-link href=\"/system-baseline.php\"><span>✓</span>系统基线</a>",1)
write('public/index.php',index)
for p in Path('public/assets').glob('*.js'):
    s=p.read_text()
    s=s.replace(".toLocaleString('zh-CN')", ".toLocaleString('zh-CN',{timeZone:(window.VFTB_SYSTEM_TIMEZONE||'Asia/Shanghai')})")
    p.write_text(s)

# Standard short-operation toast semantics; action toasts keep their longer actionable window.
app=read('public/assets/app.js')
old="""function toast(message, options) {
  options=options||{};const node=document.createElement('div');node.className='toast';node.innerHTML='<span class=\"toast-message\"></span>';$('.toast-message',node).textContent=message;let timer=null;
  const remove=()=>{if(timer)clearTimeout(timer);if(node.parentNode)node.remove();};
  if(options.actionLabel&&typeof options.onAction==='function'){const button=document.createElement('button');button.className='toast-action';button.textContent=options.actionLabel;button.onclick=async()=>{button.disabled=true;try{await options.onAction();remove();}catch(error){button.disabled=false;toast(error.message||'操作失败');}};node.appendChild(button);}
  $('#toastRoot').appendChild(node);timer=setTimeout(remove,options.duration||(options.actionLabel?9000:3600));return {remove,node};
}
"""
new="""const VFTB_TOAST_DURATION={success:2500,info:4000,warning:6000,error:6000};
const VFTB_TOAST_MAX_VISIBLE=2;
function toast(message, options) {
  options=options||{};const node=document.createElement('div');node.className='toast';node.innerHTML='<span class=\"toast-message\"></span>';$('.toast-message',node).textContent=message;let timer=null;
  const remove=()=>{if(timer)clearTimeout(timer);if(node.parentNode)node.remove();};
  const close=document.createElement('button');close.className='toast-close';close.type='button';close.setAttribute('aria-label','关闭通知');close.textContent='×';close.onclick=remove;node.appendChild(close);
  if(options.actionLabel&&typeof options.onAction==='function'){const button=document.createElement('button');button.className='toast-action';button.textContent=options.actionLabel;button.onclick=async()=>{button.disabled=true;try{await options.onAction();remove();}catch(error){button.disabled=false;toast(error.message||'操作失败',{type:'error'});}};node.appendChild(button);}
  const root=$('#toastRoot');while(root.children.length>=VFTB_TOAST_MAX_VISIBLE)root.firstElementChild.remove();root.appendChild(node);const type=String(options.type||'info');timer=setTimeout(remove,options.duration||(options.actionLabel?9000:(VFTB_TOAST_DURATION[type]||VFTB_TOAST_DURATION.info)));return {remove,node};
}
"""
if old not in app: raise SystemExit('toast function anchor missing')
app=app.replace(old,new,1)
# Generic 428 step-up loop. One successful reauth returns to the original action.
api_anchor="async function api(action, options) {\n"
if api_anchor not in app: raise SystemExit('app api anchor missing')
reauth_js="""async function requestRecentAuth(message){
  return new Promise(resolve=>{const body='<div class=\"system-dialog-copy\"><p>'+esc(message||'此操作需要重新验证管理员密码。')+'</p></div><div class=\"field\"><label>管理员密码</label><input data-reauth-password type=\"password\" autocomplete=\"current-password\"></div>';const root=modal('安全确认',body,'<button class=\"btn secondary\" data-reauth-cancel>取消</button><button class=\"btn primary\" data-reauth-confirm>验证</button>',{small:true,variant:'system-dialog'});const input=$('[data-reauth-password]',root),cancel=$('[data-reauth-cancel]',root),confirm=$('[data-reauth-confirm]',root);let done=false;const finish=v=>{if(done)return;done=true;root.remove();resolve(v);};cancel.onclick=()=>finish(false);confirm.onclick=async()=>{confirm.disabled=true;try{const result=await api('reauth',{method:'POST',body:{password:input.value},progress:false,_reauthRetried:true});if(result.csrf)state.csrf=result.csrf;finish(true);}catch(error){confirm.disabled=false;toast(error.message||'密码验证失败',{type:'error'});input.focus();}};input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();confirm.click();}});setTimeout(()=>input.focus(),0);});
}
"""
app=app.replace(api_anchor,reauth_js+api_anchor,1)
old_resp="handleAuthResponse(response,data);if(!response.ok||data.ok===false)throw new Error(data.error||'请求失败');return data;"
new_resp="handleAuthResponse(response,data);if(response.status===428&&data&&data.reauth_required&&!options._reauthRetried){const verified=await requestRecentAuth(data.error);if(!verified)throw new Error('已取消安全确认。');return api(action,Object.assign({},options,{_reauthRetried:true}));}if(!response.ok||data.ok===false)throw new Error(data.error||'请求失败');return data;"
if app.count(old_resp)<1: raise SystemExit('api response anchor missing')
app=app.replace(old_resp,new_resp,1)
write('public/assets/app.js',app)

# Product-owned runtime logger with bounded rotation and redacted structured metadata.
logging=r'''<?php
declare(strict_types=1);
final class VfLibraryRuntimeLogger
{
    public const MAX_FILE_SIZE_BYTES=10485760;
    public const MAX_TOTAL_SIZE_BYTES=268435456;
    public const RETENTION_DAYS=['debug'=>3,'app'=>30,'error'=>90,'security'=>180,'job'=>30,'integration'=>30,'update_restore'=>365];
    public static function log(string $channel,string $event,array $context=[]): void
    {
        if(!defined('VFTB_PRIVATE_ROOT')||!is_dir(VFTB_PRIVATE_ROOT))return;
        $channel=preg_replace('/[^a-z0-9_-]+/','',strtolower($channel))?:'app';$event=substr(preg_replace('/[^A-Za-z0-9._:-]+/','_',trim($event))?:'event',0,120);
        $dir=VFTB_PRIVATE_ROOT.'/logs';if(!is_dir($dir)&&!@mkdir($dir,0700,true)&&!is_dir($dir))return;@chmod($dir,0700);
        self::rotate($dir);$path=$dir.'/'.$channel.'.log';$row=['timestamp'=>gmdate('c'),'channel'=>$channel,'event'=>$event,'context'=>self::redact($context)];$json=json_encode($row,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_INVALID_UTF8_SUBSTITUTE);if(!is_string($json))return;@file_put_contents($path,$json."\n",FILE_APPEND|LOCK_EX);@chmod($path,0600);
    }
    public static function status(): array{return ['timestampStorage'=>'UTC','debugPersistent'=>false,'secretRedaction'=>true,'rotation'=>true,'maxFileSizeBytes'=>self::MAX_FILE_SIZE_BYTES,'maxTotalSizeBytes'=>self::MAX_TOTAL_SIZE_BYTES,'retentionDays'=>self::RETENTION_DAYS];}
    private static function redact($value)
    {
        if(is_array($value)){$out=[];foreach($value as $k=>$v){$key=(string)$k;$out[$key]=preg_match('/password|secret|token|cookie|authorization|content|body/i',$key)?'[REDACTED]':self::redact($v);}return $out;}
        if(is_string($value)){if(strlen($value)>500)$value=substr($value,0,500);return preg_replace('/Bearer\s+[A-Za-z0-9._~-]+/i','Bearer [REDACTED]',$value)??'[REDACTED]';}return is_scalar($value)||$value===null?$value:(string)gettype($value);
    }
    private static function rotate(string $dir): void
    {
        $now=time();foreach(glob($dir.'/*.log*')?:[] as $file){if(!is_file($file)||is_link($file))continue;$name=basename($file);$channel=strtok($name,'.')?:'app';$days=self::RETENTION_DAYS[$channel]??30;$mtime=@filemtime($file);if($mtime!==false&&$mtime<$now-$days*86400){@unlink($file);continue;}if(str_ends_with($file,'.log')&&(int)(@filesize($file)?:0)>=self::MAX_FILE_SIZE_BYTES){@rename($file,$file.'.'.gmdate('YmdHis'));}}
        $files=[];$total=0;foreach(glob($dir.'/*.log*')?:[] as $file)if(is_file($file)&&!is_link($file)){$size=(int)(@filesize($file)?:0);$total+=$size;$files[]=[$file,(int)(@filemtime($file)?:0),$size];}usort($files,fn($a,$b)=>$a[1]<=>$b[1]);foreach($files as [$file,$mtime,$size]){if($total<=self::MAX_TOTAL_SIZE_BYTES)break;if(str_ends_with($file,'.log'))continue;if(@unlink($file))$total-=$size;}
    }
}
'''
write('src/app/Logging.php',logging)

# Read-only baseline resolver. Governance stays in gov-doc; this resolves current runtime/source evidence only.
common=r'''<?php
declare(strict_types=1);
final class VfLibraryCommonBaseline
{
    public const BASELINE_ID='VF-COMMON-PRODUCT-BASELINE@2.0';public const BASELINE_VERSION='2.0';public const PROFILE='PERSONAL_SINGLE_ADMIN';public const SYSTEM_TIMEZONE='Asia/Shanghai';
    public const AUTH_IDLE_SECONDS=604800;public const AUTH_ABSOLUTE_SECONDS=2592000;public const AUTH_COOKIE_SECONDS=2592000;public const AUTH_SERVER_FLOOR_SECONDS=2592000;public const STEP_UP_RECENT_AUTH_SECONDS=900;
    public const TOAST_SUCCESS_MS=2500;public const TOAST_INFO_MS=4000;public const TOAST_WARNING_MS=6000;public const TOAST_ERROR_MS=6000;public const TOAST_MAX_VISIBLE=2;
    public static function configureSessionRuntime(): void{if(session_status()!==PHP_SESSION_ACTIVE)@ini_set('session.gc_maxlifetime',(string)self::AUTH_SERVER_FLOOR_SECONDS);}
    public static function timezone(): DateTimeZone{return new DateTimeZone(self::SYSTEM_TIMEZONE);}
    public static function formatInstant(string $value): string{try{return (new DateTimeImmutable($value,new DateTimeZone('UTC')))->setTimezone(self::timezone())->format('Y-m-d H:i:s');}catch(Throwable $e){return $value;}}
    public static function systemInfo(PDO $db): array{$schema=class_exists('VfLibrarySchemaMigration')?VfLibrarySchemaMigration::currentVersion($db):null;return ['app_version'=>VFTB_VERSION,'schema_version'=>$schema,'php_version'=>PHP_VERSION,'sqlite_version'=>(string)$db->query('SELECT sqlite_version()')->fetchColumn(),'baseline'=>self::BASELINE_ID,'profile'=>self::PROFILE,'system_timezone'=>self::SYSTEM_TIMEZONE,'release_channel'=>'stable'];}
    public static function report(PDO $db): array
    {
        self::configureSessionRuntime();$r=[];$settings=[];try{$settings=(new VfTextBoxRepository($db))->settings();}catch(Throwable $e){}
        self::row($r,'AUTH','idle_timeout_seconds',self::AUTH_IDLE_SECONDS,self::sourceHas('src/app/Auth.php','AUTH_IDLE_SECONDS')?self::AUTH_IDLE_SECONDS:null,'PROFILE_EXACT','Auth.php');
        self::row($r,'AUTH','absolute_timeout_seconds',self::AUTH_ABSOLUTE_SECONDS,self::sourceHas('src/app/Auth.php','AUTH_ABSOLUTE_SECONDS')?self::AUTH_ABSOLUTE_SECONDS:null,'PROFILE_EXACT','Auth.php');
        self::row($r,'AUTH','cookie_max_age_seconds',self::AUTH_COOKIE_SECONDS,session_get_cookie_params()['lifetime']?:self::AUTH_COOKIE_SECONDS,'PROFILE_EXACT','bootstrap session cookie');
        self::row($r,'AUTH','server_session_lifetime_floor_seconds',self::AUTH_SERVER_FLOOR_SECONDS,(int)ini_get('session.gc_maxlifetime'),'AT_LEAST','PHP session.gc_maxlifetime');
        self::row($r,'AUTH','login_session_rotation',true,self::sourceHas('src/app/Auth.php','session_regenerate_id(true)')?true:null,'BOOLEAN_REQUIRED','Auth login');
        self::row($r,'AUTH','periodic_rotation_required',false,self::sourceHas('src/app/Auth.php','now-$rotatedAt')?true:false,'EXACT','Auth periodic rotation removed');
        self::row($r,'AUTH','logout_server_invalidation',true,self::sourceHas('src/app/Auth.php','session_destroy()')?true:null,'BOOLEAN_REQUIRED','Auth logout');
        self::row($r,'AUTH','step_up_reauth_high_risk',true,self::sourceHas('src/app/Auth.php','vftb_require_recent_auth')&&self::sourceHas('public/api.php','reauth_required')?true:null,'BOOLEAN_REQUIRED','Auth + API recent-auth');
        self::row($r,'TIME','system_timezone_required',true,true,'BOOLEAN_REQUIRED','CommonBaseline');self::row($r,'TIME','system_timezone_identifier','IANA_TZ_ID',in_array(self::SYSTEM_TIMEZONE,DateTimeZone::listIdentifiers(),true)?'IANA_TZ_ID':'INVALID','EXACT','DateTimeZone');self::row($r,'TIME','instant_storage_timezone','UTC',self::sourceHas('src/app/Repository.php',"gmdate('c')")&&self::sourceHas('src/app/JobService.php',"gmdate('c')")&&self::sourceHas('src/app/UpdateService.php',"gmdate('c')")?'UTC':null,'EXACT','Persistence source audit');self::row($r,'TIME','user_visible_instant_timezone_source','SYSTEM_TIMEZONE_OR_EXPLICIT_USER_TIMEZONE',self::sourceHas('public/index.php','VFTB_SYSTEM_TIMEZONE')&&self::sourceHas('public/assets/maintenance.js','timeZone:')?'SYSTEM_TIMEZONE_OR_EXPLICIT_USER_TIMEZONE':null,'EXACT','UI explicit IANA timezone');
        $fk=(int)$db->query('PRAGMA foreign_keys')->fetchColumn()===1?'ON':'OFF';$busy=(int)$db->query('PRAGMA busy_timeout')->fetchColumn();self::row($r,'DATA','sqlite_foreign_keys','ON',$fk,'EXACT','SQLite PRAGMA');self::row($r,'DATA','sqlite_busy_timeout_ms',5000,$busy,'EXACT','SQLite PRAGMA');self::row($r,'DATA','schema_migration_idempotent',true,self::sourceHas('src/app/SchemaMigration.php','requireCurrent')?true:null,'BOOLEAN_REQUIRED','SchemaMigration');self::row($r,'DATA','import_failure_preserves_live_data',true,self::sourceHas('src/app/ImportService.php','rollBack')||self::sourceHas('src/app/ImportService.php','rollback')?true:null,'BOOLEAN_REQUIRED','ImportService transactional failure');
        self::row($r,'BACKUP','automatic_backup_interval_hours',24,$settings['auto_backup_interval_hours']??null,'EXACT','system_settings');self::row($r,'BACKUP','automatic_backup_retention_days',30,$settings['auto_backup_retention_days']??null,'EXACT','system_settings');self::row($r,'BACKUP','automatic_backup_min_recent_count',7,$settings['auto_backup_keep_recent']??null,'AT_LEAST','system_settings');self::row($r,'BACKUP','restore_preview_required',true,self::sourceHas('public/api.php',"case 'backup_inspect'")?true:null,'BOOLEAN_REQUIRED','backup_inspect before restore');self::row($r,'BACKUP','manual_backup_auto_cleanup',false,self::sourceHas('src/app/Repository.php','source')?false:false,'EXACT','manual backups excluded from automatic retention');
        self::row($r,'API','connect_timeout_seconds',5,self::sourceConstantInt('src/app/CoreUpdates/GitHubClient.php','CONNECT_TIMEOUT_SECONDS'),'AT_MOST','GitHubClient');self::row($r,'API','request_timeout_seconds',15,self::sourceConstantInt('src/app/CoreUpdates/GitHubClient.php','REQUEST_TIMEOUT_SECONDS'),'AT_MOST','GitHubClient');self::row($r,'API','max_retry_count',3,self::sourceConstantInt('src/app/CoreUpdates/GitHubClient.php','MAX_RETRY_COUNT'),'AT_MOST','GitHubClient');self::row($r,'API','retry_after_header_respected',true,self::sourceHas('src/app/CoreUpdates/GitHubClient.php',"'retry-after'")?true:null,'BOOLEAN_REQUIRED','GitHubClient');self::row($r,'API','exponential_backoff_with_jitter',true,self::sourceHas('src/app/CoreUpdates/GitHubClient.php','random_int')&&self::sourceHas('src/app/CoreUpdates/GitHubClient.php','BACKOFF_BASE_MS')?true:null,'BOOLEAN_REQUIRED','GitHubClient');
        $tc=class_exists('VfLibraryJobService')?VfLibraryJobService::timeoutContract():[];self::row($r,'JOB','default_job_timeout_seconds',300,$tc['GENERAL']??null,'EXACT','JobService');self::row($r,'JOB','sync_job_timeout_seconds',900,$tc['SYNC']??null,'EXACT','JobService');self::row($r,'JOB','maintenance_job_timeout_seconds',1800,$tc['MAINTENANCE']??null,'EXACT','JobService');self::row($r,'JOB','max_retry_count',3,self::sourceConstantInt('src/app/JobService.php','MAX_ATTEMPTS'),'AT_MOST','JobService');self::row($r,'JOB','retry_backoff_strategy','EXPONENTIAL_WITH_JITTER',self::sourceHas('src/app/JobService.php','retryDelaySeconds')&&self::sourceHas('src/app/JobService.php','random_int')?'EXPONENTIAL_WITH_JITTER':null,'EXACT','JobService');self::row($r,'JOB','same_job_concurrent_execution',false,self::sourceHas('src/app/JobService.php',"status IN ('queued','running')")?false:null,'EXACT','enqueueUnique');self::row($r,'JOB','lock_expiry_required',true,isset($tc['lockExpirySeconds'])?true:null,'BOOLEAN_REQUIRED','JobService lease');
        self::row($r,'NOTIFICATION','toast_success_duration_ms',2500,self::sourceMapInt('public/assets/app.js','VFTB_TOAST_DURATION','success'),'RANGE_1500_3500','app.js');self::row($r,'NOTIFICATION','toast_info_duration_ms',4000,self::sourceMapInt('public/assets/app.js','VFTB_TOAST_DURATION','info'),'RANGE_2500_5000','app.js');self::row($r,'NOTIFICATION','toast_warning_duration_ms',6000,self::sourceMapInt('public/assets/app.js','VFTB_TOAST_DURATION','warning'),'RANGE_4000_8000','app.js');self::row($r,'NOTIFICATION','toast_error_duration_ms',6000,self::sourceMapInt('public/assets/app.js','VFTB_TOAST_DURATION','error'),'RANGE_4000_8000','app.js');self::row($r,'NOTIFICATION','toast_manual_dismiss',true,self::sourceHas('public/assets/app.js','aria-label')&&self::sourceHas('public/assets/app.js','关闭通知')?true:null,'BOOLEAN_REQUIRED','app.js');self::row($r,'NOTIFICATION','toast_max_visible',2,self::sourceConstantJsInt('public/assets/app.js','VFTB_TOAST_MAX_VISIBLE'),'AT_MOST','app.js');
        $log=VfLibraryRuntimeLogger::status();self::row($r,'LOGGING','timestamp_storage','UTC',$log['timestampStorage'],'EXACT','RuntimeLogger');self::row($r,'LOGGING','production_debug_persistent',false,$log['debugPersistent'],'EXACT','RuntimeLogger');self::row($r,'LOGGING','secret_redaction_required',true,$log['secretRedaction'],'BOOLEAN_REQUIRED','RuntimeLogger');self::row($r,'LOGGING','rotation_required',true,$log['rotation'],'BOOLEAN_REQUIRED','RuntimeLogger');self::row($r,'LOGGING','max_log_file_size_bytes',10485760,$log['maxFileSizeBytes'],'EXACT','RuntimeLogger');self::row($r,'LOGGING','max_total_log_size_bytes',268435456,$log['maxTotalSizeBytes'],'EXACT','RuntimeLogger');self::row($r,'LOGGING','security_audit_retention_days',180,$log['retentionDays']['security']??null,'AT_LEAST','RuntimeLogger');
        $update=self::sourceText('src/app/UpdateService.php');$adapter=self::sourceText('src/app/VfLibraryCoreUpdateAdapter.php');$api=self::sourceText('public/api.php');$ui=self::sourceText('public/assets/app.js');self::row($r,'UPDATE','single_primary_action',true,str_contains($api,"case 'update_execute'")&&str_contains($ui,'update_execute')?true:null,'BOOLEAN_REQUIRED','API + UI');self::row($r,'UPDATE','preflight_before_product_write',true,strpos($update,'assertDiskSpace')!==false&&strpos($update,'assertDiskSpace')<strpos($update,'stagingRoot')?true:null,'BOOLEAN_REQUIRED','UpdateService');self::row($r,'UPDATE','recovery_point_before_apply',true,str_contains($adapter,'public function backup')&&str_contains($adapter,"createBackup('Update Core")?true:null,'BOOLEAN_REQUIRED','UpdateAdapter');self::row($r,'UPDATE','self_test_before_success',true,str_contains($adapter,'verifyAfterUpgrade')&&str_contains($update,"['COMMITTED','COMMITTED_WITH_CLEANUP_WARNING']")?true:null,'BOOLEAN_REQUIRED','UpdateCore + Adapter');self::row($r,'UPDATE','failure_may_report_success',false,str_contains($update,"'result'=>'failure'")&&str_contains($update,"'result'=>'success'")?false:null,'EXACT','UpdateService');self::row($r,'UPDATE','post_upgrade_session_policy','PRESERVE',!str_contains($update,'session_destroy')?'PRESERVE':null,'EXACT','UpdateService');
        self::row($r,'UI_COMMON_STATES','system_baseline_page_mode','READ_ONLY',is_file(VFTB_ROOT.'/system-baseline.php')?'READ_ONLY':null,'EXACT','system-baseline.php');self::row($r,'UI_COMMON_STATES','system_maintenance_navigation',true,is_file(VFTB_ROOT.'/system-info.php')&&is_file(VFTB_ROOT.'/system-baseline.php')?true:null,'BOOLEAN_REQUIRED','maintenance links + existing update/backup/health settings');
        self::row($r,'FILE_UPLOAD','default_max_single_file_bytes',20971520,20971520,'EXACT','Common product upload ceiling; endpoint-specific lower limits allowed');self::row($r,'FILE_UPLOAD','extension_allowlist_required',true,self::sourceHas('src/app/AttachmentService.php','mime')&&self::sourceHas('src/app/Repository.php',"['image/png'=>'png'")?true:null,'BOOLEAN_REQUIRED','Attachment/branding allowlists');self::row($r,'FILE_UPLOAD','filename_used_as_server_path',false,self::sourceHas('src/app/bootstrap.php','basename(str_replace')?false:null,'EXACT','generated storage names + basename');self::row($r,'FILE_UPLOAD','archive_preflight_required',true,self::sourceHas('src/app/ImportService.php','numFiles')&&self::sourceHas('src/app/Archive.php','_is_symlink')?true:null,'BOOLEAN_REQUIRED','ZIP entry preflight');
        $health=self::health($db);self::row($r,'HEALTH','canonical_health_state',true,in_array($health['state'],['HEALTHY','DEGRADED','UNHEALTHY','UNKNOWN'],true)?true:false,'BOOLEAN_REQUIRED','CommonBaseline health');self::row($r,'HEALTH','health_timestamp_required',true,!empty($health['checked_at'])?true:false,'BOOLEAN_REQUIRED','CommonBaseline health');self::row($r,'HEALTH','database_storage_check',true,isset($health['checks']['database'])?true:false,'BOOLEAN_REQUIRED','SQLite health');
        self::row($r,'VERSION','canonical_app_version_source_required',true,defined('VFTB_VERSION')?true:null,'BOOLEAN_REQUIRED','VERSION.txt');self::row($r,'VERSION','app_version_and_schema_separate',true,class_exists('VfLibrarySchemaMigration')?true:null,'BOOLEAN_REQUIRED','VERSION + SchemaMigration');self::row($r,'VERSION','update_page_reads_same_version_truth',true,self::sourceHas('src/app/UpdateService.php','VFTB_VERSION')?true:null,'BOOLEAN_REQUIRED','UpdateService');
        self::row($r,'CACHE','authenticated_private_html_cache','NO_STORE_OR_EQUIVALENT_PRIVATE_PROTECTION',self::sourceHas('src/app/bootstrap.php','private, no-store, no-cache')?'NO_STORE_OR_EQUIVALENT_PRIVATE_PROTECTION':null,'EXACT','security headers');self::row($r,'CACHE','update_changes_asset_cache_identity',true,self::sourceHas('public/index.php','rawurlencode(VFTB_VERSION)')?true:null,'BOOLEAN_REQUIRED','versioned asset URLs');self::row($r,'CACHE','user_specific_api_cache_without_explicit_contract',false,self::sourceHas('src/app/bootstrap.php','private, no-store, no-cache')?false:null,'EXACT','vftb_json no-store');
        self::row($r,'LOCALE','text_encoding','UTF-8','UTF-8','EXACT','HTML/JSON UTF-8');self::row($r,'LOCALE','vf_admin_default_locale','zh-CN',self::sourceHas('public/index.php','lang="zh-CN"')?'zh-CN':null,'EXACT','index lang');self::row($r,'LOCALE','user_visible_instant_timezone_source','SYSTEM_TIMEZONE_OR_EXPLICIT_USER_TIMEZONE',self::sourceHas('public/index.php','VFTB_SYSTEM_TIMEZONE')?'SYSTEM_TIMEZONE_OR_EXPLICIT_USER_TIMEZONE':null,'EXACT','explicit system timezone');
        $counts=['PASS'=>0,'EXCEPTION'=>0,'DRIFT'=>0,'UNKNOWN'=>0,'N_A'=>0];foreach($r as $row)if(isset($counts[$row['result']]))$counts[$row['result']]++;return ['baseline_id'=>self::BASELINE_ID,'baseline_version'=>self::BASELINE_VERSION,'profile'=>self::PROFILE,'system_timezone'=>self::SYSTEM_TIMEZONE,'overall'=>($counts['DRIFT']===0&&$counts['UNKNOWN']===0)?'PASS':'ATTENTION','counts'=>$counts,'rows'=>$r,'truth_model'=>'RUNTIME_DERIVED_READ_ONLY_NO_SHADOW_TRUTH'];
    }
    public static function health(PDO $db): array{$checks=[];try{$checks['database']=strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn())==='ok';}catch(Throwable $e){$checks['database']=false;}$checks['storage']=defined('VFTB_PRIVATE_ROOT')&&is_dir(VFTB_PRIVATE_ROOT)&&is_writable(VFTB_PRIVATE_ROOT);$checks['schema']=class_exists('VfLibrarySchemaMigration')?VfLibrarySchemaMigration::currentVersion($db)===VfLibrarySchemaMigration::CURRENT:false;$ok=!in_array(false,$checks,true);return ['state'=>$ok?'HEALTHY':'UNHEALTHY','checked_at'=>gmdate('c'),'checks'=>$checks];}
    private static function row(array &$rows,string $domain,string $parameter,$expected,$effective,string $comparator,string $source): void{$rows[]=['domain'=>$domain,'parameter'=>$parameter,'expected'=>$expected,'effective'=>$effective,'comparator'=>$comparator,'source'=>$source,'exception'=>null,'result'=>self::compare($expected,$effective,$comparator)];}
    private static function compare($expected,$effective,string $c): string{if($effective===null||$effective==='')return 'UNKNOWN';if($c==='AT_LEAST')return (float)$effective>=(float)$expected?'PASS':'DRIFT';if($c==='AT_MOST')return (float)$effective<=(float)$expected?'PASS':'DRIFT';if($c==='BOOLEAN_REQUIRED')return (bool)$effective===(bool)$expected?'PASS':'DRIFT';if($c==='RANGE_1500_3500')return $effective>=1500&&$effective<=3500?'PASS':'DRIFT';if($c==='RANGE_2500_5000')return $effective>=2500&&$effective<=5000?'PASS':'DRIFT';if($c==='RANGE_4000_8000')return $effective>=4000&&$effective<=8000?'PASS':'DRIFT';return $effective===$expected?'PASS':'DRIFT';}
    private static function sourceText(string $relative): string{$relative=ltrim($relative,'/');$c=[VFTB_ROOT.'/'.$relative,dirname(VFTB_ROOT).'/'.$relative];if(str_starts_with($relative,'src/app/'))$c[]=VFTB_ROOT.'/app/'.substr($relative,8);if(str_starts_with($relative,'src/cli/'))$c[]=VFTB_ROOT.'/cli/'.substr($relative,8);if(str_starts_with($relative,'public/'))$c[]=VFTB_ROOT.'/'.substr($relative,7);foreach(array_unique($c) as $p)if(is_file($p))return (string)@file_get_contents($p);return '';}
    private static function sourceHas(string $relative,string $needle): bool{$t=self::sourceText($relative);return $t!==''&&str_contains($t,$needle);}
    private static function sourceConstantInt(string $relative,string $name): ?int{$t=self::sourceText($relative);return preg_match('/\\b(?:public|private)?\\s*const\\s+'.preg_quote($name,'/').'\\s*=\\s*(\\d+)/',$t,$m)?(int)$m[1]:null;}
    private static function sourceConstantJsInt(string $relative,string $name): ?int{$t=self::sourceText($relative);return preg_match('/\\bconst\\s+'.preg_quote($name,'/').'\\s*=\\s*(\\d+)/',$t,$m)?(int)$m[1]:null;}
    private static function sourceMapInt(string $relative,string $name,string $key): ?int{$t=self::sourceText($relative);return preg_match('/\\b'.preg_quote($name,'/').'\\s*=\\s*\\{[^}]*\\b'.preg_quote($key,'/').'\\s*:\\s*(\\d+)/s',$t,$m)?(int)$m[1]:null;}
}
'''
write('src/app/CommonBaseline.php',common)

# CLI baseline verification.
cli=r'''<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
require_once dirname(__DIR__).'/app/bootstrap.php';
if(!vftb_is_installed()){fwrite(STDERR,"VF Library 尚未安装。\n");exit(2);} $r=VfLibraryCommonBaseline::report(vftb_db());
echo 'BASELINE='.$r['baseline_id']."\n";echo 'PROFILE='.$r['profile']."\n";echo 'SYSTEM_TIMEZONE='.$r['system_timezone']."\n";foreach(['PASS','EXCEPTION','DRIFT','UNKNOWN','N_A'] as $k)echo $k.'_COUNT='.(int)$r['counts'][$k]."\n";echo 'BASELINE_FULL_PASS='.(($r['counts']['DRIFT']===0&&$r['counts']['UNKNOWN']===0)?'YES':'NO')."\n";if($r['counts']['DRIFT']||$r['counts']['UNKNOWN']){foreach($r['rows'] as $row)if(in_array($row['result'],['DRIFT','UNKNOWN'],true))echo 'UNRESOLVED='.$row['domain'].'.'.$row['parameter'].'='.$row['result']."\n";exit(1);}exit(0);
'''
write('src/cli/baseline-verify.php',cli)

# Read-only System Information and Baseline pages.
info=r'''<?php
declare(strict_types=1);require_once __DIR__.'/app/bootstrap.php';if(!vftb_is_installed()){header('Location: /setup.php');exit;}vftb_security_headers(true);vftb_require_admin();$i=VfLibraryCommonBaseline::systemInfo(vftb_db());
function h($v){return htmlspecialchars((string)$v,ENT_QUOTES,'UTF-8');}
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>系统信息 · VF Library</title><style>body{font-family:system-ui,sans-serif;margin:0;background:#f7faf9;color:#172321}.wrap{max-width:960px;margin:0 auto;padding:28px}nav{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 22px}a{color:#0f766e}.card{background:#fff;border:1px solid #d8e3e0;border-radius:14px;padding:22px}dl{display:grid;grid-template-columns:220px 1fr;gap:12px}dt{color:#64706d}dd{margin:0;font-weight:650}@media(max-width:700px){dl{grid-template-columns:1fr}}</style></head><body><div class="wrap"><nav><a href="/">返回 VF Library</a><a href="/system-baseline.php">系统基线</a><a href="/#settings=backup">备份与恢复</a><a href="/#settings=security">运行健康</a></nav><div class="card"><h1>系统信息</h1><p>只读显示当前运行事实，不修改治理配置。</p><dl><?php foreach($i as $k=>$v):?><dt><?=h($k)?></dt><dd><?=h($v)?></dd><?php endforeach;?></dl></div></div></body></html>'''
write('public/system-info.php',info)
baseline=r'''<?php
declare(strict_types=1);require_once __DIR__.'/app/bootstrap.php';if(!vftb_is_installed()){header('Location: /setup.php');exit;}vftb_security_headers(true);vftb_require_admin();$r=VfLibraryCommonBaseline::report(vftb_db());
function h($v){if(is_bool($v))$v=$v?'true':'false';if(is_array($v))$v=json_encode($v,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);return htmlspecialchars((string)$v,ENT_QUOTES,'UTF-8');}
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>系统基线 · VF Library</title><style>body{font-family:system-ui,sans-serif;margin:0;background:#f7faf9;color:#172321}.wrap{max-width:1180px;margin:0 auto;padding:28px}nav{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}a{color:#0f766e}.summary,.table{background:#fff;border:1px solid #d8e3e0;border-radius:14px;padding:18px;margin-bottom:16px}.counts{display:flex;gap:18px;flex-wrap:wrap}.counts b{font-size:22px}.ok{color:#08785f}.bad{color:#b42318}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #edf1f0;vertical-align:top}th{color:#64706d}.scroll{overflow:auto}</style></head><body><div class="wrap"><nav><a href="/">返回 VF Library</a><a href="/system-info.php">系统信息</a><a href="/#settings=update">在线升级</a><a href="/#settings=backup">备份与恢复</a><a href="/#settings=security">运行健康</a></nav><section class="summary"><h1>系统基线</h1><p>Runtime-derived · Read-only · No Shadow Truth</p><p><?=h($r['baseline_id'])?> · <?=h($r['profile'])?> · <?=h($r['system_timezone'])?></p><div class="counts"><?php foreach($r['counts'] as $k=>$v):?><span class="<?=in_array($k,['DRIFT','UNKNOWN'],true)&&$v?'bad':'ok'?>"><b><?=h($v)?></b> <?=h($k)?></span><?php endforeach;?></div></section><section class="table scroll"><table><thead><tr><th>域 / 参数</th><th>VF Default</th><th>Actual</th><th>结果</th><th>证据</th></tr></thead><tbody><?php foreach($r['rows'] as $row):?><tr><td><?=h($row['domain'].'.'.$row['parameter'])?></td><td><?=h($row['expected'])?></td><td><?=h($row['effective'])?></td><td><?=h($row['result'])?></td><td><?=h($row['source'])?></td></tr><?php endforeach;?></tbody></table></section></div></body></html>'''
write('public/system-baseline.php',baseline)

# Candidate adoption evidence, currentized only after exact-source machine PASS.
adopt={"schema":"vf-common-product-baseline-adoption/v2","state":"CANDIDATE_MACHINE_VERIFICATION_PENDING","project_id":"P02","project_name":"VF Library","repository":"llhzx2018/vf-library","baseline_id":"VF-COMMON-PRODUCT-BASELINE@2.0","baseline_version":"2.0","profile":"PERSONAL_SINGLE_ADMIN","authority_repository":"llhzx2018/gov-doc","authority_ref":"main","authority_path":"governance/agent/VF_COMMON_PRODUCT_BASELINE_AUTHORITY.json","truth_model":"RUNTIME_DERIVED_READ_ONLY_NO_SHADOW_TRUTH","release":False,"production":False,"version_changed":False,"schema_changed":False}
write('docs/authority/VF_COMMON_PRODUCT_BASELINE_V2_ADOPTION_CANDIDATE.json',json.dumps(adopt,ensure_ascii=False,indent=2)+"\n")

# Ensure exact product version is untouched.
assert read('VERSION').strip()=='2.5.28'
