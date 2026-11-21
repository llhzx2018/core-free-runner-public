<?php
declare(strict_types=1);
// Use authentic issued v015 PHP with EXACT proposed core-updates PR JSON.
if (PHP_SAPI!=='cli' || getenv('GITHUB_ACTIONS')!=='true'
    || getenv('CHANNEL_STAGE')!=='pre' || getenv('P08_R145_ISOLATED')!=='YES') {
    throw new RuntimeException('P08_ORIGINAL_PROPOSED_CHANNEL_TEST_NOT_ISOLATED');
}
$root=(string)getenv('P08_ORIGINAL_015_ROOT');
$manifest=(string)getenv('P08_CHANNEL_V015_MANIFEST');
$candidate=(string)getenv('P08_CHANNEL_CANDIDATE_JSON');
if ($root===''||$manifest===''||$candidate===''
    ||!is_file($root.'/src/Upgrade/OwnerNextReleaseGateway.php')
    ||!is_file($manifest)||!is_file($candidate)) {
    throw new RuntimeException('P08_ORIGINAL_PROPOSED_CHANNEL_TEST_INPUT_MISSING');
}
$old=json_decode((string)file_get_contents($manifest),true,32,JSON_THROW_ON_ERROR);
$chan=json_decode((string)file_get_contents($candidate),true,32,JSON_THROW_ON_ERROR);
if(($old['source_sha']??null)!=='369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e'
    ||($chan['source_full_manifest_sha256']??null)!==hash_file('sha256',$manifest)
    ||($chan['from_versions']??null)!==[]
    ||($chan['target_version']??null)!=='0.1.16') {
    throw new RuntimeException('P08_PROPOSED_UNBRIDGED_CHANNEL_NOT_SAFE');
}
require_once $root.'/src/Upgrade/OwnerNextReleaseGateway.php';
$releaseCalls=0;
$transport=static function(string $url,string $accept)use($candidate,&$releaseCalls):array {
    if(str_contains($url,'/contents/projects/P08-ADOPS.json'))
        return [200,(string)file_get_contents($candidate)];
    ++$releaseCalls;
    return [404,'{}'];
};
$gateway=new \VF\AdOps\Upgrade\OwnerNextReleaseGateway($transport);
$installed=[
 'version'=>'0.1.15',
 'source_sha'=>'369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e',
 'source_full_manifest_sha256'=>hash_file('sha256',$manifest),
];
try {
    $offer=$gateway->check(str_repeat('z',32),$installed);
    throw new RuntimeException('P08_PROPOSED_V016_UNSAFE_015_ORDINARY_OFFER:'.json_encode($offer));
}catch(RuntimeException $e){
    if($e->getMessage()!=='P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED')throw $e;
}
if($releaseCalls!==0)throw new RuntimeException('P08_UNSAFE_015_FETCHED_ELIGIBLE_V016_ASSET');
echo "P08_V016_PROPOSED_REAL_CHANNEL_ISSUED_015_ORIGINAL_PHP_DENIED=PASS\n";
