<?php
declare(strict_types=1);

/**
 * FINAL one-off public-safe read-only check.
 * Executes actual official v0.1.12 shipped PHP with live authenticated
 * official GitHub channel/release/tag; no fixture transport, no Owner site,
 * no DB, no update state write, no Production side-effects.
 */
if (PHP_SAPI!=='cli'
    || getenv('GITHUB_ACTIONS')!=='true'
    || getenv('P08_ISOLATED_INSTALL_TEST')!=='YES'
    || !function_exists('posix_geteuid')
    || posix_geteuid()===0
    || count($argv)!==2) {
    throw new RuntimeException('P08_V013_ONLINE_CLI_ISOLATED_ONLY');
}
$zip=$argv[1];
$basename='VF_AdOps_V0.1.13_UPDATE.zip';
if (!is_string($zip)
    || !str_starts_with($zip,(string)getenv('RUNNER_TEMP').'/')
    || basename($zip)!==$basename
    || is_link($zip) || !is_file($zip)
    || filesize($zip)!==8355163
    || !hash_equals(
        '6982a7b44873ac825e6c252b309d8f11a9ade67e67f5b8b6467538a46ef71b2a',
        (string)hash_file('sha256',$zip))) {
    throw new RuntimeException('P08_V013_ONLINE_REAL_ZIP_NOT_VERIFIED');
}
$token=(string)getenv('P08_CHANNEL_TEST_TOKEN');
if (!preg_match('/^[A-Za-z0-9_.-]{20,255}$/D',$token)) {
    throw new RuntimeException('P08_V013_ONLINE_PRIVATE_READ_TOKEN_UNAVAILABLE');
}
$old=realpath('old');
if ($old===false || !is_file($old.'/vendor/autoload.php')
    || !is_file($old.'/src/Upgrade/OwnerNextReleaseGateway.php')
    || $old===realpath('target')) {
    throw new RuntimeException('P08_V013_ONLINE_OLD_RUNTIME_MISSING');
}
require_once $old.'/vendor/autoload.php';
$gate=new \VF\AdOps\Upgrade\OwnerNextReleaseGateway();
$installed=[
    // Independently machine-proven authentic official v019 FULL→v010 Atomic
    //→v012 Atomic installed origin across all three native databases.
    'version'=>'0.1.12',
    'source_sha'=>'dac7bc1d5410c077f32e522eb5740537f618ef9d',
    'source_full_manifest_sha256'=>'607b3a02a20021c0747d42440497b7e9e3e0fe39040869f475ba22f9f19437e9',
];
$result=$gate->check($token,$installed);
if (($result['status']??null)!=='OFFICIAL_NEXT_VERIFIED_NOT_STAGED'
    || ($result['can_install']??null)!==false
    || ($result['source_sha']??null)!==$installed['source_sha']
    || ($result['source_version']??null)!=='0.1.12'
    || ($result['source_full_manifest_sha256']??null)
      !==$installed['source_full_manifest_sha256']
    || ($result['target_version']??null)!=='0.1.13'
    || ($result['target_sha']??null)!=='8b385fecd132a02ac79f5b67e670783e98997c3e'
    || ($result['tag']??null)!=='v0.1.13'
    || ($result['release_id']??null)!==452233612
    || ($result['asset_id']??null)!==770296935
    || ($result['asset_bytes']??null)!==8355163
    || ($result['asset_sha256']??null)
      !=='6982a7b44873ac825e6c252b309d8f11a9ade67e67f5b8b6467538a46ef71b2a') {
    throw new RuntimeException('P08_V013_ONLINE_OLD_CLIENT_REAL_CHANNEL_MISMATCH');
}
echo "P08_V013_OLD_SHIPPED_V012_PHP_REAL_OFFICIAL_CHANNEL_RELEASE_TAG_SHA=PASS\n";
$gate->verifyArchive($result,$zip);
echo "P08_V013_OLD_SHIPPED_PHP_REAL_REMOTE_ATOMIC_ARCHIVE_VERIFY=PASS\n";

// Negative: a newly installed CLEAN v012 FULL is NOT the original
// issued Atomic-origin. The LIVE old gateway MUST reject it.
$clean=$installed;
$clean['source_full_manifest_sha256']='4df28b7a9dcfbaf4c0bec18009955fe1b0c7764ccfe94f4257ae2ca0dc3794cc';
try {
    $gate->check($token,$clean);
    throw new RuntimeException('P08_V013_UNSUPPORTED_CLEAN_012_WAS_ACCEPTED');
} catch (\RuntimeException $e) {
    if ($e->getMessage()!=='P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED')throw $e;
}
echo "P08_V013_OLD_SHIPPED_PHP_CLEAN_ORIGIN_LIVE_CHANNEL_REJECTED=PASS\n";

// Negative: same verified channel, but a cryptographically wrong Atomic
// archive may never get to the stage writer.
$tmp=$zip.'.corrupt';
$src=fopen($zip,'rb');$dst=fopen($tmp,'xb');
if (!is_resource($src)||!is_resource($dst))
    throw new RuntimeException('P08_V013_ONLINE_TMP_ISOLATION_FAILED');
stream_copy_to_stream($src,$dst);
fclose($src);fclose($dst);
$fd=fopen($tmp,'r+b');
if (!is_resource($fd)) throw new RuntimeException('P08_V013_ONLINE_TAMPER_OPEN_FAILED');
fseek($fd,0);fwrite($fd,"\x00");fclose($fd);
try {
    $gate->verifyArchive($result,$tmp);
    throw new RuntimeException('P08_V013_TAMPERED_REMOTE_ARCHIVE_ACCEPTED');
} catch (\RuntimeException $e) {
    if ($e->getMessage()!=='P08_NEXT_ARCHIVE_BYTES_UNTRUSTED')throw $e;
} finally {
    @unlink($tmp);
}
echo "P08_V013_OLD_SHIPPED_PHP_REAL_REMOTE_TAMPER_REFUSAL=PASS\n";
echo "P08_V013_REAL_LIVE_ONLINE_OLD_CLIENT_PREFLIGHT=PASS\n";
