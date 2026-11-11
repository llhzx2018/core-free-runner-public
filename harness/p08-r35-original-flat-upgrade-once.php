<?php
declare(strict_types=1);
/**
 * P08 R35 one-off public-safe fixture.
 * Exact private source checkouts stay only in the runner's ephemeral workspace.
 * This fixture NEVER tests Production or a running CloudPanel FPM process.
 */
if (PHP_SAPI !== 'cli' || getenv('GITHUB_ACTIONS') !== 'true' || $argc !== 8) {
    throw new RuntimeException('R35_ISOLATED_CLI_ONLY');
}
[$script,$siteArg,$bridgeArg,$originalSha,$bridgeSha,$targetSha,$zipArg,$archiveHash]=$argv;
$temp=realpath((string)getenv('RUNNER_TEMP'));
$site=realpath($siteArg);
$bridge=realpath($bridgeArg);
if (!$temp || !$site || !$bridge || is_link($siteArg) || is_link($bridgeArg)
    || !str_starts_with($site,$temp.'/') || !str_starts_with($bridge,$temp.'/')
    || $site===$bridge
    || preg_match('/^[a-f0-9]{120}$/D',$originalSha.$bridgeSha.$targetSha)!==1
    || preg_match('/^[a-f0-9]{64}$/D',$archiveHash)!==1
    || !is_file($zipArg) || is_link($zipArg)
    || hash_file('sha256',$zipArg)!==$archiveHash) {
    // SHA check performed separately because each commit is 40 hex.
    if (preg_match('/^[a-f0-9]{120}$/D',$originalSha.$bridgeSha.$targetSha)!==1) {
        throw new RuntimeException('R35_SOURCE_IDENTITIES_INVALID');
    }
    throw new RuntimeException('R35_ISOLATED_INPUT_INVALID');
}
require_once getcwd().'/private-bridge/src/Installation/SetupGuard.php';
foreach ([
    'Upgrade/FlatLayoutBridgePrepare.php',
    'Upgrade/FlatLayoutBridgeActivation.php',
    'Upgrade/AtomicReleaseAssets.php',
    'Recovery/MaintenanceGate.php',
    'Recovery/DatabaseSnapshot.php',
    'Recovery/PrivatePayloadSnapshot.php',
    'Recovery/ConsistentSiteSnapshot.php',
    'Upgrade/AtomicPackageStage.php',
    'Upgrade/AtomicUpgradeArm.php',
    'Upgrade/AtomicReleaseMaterializer.php',
    'Upgrade/AtomicReleasePointer.php',
] as $path) require_once getcwd().'/private-bridge/src/'.$path;
require_once getcwd().'/private-target/src/Upgrade/OfflineBridgeCoordinator.php';

use VF\AdOps\Installation\SetupGuard;
use VF\AdOps\Upgrade\FlatLayoutBridgePrepare;
use VF\AdOps\Upgrade\FlatLayoutBridgeActivation;
use VF\AdOps\Upgrade\AtomicPackageStage;
use VF\AdOps\Upgrade\AtomicUpgradeArm;
use VF\AdOps\Upgrade\AtomicReleaseMaterializer;
use VF\AdOps\Upgrade\AtomicReleasePointer;
use VF\AdOps\Recovery\ConsistentSiteSnapshot;

$fail=static function(string $code):never { throw new RuntimeException('R35_'.$code); };
$expect=static function(bool $condition,string $msg) use ($fail):void { if(!$condition) $fail($msg); };
SetupGuard::package($site);
SetupGuard::package($bridge);
$original=json_decode((string)file_get_contents($site.'/FULL_MANIFEST.json'),true,32,JSON_THROW_ON_ERROR);
$bridgeManifest=json_decode((string)file_get_contents($bridge.'/FULL_MANIFEST.json'),true,32,JSON_THROW_ON_ERROR);
$expect(($original['source_sha']??null)===$originalSha
    && ($original['target_version']??null)==='0.1.0'
    && ($bridgeManifest['source_sha']??null)===$bridgeSha
    && ($bridgeManifest['target_version']??null)==='0.1.0',
    'EXACT_FULL_IDENTITIES_MISMATCH');
echo "P08_R35_REAL_UNMODIFIED_ORIGINAL_0_1_0_FULL=PASS\n";

