<?php
declare(strict_types=1);
/**
 * Disposable CI historical-stage witness: every stage and backup MUST have
 * actually committed using official issued ZIPs and original PHP primitives.
 * The test-only owner-job witness IS NOT a real Owner browser click; it is
 * labeled as such and cannot be used outside the isolated Runner site.
 * Real old-v0.1.12 Owner HTTPS click remains SQLite-only in this lane;
 * SQL native historic predecessor steps use only original committed ZIPs,
 * receipts, backups and explicitly labeled synthetic prior job witnesses.
 */
if (PHP_SAPI !== 'cli' || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('P08_ISOLATED_INSTALL_TEST') !== 'YES'
    || count($argv) !== 4
    || !function_exists('posix_geteuid') || posix_geteuid() === 0) {
    throw new RuntimeException('P08_607B_TEST_ONLY');
}
[, $site, $expected, $mode] = $argv;
$tmp = (string) getenv('RUNNER_TEMP');
if (!in_array($mode, ['archive_v010', 'archive_v012', 'witness_v012', 'witness_v013'], true)
    || !preg_match('/^[a-f0-9]{40}$/D', $expected)
    || $expected !== match ($mode) {
        'archive_v010' => 'ef78dcb21117c822e2756360280f2418f794704f',
        'archive_v012','witness_v012' => 'dac7bc1d5410c077f32e522eb5740537f618ef9d',
        'witness_v013' => '8b385fecd132a02ac79f5b67e670783e98997c3e',
    }
    || !in_array($site, array_map(
        fn(string $engine):string=>$tmp.'/p08-r129-real-issued-r131-r155-'.$engine.'-chain',
        ['sqlite','mysql','mariadb']),true)
    || realpath($site) !== $site || is_link($site)
    || fileowner($site) !== posix_geteuid()
    || readlink($site.'/current') !== 'releases/'.$expected) {
    throw new RuntimeException('P08_607B_TEST_SOURCE_IDENTITY');
}
require_once $site.'/current/vendor/autoload.php';
$id=(new \VF\AdOps\Upgrade\OwnerNextReleaseGateway())->installed($site);
if (($id['source_sha'] ?? null) !== $expected
    || ($id['version'] ?? null) !== match ($mode) {
        'archive_v010'=>'0.1.10',
        'archive_v012','witness_v012'=>'0.1.12',
        'witness_v013'=>'0.1.13',
    }) {
    throw new RuntimeException('P08_607B_REAL_INSTALLED_MANIFEST_REQUIRED');
}
$dir=$site.'/storage/app/private/adops/upgrade';
$all=array_values(array_filter(scandir($dir) ?: [],
    fn(string $s):bool=>preg_match('/^[a-f0-9]{32}$/D',$s)===1));
if (count($all)!==1) {
    throw new RuntimeException('P08_607B_PREVIOUS_STAGE_COUNT_UNSAFE');
}
$stageId=$all[0];
$p=$dir.'/'.$stageId.'/pointer-transaction.json';
if (is_link($p) || !is_file($p) || filesize($p)>8192) {
    throw new RuntimeException('P08_607B_STAGE_RECEIPT_MISSING');
}
$x=json_decode((string)file_get_contents($p),true,32,JSON_THROW_ON_ERROR);
if (($x['type']??null)!=='P08_POINTER_TRANSACTION_V1'
    || ($x['status']??null)!=='COMMITTED'
    || ($x['stage_id']??null)!==$stageId
    || ($x['target_sha']??null)!==$expected
    || ($x['next']??null)!=='releases/'.$expected) {
    throw new RuntimeException('P08_607B_PREVIOUS_POINTER_UNTRUSTED');
}
$job=$dir.'/owner-job.json';
if (file_exists($job)||is_link($job)) {
    throw new RuntimeException('P08_607B_PREVIOUS_JOB_EXISTS');
}
$fixture=[
    'status'=>'SUCCEEDED',
    'target_sha'=>$expected,
    'stage_id'=>$stageId,
    'ci_provenance'=>'SYNTHETIC_PREVIOUS_OWNER_JOB_WITNESS_NOT_REAL_BROWSER',
];
$raw=json_encode($fixture,JSON_THROW_ON_ERROR)."\n";
$f=@fopen($job,'xb');
if (!is_resource($f))throw new RuntimeException('P08_607B_JOB_CREATE_FAILED');
try{
    if (!chmod($job,0600)||fwrite($f,$raw)!==strlen($raw)||!fflush($f))
        throw new RuntimeException('P08_607B_JOB_WRITE_FAILED');
}finally{fclose($f);}
if (in_array($mode,['archive_v010','archive_v012'],true)) {
    // This is the exact ORIGINAL shipped v010 production class, not a
    // simulated or relaxed archive. It independently verifies stage seal,
    // native backup, committed pointer and credential before rotating.
    $result=(new \VF\AdOps\Upgrade\OwnerPreviousCycleArchive())->rotate($site);
    if (($result['status']??null)!=='PREVIOUS_CYCLE_ARCHIVED'
        || ($result['previous_stage_id']??null)!==$stageId
        || count(array_filter(scandir($dir) ?: [],
            fn(string $s):bool=>preg_match('/^[a-f0-9]{32}$/D',$s)===1))!==0) {
        throw new RuntimeException('P08_607B_V010_ARCHIVE_FAILED');
    }
    echo "P08_607B_ISSUED_".($mode==='archive_v010'?'V010':'V012')."_NATIVE_BACKUP_STAGE_ARCHIVE=PASS\n";
} else {
    echo "P08_607B_ISSUED_".($mode==='witness_v012'?'V012':'V013')."_COMMITTED_NATIVE_STAGE_WITNESS_TEST_ONLY=PASS\n";
}
