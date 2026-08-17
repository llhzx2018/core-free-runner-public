#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, gzip, hashlib, json, re, shutil, zipfile
from pathlib import Path

PACKAGE_ID='vf-forge'
PACKAGE_TYPE='app'
TARGET_VERSION='1.35.4'
TARGET_SCHEMA=30
SOURCE_VERSION='1.35.3'
SOURCE_SCHEMA=29
MIGRATION_ID='M030_EXTERNAL_AUTHORITY_MEMORY_INDEX'
PRODUCT_COMMIT='af34b84a3135333cf05077b3eb64e22ef6b3afef'
PRODUCT_TREE='08eee7e8c891a57c357553dd5de20c1a7bd79849'
RUNTIME_FINGERPRINT='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083'
MANAGED_ROOT_FILES={'api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','robots.txt','setup.php','share.php'}
MANAGED_DIRS={'app','assets','cli','mcp'}
FIXED_ZIP_TIME=(2020,1,1,0,0,0)


def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def fsha(p:Path)->str:return sha(p.read_bytes())

def source_files(root:Path)->dict[str,bytes]:
    out={}
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink():continue
        rel=p.relative_to(root).as_posix();top=rel.split('/',1)[0]
        if rel=='app/.runtime.php' or re.match(r'^repair-v[^/]+\.php$',rel):continue
        if rel in MANAGED_ROOT_FILES or top in MANAGED_DIRS:out[rel]=p.read_bytes()
    return out

def manifest_rows(files:dict[str,bytes])->list[str]:
    return [f'{p}\t{len(b)}\t{sha(b)}' for p,b in sorted(files.items())]

def source_manifest(files:dict[str,bytes])->bytes:
    return ('\n'.join(manifest_rows(files))+'\n').encode()

def runtime_fingerprint(files:dict[str,bytes])->str:
    h=hashlib.sha256()
    for p,b in sorted(files.items()):h.update(p.encode()+b'\0'+sha(b).encode()+b'\0'+str(len(b)).encode()+b'\n')
    return h.hexdigest()

def migration_checksum(target_root:Path)->str:
    h=hashlib.sha256()
    for name in ['schema.php','schema30.sql']:
        b=(target_root/'app'/name).read_bytes();h.update(name.encode()+b'\0'+b+b'\0')
    return h.hexdigest()

def deterministic_zip_tree(root:Path,out:Path)->None:
    with zipfile.ZipFile(out,'w') as z:
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.is_symlink():continue
            rel=p.relative_to(root).as_posix();zi=zipfile.ZipInfo(rel,date_time=FIXED_ZIP_TIME);zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=(0o100644&0xFFFF)<<16
            z.writestr(zi,p.read_bytes(),compresslevel=9)

def deterministic_zip_one(out:Path,name:str,data:bytes)->None:
    zi=zipfile.ZipInfo(name,date_time=FIXED_ZIP_TIME);zi.compress_type=zipfile.ZIP_DEFLATED;zi.external_attr=(0o100644&0xFFFF)<<16
    with zipfile.ZipFile(out,'w') as z:z.writestr(zi,data,compresslevel=9)

def payload_blob(files:dict[str,bytes],delete_paths:list[str],m030_sha:str,migration_fp:str)->tuple[str,str,str]:
    sm=source_manifest(files);obj={
      'format':'vf-forge-atomic-payload-v2','package_id':PACKAGE_ID,'package_type':PACKAGE_TYPE,
      'source_version':SOURCE_VERSION,'source_schema':SOURCE_SCHEMA,'target_version':TARGET_VERSION,'target_schema':TARGET_SCHEMA,
      'allowed_source_versions':[SOURCE_VERSION],'migration':MIGRATION_ID,'migration_runtime_path':'app/schema30.sql','migration_runtime_sha256':m030_sha,'migration_checksum':migration_fp,
      'product_commit':PRODUCT_COMMIT,'product_tree':PRODUCT_TREE,'runtime_fingerprint':RUNTIME_FINGERPRINT,
      'project_asset_storage':'NONE','user_upload':'RETIRED','source_manifest_sha256':sha(sm),'source_file_count':len(files),'delete_paths':delete_paths,
      'files':{p:{'bytes':len(b),'sha256':sha(b),'content':base64.b64encode(b).decode()} for p,b in sorted(files.items())}}
    raw=json.dumps(obj,separators=(',',':'),sort_keys=True).encode();gz=gzip.compress(raw,compresslevel=9,mtime=0)
    return base64.b64encode(gz).decode(),sha(raw),sha(sm)

