<?php
declare(strict_types=1);
/**
 * R174 isolated owner site e2e. Actual published v0.1.5 FULL must have
 * been unpacked into an empty Runner temporary directory.
 * No Production, outside URL or private log values are ever persisted.
 */
if (PHP_SAPI !== 'cli' || posix_geteuid() === 0 ||
    getenv('GITHUB_ACTIONS') !== 'true' ||
    getenv('P08_R174_ISOLATED') !== 'YES' ||
    $argc !== 3 || !in_array($argv[1], ['seed','verify'], true)) {
    fwrite(STDERR, "P08_R174_DISPOSABLE_SITE_ONLY\n");exit(2);
}
$root=$argv[2];$real=realpath($root);
if (!$real || $real !== $root || is_link($root) ||
    !str_starts_with($root, (string)getenv('RUNNER_TEMP').'/p08-r174-site')) {
    fwrite(STDERR,"P08_R174_SITE_PATH_UNSAFE\n");exit(2);
}
function expect174(bool $ok,string $code):void {
    if (!$ok)throw new RuntimeException("P08_R174_TEST_".$code);
}
$old='75fdcab08f84e5bb7e4edb1a3f42098096907598';
$manifestHash='cda5fbe9523dbdb5d35d0a1ef5ea4e55e45d3ad19de1a82b259f7ed2edc1de46';
try {
if ($argv[1]==='seed') {
    expect174(!file_exists($root.'/.env') && is_file($root.'/FULL_MANIFEST.json'),'NOT_CLEAN_OLD_FULL');
    $indexed=json_decode((string)file_get_contents($root.'/FULL_MANIFEST.json'),true,32,JSON_THROW_ON_ERROR);
    expect174($indexed['source_sha']===$old && $indexed['target_version']==='0.1.5'
        && hash('sha256',(string)file_get_contents($root.'/FULL_MANIFEST.json'))===$manifestHash,
        'NOT_EXACT_OFFICIAL_015');
    $name=str_repeat('a',32).'.sqlite';
    expect174(file_put_contents($root.'/database/'.$name,'')===0,'SQLITE_CREATE_PROOF');
    $_SERVER['HTTPS']='on';$_SERVER['HTTP_HOST']='isolated-p08.test';
    require_once $root.'/src/Support/Autoload.php';
    require_once $root.'/vendor/autoload.php';
    $read=(string)getenv('P08_PRIVATE_READ_TOKEN');
    expect174(strlen($read)>=20,'PRIVATE_READ_CAPABILITY_MISSING');
    $payload=[
        'db_driver'=>'sqlite','db_database'=>$name,
        'site_name'=>'P08 isolated official update','owner_username'=>'r174_owner',
        'github_read_token'=>$read,'owner_email'=>'r174@isolated.test',
        'owner_password'=>'Synthetic-R174-Only-1234567!',
        'owner_confirm'=>'Synthetic-R174-Only-1234567!',
    ];
    $installer=new \VF\AdOps\Installation\OwnerWebInstaller(
        static fn(string $given):bool=>hash_equals((string)getenv('P08_PRIVATE_READ_TOKEN'),$given));
    $result=$installer->install($payload,$root);
    expect174(($result['status']??null)==='INSTALLED'
        && ($result['github_credential']??null)==='CONNECTED',
        'OWNER_OR_TOKEN_NOT_INSTALLED');
    expect174(is_link($root.'/current')
        && readlink($root.'/current')==='releases/'.$old,'OFFICIAL_OLD_POINTER_NOT_INSTALLED');
    expect174(hash_file('sha256',$root.'/current/FULL_MANIFEST.json')===$manifestHash,
        'OFFICIAL_INDEX_DRIFT');
    $installed=json_decode((string)file_get_contents($root.'/storage/app/private/adops/installation/installed.json'),true,16,JSON_THROW_ON_ERROR);
    $owner=(string)($installed['owner_id']??'');
    expect174($owner!=='' && $owner!=='0','OWNER_MISSING');
    $next=$root.'/storage/app/private/adops/owner-next-update';
    if(!is_dir($next))expect174(mkdir($next,0700,true),'NEXT_DIR_CREATE_FAILED');
    chmod($next,0700);
    $lock=$next.'/state.lock';
    if(!is_file($lock))expect174(file_put_contents($lock,'')===0,'NEXT_STATE_LOCK_FAILED');
    chmod($lock,0600);
    expect174(!is_file($next.'/status.json') && !is_file($next.'/intent.json'),
        'PREEXISTING_STATE_REFUSED');
    $intent=[
        'type'=>'P08_FUTURE_OWNER_INTENT_V1','id'=>str_repeat('a',32),
        'status'=>'NEEDS_RECOVERY','failure_phase'=>'PREPARE',
        'source_sha'=>$old,
        'target_sha'=>'12b04ba4da0dc226e30f7a68294de2d4fbda949b',
        'target_version'=>'0.1.6','owner_hash'=>hash('sha256',$owner),
    ];
    expect174(file_put_contents($next.'/intent.json',json_encode($intent,JSON_THROW_ON_ERROR)."\n")>0,
        'FAILED_PREPARE_FIXTURE_WRITE');
    chmod($next.'/intent.json',0600);
    echo "P08_R174_OFFICIAL_015_FULL_REAL_SQLITE_INSTALL_AND_FAILED_PREPARE=PASS\n";
    exit(0);
}
expect174(is_link($root.'/current') && readlink($root.'/current')==='releases/'.$old,
    'RESCUE_AUTOMATICALLY_CHANGED_POINTER');
$next=$root.'/storage/app/private/adops/owner-next-update';
$history=$next.'/history';
expect174(!is_file($next.'/intent.json')
    && is_dir($history)
    && is_file($history.'/r168-failed-'.str_repeat('a',32).'.json'),
    'FAILED_JOURNAL_NOT_ARCHIVED');
$record=json_decode((string)file_get_contents($next.'/status.json'),true,24,JSON_THROW_ON_ERROR);
expect174(($record['status']??null)==='PREPARED','ONLINE_PREPARE_NOT_VERIFIED');
expect174(hash_file('sha256',$root.'/current/FULL_MANIFEST.json')===$manifestHash,
    'SOURCE_CHANGED_DURING_PREPARE');
$private=$root.'/storage/app/private/adops/recovery';
expect174(is_dir($private) && count(array_diff(scandir($private),['.','..']))>0,
    'NATIVE_BACKUP_NOT_STAGED');
echo "P08_R174_REAL_OFFICIAL_ONLINE_FAILED_PREPARE_ARCHIVE_AND_NATIVE_BACKUP=PASS\n";
echo "P08_R174_CURRENT_POINTER_STILL_OFFICIAL_015=PASS\n";
echo "P08_R174_APPLY_NOT_RUN_REQUIRES_OWNER_CLICK=PASS\n";
} catch(Throwable $e) {
    $message=$e->getMessage();
    if(!preg_match('/\AP08_R174_[A-Z0-9_]{4,100}\z/D',$message))
        $message='P08_R174_SAFE_SITE_SMOKE_FAILURE';
    fwrite(STDERR,$message."\n");
    exit(1);
}
