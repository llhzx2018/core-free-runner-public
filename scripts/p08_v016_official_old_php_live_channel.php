<?php
declare(strict_types=1);
// Only a disposable official v015 FULL, and its own UNMODIFIED old PHP.
// No test transport, no fake data, no Production and no remote writes.
if (PHP_SAPI !== 'cli' || getenv('GITHUB_ACTIONS') !== 'true'
    || getenv('CHANNEL_STAGE') !== 'post') {
    fwrite(STDERR, "P08_V016_POSTCHANNEL_ISOLATION_REQUIRED\n");
    exit(2);
}
$root=(string)getenv('P08_ORIGINAL_015_ROOT');
$oldManifest=(string)getenv('P08_CHANNEL_V015_MANIFEST');
$token=(string)getenv('GH_TOKEN');
if ($root==='' || $oldManifest==='' || strlen($token)<20
    || !is_file($oldManifest) || !is_file($root.'/src/Upgrade/OwnerNextReleaseGateway.php')) {
    throw new RuntimeException('P08_V016_ORIGINAL_SOURCE_REQUIRED');
}
$m=json_decode((string)file_get_contents($oldManifest),true,32,JSON_THROW_ON_ERROR);
if (($m['source_sha']??null)!=='369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e'
    ||($m['target_version']??null)!=='0.1.15'
    ||($m['type']??null)!=='CLEAN_FULL_ONLY') {
    throw new RuntimeException('P08_V016_OLD_MANIFEST_UNTRUSTED');
}
require_once $root.'/src/Upgrade/OwnerNextReleaseGateway.php';
require_once $root.'/app/Http/Controllers/OwnerFutureUpdateController.php';
$installed=[
    'version'=>'0.1.15',
    'source_sha'=>'369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e',
    'source_full_manifest_sha256'=>hash_file('sha256',$oldManifest),
];
$gateway=new \VF\AdOps\Upgrade\OwnerNextReleaseGateway();
try {
    $offer=$gateway->check($token,$installed);
    throw new RuntimeException('P08_V016_UNSAFE_ORIGINAL_015_OFFER:'.json_encode($offer));
} catch (RuntimeException $e) {
    if($e->getMessage()!=='P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED') throw $e;
}
$meth=new ReflectionMethod(\App\Http\Controllers\OwnerFutureUpdateController::class,'safeCheckFailure');
$out=$meth->invoke(null,'P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED');
if (!is_array($out) || $out[0]!=='SOURCE_LINEAGE_NOT_SUPPORTED'
    || $out[2]!==409) throw new RuntimeException('P08_V016_OLD_PHP_WRONG_SAFE_STATUS');
echo "P08_V016_ORIGINAL_ISSUED_V015_NORMAL_OWNER_GATEWAY_LIVE_INELIGIBLE=PASS\n";
echo "P08_V016_ORIGINAL_ISSUED_V015_NORMAL_OWNER_HTTP409_SAFE_CLASS=PASS\n";
