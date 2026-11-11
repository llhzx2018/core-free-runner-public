<?php
declare(strict_types=1);
/**
 * Temporary public-safe harness: all source is loaded via transient exact
 * private checkouts; only synthetic SQLite + extracted disposable FULL.
 * No Production site, customer data, secret or distributed artifact.
 */
if (PHP_SAPI !== 'cli' || getenv('GITHUB_ACTIONS') !== 'true'
    || $argc !== 7) {
    throw new RuntimeException('P08_R33_HARNESS_CLI_AND_ARGS_REQUIRED');
}
[$script,$inputRoot,$bridgeZip,$atomicZip,$zipHash,$targetSha,$bridgeSha] = $argv;
$root=realpath($inputRoot);
$temp=realpath((string)getenv('RUNNER_TEMP'));
if ($root===false || $temp===false || !str_starts_with($root,$temp.'/')
    || preg_match('/^[a-f0-9]{40}$/D',$targetSha)!==1
    || preg_match('/^[a-f0-9]{40}$/D',$bridgeSha)!==1
    || preg_match('/^[a-f0-9]{64}$/D',$zipHash)!==1
    || !is_file($bridgeZip) || !is_file($atomicZip)) {
    throw new RuntimeException('P08_R33_UNSAFE_TEST_ROOT_OR_SOURCE');
}
foreach ([
    'Installation/SetupGuard.php',
] as $p) require_once getcwd().'/private-bridge/src/'.$p;
foreach ([
    'Recovery/MaintenanceGate.php',
    'Recovery/DatabaseSnapshot.php',
    'Recovery/PrivatePayloadSnapshot.php',
    'Recovery/ConsistentSiteSnapshot.php',
    'Upgrade/AtomicPackageStage.php',
    'Upgrade/AtomicUpgradeArm.php',
    'Upgrade/AtomicReleaseMaterializer.php',
    'Upgrade/AtomicReleasePointer.php',
] as $p) require_once getcwd().'/private-bridge/src/'.$p;

$release=$root.'/releases/'.$bridgeSha;
if (!mkdir($release,0700,true)) throw new RuntimeException('P08_R33_RELEASE_DIR_CREATE_FAILED');
$zip=new ZipArchive();
if ($zip->open($bridgeZip,ZipArchive::RDONLY)!==true
    || !$zip->extractTo($release)) throw new RuntimeException('P08_R33_BRIDGE_EXTRACT_FAILED');
$zip->close();
\VF\AdOps\Installation\SetupGuard::package($release);
if (!symlink('releases/'.$bridgeSha,$root.'/current')) {
    throw new RuntimeException('P08_R33_CURRENT_LINK_FAILED');
}
// R29 has already replaced the flat public/CLI gateway; root FULL is obsolete.
file_put_contents($root.'/FULL_MANIFEST.json',"\nOBSOLETE_ROOT_MANIFEST",FILE_APPEND);
try {
    \VF\AdOps\Installation\SetupGuard::package($root);
    throw new RuntimeException('P08_R33_FLAT_ROOT_UNEXPECTEDLY_VALID');
} catch (RuntimeException $e) {
    if ($e->getMessage()==='P08_R33_FLAT_ROOT_UNEXPECTEDLY_VALID') throw $e;
}
echo "P08_R33_VERSIONED_SOURCE_ONLY_NOT_OBSOLETE_FLAT=PASS\n";

$dbfile=$root.'/database/'.str_repeat('a',32).'.sqlite';
$sqlite=new SQLite3($dbfile,SQLITE3_OPEN_READWRITE|SQLITE3_OPEN_CREATE);
$sqlite->exec('CREATE TABLE p08_atomic_owner (id INTEGER PRIMARY KEY, value TEXT NOT NULL)');
$sqlite->exec("INSERT INTO p08_atomic_owner(value) VALUES ('OWNER_PRESERVED')");
$sqlite->close();
$env="APP_NAME=\"VF AdOps Isolated\"\nAPP_KEY=\"base64:ISOLATED-NOT-A-REAL-SECRET\"\nDB_CONNECTION=\"sqlite\"\nDB_DATABASE=\"".$dbfile."\"\n";
file_put_contents($root.'/.env',$env);
chmod($root.'/.env',0600);
$installed=$root.'/storage/app/private/adops/installation/installed.json';
$markerHash=hash_file('sha256',$installed);
$envHash=hash_file('sha256',$root.'/.env');
$sqliteHash=hash_file('sha256',$dbfile);