def repair_php(payload_b64:str,payload_sha:str,manifest_sha:str,m030_sha:str,migration_fp:str,test_fail_stage:str='')->bytes:
    fail=json.dumps(test_fail_stage,separators=(',',':'))
    template=r'''<?php
/** VF Forge 1.35.4 Formal Atomic Maintenance Release. Generated from frozen Product Candidate; do not edit. */
declare(strict_types=1);
const VFF_PACKAGE_ID='vf-forge';
const VFF_PACKAGE_TYPE='app';
const VFF_SOURCE_VERSION='1.35.3';
const VFF_SOURCE_SCHEMA=29;
const VFF_ATOMIC_TARGET='1.35.4';
const VFF_ATOMIC_SCHEMA=30;
const VFF_MIGRATION_ID='M030_EXTERNAL_AUTHORITY_MEMORY_INDEX';
const VFF_MIGRATION_RUNTIME_PATH='app/schema30.sql';
const VFF_MIGRATION_RUNTIME_SHA256='__M030_SHA__';
const VFF_MIGRATION_CHECKSUM='__MIGRATION_FP__';
const VFF_PRODUCT_COMMIT='af34b84a3135333cf05077b3eb64e22ef6b3afef';
const VFF_PRODUCT_TREE='08eee7e8c891a57c357553dd5de20c1a7bd79849';
const VFF_RUNTIME_FINGERPRINT='2fd3ebbbebfd7155371fe44664715cbe34f63cfb98dfeb691bba90d4864ca083';
const VFF_ATOMIC_PAYLOAD_JSON_SHA256='__PAYLOAD_SHA__';
const VFF_ATOMIC_SOURCE_MANIFEST_SHA256='__MANIFEST_SHA__';
const VFF_ATOMIC_PAYLOAD='__PAYLOAD_B64__';
const VFF_TEST_FAIL_STAGE=__FAIL__;

function vff_render(string $title,string $message,string $type='normal',bool $form=false,string $csrf=''): never {
 $t=htmlspecialchars($title,ENT_QUOTES,'UTF-8');$m=htmlspecialchars($message,ENT_QUOTES,'UTF-8');$c=$type==='error'?'#b62c25':'#12a46b';
 header('Content-Type: text/html; charset=utf-8');header('X-Robots-Tag: noindex, nofollow, noarchive');header('X-Frame-Options: DENY');header('X-Content-Type-Options: nosniff');header('Cache-Control: no-store');
 echo '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VF Forge 原子升级</title><body style="margin:0;padding:36px 18px;font:15px/1.65 Segoe UI,Microsoft YaHei,sans-serif;background:#f7fbf9;color:#173029"><main style="width:min(760px,100%);margin:auto;background:#fff;border:1px solid #dfe9e4;border-radius:16px;padding:28px"><div>P03 · VF Forge · Formal Atomic</div><h1>'.$t.'</h1><div style="padding:13px;border-left:4px solid '.$c.'">'.$m.'</div>';
 if($form)echo '<form method="post"><input type="hidden" name="_csrf" value="'.htmlspecialchars($csrf,ENT_QUOTES,'UTF-8').'"><input type="hidden" name="confirmation" value="UPGRADE"><button style="margin-top:18px;padding:10px 17px" type="submit">执行原子升级</button></form>';
 echo '</main></body></html>';exit;
}
function vff_safe_rel(string $rel):string{$rel=str_replace('\\','/',$rel);if($rel===''||str_starts_with($rel,'/')||str_contains($rel,"\0")||preg_match('#(^|/)\.\.(/|$)#',$rel)||preg_match('/^[A-Za-z]:/',$rel))throw new RuntimeException('Unsafe Atomic path: '.$rel);$top=explode('/',$rel,2)[0];$roots=['api.php','diagnose.php','download.php','index.html','index.php','maintenance.php','robots.txt','setup.php','share.php'];if(!in_array($rel,$roots,true)&&!in_array($top,['app','assets','cli','mcp'],true))throw new RuntimeException('Atomic path outside managed runtime scope: '.$rel);if($rel==='app/.runtime.php'||preg_match('#(^|/)repair-v[^/]+\.php$#',$rel))throw new RuntimeException('Atomic payload contains private repair path.');return $rel;}
function vff_mkdir(string $d,int $mode=0750):void{if(is_link($d))throw new RuntimeException('Symlink directory rejected.');if(!is_dir($d)&&!mkdir($d,$mode,true)&&!is_dir($d))throw new RuntimeException('Cannot create directory.');}
function vff_rrmdir(string $p):void{if(!is_dir($p)||is_link($p))return;$it=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($p,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::CHILD_FIRST);foreach($it as $x){$q=$x->getPathname();if($x->isLink()||$x->isFile())@unlink($q);else@rmdir($q);}@rmdir($p);}
function vff_atomic_write(string $p,string $b):void{vff_mkdir(dirname($p));if(is_link($p))throw new RuntimeException('Symlink target rejected.');$t=$p.'.vff-new-'.bin2hex(random_bytes(5));if(file_put_contents($t,$b,LOCK_EX)!==strlen($b)){@unlink($t);throw new RuntimeException('Atomic write failed.');}@chmod($t,0644);if(!@rename($t,$p)){@unlink($t);throw new RuntimeException('Atomic rename failed.');}}
function vff_copy_verified(string $a,string $b):void{vff_mkdir(dirname($b));if(!copy($a,$b))throw new RuntimeException('Backup copy failed.');if(!hash_equals((string)hash_file('sha256',$a),(string)hash_file('sha256',$b)))throw new RuntimeException('Backup SHA mismatch.');}
function vff_db_check(PDO $db):void{if(strtolower((string)$db->query('PRAGMA integrity_check')->fetchColumn())!=='ok')throw new RuntimeException('SQLite integrity_check failed.');if($db->query('PRAGMA foreign_key_check')->fetchAll())throw new RuntimeException('SQLite foreign_key_check failed.');}
function vff_failpoint(string $s):void{if(VFF_TEST_FAIL_STAGE!==''&&hash_equals(VFF_TEST_FAIL_STAGE,$s))throw new RuntimeException('TEST_FAILPOINT_'.$s);}
function vff_payload():array{$gz=base64_decode(VFF_ATOMIC_PAYLOAD,true);if(!is_string($gz))throw new RuntimeException('Atomic payload base64 invalid.');$raw=gzdecode($gz);if(!is_string($raw)||!hash_equals(VFF_ATOMIC_PAYLOAD_JSON_SHA256,hash('sha256',$raw)))throw new RuntimeException('Atomic payload checksum invalid.');$p=json_decode($raw,true,64,JSON_THROW_ON_ERROR);if(($p['format']??'')!=='vf-forge-atomic-payload-v2'||($p['package_id']??'')!==VFF_PACKAGE_ID||($p['source_version']??'')!==VFF_SOURCE_VERSION||($p['target_version']??'')!==VFF_ATOMIC_TARGET||(int)($p['source_schema']??0)!==VFF_SOURCE_SCHEMA||(int)($p['target_schema']??0)!==VFF_ATOMIC_SCHEMA||($p['migration']??'')!==VFF_MIGRATION_ID)throw new RuntimeException('Atomic Package Identity mismatch.');if(!hash_equals((string)($p['source_manifest_sha256']??''),VFF_ATOMIC_SOURCE_MANIFEST_SHA256))throw new RuntimeException('Atomic source manifest mismatch.');return$p;}
function vff_parse_bootstrap(string $f):array{$s=@file_get_contents($f);if(!is_string($s))throw new RuntimeException('bootstrap unavailable.');if(!preg_match("/define\\('VFAB_VERSION',\\s*'([^']+)'\\);/",$s,$v)||!preg_match("/define\\('VFAB_SCHEMA_VERSION',\\s*(\\d+)\\);/",$s,$m))throw new RuntimeException('bootstrap identity unreadable.');return[$v[1],(int)$m[1]];}
function vff_https():bool{if(!empty($_SERVER['HTTPS'])&&strtolower((string)$_SERVER['HTTPS'])!=='off')return true;if((int)($_SERVER['SERVER_PORT']??0)===443)return true;$trust=strtolower(trim((string)(getenv('VF_FORGE_TRUST_PROXY_HTTPS')?:'')));if(in_array($trust,['1','true','yes','on'],true)){return strtolower(trim(explode(',',(string)($_SERVER['HTTP_X_FORWARDED_PROTO']??''),2)[0]))==='https';}return false;}
function vff_same_origin():bool{$o=trim((string)($_SERVER['HTTP_ORIGIN']??''));if($o==='')return true;$h=parse_url($o,PHP_URL_HOST);$s=strtolower((string)(parse_url($o,PHP_URL_SCHEME)??''));$p=parse_url($o,PHP_URL_PORT);$rh=parse_url('http://'.(string)($_SERVER['HTTP_HOST']??''),PHP_URL_HOST);$rp=parse_url('http://'.(string)($_SERVER['HTTP_HOST']??''),PHP_URL_PORT);if(!is_string($h)||!is_string($rh)||!hash_equals(strtolower(rtrim($h,'.')),strtolower(rtrim($rh,'.'))))return false;$rs=vff_https()?'https':'http';if(!hash_equals($rs,$s))return false;return ($p??($s==='https'?443:80))===($rp??((int)($_SERVER['SERVER_PORT']??0)?:($rs==='https'?443:80)));}
function vff_auth(string $root):array{$rf=$root.'/app/.runtime.php';if(!is_file($rf)||is_link($rf))throw new RuntimeException('Runtime settings unavailable.');$rt=include $rf;if(!is_array($rt)||empty($rt['data_root'])||empty($rt['db_file'])||empty($rt['config_file']))throw new RuntimeException('Runtime settings invalid.');$raw=@file_get_contents((string)$rt['config_file']);$cfg=is_string($raw)?json_decode($raw,true):null;if(!is_array($cfg))throw new RuntimeException('Config unavailable.');if(session_status()!==PHP_SESSION_ACTIVE){session_name('vfforge_session');ini_set('session.use_strict_mode','1');ini_set('session.use_only_cookies','1');session_start();}if(empty($_SESSION['vfab_admin']))vff_render('需要登录','请先登录 VF Forge 管理后台。','error');$epoch=hash('sha256',(string)($cfg['admin_password_hash']??'').'|'.(string)($cfg['session_secret']??'').'|'.(string)($cfg['password_updated_at']??''));$stored=(string)($_SESSION['vfab_auth_epoch']??'');if($stored===''||!hash_equals($epoch,$stored))vff_render('登录已失效','认证纪元不一致，请重新登录。','error');$sid=session_id();$secret=(string)($cfg['session_secret']??$cfg['admin_password_hash']??'vf-forge');$sh=$sid===''?'':hash_hmac('sha256',$sid,$secret);$db=new PDO('sqlite:'.(string)$rt['db_file'],null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);$db->exec('PRAGMA foreign_keys=ON');$q=$db->prepare('SELECT revoked_at,expires_at FROM admin_sessions WHERE session_hash=? LIMIT 1');$q->execute([$sh]);$row=$q->fetch();if(!$row||!empty($row['revoked_at'])||((strtotime((string)($row['expires_at']??''))?:PHP_INT_MAX)<=time()))vff_render('登录已失效','当前管理员 Session 已失效。','error');return[$rt,$cfg,$db,(string)($_SESSION['vfab_csrf']??'')];}

$root=__DIR__;[$current,$currentSchema]=vff_parse_bootstrap($root.'/app/bootstrap.php');if($current!==VFF_SOURCE_VERSION||$currentSchema!==VFF_SOURCE_SCHEMA)vff_render('版本不允许','仅允许 V'.VFF_SOURCE_VERSION.' / Schema '.VFF_SOURCE_SCHEMA.' → V'.VFF_ATOMIC_TARGET.' / Schema '.VFF_ATOMIC_SCHEMA.'。','error');
[$rt,$cfg,$authDb,$csrf]=vff_auth($root);if($_SERVER['REQUEST_METHOD']!=='POST')vff_render('VF Forge V'.VFF_SOURCE_VERSION.' → V'.VFF_ATOMIC_TARGET,'Schema '.VFF_SOURCE_SCHEMA.' → '.VFF_ATOMIC_SCHEMA.'；Migration '.VFF_MIGRATION_ID.'。执行前建立源码与 SQLite 恢复点，失败自动恢复。','normal',true,$csrf);
if(!vff_same_origin())vff_render('来源校验失败','请求 Origin 与当前站点不一致。','error');$provided=(string)($_POST['_csrf']??'');if($provided===''||$csrf===''||!hash_equals($csrf,$provided))vff_render('CSRF 校验失败','登录状态已变化，请刷新后重试。','error');if((string)($_POST['confirmation']??'')!=='UPGRADE')vff_render('确认失败','原子升级确认参数无效。','error');
$payload=vff_payload();$files=(array)($payload['files']??[]);$delete=(array)($payload['delete_paths']??[]);if(!$files)throw new RuntimeException('Atomic payload empty.');if(!isset($files[VFF_MIGRATION_RUNTIME_PATH])||!hash_equals(VFF_MIGRATION_RUNTIME_SHA256,(string)($files[VFF_MIGRATION_RUNTIME_PATH]['sha256']??'')))throw new RuntimeException('Migration 030 missing from Atomic payload.');
$dataRoot=(string)$rt['data_root'];$dbFile=(string)$rt['db_file'];$tempDir=$dataRoot.'/temp';$backupDir=$dataRoot.'/backups';$lockDir=$dataRoot.'/locks';$op=gmdate('Ymd-His').'-'.bin2hex(random_bytes(4));$stage=$tempDir.'/atomic-'.$op;$recovery=$backupDir.'/atomic-recovery-v'.VFF_SOURCE_VERSION.'-to-v'.VFF_ATOMIC_TARGET.'-'.$op;$sourceBackup=$recovery.'/source';$dbSnapshot=$recovery.'/pre-upgrade.sqlite';$meta=$recovery.'/RECOVERY.json';$lockPath=$lockDir.'/atomic-upgrade.lock';vff_mkdir($stage);vff_mkdir($sourceBackup);vff_mkdir($lockDir);$lock=fopen($lockPath,'c+');if(!$lock||!flock($lock,LOCK_EX|LOCK_NB))throw new RuntimeException('另一个 Atomic/维护任务正在执行。');$changed=[];$absent=[];$migrateDb=null;$migrationApplied=false;
try{
 foreach($files as $rel=>$spec){$rel=vff_safe_rel((string)$rel);$b=base64_decode((string)($spec['content']??''),true);if(!is_string($b)||(int)($spec['bytes']??-1)!==strlen($b)||!hash_equals((string)$spec['sha256'],hash('sha256',$b)))throw new RuntimeException('Payload file verify failed: '.$rel);$d=$stage.'/'.$rel;vff_mkdir(dirname($d));if(file_put_contents($d,$b,LOCK_EX)!==strlen($b))throw new RuntimeException('Stage write failed: '.$rel);}vff_failpoint('after_stage');
 vff_db_check($authDb);try{$authDb->exec('PRAGMA wal_checkpoint(TRUNCATE)');}catch(Throwable $ignore){}$authDb->exec('VACUUM INTO '.$authDb->quote($dbSnapshot));if(!is_file($dbSnapshot)||filesize($dbSnapshot)<=0)throw new RuntimeException('Pre-upgrade SQLite snapshot failed.');$verify=new PDO('sqlite:'.$dbSnapshot);vff_db_check($verify);$verify=null;
 foreach($files as $rel=>$spec){$rel=vff_safe_rel((string)$rel);$t=$root.'/'.$rel;$wanted=(string)$spec['sha256'];if(is_file($t)&&!is_link($t)&&hash_equals($wanted,(string)hash_file('sha256',$t)))continue;if(file_exists($t)||is_link($t)){if(!is_file($t)||is_link($t))throw new RuntimeException('Unsafe source path: '.$rel);vff_copy_verified($t,$sourceBackup.'/'.$rel);}else{$absent[]=$rel;}$changed[]=$rel;}
 foreach($delete as $rel){$rel=vff_safe_rel((string)$rel);$t=$root.'/'.$rel;if(file_exists($t)||is_link($t)){if(!is_file($t)||is_link($t))throw new RuntimeException('Unsafe delete path: '.$rel);vff_copy_verified($t,$sourceBackup.'/'.$rel);$changed[]=$rel;}}
 file_put_contents($meta,json_encode(['format'=>'vf-forge-atomic-recovery-v2','from_version'=>VFF_SOURCE_VERSION,'target_version'=>VFF_ATOMIC_TARGET,'schema_from'=>VFF_SOURCE_SCHEMA,'schema_to'=>VFF_ATOMIC_SCHEMA,'migration'=>VFF_MIGRATION_ID,'changed_paths'=>array_values(array_unique($changed)),'absent_before'=>$absent,'db_snapshot'=>'pre-upgrade.sqlite','source_manifest_sha256'=>VFF_ATOMIC_SOURCE_MANIFEST_SHA256,'created_at'=>gmdate('c')],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES));vff_failpoint('after_recovery');
 $order=array_keys($files);usort($order,static function($a,$b){$aa=$a==='app/bootstrap.php'?1:0;$bb=$b==='app/bootstrap.php'?1:0;return$aa<=>$bb?:strcmp($a,$b);});foreach($order as $rel){$rel=vff_safe_rel((string)$rel);$t=$root.'/'.$rel;$wanted=(string)$files[$rel]['sha256'];if(is_file($t)&&!is_link($t)&&hash_equals($wanted,(string)hash_file('sha256',$t)))continue;$b=file_get_contents($stage.'/'.$rel);if(!is_string($b))throw new RuntimeException('Staged source missing: '.$rel);vff_atomic_write($t,$b);if(!hash_equals($wanted,(string)hash_file('sha256',$t)))throw new RuntimeException('Post-switch SHA mismatch: '.$rel);}foreach($delete as $rel){$t=$root.'/'.vff_safe_rel((string)$rel);if(is_file($t)&&!is_link($t)&&!@unlink($t))throw new RuntimeException('Obsolete runtime removal failed: '.$rel);}clearstatcache(true);if(function_exists('opcache_reset'))@opcache_reset();vff_failpoint('after_source_switch');
 [$nv,$ns]=vff_parse_bootstrap($root.'/app/bootstrap.php');if($nv!==VFF_ATOMIC_TARGET||$ns!==VFF_ATOMIC_SCHEMA)throw new RuntimeException('Target bootstrap identity mismatch.');if(!hash_equals(VFF_MIGRATION_RUNTIME_SHA256,(string)hash_file('sha256',$root.'/'.VFF_MIGRATION_RUNTIME_PATH)))throw new RuntimeException('Migration 030 runtime checksum mismatch.');$authDb=null;
 require_once $root.'/app/bootstrap.php';require_once $root.'/app/MigrationRunner.php';$migrateDb=vfab_open_sqlite_file($dbFile,false);$mr=(new VfMigrationRunner($migrateDb))->run();if((int)($mr['before_schema']??-1)!==VFF_SOURCE_SCHEMA||(int)($mr['after_schema']??-1)!==VFF_ATOMIC_SCHEMA||($mr['migration_id']??'')!==VFF_MIGRATION_ID||empty($mr['verified']))throw new RuntimeException('Migration 030 result mismatch.');$migrationApplied=true;vff_db_check($migrateDb);$q=$migrateDb->prepare('SELECT migration_id,checksum,status FROM schema_migrations WHERE version=?');$q->execute([VFF_ATOMIC_SCHEMA]);$row=$q->fetch();if(!$row||($row['migration_id']??'')!==VFF_MIGRATION_ID||($row['status']??'')!=='applied'||!hash_equals(VFF_MIGRATION_CHECKSUM,(string)($row['checksum']??'')))throw new RuntimeException('Migration 030 identity/checksum readback mismatch.');vff_failpoint('after_migration');
 foreach($files as $rel=>$spec){$t=$root.'/'.vff_safe_rel((string)$rel);if(!is_file($t)||is_link($t)||!hash_equals((string)$spec['sha256'],(string)hash_file('sha256',$t)))throw new RuntimeException('Final runtime verification failed: '.$rel);}vff_failpoint('before_success');
 $migrateDb=null;flock($lock,LOCK_UN);fclose($lock);$lock=null;vff_rrmdir($stage);@unlink(__FILE__);vff_render('升级完成','VF Forge 已原子升级到 V'.VFF_ATOMIC_TARGET.'；Schema '.VFF_SOURCE_SCHEMA.' → '.VFF_ATOMIC_SCHEMA.' / '.VFF_MIGRATION_ID.' PASS。升级前源码与 SQLite 恢复点已保留。');
}catch(Throwable $e){
 $migrateDb=null;$authDb=null;if(is_file($dbSnapshot)){@unlink($dbFile.'-wal');@unlink($dbFile.'-shm');try{$b=file_get_contents($dbSnapshot);if(is_string($b))vff_atomic_write($dbFile,$b);}catch(Throwable $ignore){}}
 foreach(array_reverse(array_values(array_unique($changed))) as $rel){try{$rel=vff_safe_rel((string)$rel);$b=$sourceBackup.'/'.$rel;$t=$root.'/'.$rel;if(is_file($b)&&!is_link($b)){$x=file_get_contents($b);if(is_string($x))vff_atomic_write($t,$x);}elseif(in_array($rel,$absent,true)&&is_file($t)&&!is_link($t))@unlink($t);}catch(Throwable $ignore){}}
 clearstatcache(true);if(function_exists('opcache_reset'))@opcache_reset();if(is_resource($lock)){@flock($lock,LOCK_UN);@fclose($lock);}vff_rrmdir($stage);vff_render('原子升级失败，已执行恢复',$e->getMessage().'；源码与 SQLite 已按升级前恢复点恢复，恢复快照继续保留。','error');
}
'''
    return (template.replace('__M030_SHA__',m030_sha).replace('__MIGRATION_FP__',migration_fp).replace('__PAYLOAD_SHA__',payload_sha).replace('__MANIFEST_SHA__',manifest_sha).replace('__PAYLOAD_B64__',payload_b64).replace('__FAIL__',fail)).encode()

