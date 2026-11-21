<?php
declare(strict_types=1);
// Mandatory v016 Mode Y preissue NEGATIVE: run ORIGINAL issued v015 PHP only,
// read verified old FULL bytes. No official v016 release/channel is published.
if (PHP_SAPI !== 'cli' || getenv('P08_R145_ISOLATED') !== 'YES'
    || getenv('P08_ISOLATED_INSTALL_TEST') !== 'YES') {
    fwrite(STDERR,"P08_MODE_Y_OLD_CLIENT_ISOLATION_REQUIRED\n"); exit(2);
}
$root=getenv('P08_ORIGINAL_ISSUED_ROOT') ?: '';
$manifest=getenv('P08_ORIGINAL_FULL_MANIFEST') ?: '';
if ($root===''||$manifest===''||!is_file($root.'/src/Upgrade/OwnerNextReleaseGateway.php')
    ||!is_file($manifest))throw new RuntimeException('ORIGINAL_FULL_REQUIRED');
$m=json_decode((string)file_get_contents($manifest),true,32,JSON_THROW_ON_ERROR);
$oldSha='369fcb0aa8fef71b0a2b79c2b7a6c473d2527c3e';
$targetSha='ed96b18627cd0a63b1da20a1fd8c9b6c1808f159';
if(($m['source_sha']??null)!==$oldSha ||($m['target_version']??null)!=='0.1.15'
    || ($m['type']??null)!=='CLEAN_FULL_ONLY')throw new RuntimeException('ISSUED_015_MANIFEST_IDENTITY_MISMATCH');
require_once $root.'/src/Upgrade/OwnerNextReleaseGateway.php';
require_once $root.'/app/Http/Controllers/OwnerFutureUpdateController.php';
$installed=[
  'version'=>'0.1.15','source_sha'=>$oldSha,
  'source_full_manifest_sha256'=>hash_file('sha256',$manifest)
];
$channel=[
 'schema_version'=>'1.0','project_id'=>'P08','component_id'=>'APP',
 'repository'=>'llhzx2018/vf-adops','project_slug'=>'vf-adops',
 'channel'=>'stable','enabled'=>true,'update_type'=>'ATOMIC',
 'backup_required'=>true,'rollback_supported'=>true,
 'production_auto_apply'=>false,'signature_required'=>false,
 'target_version'=>'0.1.16','target_sha'=>$targetSha,'release_tag'=>'v0.1.16',
 'from_versions'=>[],'source_sha'=>$oldSha,
 'source_full_manifest_sha256'=>$installed['source_full_manifest_sha256'],
 'schema_from'=>'1.1','schema_to'=>'1.1','minimum_php'=>'8.4.1',
 'release_id'=>111,'asset_id'=>112,'asset_name'=>'VF_AdOps_V0.1.16_UPDATE.zip',
 'asset_bytes'=>2000,'asset_sha256'=>str_repeat('a',64),
 'full_asset_id'=>113,'full_asset_name'=>'VF_AdOps_V0.1.16_FULL.zip',
 'full_asset_bytes'=>3000,'full_asset_sha256'=>str_repeat('b',64)
];
$channelCode=200; $otherCalls=0;
$transport=static function(string $url,string $accept)use(&$channel,$installed,&$channelCode,&$otherCalls):array {
 if(!str_contains($url,'/contents/projects/P08-ADOPS.json')) {
   ++$otherCalls; return [404,'{}'];
 }
 return [$channelCode,json_encode($channel,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)];
};
$gateway=new \VF\AdOps\Upgrade\OwnerNextReleaseGateway($transport);
$credential=str_repeat('z',32);
$deny=static function(string $expected)use($gateway,$credential,$installed):void {
 try { $result=$gateway->check($credential,$installed);
   throw new RuntimeException('UNSAFE_OLD_OFFER_ACCEPTED:'.json_encode($result)); }
 catch(RuntimeException $e){ if($e->getMessage()!==$expected)throw $e; }
};
$deny('P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED');
if($otherCalls!==0)throw new RuntimeException('OLD_CLIENT_FETCHED_V016_ASSETS_BEFORE_SOURCE_DENIAL');
echo "P08_MODE_Y_AUTHENTIC_ISSUED_015_NO_ELIGIBLE_GENERIC_V016_CHANNEL=PASS\n";
$channel['from_versions']=['0.1.14'];
$deny('P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED');
$channel['from_versions']=['0.1.15'];
$channel['source_sha']=str_repeat('f',40);
$deny('P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED');
$channel['source_sha']=$oldSha;
$channel['source_full_manifest_sha256']=str_repeat('f',64);
$deny('P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED');
$channel['from_versions']=[]; $channel['source_full_manifest_sha256']=$installed['source_full_manifest_sha256'];
$channel['production_auto_apply']=true;
$deny('P08_NEXT_CHANNEL_POLICY_INVALID');
$channel['production_auto_apply']=false;
$channelCode=403;$deny('P08_NEXT_CHANNEL_ACCESS_DENIED');
$channelCode=503;$deny('P08_NEXT_CHANNEL_FETCH_FAILED');
$channelCode=404;
$out=$gateway->check($credential,$installed);
if(($out['status']??null)!=='OFFICIAL_CHANNEL_MISSING'||($out['can_install']??null)!==false)
 throw new RuntimeException('OLD_CHANNEL_MISSING_UNSAFE');
$channelCode=200;
if($otherCalls!==0)throw new RuntimeException('OLD_CLIENT_FOLLOWED_RELEASE_DETAILS_UNSAFELY');
$reflect=new ReflectionMethod(\App\Http\Controllers\OwnerFutureUpdateController::class,'safeCheckFailure');
foreach([
 'P08_NEXT_SOURCE_OR_SCHEMA_UNSUPPORTED'=>['SOURCE_LINEAGE_NOT_SUPPORTED',409],
 'P08_NEXT_CHANNEL_ACCESS_DENIED'=>['OFFICIAL_CHANNEL_ACCESS_DENIED',403],
 'P08_NEXT_CHANNEL_FETCH_FAILED'=>['OFFICIAL_CHANNEL_UNREACHABLE',503],
] as $failure=>$expected) {
 $got=$reflect->invoke(null,$failure);
 if(!is_array($got)||$got[0]!==$expected[0]||$got[2]!==$expected[1])
  throw new RuntimeException('ORIGINAL_ISSUED_V015_UNSAFE_ERROR_MAPPING:'.$failure);
}
echo "P08_MODE_Y_OLD_V015_FUTURE_V016_SOURCE_MANIFEST_POLICY_NEGATIVES=PASS\n";
echo "P08_MODE_Y_ORIGINAL_V015_SAFE_409_403_503_ERROR_MAPPING=PASS\n";