$svc=new \VF\AdOps\Upgrade\AtomicPackageStage();
$stage=$svc->prepare($root,$atomicZip,$zipHash,$targetSha);
if (($stage['source_version']??'')!=='0.1.0'
    || ($stage['target_version']??'')!=='0.1.1') {
    throw new RuntimeException('P08_R33_VERSIONED_STAGE_WRONG_SOURCE');
}
echo "P08_R33_REAL_VERSIONED_STAGE_PHP=PASS\n";
$backup=(new \VF\AdOps\Recovery\ConsistentSiteSnapshot())->create($root,
    ['driver'=>'sqlite','database'=>$dbfile]);
if (($backup['driver']??'')!=='sqlite'
    || !is_file($root.'/storage/app/private/adops/recovery/'.$backup['database_id'].'/files-manifest.json')) {
    throw new RuntimeException('P08_R33_NATIVE_SQLITE_BACKUP_MISSING');
}
echo "P08_R33_REAL_SQLITE_AND_OWNER_FILES_BACKUP=PASS\n";
$arm=(new \VF\AdOps\Upgrade\AtomicUpgradeArm())->arm(
    $root,$stage['id'],$backup['database_id'],$zipHash,$targetSha);
if (($arm['status']??'')!=='PREPARED_NOT_APPLIED') {
    throw new RuntimeException('P08_R33_REAL_BRIDGE_ARM_FAILED');
}
echo "P08_R33_REAL_EXTRACTED_ARM=PASS\n";
$material=(new \VF\AdOps\Upgrade\AtomicReleaseMaterializer())->prepare(
    $root,$stage['id'],$zipHash,$targetSha);
if (($material['status']??'')!=='MATERIALIZED_NOT_ACTIVATED') {
    throw new RuntimeException('P08_R33_REAL_MATERIALIZATION_FAILED');
}
$switched=(new \VF\AdOps\Upgrade\AtomicReleasePointer())->switch(
    $root,$stage['id'],$zipHash,$targetSha);
if (($switched['status']??'')!=='COMMITTED') {
    throw new RuntimeException('P08_R33_REAL_ATOMIC_SWITCH_FAILED');
}
$active=(new \VF\AdOps\Upgrade\AtomicReleasePointer())->verifyActiveRelease($root,$targetSha);
if (($active['status']??'')!=='VERIFIED_ACTIVE_FULL'
    || ($active['target_version']??'')!=='0.1.1') {
    throw new RuntimeException('P08_R33_ACTIVE_FULL_FAILED');
}
if (hash_file('sha256',$root.'/.env')!==$envHash
    || hash_file('sha256',$installed)!==$markerHash
    || hash_file('sha256',$dbfile)!==$sqliteHash) {
    throw new RuntimeException('P08_R33_OWNER_DATA_CHANGED');
}
$db=new SQLite3($dbfile,SQLITE3_OPEN_READONLY);
$row=$db->querySingle('SELECT value FROM p08_atomic_owner WHERE id=1');
$db->close();
if ($row!=='OWNER_PRESERVED')throw new RuntimeException('P08_R33_SQLITE_OWNER_ROW_LOST');
echo "P08_R33_REAL_FULL_TO_ATOMIC_POINTER_AND_OWNER_PRESERVED=PASS\n";
echo "P08_R33_CLOUDPANEL_STOP_DRAIN_OPCACHE_BROWSER=NOT_PROVEN\n";