def release_notes()->bytes:
    s='''# VF Forge V1.35.4 发布说明\n\nV1.35.4 不是普通 UI 更新。VF Forge 从“本地文件仓库”正式转为“个人项目记忆与资产索引中心”。\n\n## 主要变化\n\n- Schema 30 / M030_EXTERNAL_AUTHORITY_MEMORY_INDEX\n- External Authority\n- GitHub Read-only\n- Observation\n- Truth Relation Graph\n- Derived Current Truth\n- Project Memory\n- Cross-Authority Search\n- Authority-aware Retrieval\n- Project-Asset Storage = NONE\n- User Upload = RETIRED\n\n## Legacy Compatibility\n\n旧 Local Asset 继续保留 Legacy Compatibility。本次 1.35.3 → 1.35.4 升级不会物理删除旧项目文件；Existing Binary 必须保持 SHA / Bytes / Path / MTIME 不变。Legacy Storage Cleanup 尚未执行，后续必须由独立 Gate 授权。\n\n## 升级边界\n\n唯一授权升级来源：V1.35.3 / Schema 29。目标：V1.35.4 / Schema 30。升级前必须建立 SQLite 与源码恢复点；失败按 Atomic Recovery Contract 恢复。\n'''
    return s.encode()

def build(base_root:Path,target_root:Path,out:Path,test_fail_stage:str='')->dict:
    out.mkdir(parents=True,exist_ok=True);base=source_files(base_root);target=source_files(target_root)
    if len(target)!=42:raise SystemExit(f'RUNTIME_FILE_COUNT_MISMATCH {len(target)}')
    if runtime_fingerprint(target)!=RUNTIME_FINGERPRINT:raise SystemExit('RUNTIME_FINGERPRINT_MISMATCH')
    delete=sorted(set(base)-set(target));m030=sha(target['app/schema30.sql']);mfp=migration_checksum(target_root)
    payload,payload_sha,manifest_sha=payload_blob(target,delete,m030,mfp);repair=repair_php(payload,payload_sha,manifest_sha,m030,mfp,test_fail_stage)
    full=out/f'VF_Forge_V{TARGET_VERSION}_FULL.zip';deterministic_zip_tree(target_root,full)
    repair_name=f'repair-v{TARGET_VERSION}.php';(out/repair_name).write_bytes(repair)
    atomic=out/f'VF_Forge_V{TARGET_VERSION}_Atomic_Upgrade.zip';deterministic_zip_one(atomic,repair_name,repair)
    update=out/f'VF_Forge_V{TARGET_VERSION}_UPDATE.zip';shutil.copyfile(atomic,update)
    sm_name=f'VF_Forge_V{TARGET_VERSION}_SOURCE_MANIFEST.txt';sm=source_manifest(target);(out/sm_name).write_bytes(sm)
    notes_name=f'VF_Forge_V{TARGET_VERSION}_RELEASE_NOTES.md';(out/notes_name).write_bytes(release_notes())
    pkg_name=f'VF_Forge_V{TARGET_VERSION}_PACKAGE_MANIFEST.json';pkg={
      'format':'vf-forge-maintenance-release-v1','package_id':PACKAGE_ID,'package_type':PACKAGE_TYPE,'version':TARGET_VERSION,'schema':TARGET_SCHEMA,
      'source_version':SOURCE_VERSION,'schema_from':SOURCE_SCHEMA,'schema_to':TARGET_SCHEMA,'migration':MIGRATION_ID,'allowed_source_versions':[SOURCE_VERSION],
      'product_commit':PRODUCT_COMMIT,'product_tree':PRODUCT_TREE,'runtime_files':len(target),'runtime_fingerprint':RUNTIME_FINGERPRINT,
      'atomic_file':atomic.name,'atomic_sha256':fsha(atomic),'repair_file':repair_name,'repair_sha256':sha(repair),'source_manifest_file':sm_name,'source_manifest_sha256':sha(sm),
      'changed_files':sorted(p for p in target if base.get(p)!=target[p]),'deleted_runtime_files':delete,'project_asset_storage':'NONE','user_upload':'RETIRED','physical_project_asset_delete':0}
    (out/pkg_name).write_text(json.dumps(pkg,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    rel_name=f'VF_Forge_V{TARGET_VERSION}_RELEASE_MANIFEST.json';artifact_pre={
      full.name:{'bytes':full.stat().st_size,'sha256':fsha(full)},update.name:{'bytes':update.stat().st_size,'sha256':fsha(update)},atomic.name:{'bytes':atomic.stat().st_size,'sha256':fsha(atomic)},repair_name:{'bytes':len(repair),'sha256':sha(repair)},sm_name:{'bytes':len(sm),'sha256':sha(sm)},notes_name:{'bytes':(out/notes_name).stat().st_size,'sha256':fsha(out/notes_name)},pkg_name:{'bytes':(out/pkg_name).stat().st_size,'sha256':fsha(out/pkg_name)}}
    rel={'format':'vf-forge-release-manifest-v1','project':'P03','project_name':'VF Forge','version':TARGET_VERSION,'schema':TARGET_SCHEMA,'source_version':SOURCE_VERSION,'schema_from':SOURCE_SCHEMA,'schema_to':TARGET_SCHEMA,'migration':MIGRATION_ID,'migration_runtime_path':'app/schema30.sql','migration_runtime_sha256':m030,'migration_checksum':mfp,'product_commit':PRODUCT_COMMIT,'product_tree':PRODUCT_TREE,'runtime_files':len(target),'runtime_fingerprint':RUNTIME_FINGERPRINT,'source_manifest_sha256':sha(sm),'project_asset_storage':'NONE','user_upload':'RETIRED','backup_required':True,'rollback_recovery':'SUPPORTED / ATOMIC SOURCE + SQLITE SNAPSHOT + M030 PRE-MIGRATION BACKUP','physical_project_asset_delete':0,'legacy_storage_cleanup':'NOT_EXECUTED','formal_release':'NOT_EXECUTED','artifacts':artifact_pre}
    (out/rel_name).write_text(json.dumps(rel,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    names=[full.name,update.name,atomic.name,repair_name,rel_name,sm_name,notes_name,pkg_name];sums=''.join(f'{fsha(out/n)}  {n}\n' for n in names);(out/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    return {'runtime_files':len(target),'runtime_fingerprint':runtime_fingerprint(target),'source_manifest_sha256':sha(sm),'migration_runtime_sha256':m030,'migration_checksum':mfp,'deleted_runtime_files':delete,'artifacts':{n:{'bytes':(out/n).stat().st_size,'sha256':fsha(out/n)} for n in names+['SHA256SUMS.txt']}}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--base-runtime',required=True);ap.add_argument('--target-runtime',required=True);ap.add_argument('--output',required=True);ap.add_argument('--test-fail-stage',default='');a=ap.parse_args()
    r=build(Path(a.base_runtime),Path(a.target_runtime),Path(a.output),a.test_fail_stage);print(json.dumps(r,ensure_ascii=False,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
