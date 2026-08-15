#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, json, os, shutil, stat, zipfile
from pathlib import Path, PurePosixPath

VERSION='2.21.15'
SOURCE_VERSION='2.21.14'
SCHEMA='2026080902'
PROJECT='VF Start'
PROJECT_ID='P01'
COMPONENT_ID='APP'
REPO='llhzx2018/vf-start'

FORBIDDEN_PARTS={'.git','node_modules','private_data','PRIVATE_DATA','_import_chunks'}
FORBIDDEN_SUFFIXES={'.sqlite','.sqlite3','.db','.log','.env'}
SKIP_NAMES={'app/.runtime.php','app/.setup-key.php','app/.setup.lock','release-manifest.json'}

def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha256_file(p:Path)->str: return sha256_bytes(p.read_bytes())

def safe_rel(rel:str)->str:
    q=PurePosixPath(rel)
    if rel.startswith('/') or '\\' in rel or '..' in q.parts or str(q)!=rel or rel in ('','.'): raise ValueError(rel)
    return rel

def include_runtime(rel:str)->bool:
    safe_rel(rel)
    p=PurePosixPath(rel)
    if any(part in FORBIDDEN_PARTS or part.startswith('.vfnav-data-') for part in p.parts): return False
    if rel in SKIP_NAMES: return False
    low=rel.lower()
    if any(low.endswith(x) for x in FORBIDDEN_SUFFIXES): return False
    if p.name.startswith('repair-v') and p.suffix=='.php': return False
    return True

def collect(root:Path, include_release_manifest:bool=False)->dict[str,bytes]:
    out={}
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink(): continue
        rel=p.relative_to(root).as_posix()
        if rel=='release-manifest.json' and include_release_manifest:
            out[rel]=p.read_bytes(); continue
        if include_runtime(rel): out[rel]=p.read_bytes()
    return out

