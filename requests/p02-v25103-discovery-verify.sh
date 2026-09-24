#!/usr/bin/env bash
set -Eeuo pipefail

URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/contents/projects/P02.json?ref=main"
MANIFEST="${RUNNER_TEMP}/p02-v25103-discovery.json"

curl -fsSL   -H 'Accept: application/vnd.github.raw+json'   -H 'X-GitHub-Api-Version: 2022-11-28'   -H 'User-Agent: vf-library-discovery-verify'   "$URL" > "$MANIFEST"

python3 - "$MANIFEST" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
assert x['project_id']=='P02'
assert x['component_id']=='APP'
assert x['target_version']=='2.5.103'
assert x['from_versions']==['2.5.81','2.5.82','2.5.102']
assert x['schema_from']=='2401' and x['schema_to']=='2401'
assert x['release_tag']=='v2.5.103'
assert x['release_id']==395243687
assert x['product_identity']=='2c8a75f4fbe391a3beddafe977ebca33ddfd8e1a'
assert x['asset_name']=='VF_Library_V2.5.103_UPDATE.zip'
assert x['asset_bytes']==424871
assert x['asset_sha256']=='af8373147fcae999cc84b91cded6a022e74aa0e367583be325a215a1ec18e184'
print('P02_V25103_PUBLIC_MIRROR_IDENTITY=PASS')
PY

php - "$MANIFEST" <<'PHP'
<?php
require getcwd().'/product/src/app/CoreUpdates/UpdateCore.php';
$manifest=json_decode(file_get_contents($argv[1]),true,512,JSON_THROW_ON_ERROR);
$core=new \CoreUpdates\UpdateCore('P02','APP');
$expected=[
  '2.5.81'=>'AVAILABLE',
  '2.5.82'=>'AVAILABLE',
  '2.5.102'=>'AVAILABLE',
  '2.5.103'=>'UP_TO_DATE',
];
foreach($expected as $version=>$status){
  $result=$core->check($version,'2401',$manifest);
  if(($result['status']??'')!==$status){
    fwrite(STDERR,$version.' expected '.$status.' got '.($result['status']??'UNKNOWN').PHP_EOL);
    exit(1);
  }
  echo 'P02_V25103_DISCOVERY_'.$version.'='.$status.PHP_EOL;
}
echo "P02_V25103_DISCOVERY_VERIFY=PASS\n";
PHP
