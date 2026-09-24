#!/usr/bin/env bash
set -Eeuo pipefail

URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/contents/projects/P02.json?ref=main"
MANIFEST="${RUNNER_TEMP}/p02-v25105-discovery.json"

curl -fsSL   -H 'Accept: application/vnd.github.raw+json'   -H 'X-GitHub-Api-Version: 2022-11-28'   -H 'User-Agent: vf-library-discovery-verify'   "$URL" > "$MANIFEST"

python3 - "$MANIFEST" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
assert x['project_id']=='P02'
assert x['component_id']=='APP'
assert x['current_version']=='2.5.104'
assert x['target_version']=='2.5.105'
assert x['from_versions']==['2.5.81','2.5.82','2.5.102','2.5.103','2.5.104']
assert x['schema_from']=='2401' and x['schema_to']=='2401'
assert x['release_tag']=='v2.5.105'
assert x['release_id']==395328252
assert x['product_identity']=='c103134ba9e23f83d68c9676cdf892fb2629e8f8'
assert x['asset_name']=='VF_Library_V2.5.105_UPDATE.zip'
assert x['asset_bytes']==426658
assert x['asset_sha256']=='43311c8f9730d3baa0ace932ee1eed6857c133755e68048cd143a6cf1e2e5c0b'
print('P02_V25105_PUBLIC_MIRROR_IDENTITY=PASS')
PY

PHP_CHECK="${RUNNER_TEMP}/p02-v25105-discovery-check.php"
cat > "$PHP_CHECK" <<'PHP'
<?php
require getcwd().'/product/src/app/CoreUpdates/UpdateCore.php';
$manifest=json_decode(file_get_contents($argv[1]),true,512,JSON_THROW_ON_ERROR);
$core=new \CoreUpdates\UpdateCore('P02','APP');
$expected=[
  '2.5.81'=>'AVAILABLE',
  '2.5.82'=>'AVAILABLE',
  '2.5.102'=>'AVAILABLE',
  '2.5.103'=>'AVAILABLE',
  '2.5.104'=>'AVAILABLE',
  '2.5.105'=>'UP_TO_DATE',
];
foreach($expected as $version=>$status){
  $result=$core->check($version,'2401',$manifest);
  if(($result['status']??'')!==$status){
    fwrite(STDERR,$version.' expected '.$status.' got '.($result['status']??'UNKNOWN').PHP_EOL);
    exit(1);
  }
  echo 'P02_V25105_DISCOVERY_'.$version.'='.$status.PHP_EOL;
}
echo "P02_V25105_DISCOVERY_VERIFY=PASS\n";
PHP
php "$PHP_CHECK" "$MANIFEST"
