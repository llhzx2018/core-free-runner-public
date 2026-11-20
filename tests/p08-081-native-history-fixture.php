<?php
declare(strict_types=1);
/**
 * P08 #81 3DB test-only historical fixture. NOT evidence of any human Owner
 * click, NOT production data, and NEVER a bypass of original v012 native PHP.
 * The actual installed stage/backup/pointer is obtained from official issued
 * FULL+Atomic packages in the same isolated test job.
 */
if (PHP_SAPI!=='cli' || getenv('GITHUB_ACTIONS')!=='true'
    || getenv('P08_ISOLATED_INSTALL_TEST')!=='YES'
    || !function_exists('posix_geteuid') || posix_geteuid()===0
    || count($argv)!==3) {
    throw new RuntimeException('P08_081_FIXTURE_FORBIDDEN');
}
[, $site, $mode]=$argv;
$home=(string)getenv('HOME');
if (!is_string($site)
    || !str_starts_with($site,$home.'/htdocs/adops-vf-081-')
    || !in_array($mode,['archive_v010','seed_v012_failed','duplicate_history'],true)
    || is_link($site)||realpath($site)!==$site
    || fileowner($site)!==posix_geteuid()
    || !is_dir($site.'/current')) {
    throw new RuntimeException('P08_081_FIXTURE_SITE_UNTRUSTED');
}
$expected= $mode==='archive_v010'
    ? 'ef78dcb21117c822e2756360280f2418f794704f'
    : 'dac7bc1d5410c077f32e522eb5740537f618ef9d';
if (readlink($site.'/current')!=='releases/'.$expected)
    throw new RuntimeException('P08_081_FIXTURE_SOURCE_UNVERIFIED');
$dir=$site.'/storage/app/private/adops/upgrade';
$stages=array_values(array_filter(scandir($dir)?:[],
    fn(string $n):bool=>preg_match('/^[a-f0-9]{32}$/D',$n)===1));
if (count($stages)!==1)throw new RuntimeException('P08_081_FIXTURE_STAGE_UNSAFE');
$stage=$stages[0];
$p=$dir.'/'.$stage.'/pointer-transaction.json';
$ptr=json_decode((string)file_get_contents($p),true,32,JSON_THROW_ON_ERROR);
if (($ptr['type']??null)!=='P08_POINTER_TRANSACTION_V1'
    || ($ptr['status']??null)!=='COMMITTED'
    || ($ptr['stage_id']??null)!==$stage
    || ($ptr['target_sha']??null)!==$expected
    || ($ptr['next']??null)!=='releases/'.$expected)
    throw new RuntimeException('P08_081_FIXTURE_REAL_POINTER_NOT_COMMITTED');

$write=static function(string $name,array $data):void {
    if (is_link($name)||file_exists($name))throw new RuntimeException('P08_081_FIXTURE_DUPLICATE_PATH');
    $f=fopen($name,'xb');
    if (!is_resource($f))throw new RuntimeException('P08_081_FIXTURE_CANNOT_CREATE');
    try {
        if (!chmod($name,0600)
            || fwrite($f,json_encode($data,JSON_THROW_ON_ERROR)."\n")===false
            || !fflush($f))
            throw new RuntimeException('P08_081_FIXTURE_WRITE_FAILED');
    }finally{fclose($f);}
};

if ($mode==='archive_v010') {
    require_once $site.'/current/vendor/autoload.php';
    $write($dir.'/owner-job.json',[
      'status'=>'SUCCEEDED','target_sha'=>$expected,'stage_id'=>$stage,
      'ci_provenance'=>'SYNTHETIC_V010_OWNER_JOB_PRIOR_GENERATION_NOT_BROWSER'
    ]);
    $result=(new \VF\AdOps\Upgrade\OwnerPreviousCycleArchive())->rotate($site);
    if (($result['status']??null)!=='PREVIOUS_CYCLE_ARCHIVED')
        throw new RuntimeException('P08_081_REAL_V010_ARCHIVE_NOT_SUCCESSFUL');
    echo "P08_081_REAL_ISSUED_V010_NATIVE_ARCHIVE=PASS\n";
    exit;
}
$history=$site.'/storage/app/private/adops/owner-next-update/history';
if ($mode==='seed_v012_failed') {
    if (is_dir($history)||!mkdir($history,0700))
        throw new RuntimeException('P08_081_EXPECT_FRESH_HISTORY');
    $jid=bin2hex(random_bytes(16));
    $failedId=bin2hex(random_bytes(16));
    $owner=hash('sha256','P08_081_SYNTHETIC_OWNER_NOT_REAL_OWNER');
    $prior=[
      'type'=>'P08_FUTURE_OWNER_INTENT_V1',
      'id'=>$jid,'status'=>'SUCCEEDED',
      'source_sha'=>'ef78dcb21117c822e2756360280f2418f794704f',
      'target_sha'=>$expected,
      'target_version'=>'0.1.12',
      'owner_hash'=>$owner,
      'ci_provenance'=>'SYNTHETIC_PRIOR_OWNER_SUCCESS_BOUND_TO_REAL_NATIVE_V012_STAGE'
    ];
    $state=[
      'type'=>'P08_FUTURE_OWNER_UPDATE_V1',
      'job_id'=>$jid,'status'=>'SUCCEEDED',
      'source_sha'=>'ef78dcb21117c822e2756360280f2418f794704f',
      'stage_id'=>$stage,'target_sha'=>$expected,'target_version'=>'0.1.12',
      'ci_provenance'=>'SYNTHETIC_PRIOR_OWNER_STATUS_NOT_REAL_BROWSER'
    ];
    $write($history.'/intent-'.$jid.'.json',$prior);
    $write($history.'/status-'.$jid.'.json',$state);
    $write($site.'/storage/app/private/adops/owner-next-update/intent.json',[
      'type'=>'P08_FUTURE_OWNER_INTENT_V1','id'=>$failedId,
      'status'=>'NEEDS_RECOVERY',
      'source_sha'=>$expected,'target_sha'=>'8b385fecd132a02ac79f5b67e670783e98997c3e',
      'target_version'=>'0.1.13',
      'owner_hash'=>$owner,'single_click_authorized'=>true,
      'failure_phase'=>'PREPARE',
      'failure_code'=>'P08_CYCLE_PREVIOUS_SUCCESS_NOT_PROVEN',
      'ci_provenance'=>'SYNTHETIC_FAILED_PREPARE_TEST_ONLY'
    ]);
    echo "P08_081_SYNTHETIC_HISTORY_BOUND_TO_GENUINE_ISSUED_V012_STAGE=PASS\n";
    exit;
}
$priorFiles=array_values(array_filter(scandir($history)?:[],
    fn(string $n):bool=>preg_match('/^intent-[a-f0-9]{32}\.json$/D',$n)===1));
if (count($priorFiles)!==1)
    throw new RuntimeException('P08_081_DUPLICATE_TEST_BAD_BASELINE');
$old=json_decode((string)file_get_contents($history.'/'.$priorFiles[0]),true);
$oldState=$history.'/status-'.substr($priorFiles[0],7);
$id=bin2hex(random_bytes(16));
$old['id']=$id;
$old['ci_provenance']='SYNTHETIC_AMBIGUOUS_SECOND_SUCCESS_TEST_ONLY';
$st=json_decode((string)file_get_contents($oldState),true);
$st['job_id']=$id;
$write($history.'/intent-'.$id.'.json',$old);
$write($history.'/status-'.$id.'.json',$st);
echo "P08_081_NEGATIVE_DUPLICATE_HISTORY_FIXTURE_READY=PASS\n";