def deterministic_zip(path:Path, files:dict[str,bytes]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(files):
            safe_rel(name)
            zi=zipfile.ZipInfo(name,date_time=(2026,8,15,0,0,0))
            zi.compress_type=zipfile.ZIP_DEFLATED
            zi.external_attr=(0o100644 & 0xFFFF)<<16
            zi.create_system=3
            z.writestr(zi,files[name])

def b64json(obj)->str:
    return base64.b64encode(json.dumps(obj,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()).decode()

def php_quote(s:str)->str:
    return "'"+s.replace('\\','\\\\').replace("'","\\'")+"'"

def build_repair(source:dict[str,bytes],target:dict[str,bytes],bridge_update_hash:str)->str:
    src_manifest={k:sha256_bytes(v) for k,v in source.items()}
    target_manifest={k:sha256_bytes(v) for k,v in target.items() if k!='release-manifest.json'}
    payload={k:base64.b64encode(v).decode() for k,v in target.items()}
    removed=sorted(set(source)-set(target))
    old_update=src_manifest.get('app/UpdateManager.php','')
    alternates={'app/UpdateManager.php':sorted({x for x in [old_update,bridge_update_hash] if x})}
    template=r'''<?php
declare(strict_types=1);
final class VfAtomicPackage
{
    public const SOURCE_VERSION='@@SOURCE_VERSION@@';
    public const TARGET_VERSION='@@TARGET_VERSION@@';
    public const TARGET_SCHEMA='@@SCHEMA@@';
    private const SOURCE_MANIFEST='@@SOURCE_MANIFEST@@';
    private const TARGET_MANIFEST='@@TARGET_MANIFEST@@';
    private const PAYLOAD='@@PAYLOAD@@';
    private const REMOVED='@@REMOVED@@';
    private const SOURCE_ALTERNATES='@@ALTERNATES@@';

    private static function decode(string $b64): array {
        $raw=base64_decode($b64,true); if($raw===false) throw new RuntimeException('Atomic metadata decode failed.');
        $x=json_decode($raw,true); if(!is_array($x)) throw new RuntimeException('Atomic metadata JSON invalid.'); return $x;
    }
    private static function rel(string $rel): string {
        if($rel===''||$rel[0]==='/'||strpos($rel,'\\')!==false||preg_match('#(^|/)\.\.(/|$)#',$rel)) throw new RuntimeException('Unsafe Atomic path.');
        return $rel;
    }
    private static function writeExact(string $path,string $bytes): void {
        $dir=dirname($path); if(!is_dir($dir)&&!@mkdir($dir,0750,true)&&!is_dir($dir)) throw new RuntimeException('Cannot create Atomic directory.');
        $tmp=$path.'.atomic-tmp-'.bin2hex(random_bytes(4)); $h=@fopen($tmp,'xb'); if(!$h) throw new RuntimeException('Cannot create Atomic temp file.');
        try { $off=0;$len=strlen($bytes); while($off<$len){$n=@fwrite($h,substr($bytes,$off));if($n===false||$n===0)throw new RuntimeException('Short Atomic write.');$off+=$n;} if(!@fflush($h))throw new RuntimeException('Atomic flush failed.'); if(function_exists('fsync'))@fsync($h); }
        finally { @fclose($h); }
        @chmod($tmp,0640); if(!@rename($tmp,$path)){@unlink($tmp);throw new RuntimeException('Atomic rename failed.');}
    }
    private static function verifyManifest(string $root,array $manifest,bool $source=false): array {
        $alts=$source?self::decode(self::SOURCE_ALTERNATES):[]; $errors=[];
        foreach($manifest as $rel=>$expected){$rel=self::rel((string)$rel);$p=rtrim($root,'/').'/'.$rel;if(!is_file($p)||is_link($p)){$errors[]=$rel.':missing';continue;}$got=hash_file('sha256',$p)?:'';$allowed=[$expected];if($source&&isset($alts[$rel])&&is_array($alts[$rel]))$allowed=array_values(array_unique(array_merge($allowed,$alts[$rel])));if(!in_array($got,$allowed,true))$errors[]=$rel.':sha';}
        return ['ok'=>$errors===[],'errors'=>$errors,'checked'=>count($manifest)];
    }
    private static function runtime(string $root): array {
        $f=rtrim($root,'/').'/app/.runtime.php'; if(!is_file($f)||is_link($f)) throw new RuntimeException('Installed runtime pointer is missing.');
        $x=include $f; if(!is_array($x)||empty($x['data_dir'])||empty($x['db_file'])||empty($x['config_file'])) throw new RuntimeException('Installed runtime pointer invalid.'); return $x;
    }
    private static function dbVerify(string $db): array {
        if(!extension_loaded('pdo_sqlite')) throw new RuntimeException('PDO_SQLITE is required.');
        $p=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
        $p->exec('PRAGMA foreign_keys=ON');$p->exec('PRAGMA busy_timeout=5000');
        $integrity=strtolower((string)$p->query('PRAGMA integrity_check')->fetchColumn());$fk=$p->query('PRAGMA foreign_key_check')->fetchAll();
        $head=(string)$p->query("SELECT COALESCE(MAX(version),'') FROM schema_migrations WHERE status='success'")->fetchColumn();
        if($integrity!=='ok'||$fk||$head!==self::TARGET_SCHEMA) throw new RuntimeException('Database verification failed.');
        return ['integrity'=>$integrity,'foreign_key_errors'=>count($fk),'schema'=>$head];
    }
    private static function snapshotDb(string $db,string $dest): void {
        $p=new PDO('sqlite:'.$db,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);$p->exec('PRAGMA wal_checkpoint(FULL)');$q=str_replace("'","''",$dest);$p->exec("VACUUM INTO '$q'");@chmod($dest,0600);
    }
    private static function restoreDb(string $snapshot,string $db): void {
        if(!is_file($snapshot)) throw new RuntimeException('Rollback database snapshot missing.');
        @unlink($db.'-wal');@unlink($db.'-shm');self::writeExact($db,(string)file_get_contents($snapshot));@chmod($db,0640);
    }
    private static function backupFiles(string $root,string $stage,array $paths): array {
        $meta=[];foreach($paths as $rel){$rel=self::rel((string)$rel);$src=rtrim($root,'/').'/'.$rel;$exists=is_file($src)&&!is_link($src);$meta[$rel]=$exists;if($exists){$dst=$stage.'/source/'.$rel;self::writeExact($dst,(string)file_get_contents($src));}}return $meta;
    }
    private static function restoreFiles(string $root,string $stage,array $meta): void {
        foreach($meta as $rel=>$existed){$rel=self::rel((string)$rel);$dst=rtrim($root,'/').'/'.$rel;$src=$stage.'/source/'.$rel;if($existed){if(!is_file($src))throw new RuntimeException('Rollback source snapshot missing.');self::writeExact($dst,(string)file_get_contents($src));}else{@unlink($dst);}}
    }
    private static function removeTree(string $p): void {if(!file_exists($p))return;if(is_file($p)||is_link($p)){@unlink($p);return;}foreach(scandir($p)?:[] as $n){if($n==='.'||$n==='..')continue;self::removeTree($p.'/'.$n);}@rmdir($p);}
    public static function selfTest(): array {
        if(PHP_VERSION_ID<80000) throw new RuntimeException('PHP 8.0+ required.');
        $src=self::decode(self::SOURCE_MANIFEST);$tar=self::decode(self::TARGET_MANIFEST);$pay=self::decode(self::PAYLOAD);$removed=self::decode(self::REMOVED);
        if(!$src||!$tar||!$pay)throw new RuntimeException('Atomic metadata empty.');
        foreach($tar as $rel=>$sha){if(!isset($pay[$rel]))throw new RuntimeException('Atomic payload misses target file: '.$rel);$b=base64_decode((string)$pay[$rel],true);if($b===false||!hash_equals((string)$sha,hash('sha256',$b)))throw new RuntimeException('Atomic payload hash mismatch: '.$rel);}
        foreach($removed as $rel)self::rel((string)$rel);
        return ['ok'=>true,'source_files'=>count($src),'target_files'=>count($tar),'payload_files'=>count($pay),'removed_files'=>count($removed),'php_min'=>'8.0.0'];
    }
    public static function verifySource(string $root): array {return self::verifyManifest($root,self::decode(self::SOURCE_MANIFEST),true);}
    public static function verifyTarget(string $root): array {return self::verifyManifest($root,self::decode(self::TARGET_MANIFEST),false);}
    public static function run(string $root): array {
        self::selfTest();$root=rtrim(realpath($root)?:$root,'/');$v=trim((string)@file_get_contents($root.'/VERSION.txt'));
        if($v===self::TARGET_VERSION){$t=self::verifyTarget($root);if(!$t['ok'])throw new RuntimeException('Target version files are inconsistent.');$rt=self::runtime($root);$db=self::dbVerify((string)$rt['db_file']);return ['ok'=>true,'already_current'=>true,'schema'=>$db['schema'],'integrity'=>$db['integrity'],'fk'=>$db['foreign_key_errors']];}
        if($v!==self::SOURCE_VERSION)throw new RuntimeException('Unsupported source version: '.$v);
        $s=self::verifySource($root);if(!$s['ok'])throw new RuntimeException('Source verification failed: '.implode(',',$s['errors']));
        $rt=self::runtime($root);$data=rtrim((string)$rt['data_dir'],'/');$db=(string)$rt['db_file'];$config=(string)$rt['config_file'];if(!is_file($db)||!is_file($config))throw new RuntimeException('Installed database/config missing.');
        $udir=$data.'/updates';if(!is_dir($udir)&&!@mkdir($udir,0750,true)&&!is_dir($udir))throw new RuntimeException('Cannot create update directory.');$lock=@fopen($udir.'/p01-atomic.lock','c+');if(!$lock||!@flock($lock,LOCK_EX))throw new RuntimeException('Cannot acquire update lock.');
        $stage=$udir.'/.atomic-'.self::TARGET_VERSION.'-'.bin2hex(random_bytes(5));@mkdir($stage,0700,true);$sourceMeta=[];$configBytes=(string)file_get_contents($config);$dbSnap=$stage.'/database.sqlite';
        try {
            $s=self::verifySource($root);if(!$s['ok'])throw new RuntimeException('Source changed after lock.');self::snapshotDb($db,$dbSnap);
            $payload=self::decode(self::PAYLOAD);$removed=self::decode(self::REMOVED);$all=array_values(array_unique(array_merge(array_keys($payload),$removed)));$sourceMeta=self::backupFiles($root,$stage,$all);
            foreach($payload as $rel=>$b64){$bytes=base64_decode((string)$b64,true);if($bytes===false)throw new RuntimeException('Payload decode failed.');self::writeExact($root.'/'.self::rel((string)$rel),$bytes);}
            foreach($removed as $rel){$p=$root.'/'.self::rel((string)$rel);if(is_file($p)||is_link($p))@unlink($p);}
            if(getenv('VF_ATOMIC_TEST_FAIL_AFTER_APPLY')==='1')throw new RuntimeException('Injected failure after source apply.');
            $cfg=json_decode((string)file_get_contents($config),true);if(!is_array($cfg))throw new RuntimeException('Config JSON invalid.');$cfg['version']=self::TARGET_VERSION;$j=json_encode($cfg,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);if($j===false)throw new RuntimeException('Config serialize failed.');self::writeExact($config,$j."\n");
            $target=self::verifyTarget($root);if(!$target['ok'])throw new RuntimeException('Target verification failed: '.implode(',',$target['errors']));$dbv=self::dbVerify($db);
            self::removeTree($stage);@flock($lock,LOCK_UN);@fclose($lock);$self=basename((string)($_SERVER['SCRIPT_FILENAME']??''));if($self==='repair-v'.self::TARGET_VERSION.'.php')@unlink($root.'/'.$self);
            return ['ok'=>true,'already_current'=>false,'schema'=>$dbv['schema'],'integrity'=>$dbv['integrity'],'fk'=>$dbv['foreign_key_errors'],'source_checked'=>$s['checked'],'target_checked'=>$target['checked'],'rollback_supported'=>true];
        } catch(Throwable $e) {
            try {if($sourceMeta)self::restoreFiles($root,$stage,$sourceMeta);self::restoreDb($dbSnap,$db);self::writeExact($config,$configBytes);$after=self::verifySource($root);if(!$after['ok'])throw new RuntimeException('Rollback source verification failed.');self::dbVerify($db);} catch(Throwable $rb){$msg='Atomic failed and rollback verification failed.';@flock($lock,LOCK_UN);@fclose($lock);throw new RuntimeException($msg,0,$e);}
            self::removeTree($stage);@flock($lock,LOCK_UN);@fclose($lock);throw new RuntimeException('Atomic failed; source, config and database were restored: '.$e->getMessage(),0,$e);
        }
    }
}
if(defined('VF_ATOMIC_LIBRARY_MODE')&&VF_ATOMIC_LIBRARY_MODE)return;
if(PHP_SAPI==='cli'){
    try {if(in_array('--self-test',$argv,true)){echo json_encode(VfAtomicPackage::selfTest(),JSON_UNESCAPED_SLASHES)."\n";exit(0);}foreach($argv as $a){if(strpos($a,'--verify-source=')===0){$r=VfAtomicPackage::verifySource(substr($a,16));echo json_encode($r)."\n";exit($r['ok']?0:1);}if(strpos($a,'--verify-target=')===0){$r=VfAtomicPackage::verifyTarget(substr($a,16));echo json_encode($r)."\n";exit($r['ok']?0:1);}if(strpos($a,'--run=')===0){echo json_encode(VfAtomicPackage::run(substr($a,6)),JSON_UNESCAPED_SLASHES)."\n";exit(0);}}fwrite(STDERR,"Use --self-test, --verify-source=PATH, --verify-target=PATH or --run=PATH\n");exit(2);}catch(Throwable $e){fwrite(STDERR,$e->getMessage()."\n");exit(1);}
}
$root=__DIR__;require_once $root.'/app/bootstrap.php';vf_security_headers(true);header('X-Robots-Tag: noindex,nofollow,noarchive');vf_start_session();
if(!vf_is_admin()){http_response_code(403);echo '<!doctype html><meta charset="utf-8"><title>VF Start 升级</title><p>需要管理员登录后再执行升级。</p>';exit;}
$csrf=vf_csrf_token();$result=null;$error='';if(($_SERVER['REQUEST_METHOD']??'GET')==='POST'){try{if(!hash_equals($csrf,(string)($_POST['csrf']??'')))throw new RuntimeException('请求已过期。');$result=VfAtomicPackage::run($root);}catch(Throwable $e){$error=$e->getMessage();}}
?><!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VF Start V<?=htmlspecialchars(VfAtomicPackage::TARGET_VERSION)?> 升级</title></head><body><main><h1>VF Start 升级</h1><?php if($result):?><h2>升级完成</h2><p>版本：V<?=htmlspecialchars(VfAtomicPackage::TARGET_VERSION)?></p><p><a href="./">打开 VF Start</a></p><?php elseif($error!==''):?><h2>升级失败</h2><p><?=htmlspecialchars($error,ENT_QUOTES,'UTF-8')?></p><?php else:?><p>将从 V<?=htmlspecialchars(VfAtomicPackage::SOURCE_VERSION)?> 升级到 V<?=htmlspecialchars(VfAtomicPackage::TARGET_VERSION)?>。执行前会建立数据库、配置和源码恢复点。</p><form method="post"><input type="hidden" name="csrf" value="<?=htmlspecialchars($csrf,ENT_QUOTES,'UTF-8')?>"><button type="submit">执行原子升级</button></form><p><a href="./">返回 VF Start</a></p><?php endif;?></main></body></html>
'''
    return (template.replace('@@SOURCE_VERSION@@',SOURCE_VERSION).replace('@@TARGET_VERSION@@',VERSION).replace('@@SCHEMA@@',SCHEMA)
            .replace('@@SOURCE_MANIFEST@@',b64json(src_manifest)).replace('@@TARGET_MANIFEST@@',b64json(target_manifest))
            .replace('@@PAYLOAD@@',b64json(payload)).replace('@@REMOVED@@',b64json(removed)).replace('@@ALTERNATES@@',b64json(alternates)))

def build_bridge(old_update:bytes,new_update:bytes,core_files:dict[str,bytes])->str:
    oldsha=sha256_bytes(old_update); newsha=sha256_bytes(new_update)
    payload={'app/UpdateManager.php':base64.b64encode(new_update).decode()}
    for k,v in core_files.items(): payload[k]=base64.b64encode(v).decode()
    hashes={k:sha256_bytes(base64.b64decode(v)) for k,v in payload.items()}
    template=r'''<?php
declare(strict_types=1);
final class VfP01DiscoveryBridge
{
 private const SOURCE_VERSION='2.21.14';
 private const OLD_UPDATE_SHA='@@OLDSHA@@';
 private const NEW_UPDATE_SHA='@@NEWSHA@@';
 private const PAYLOAD='@@PAYLOAD@@';
 private const HASHES='@@HASHES@@';
 private static function d(string $x):array{$r=base64_decode($x,true);$j=$r===false?null:json_decode($r,true);if(!is_array($j))throw new RuntimeException('Bridge metadata invalid.');return $j;}
 private static function rel(string $r):string{if($r===''||$r[0]==='/'||strpos($r,'\\')!==false||preg_match('#(^|/)\.\.(/|$)#',$r))throw new RuntimeException('Unsafe bridge path.');return $r;}
 private static function w(string $p,string $b):void{$d=dirname($p);if(!is_dir($d)&&!@mkdir($d,0750,true)&&!is_dir($d))throw new RuntimeException('Bridge directory create failed.');$t=$p.'.bridge-tmp-'.bin2hex(random_bytes(4));if(file_put_contents($t,$b,LOCK_EX)!==strlen($b)){@unlink($t);throw new RuntimeException('Bridge write failed.');}@chmod($t,0640);if(!@rename($t,$p)){@unlink($t);throw new RuntimeException('Bridge rename failed.');}}
 public static function selfTest():array{$p=self::d(self::PAYLOAD);$h=self::d(self::HASHES);foreach($p as $r=>$b){$x=base64_decode((string)$b,true);if($x===false||!isset($h[$r])||!hash_equals((string)$h[$r],hash('sha256',$x)))throw new RuntimeException('Bridge payload hash mismatch.');}return ['ok'=>true,'files'=>count($p),'version_unchanged'=>true,'schema_unchanged'=>true];}
 public static function run(string $root):array{self::selfTest();$root=rtrim(realpath($root)?:$root,'/');if(trim((string)@file_get_contents($root.'/VERSION.txt'))!==self::SOURCE_VERSION)throw new RuntimeException('Bridge accepts exact V2.21.14 only.');$u=$root.'/app/UpdateManager.php';$cur=is_file($u)?(hash_file('sha256',$u)?:''):'';if($cur===self::NEW_UPDATE_SHA)return ['ok'=>true,'already_applied'=>true,'version'=>self::SOURCE_VERSION];if($cur!==self::OLD_UPDATE_SHA)throw new RuntimeException('UpdateManager source is not exact Production V2.21.14.');$payload=self::d(self::PAYLOAD);$hashes=self::d(self::HASHES);$backup=[];try{foreach($payload as $rel=>$b64){$rel=self::rel((string)$rel);$p=$root.'/'.$rel;$backup[$rel]=is_file($p)?base64_encode((string)file_get_contents($p)):null;$b=base64_decode((string)$b64,true);if($b===false)throw new RuntimeException('Bridge payload decode failed.');self::w($p,$b);if(!hash_equals((string)$hashes[$rel],hash_file('sha256',$p)?:''))throw new RuntimeException('Bridge verification failed.');}if(trim((string)file_get_contents($root.'/VERSION.txt'))!==self::SOURCE_VERSION)throw new RuntimeException('Bridge changed VERSION unexpectedly.');return ['ok'=>true,'already_applied'=>false,'version'=>self::SOURCE_VERSION,'schema_unchanged'=>true,'files'=>count($payload)];}catch(Throwable $e){foreach($backup as $rel=>$b64){$p=$root.'/'.self::rel($rel);if($b64===null)@unlink($p);else self::w($p,(string)base64_decode($b64,true));}throw new RuntimeException('Bridge failed and was restored: '.$e->getMessage(),0,$e);}}
}
if(defined('VF_P01_BRIDGE_LIBRARY_MODE')&&VF_P01_BRIDGE_LIBRARY_MODE)return;
if(PHP_SAPI==='cli'){try{if(in_array('--self-test',$argv,true)){echo json_encode(VfP01DiscoveryBridge::selfTest())."\n";exit(0);}foreach($argv as $a)if(strpos($a,'--run=')===0){echo json_encode(VfP01DiscoveryBridge::run(substr($a,6)))."\n";exit(0);}fwrite(STDERR,"Use --self-test or --run=PATH\n");exit(2);}catch(Throwable $e){fwrite(STDERR,$e->getMessage()."\n");exit(1);}}
$root=__DIR__;require_once $root.'/app/bootstrap.php';vf_security_headers(true);header('X-Robots-Tag: noindex,nofollow,noarchive');vf_start_session();if(!vf_is_admin()){http_response_code(403);echo '<meta charset="utf-8"><p>需要管理员登录。</p>';exit;}$csrf=vf_csrf_token();$result=null;$error='';if(($_SERVER['REQUEST_METHOD']??'GET')==='POST'){try{if(!hash_equals($csrf,(string)($_POST['csrf']??'')))throw new RuntimeException('请求已过期。');$result=VfP01DiscoveryBridge::run($root);}catch(Throwable $e){$error=$e->getMessage();}}?><!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>VF Start 在线更新接入</title><body><main><h1>一次性在线更新接入</h1><?php if($result):?><p>接入完成。VF Start 版本仍为 V2.21.14；现在可以回到后台“更新”检查 V2.21.15。</p><?php elseif($error):?><p><?=htmlspecialchars($error,ENT_QUOTES,'UTF-8')?></p><?php else:?><p>只安装新的在线更新发现能力，不升级 VF Start，不改变 Schema 或业务数据。</p><form method="post"><input type="hidden" name="csrf" value="<?=htmlspecialchars($csrf,ENT_QUOTES,'UTF-8')?>"><button type="submit">接入统一在线更新</button></form><?php endif;?></main></body></html>
'''
    return template.replace('@@OLDSHA@@',oldsha).replace('@@NEWSHA@@',newsha).replace('@@PAYLOAD@@',b64json(payload)).replace('@@HASHES@@',b64json(hashes))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',required=True);ap.add_argument('--production',required=True);ap.add_argument('--out',required=True);ap.add_argument('--candidate-commit',required=True);ap.add_argument('--candidate-tree',required=True);ap.add_argument('--production-commit',required=True);args=ap.parse_args()
    cand=Path(args.candidate).resolve();prod=Path(args.production).resolve();out=Path(args.out).resolve();shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
    target=collect(cand); source=collect(prod)
    if target.get('VERSION.txt',b'').strip()!=VERSION.encode(): raise SystemExit('candidate VERSION.txt mismatch')
    if source.get('VERSION.txt',b'').strip()!=SOURCE_VERSION.encode(): raise SystemExit('production VERSION.txt mismatch')
    ext=json.loads(target['browser-extension/manifest.json'].decode());extver=str(ext.get('version',''))
    if extver!='1.6.4': raise SystemExit('browser extension version drift')
    runtime_files={k:sha256_bytes(v) for k,v in target.items()}
    release_manifest={
      'project':PROJECT,'project_id':PROJECT_ID,'project_slug':'vf-start','version':VERSION,'release_type':'formal-release','deployable':True,
      'release_scope':'p01-app-unified-update','stage':'FINAL_CANDIDATE_BYTES','source_commit':args.candidate_commit,'source_tree':args.candidate_tree,
      'production_source_commit':args.production_commit,'source_version':SOURCE_VERSION,'schema_change':False,'schema_migrations':[],
      'schema_version':SCHEMA,'runtime_data_included':False,'seed_user_business_data_included':False,
      'platform':{'version':'1.1.0','api_version':'1'},
      'browser_extension':{'version':extver,'release_unit':'INDEPENDENT','included_as_separate_release_asset':False,'mechanical_version_bump':False},
      'update':{'project_id':PROJECT_ID,'component_id':COMPONENT_ID,'manifest_truth':'llhzx2018/core-updates/projects/P01.json','release_truth':'GitHub Release','asset_name':f'VF_Start_V{VERSION}_UPDATE.zip','supported_from':[SOURCE_VERSION],'backup_required':True,'rollback_supported':True},
      'runtime_hashed_file_count':len(runtime_files),'runtime_files':runtime_files
    }
    target_with=dict(target);target_with['release-manifest.json']=(json.dumps(release_manifest,ensure_ascii=False,indent=2)+'\n').encode()
    bridge=build_bridge(source['app/UpdateManager.php'],target['app/UpdateManager.php'],{
      'app/CoreUpdates/UpdateCore.php':target['app/CoreUpdates/UpdateCore.php'],
      'app/CoreUpdates/GitHubClient.php':target['app/CoreUpdates/GitHubClient.php'],
    })
    repair=build_repair(source,target_with,sha256_bytes(target['app/UpdateManager.php']))
    repair_name=f'repair-v{VERSION}.php'; bridge_name=f'P01_V{SOURCE_VERSION}_DISCOVERY_BRIDGE.php'
    (out/repair_name).write_text(repair,encoding='utf-8',newline='\n');(out/bridge_name).write_text(bridge,encoding='utf-8',newline='\n')
    deterministic_zip(out/f'VF_Start_V{VERSION}_FULL.zip',target_with)
    deterministic_zip(out/f'VF_Start_V{VERSION}_SOURCE.zip',target_with)
    rb=(out/repair_name).read_bytes();deterministic_zip(out/f'VF_Start_V{VERSION}_ATOMIC.zip',{repair_name:rb});deterministic_zip(out/f'VF_Start_V{VERSION}_UPDATE.zip',{repair_name:rb})
    notes=f'''# VF Start V{VERSION}\n\n本版本只完成 P01 APP 的统一在线更新体系接入。\n\n- Production 仍为 V{SOURCE_VERSION}，本 Release 不等于 Production 已升级。\n- 在线发现：core-updates。\n- 正式 UPDATE 资产：GitHub Release。\n- 完整性：Project / Component / Tag / Asset / bytes / SHA-256。\n- 升级执行：沿用 VF Start Atomic + Backup + Rollback。\n- Schema：{SCHEMA} → {SCHEMA}，无 Schema 变化。\n- Browser Extension：1.6.4，独立组件，本轮不升版。\n- V{SOURCE_VERSION} 首次迁入统一发现体系需要一次性 Discovery Bridge；Bridge 不改版本、Schema 或业务数据。\n'''
    (out/f'VF_Start_V{VERSION}_RELEASE_NOTES.md').write_text(notes,encoding='utf-8')
    formal={'schema':'vf-release-manifest/2.2','project_id':PROJECT_ID,'component_id':COMPONENT_ID,'project':PROJECT,'version':VERSION,'schema_version':SCHEMA,
            'source':{'repository':REPO,'candidate_commit':args.candidate_commit,'candidate_tree':args.candidate_tree,'production_commit':args.production_commit},
            'update':{'from_versions':[SOURCE_VERSION],'asset_name':f'VF_Start_V{VERSION}_UPDATE.zip','backup_required':True,'rollback_supported':True,'discovery_bridge':bridge_name},
            'browser_extension':{'version':'1.6.4','independent':True,'released_this_round':False},
            'gates':{'candidate_update_core':'PASS','formal_bytes':'PENDING_REVERSE_VERIFICATION','fresh_install':'PENDING','atomic_upgrade':'PENDING','rollback':'PENDING','privacy':'PENDING'}}
    (out/f'VF_Start_V{VERSION}_RELEASE_MANIFEST.json').write_text(json.dumps(formal,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    arts=[p for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt']
    (out/'SHA256SUMS.txt').write_text(''.join(f'{sha256_file(p)}  {p.name}\n' for p in arts),encoding='utf-8')
    print(json.dumps({'version':VERSION,'source_files':len(source),'target_files':len(target),'payload_files':len(target_with),'candidate_commit':args.candidate_commit,'candidate_tree':args.candidate_tree,'out':str(out)},indent=2))
if __name__=='__main__': main()
