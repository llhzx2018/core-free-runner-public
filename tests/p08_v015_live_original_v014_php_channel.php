<?php
declare(strict_types=1);

/**
 * FINAL one-off public-safe read-only check.
 * Executes actual official v0.1.14 shipped PHP with live authenticated
 * official GitHub channel/release/tag; no fixture transport, no Owner site,
 * no DB, no update state write, no Production side-effects.
 */
if (PHP_SAPI!=='cli'
    || getenv('GITHUB_ACTIONS')!=='true'
    || getenv('P08_ISOLATED_INSTALL_TEST')!=='YES'
    || !function_exists('posix_geteuid')
    || posix_geteuid()===0
    || count($argv)!==2) {
    throw new RuntimeException('P08_V015_ONLINE_CLI_ISOLATED_ONLY');
}
$zip=$argv[1];
$basename='VF_AdOps_V0.1.15_UPDATE.zip';
if (!is_string($zip)
    || !str_starts_with($zip,(string)getenv('RUNNER_TEMP').'/')
    || basename($zip)!==$basename
    || is_link($zip) || !is_file($zip)
    || filesize($zip)!==8356933
    || !hash_equals(
        'e8b949d46f6adba0221c6a258c2e844891379494f7ed5b8dcb5903689e4fe51f',
        (string)hash_file('sha256',$zip))) {
    throw new RuntimeException('P08_V015_ONLINE_REAL_ZIP_NOT_VERIFIED');
}
$token=(string)getenv('P08_CHANNEL_TEST_TOKEN');
if (!preg_match('/^[A-Za-z0-9_.-]{20,255}$/D',$token)) {
    throw new RuntimeException('P08_V015_ONLINE_PRIVATE_READ_TOKEN_UNAVAILABLE');
}
$old=realpath('old');
if ($old===false || !is_file($old.'/vendor/autoload.php')
    || !is_file($old.'/src/Upgrade/OwnerNextReleaseGateway.php')
    || $old===realpath('target')) {
    throw new RuntimeException('P08_V015_ONLINE_OLD_RUNTIME_MISSING');
}
require_once $old.'/vendor/autoload.php';
$gate=new \VF\AdOps\Upgrade\OwnerNextReleaseGateway();
$installed=[
    // Independently machine-proven genuine issued v0.1.14 FULL or original v0.1.13→v0.1.14
    // Atomic-installed source, proven to have identical manifest on all 3DB.
    'version'=>'0.1.14',
    'source_sha'=>'6fae792864a594465e4b3224bd6d73abde976f12',
    'source_full_manifest_sha256'=>'efcfa190b08e11e2ff93c9ade976e86355f933fb22417c9668e4cb1f840cf09b',
];
$result=$gate->check($token,$installed);
if (($result['status']??null)!=='OFFICIAL_NEXT_VERIFIED_NOT_STAGED'
    || ($result['can_install']??null)!==false
    || ($result['source_sha']??null)!==$installed['source_sha']
    || ($result['source_version']??null)!=='0.1.14'
    || ($result['source_full_manifest_sha256']??null)
      !==$installed['source_full_manifest_sha256']
    || ($result['target_version']??null)!=='0.1.15'
    || ($result['target_sha']??null)!=='369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e'
    || ($result['tag']??null)!=='v0.1.15'
    || ($result['release_id']??null)!==453401976
    || ($result['asset_id']??null)!==774232507
    || ($result['asset_bytes']??null)!==8356933
    || ($result['asset_sha256']??null)
      !=='e8b949d46f6adba0221c6a258c2e844891379494f7ed5b8dcb5903689e4fe51f') {
    throw new RuntimeException('P08_V015_ONLINE_OLD_CLIENT_REAL_CHANNEL_MISMATCH');
}
echo "P08_V015_OLD_SHIPPED_V014_PHP_REAL_OFFICIAL_CHANNEL_RELEASE_TAG_SHA=PASS\n";
$gate->verifyArchive($result,$zip);
echo "P08_V015_OLD_SHIPPED_PHP_REAL_REMOTE_ATOMIC_ARCHIVE_VERIFY=PASS\n";
$alreadyCurrent=[
  'version'=>'0.1.15',
  'source_sha'=>'369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e',
  // Status-only simulated current identity, not proof of an installed v015 site.
  'source_full_manifest_sha256'=>str_repeat('a',64),
];
$current=$gate->check($token,$alreadyCurrent);
if (($current['status']??null)!=='OFFICIAL_VERSION_CURRENT'
    || ($current['can_install']??null)!==false
    || ($current['target_version']??null)!=='0.1.15') {
    throw new RuntimeException('P08_V015_ONLINE_CURRENT_VERSION_STATUS_WRONG');
}
echo "P08_V015_OLD_PHP_REAL_CHANNEL_CURRENT_VERSION=PASS\n";
$forgedCurrent=$alreadyCurrent;
$forgedCurrent['source_sha']=str_repeat('f',40);
try {
    $gate->check($token,$forgedCurrent);
    throw new RuntimeException('P08_V015_FORGED_CURRENT_SOURCE_ACCEPTED');
} catch (\RuntimeException $e) {
    if ($e->getMessage()!=='P08_NEXT_INSTALLED_SHA_NOT_CHANNEL_TARGET') throw $e;
}
echo "P08_V015_OLD_PHP_FORGED_CURRENT_SOURCE_REJECTED=PASS\n";


// Negative: a previous issued CLEAN v013 FULL is NOT the original
// valid v0.1.14 source manifest. The LIVE old gateway MUST reject it.
$clean=$installed;
$clean['source_full_manifest_sha256']='c7ea39bba377507c335031801a7f1d193de0ddd04715547abdb067928ef7cd5d';
try {
    $gate->check($token,$clean);
    throw new RuntimeException('P08_V015_UNSUPPORTED_V013_ORIGIN_WAS_ACCEPTED');
} catch (\RuntimeException $e) {
    if ($e->getMessage()!=='P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED')throw $e;
}
echo "P08_V015_OLD_SHIPPED_PHP_CLEAN_ORIGIN_LIVE_CHANNEL_REJECTED=PASS\n";

// Negative: same verified channel, but a cryptographically wrong Atomic
// archive may never get to the stage writer.
$tmp=$zip.'.corrupt';
$src=fopen($zip,'rb');$dst=fopen($tmp,'xb');
if (!is_resource($src)||!is_resource($dst))
    throw new RuntimeException('P08_V015_ONLINE_TMP_ISOLATION_FAILED');
stream_copy_to_stream($src,$dst);
fclose($src);fclose($dst);
$fd=fopen($tmp,'r+b');
if (!is_resource($fd)) throw new RuntimeException('P08_V015_ONLINE_TAMPER_OPEN_FAILED');
fseek($fd,0);fwrite($fd,"\x00");fclose($fd);
try {
    $gate->verifyArchive($result,$tmp);
    throw new RuntimeException('P08_V015_TAMPERED_REMOTE_ARCHIVE_ACCEPTED');
} catch (\RuntimeException $e) {
    if ($e->getMessage()!=='P08_NEXT_ARCHIVE_BYTES_UNTRUSTED')throw $e;
} finally {
    @unlink($tmp);
}
echo "P08_V015_OLD_SHIPPED_PHP_REAL_REMOTE_TAMPER_REFUSAL=PASS\n";
echo "P08_V015_REAL_LIVE_ONLINE_OLD_CLIENT_PREFLIGHT=PASS\n";
