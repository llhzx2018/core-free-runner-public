<?php
declare(strict_types=1);

/**
 * Public-safe, never-shipped R131 fault worker:
 * genuine issued v0.1.15 native pointer + candidate image/token allowlist.
 * ONLY on disposable GitHub Actions runner and exact 3DB test site prefix.
 */
if (PHP_SAPI!=='cli' || !function_exists('posix_geteuid')
    || posix_geteuid()===0 || count($argv)!==6
    || getenv('GITHUB_ACTIONS')!=='true'
    || getenv('P08_R131_DISPOSABLE')!=='YES'
    || getenv('P08_ISOLATED_INSTALL_TEST')!=='YES'
    || getenv('CI')!=='true') {
    fwrite(STDERR,"P08_R131_TEST_DISPOSABLE_ONLY\n");exit(3);
}
[$script,$mode,$site,$full,$update,$target]=$argv;
$old='369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e';
$tmp=realpath((string)getenv('RUNNER_TEMP'));
if(!in_array($mode,['kill','recover'],true)
    || !is_string($tmp) || $tmp!=='/home/runner/work/_temp'
    || realpath($site)!==$site || is_link($site)
    || fileowner($site)!==posix_geteuid()
    || !preg_match('~^'.preg_quote($tmp,'~').'/p08-r129-real-issued-r131-v016-(sqlite|mysql|mariadb)$~D',$site)
    || !preg_match('/^[a-f0-9]{40}$/D',$target)
    || !is_file($full.'/FULL_MANIFEST.json')
    || is_link($full)
    || !is_file($update) || is_link($update)
    || readlink($site.'/current')!=='releases/'.$old && $mode==='kill') {
    fwrite(STDERR,"P08_R131_TEST_PATH_OR_SOURCE_UNSAFE\n");exit(3);
}
$manifest=json_decode((string)file_get_contents($full.'/FULL_MANIFEST.json'),true,64,JSON_THROW_ON_ERROR);
if(($manifest['source_sha']??null)!==$target
    || ($manifest['target_version']??null)!=='0.1.16'
    || ($manifest['repository']??null)!=='llhzx2018/vf-adops') {
    fwrite(STDERR,"P08_R131_TEST_TARGET_UNTRUSTED\n");exit(3);
}
try{
    foreach(['src/Recovery/PrivatePayloadSnapshot.php','src/Upgrade/AtomicUpgradeArm.php',
             'src/Upgrade/AtomicReleaseMaterializer.php'] as $file){
        $path=$full.'/'.$file;
        if(!is_file($path)||is_link($path))throw new RuntimeException('R131_TEST_OVERLAY_INVALID');
        require_once $path;
    }
    require_once $site.'/releases/'.$old.'/vendor/autoload.php';
    $private=$site.'/storage/app/private/adops';
    $media=$private.'/landing-assets/00000000-0000-4000-8000-000000000001.png';
    $token=$private.'/upgrade/github-read-token';
    if(!is_file($media)||!is_file($token)||is_link($media)||is_link($token)){
        throw new RuntimeException('R131_TEST_NONEMPTY_MEDIA_TOKEN_REQUIRED');
    }
    if($mode==='kill'){
        $db=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($site);
        $archiveSha=(string)hash_file('sha256',$update);
        $staged=(new \VF\AdOps\Upgrade\AtomicPackageStage())
           ->prepare($site,$update,$archiveSha,$target);
        if(($staged['source_version']??null)!=='0.1.15'
            || ($staged['target_version']??null)!=='0.1.16'
            || ($staged['target_sha']??null)!==$target){
            throw new RuntimeException('R131_TEST_PREPARE_NOT_ORIGINAL_V015');
        }
        $snapshot=(new \VF\AdOps\Recovery\ConsistentSiteSnapshot())->create($site,$db);
        $armed=(new \VF\AdOps\Upgrade\AtomicUpgradeArm())->arm(
            $site,$staged['id'],$snapshot['database_id'],$archiveSha,$target);
        if(($armed['status']??null)!=='PREPARED_NOT_APPLIED'){
            throw new RuntimeException('R131_TEST_BACKUP_NOT_ARMED');
        }
        $new=(new \VF\AdOps\Upgrade\AtomicReleaseMaterializer())->prepare(
            $site,$staged['id'],$archiveSha,$target);
        if(($new['status']??null)!=='MATERIALIZED_NOT_ACTIVATED'){
            throw new RuntimeException('R131_TEST_NEW_RELEASE_NOT_MATERIALIZED');
        }
        (new \VF\AdOps\Upgrade\AtomicReleaseAssets())->prepare($site,$target);
        $fresh=static function(string $root,string $id,string $zip,string $sha,mixed $gate):void{
            (new \VF\AdOps\Upgrade\FreshOwnerUpgradeBackup())->refresh($root,$id,$zip,$sha,$gate);
        };
        // Original immutable R131IsolatedFault requires explicit real kill
        // after pointer NEW but BEFORE durable COMMITTED journal.
        (new \VF\AdOps\Upgrade\AtomicReleasePointer())->switch(
            $site,$staged['id'],$archiveSha,$target,'r131_sigkill_after_swap',$fresh
        );
        throw new RuntimeException('R131_TEST_REAL_KILL_NOT_OBSERVED');
    }
    $marker=$private.'/maintenance/maintenance.json';
    $files=glob($private.'/upgrade/*/pointer-transaction.json') ?: [];
    if(count($files)!==1 || !is_file($marker)
        || readlink($site.'/current')!=='releases/'.$target){
        throw new RuntimeException('R131_TEST_DURABLE_INTERRUPTED_STATE_MISSING');
    }
    $stageId=basename(dirname($files[0]));
    $j=json_decode((string)file_get_contents($files[0]),true,64,JSON_THROW_ON_ERROR);
    if(!preg_match('/^[a-f0-9]{32}$/D',$stageId)
        || ($j['status']??null)!=='PREPARED'
        || ($j['previous']??null)!=='releases/'.$old
        || ($j['next']??null)!=='releases/'.$target){
        throw new RuntimeException('R131_TEST_JOURNAL_NOT_PREPARED');
    }
    $result=(new \VF\AdOps\Upgrade\AtomicReleasePointer())->recover($site,$stageId);
    if(($result['status']??null)!=='ROLLED_BACK_INTERRUPTED'
        || ($result['current']??null)!=='releases/'.$old
        || readlink($site.'/current')!=='releases/'.$old
        || file_exists($marker)){
        throw new RuntimeException('R131_TEST_INDEPENDENT_POINTER_ROLLBACK_FAILED');
    }
    echo "P08_V016_R131_INDEPENDENT_POINTER_ROLLBACK=PASS\n";

    $snapshots=glob($private.'/recovery/*/files-manifest.json')?:[];
    $homeInfo=posix_getpwuid(posix_geteuid());
    $home=is_array($homeInfo)?($homeInfo['dir']??''):'';
    if(!is_string($home)||is_link($home)||realpath($home)!==$home){
        throw new RuntimeException('R131_TEST_EXTERNAL_HOME_UNTRUSTED');
    }
    $stageRoot=$home.'/.p08-v016-legacy-r131-'.substr(hash('sha256',$site),0,16);
    if(!is_dir($stageRoot)&&!mkdir($stageRoot,0700,false)){
        throw new RuntimeException('R131_TEST_EXTERNAL_STAGE_DIR_UNAVAILABLE');
    }
    if(is_link($stageRoot)||realpath($stageRoot)!==$stageRoot
        || (fileperms($stageRoot)&0077)!==0){
        throw new RuntimeException('R131_TEST_EXTERNAL_STAGE_DIR_UNSAFE');
    }
    $count=0;
    $usedId='';
    foreach($snapshots as $file){
        $id=basename(dirname($file));
        $record=json_decode((string)file_get_contents($file),true,64,JSON_THROW_ON_ERROR);
        $entries=[];
        foreach(($record['files']??[]) as $item){
            if(is_array($item) && is_string($item['path']??null)){
                $entries[$item['path']]=$item;
            }
        }
        $key='private/landing-assets/00000000-0000-4000-8000-000000000001.png';
        if(!isset($entries[$key],$entries['config/github-read-token']))continue;
        if(($entries[$key]['sha256']??null)!==hash_file('sha256',$media)
            || ($entries['config/github-read-token']['sha256']??null)!==hash_file('sha256',$token)){
            throw new RuntimeException('R131_TEST_IMAGE_TOKEN_MISSING_OR_CHANGED');
        }
        $destination=$stageRoot.'/stage-'.$id;
        $verified=(new \VF\AdOps\Recovery\PrivatePayloadSnapshot())
            ->verifyAndStage($site,$id,$destination);
        if(($verified['status']??null)!=='STAGED_NOT_APPLIED'
            || hash_file('sha256',$destination.'/'.$key)!==hash_file('sha256',$media)
            || hash_file('sha256',$destination.'/config/github-read-token')
                !==hash_file('sha256',$token)){
            throw new RuntimeException('R131_TEST_INDEPENDENT_MEDIA_STAGE_FAILED');
        }
        $count++;
        $usedId=$id;
    }
    if($count<2 || $usedId===''){
        throw new RuntimeException('R131_TEST_INITIAL_AND_FRESH_SNAPSHOTS_REQUIRED');
    }
    echo "P08_V016_R131_TWO_NATIVE_MEDIA_TOKEN_BACKUPS_AND_RESTORES=PASS\n";

    $cfg=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($site);
    if($cfg['driver']==='sqlite'){
        $cfg['database']=$site.'/database/'.str_repeat('b',32).'.sqlite';
    }else{
        $cfg['database']='p08_ci_016_fault_restore';
    }
    (new \VF\AdOps\Recovery\DatabaseSnapshot())->restoreToEmpty($site,$usedId,$cfg);
    $real=(new \VF\AdOps\Upgrade\InstalledDatabaseConfig())->read($site);
    $opts=[\PDO::ATTR_ERRMODE=>\PDO::ERRMODE_EXCEPTION];
    $connection=static function(array $d)use($opts):\PDO {
        if($d['driver']==='sqlite'){
            return new \PDO('sqlite:'.$d['database'],null,null,$opts);
        }
        return new \PDO('mysql:host='.$d['host'].';port='.$d['port'].';dbname='
            .$d['database'].';charset=utf8mb4',$d['username'],$d['password'],$opts);
    };
    $live=$connection($real);
    $restored=$connection($cfg);
    foreach(['users','landing_pages','landing_revisions'] as $table){
        $count1=(int)$live->query('SELECT COUNT(*) FROM '.$table)->fetchColumn();
        $count2=(int)$restored->query('SELECT COUNT(*) FROM '.$table)->fetchColumn();
        if($count1!==$count2 || ($table==='users'&&$count1!==1)){
            throw new RuntimeException('R131_TEST_NATIVE_DB_RESTORE_ROW_PARITY_FAILED');
        }
    }
    if(readlink($site.'/current')!=='releases/'.$old || !is_file($media)||!is_file($token)){
        throw new RuntimeException('R131_TEST_ORIGINAL_SITE_CHANGED_BY_RECOVERY');
    }
    echo "P08_V016_R131_NATIVE_DB_INDEPENDENT_RESTORE_ROW_PARITY=PASS\n";
    echo "P08_V016_R131_REAL_SIGKILL_POST_SWAP_THREE_DB_RECOVERY=PASS\n";
    exit(0);
}catch(\Throwable $e){
    $s=$e->getMessage();
    if(!preg_match('/^[A-Z][A-Z0-9_]{5,120}$/D',$s)){
        $s='R131_TEST_UNVERIFIED';
    }
    fwrite(STDERR,$s."\n");
    exit(2);
}
