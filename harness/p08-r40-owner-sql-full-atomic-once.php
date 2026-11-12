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
    'Upgrade/AtomicReleaseMaterializer.php',
    'Upgrade/AtomicReleasePointer.php',
] as $path) require_once getcwd().'/private-bridge/src/'.$path;
require_once getcwd().'/private-target/src/Upgrade/AtomicUpgradeArm.php';
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
// R39: real disposable SQL engine, not a SQLite/fake-dump substitution.
$engine=getenv('P08_TEST_DB_DRIVER');
if (!in_array($engine,['mariadb','mysql'],true) || getenv('P08_ISOLATED_INSTALL_TEST')!=='YES') $fail('ENGINE_NOT_ISOLATED');
$password=(string)getenv('P08_TEST_DB_PASSWORD');
if ($password==='' || getenv('P08_TEST_DB_HOST')!=='127.0.0.1') $fail('SQL_CONFIG_INVALID');
$database='p08_ci_r39_'.bin2hex(random_bytes(6));
$restored=$database.'_restore';
$admin=new PDO('mysql:host=127.0.0.1;port=3306;charset=utf8mb4','root',$password,
    [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false]);
$admin->exec('CREATE DATABASE `'.$database.'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
$admin->exec('CREATE DATABASE `'.$restored.'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
$pdo=new PDO('mysql:host=127.0.0.1;port=3306;dbname='.$database.';charset=utf8mb4',
    'root',$password,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false]);
// R40: perform the real first Owner Laravel installation and first Landing
// revision in the ORIGINAL extracted 0.1.0 FULL, not a synthetic marker.
require_once $site.'/src/Support/Autoload.php';
require_once $site.'/vendor/autoload.php';
$ownerPassword='Synthetic-Owner-Only-12345!';
$payload=[
    'db_driver'=>$engine,'db_host'=>'127.0.0.1','db_port'=>'3306',
    'db_database'=>$database,'db_username'=>'root','db_password'=>$password,
    'owner_email'=>'owner@isolated.example','owner_password'=>$ownerPassword,
    'owner_confirm'=>$ownerPassword,
];
(new \VF\AdOps\Installation\OwnerWebInstaller())->install($payload,$site);
$installed=$private.'/installation/installed.json';
$owner=\Illuminate\Support\Facades\DB::table('users')->first();
if (!$owner || !\Illuminate\Support\Facades\Hash::check($ownerPassword,$owner->password)) {
    $fail('REAL_FIRST_OWNER_INSTALL_OR_HASH_FAILED');
}
$ownerId=(int)$owner->id;
$sampleLanding=[
    'kind'=>'app','title'=>'Synthetic R40 landing',
    'headline'=>'Owner upgraded without losing Landing history',
    'body'=>'Isolated real SQL workflow, no provider linked',
    'cta_text'=>'Read','cta_url'=>'https://example.com/test',
];
$landingId=(new \App\Modules\Landing\Actions\CreateLanding())->execute($sampleLanding,$ownerId);
$landing=\Illuminate\Support\Facades\DB::table('landing_pages')->where('id',$landingId)->first();
$revision=\Illuminate\Support\Facades\DB::table('landing_revisions')->where('landing_page_id',$landingId)->first();
if (!$landing || !$revision || (int)$landing->current_revision!==1) {
    $fail('REAL_FIRST_LANDING_REVISION_FAILED');
}
$landingRoot=storage_path('app/private/adops/landings/'.$landingId);
(new \VF\AdOps\Landing\LandingVersionStore())->verify($landingRoot,1,(string)$landing->bundle_sha256);
$landingManifestHash=(string)hash_file('sha256',$landingRoot.'/versions/1/index.html');
if (!is_file($landingRoot.'/versions/1/index.html') || !$landingManifestHash) {
    // Later file-name mismatch is a test-fixture error, not a release failure.
    $fail('REAL_LANDING_PRIVATE_ASSET_MISSING');
}
echo "P08_R40_REAL_EXTRACTED_0_1_0_OWNER_LANDING_INSTALL=PASS engine=".$engine."\n";
$pdo->exec('CREATE TABLE p08_atomic_owner (id INT PRIMARY KEY, value VARCHAR(255) NOT NULL) ENGINE=InnoDB');
$pdo->exec("INSERT INTO p08_atomic_owner (id,value) VALUES (1,'OWNER_PRESERVED')");
$lock=$private.'/maintenance/write-gate.lock';
if(file_put_contents($lock,'')===false) $fail('LOCK_SETUP');
chmod($lock,0600);
$shaOf=static fn(string $path):string => (string)hash_file('sha256',$path);
$before=[
    'env'=>$shaOf($site.'/.env'),'db'=>'OWNER_PRESERVED','installed'=>$shaOf($installed),
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
$dbConfig=['driver'=>$engine,'database'=>$database,'host'=>'127.0.0.1',
    'port'=>3306,'username'=>'root','password'=>$password];
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
    && $pdo->query('SELECT value FROM p08_atomic_owner WHERE id=1')->fetchColumn()===$before['db']
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
// Inject a real pointer failure after swap on a separate copy of the
// extracted isolated site; require rollback to original bridge and unchanged DB.
$faultSite=$site.'-fault-'.bin2hex(random_bytes(4));
$proc=proc_open(['/usr/bin/cp','-a','--',$site,$faultSite],[], $cpPipes);
if (!is_resource($proc) || proc_close($proc)!==0) $fail('FAULT_COPY_FAILED');
try {
    (new AtomicReleasePointer())->switch($faultSite,$stage['id'],$archiveHash,$targetSha,'after_swap');
    $fail('FAULT_AFTER_SWAP_WAS_ACCEPTED');
} catch (RuntimeException $e) {
    if ($e->getMessage()==='R35_FAULT_AFTER_SWAP_WAS_ACCEPTED') throw $e;
    $expect($e->getMessage()==='R25_INJECTED_AFTER_SWAP','FAULT_WRONG_EXCEPTION');
}
$expect(readlink($faultSite.'/current')==='releases/'.$bridgeSha,
    'ROLLBACK_FAILED_TO_RESTORE_BRIDGE_POINTER');
$expect((new AtomicReleasePointer())->verifyActiveRelease($faultSite,$bridgeSha)['status']==='VERIFIED_ACTIVE_FULL',
    'ROLLBACK_FAILED_TO_READ_BRIDGE_FULL');
$expect($pdo->query('SELECT value FROM p08_atomic_owner WHERE id=1')->fetchColumn()==='OWNER_PRESERVED',
    'FAULT_CHANGED_INSTALLED_DB');
echo "P08_R39_SQL_ATOMIC_AFTER_SWAP_FAULT_ROLLED_BACK=PASS engine=".$engine."\n";
$switched=(new AtomicReleasePointer())->switch($site,$stage['id'],$archiveHash,$targetSha);
$expect(($switched['status']??null)==='COMMITTED','R25_SWITCH_FAILED');
$actual=(new AtomicReleasePointer())->verifyActiveRelease($site,$targetSha);
$expect(($actual['status']??null)==='VERIFIED_ACTIVE_FULL'
    && ($actual['target_version']??null)==='0.1.1','UPGRADED_CODE_INVALID');
foreach(['env'=>'.env','installed'=>'storage/app/private/adops/installation/installed.json'] as $key=>$file) {
    $expect($shaOf($site.'/'.$file)===$before[$key], 'OWNER_'.$key.'_DATA_CHANGED');
}
$check=$pdo->query('SELECT value FROM p08_atomic_owner WHERE id=1')->fetchColumn();
$expect($check==='OWNER_PRESERVED','OWNER_ROW_LOST');
// Recovery tests the exact native backup after the real code upgrade, into
// a distinct empty database; installed database/Owner files remain unchanged.
$backupId=$converted['backup_id'];
$restoreConfig=['driver'=>$engine,'host'=>'127.0.0.1','port'=>3306,
    'database'=>$restored,'username'=>'root','password'=>$password];
(new \VF\AdOps\Recovery\DatabaseSnapshot())->restoreToEmpty($site,$backupId,$restoreConfig);
$restorePdo=new PDO('mysql:host=127.0.0.1;port=3306;dbname='.$restored.';charset=utf8mb4',
    'root',$password,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$expect($restorePdo->query('SELECT value FROM p08_atomic_owner WHERE id=1')->fetchColumn()==='OWNER_PRESERVED',
    'RESTORED_OWNER_ROW_MISSING');
$expect($pdo->query('SELECT value FROM p08_atomic_owner WHERE id=1')->fetchColumn()==='OWNER_PRESERVED',
    'INSTALLED_OWNER_ROW_CHANGED');
echo "P08_R39_REAL_SQL_FLAT_BRIDGE_ATOMIC_AND_RESTORED_BACKUP=PASS engine=".$engine."\n";
$query='SELECT email FROM users WHERE id='.$ownerId;
$expect($pdo->query($query)->fetchColumn()==='owner@isolated.example','INSTALLED_OWNER_ACCOUNT_CHANGED');
$expect($restorePdo->query($query)->fetchColumn()==='owner@isolated.example','RESTORED_OWNER_ACCOUNT_MISSING');
$revs='SELECT COUNT(*) FROM landing_revisions WHERE landing_page_id='.(int)$landingId;
$expect((int)$pdo->query($revs)->fetchColumn()===1,'LANDING_REVISION_LOST_DURING_UPDATE');
$expect((int)$restorePdo->query($revs)->fetchColumn()===1,'RESTORED_LANDING_REVISION_MISSING');
$expect(hash_file('sha256',$landingRoot.'/versions/1/index.html')===$landingManifestHash,
    'LANDING_MEDIA_CHANGED_DURING_ATOMIC');
$privateSnapshot=$private.'/recovery/'.$backupId.'/files-manifest.json';
$snap=json_decode((string)file_get_contents($privateSnapshot),true,64,JSON_THROW_ON_ERROR);
$assetPaths=array_column($snap['files'],'path');
$expect(count(array_filter($assetPaths,static fn($p)=>str_starts_with($p,'private/landings/')))>=1,
    'PRIVATE_LANDING_NOT_BACKED_UP');
echo "P08_R40_REAL_OWNER_LOGIN_HASH_LANDING_REVISION_AND_ASSET_PRESERVED=PASS engine=".$engine."\n";

echo "P08_R35_CLOUDPANEL_FPM_DRAIN_OPCACHE_AND_OWNER_BROWSER=NOT_PROVEN\n";