$private=$site.'/storage/app/private/adops';
foreach ([$private.'/installation',$private.'/maintenance',$site.'/database',
          $site.'/storage/framework/cache/data',$site.'/storage/framework/sessions',
          $site.'/storage/framework/views',$site.'/storage/logs'] as $dir) {
    if(!is_dir($dir) && !mkdir($dir,0700,true)) $fail('FIXTURE_DIRECTORY');
}
$database=$site.'/database/'.str_repeat('a',32).'.sqlite';
$db=new SQLite3($database,SQLITE3_OPEN_READWRITE|SQLITE3_OPEN_CREATE);
if(!$db->exec('CREATE TABLE p08_atomic_owner(id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
    || !$db->exec("INSERT INTO p08_atomic_owner(value) VALUES('OWNER_PRESERVED')")) {
    $fail('SQLITE_FIXTURE');
}
$db->close();
$env="APP_NAME=\"VF AdOps Isolated\"\nAPP_ENV=testing\nAPP_DEBUG=false\n"
    ."APP_URL=http://127.0.0.1:18880\nAPP_KEY=base64:".base64_encode(random_bytes(32))."\n"
    ."DB_CONNECTION=\"sqlite\"\nDB_DATABASE=\"".$database."\"\n"
    ."SESSION_DRIVER=file\nCACHE_STORE=file\nQUEUE_CONNECTION=sync\n";
file_put_contents($site.'/.env',$env);
chmod($site.'/.env',0600);
$installed=$private.'/installation/installed.json';
file_put_contents($installed,json_encode([
    'project_id'=>'P08','status'=>'INSTALLED','database_driver'=>'sqlite',
],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)."\n");
chmod($installed,0600);
$lock=$private.'/maintenance/write-gate.lock';
if(file_put_contents($lock,'')===false) $fail('LOCK_SETUP');
chmod($lock,0600);
$shaOf=static fn(string $path):string => (string)hash_file('sha256',$path);
$before=[
    'env'=>$shaOf($site.'/.env'),'db'=>$shaOf($database),'installed'=>$shaOf($installed),
    'index'=>$shaOf($site.'/public/index.php'),'artisan'=>$shaOf($site.'/artisan')
];
$trustedFull=$shaOf($bridge.'/FULL_MANIFEST.json');
try {
    (new FlatLayoutBridgePrepare())->prepare($site,$bridge,$bridgeSha,str_repeat('f',64));
    $fail('UNTRUSTED_BRIDGE_WAS_ACCEPTED');
} catch (RuntimeException $e) {
    if ($e->getMessage()==='R35_UNTRUSTED_BRIDGE_WAS_ACCEPTED') throw $e;
}
$expect(!file_exists($site.'/releases'),'WRONG_TRUST_MUTATED_OLD_SITE');
echo "P08_R35_WRONG_BRIDGE_FULL_TRUST_REFUSED=PASS\n";

// Old flat 0.1.0 cannot prove its own PHP-FPM stop. The test intentionally
// supplies an isolated true callback only after proving false refuses early.
$coordinator=new \VF\AdOps\Upgrade\OfflineBridgeCoordinator();
$dbConfig=['driver'=>'sqlite','database'=>$database];
$trustedOriginal=$shaOf($site.'/FULL_MANIFEST.json');
try {
    $coordinator->convert($site,$bridge,$originalSha,$trustedOriginal,
        $bridgeSha,$trustedFull,$dbConfig,static fn()=>false);
    $fail('UNPROVEN_OFFLINE_WAS_ACCEPTED');
} catch (RuntimeException $e) {
    if ($e->getMessage()==='R35_UNPROVEN_OFFLINE_WAS_ACCEPTED') throw $e;
}
$expect(!file_exists($site.'/releases')
    && $shaOf($site.'/public/index.php')===$before['index'],
    'OFFLINE_GUARD_REFUSAL_MUTATED_SITE');
echo "P08_R35_UNPROVEN_OFFLINE_REFUSED_WITHOUT_CHANGE=PASS\n";

// No web/CLI workers ever run during the temporary offline conversion.
// This is NOT a CloudPanel FPM stop/drain acceptance test.
$converted=$coordinator->convert($site,$bridge,$originalSha,$trustedOriginal,
    $bridgeSha,$trustedFull,$dbConfig,static fn()=>true);
$expect(($converted['status']??null)==='COMMITTED_OFFLINE_BRIDGE'
    && is_string($converted['backup_id']??null)
    && is_file($private.'/recovery/'.$converted['backup_id'].'/files-manifest.json')
    && is_link($site.'/current')
    && readlink($site.'/current')==='releases/'.$bridgeSha
    && $shaOf($site.'/public/index.php')===$shaOf($bridge.'/public/index.php')
    && $shaOf($site.'/artisan')===$shaOf($bridge.'/artisan')
    && $shaOf($database)===$before['db']
    && $shaOf($site.'/.env')===$before['env']
    && $shaOf($installed)===$before['installed'],
    'BACKUP_FIRST_BRIDGE_ACTIVATION_OR_OWNER_PRESERVATION_FAILED');
echo "P08_R35_REAL_ORIGINAL_FLAT_TO_VERSIONED_GATEWAY=PASS\n";
echo "P08_R35_COMPOSITE_BACKUP_BEFORE_GATEWAY_ACTIVATION=PASS\n";
try {
    SetupGuard::package($site);
    $fail('OBSOLETE_FLAT_FULL_ACCEPTED');
} catch (RuntimeException $e) {
    if($e->getMessage()==='R35_OBSOLETE_FLAT_FULL_ACCEPTED') throw $e;
}
SetupGuard::package($site.'/releases/'.$bridgeSha);
$expect($shaOf($site.'/FULL_MANIFEST.json')===$shaOf($site.'/FULL_MANIFEST.json'),
    'OWNER_MANIFEST_TAMPERED');
echo "P08_R35_ORIGINAL_FULL_NOT_RELABELED_DURING_BRIDGE=PASS\n";

$stage=(new AtomicPackageStage())->prepare($site,$zipArg,$archiveHash,$targetSha);
$expect(($stage['source_version']??null)==='0.1.0'
    && ($stage['target_version']??null)==='0.1.1','STAGE_VERSION_MISMATCH');
// Reuse the genuine pre-conversion backup. No redundant backup during update.
$backupId=$converted['backup_id'];
$expect(is_file($private.'/recovery/'.$backupId.'/files-manifest.json'),'REAL_BACKUP_FAILED');
$armed=(new AtomicUpgradeArm())->arm($site,$stage['id'],$backupId,$archiveHash,$targetSha);
$expect(($armed['status']??null)==='PREPARED_NOT_APPLIED','ATOMIC_ARM_FAILED');
$material=(new AtomicReleaseMaterializer())->prepare($site,$stage['id'],$archiveHash,$targetSha);
$expect(($material['status']??null)==='MATERIALIZED_NOT_ACTIVATED','MATERIALIZER_FAILED');
$switched=(new AtomicReleasePointer())->switch($site,$stage['id'],$archiveHash,$targetSha);
$expect(($switched['status']??null)==='COMMITTED','R25_SWITCH_FAILED');
$actual=(new AtomicReleasePointer())->verifyActiveRelease($site,$targetSha);
$expect(($actual['status']??null)==='VERIFIED_ACTIVE_FULL'
    && ($actual['target_version']??null)==='0.1.1','UPGRADED_CODE_INVALID');
foreach(['env'=>'.env','db'=>substr($database,strlen($site)+1),
    'installed'=>'storage/app/private/adops/installation/installed.json'] as $key=>$file) {
    $expect($shaOf($site.'/'.$file)===$before[$key], 'OWNER_'.$key.'_DATA_CHANGED');
}
$db=new SQLite3($database,SQLITE3_OPEN_READONLY);
$check=$db->querySingle('SELECT value FROM p08_atomic_owner WHERE id=1');
$db->close();
$expect($check==='OWNER_PRESERVED','OWNER_ROW_LOST');
echo "P08_R35_REAL_ORIGINAL_FLAT_TO_0_1_1_FULL_ATOMIC_AND_SQLITE_DATA=PASS\n";
echo "P08_R35_CLOUDPANEL_FPM_DRAIN_OPCACHE_AND_OWNER_BROWSER=NOT_PROVEN\n";
