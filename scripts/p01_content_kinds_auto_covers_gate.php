<?php
declare(strict_types=1);
require getenv('ROOT').'/app/bootstrap.php';
require getenv('ROOT').'/app/ResourceCoverCache.php';
require getenv('ROOT').'/app/SurfaceRepository.php';
function A($v,string $m): void { if(!$v){fwrite(STDERR,"FAIL: $m\n");exit(1);} }
$db=vf_db();$repo=new VfRepository($db);$surface=new VfSurfaceRepository($db);
$p=VfResourceMetadata::provider('https://www.youtube.com/@vf-private');A($p['code']==='youtube'&&$p['label']==='YouTube','provider');
A(VfResourceMetadata::normalizeKind('channels','YouTube')==='频道','YouTube taxonomy');
A(VfResourceMetadata::normalizeKind('watch','movie')==='电影','movie taxonomy');
A(VfResourceMetadata::normalizeKind('watch','series')==='剧集','series taxonomy');
$c=VfResourceCoverCache::extractCoverCandidates('<meta property="og:image" content="/poster.png">','https://media.example/film/1');A(($c[0]??'')==='https://media.example/poster.png','og image resolve');
$cat=$repo->createCategory(['name'=>'Gate Backing','description'=>'','icon'=>'','is_private'=>0,'sort_order'=>0]);
$channel=$repo->saveLink(null,['category_id'=>$cat,'title'=>'VF 私人频道','url'=>'https://www.youtube.com/@vf-private','description'=>'','is_private'=>1],'manual')['id'];
$watch=$repo->saveLink(null,['category_id'=>$cat,'title'=>'VF 公开电影','url'=>'https://iyf.tv/movie/vf-public','description'=>'','is_private'=>0],'manual')['id'];
$pending=$repo->saveLink(null,['category_id'=>$cat,'title'=>'VF 待整理频道','url'=>'https://www.youtube.com/@vf-pending','description'=>'','is_private'=>1,'is_pending'=>1],'manual')['id'];
$manual=$repo->saveLink(null,['category_id'=>$cat,'title'=>'VF 手工封面频道','url'=>'https://www.bilibili.com/12345','description'=>'','is_private'=>1],'manual')['id'];
$hydrate=$repo->saveLink(null,['category_id'=>$cat,'title'=>'VF 自动触发频道','url'=>'https://www.youtube.com/@vf-hydrate','description'=>'','is_private'=>1],'manual')['id'];
foreach([[$channel,'channels','频道'],[$watch,'watch','电影'],[$pending,'channels','频道'],[$manual,'channels','频道'],[$hydrate,'channels','频道']] as [$id,$s,$k])$surface->upsertProfile($id,['surface'=>$s,'resource_kind'=>$k,'media_year'=>$s==='watch'?'2024':'']);
$db->prepare("UPDATE resource_domain_profiles SET resource_kind='YouTube' WHERE link_id=?")->execute([$channel]);
$db->prepare("UPDATE resource_domain_profiles SET resource_kind='movie' WHERE link_id=?")->execute([$watch]);
$img=file_get_contents(getenv('IMG'));$calls=0;
$fetcher=function(string $url,int $max,string $accept)use($img,&$calls){$calls++;if(str_contains($url,'img.example')||str_contains($url,'/covers/'))return ['status'=>200,'contentType'=>'image/png','body'=>$img,'url'=>$url];if(str_contains($url,'youtube.com/@vf-private'))return ['status'=>200,'contentType'=>'text/html','body'=>'<meta property="og:image" content="https://img.example/private.png">','url'=>$url];if(str_contains($url,'iyf.tv/movie/vf-public'))return ['status'=>200,'contentType'=>'text/html','body'=>'<meta property="og:image" content="/covers/movie.png">','url'=>$url];throw new RuntimeException('unexpected '.$url);};
$cache=new VfResourceCoverCache($db,$fetcher);$r=$cache->refreshOne($channel);A($r['success']&&!$r['cached'],'channel auto cover');$n=$calls;$r=$cache->refreshOne($channel);A($r['success']&&$r['cached']&&$calls===$n,'cover cache reuse');A($cache->refreshOne($watch)['success'],'watch auto cover');
try{$cache->refreshOne($pending);A(false,'pending fetch');}catch(RuntimeException $e){A(str_contains($e->getMessage(),'不会向远端请求封面'),'pending reason');}
$dir=rtrim(VF_PRIVATE_ROOT,'/\\').'/resource-assets/covers';if(!is_dir($dir))mkdir($dir,0750,true);$mf='cover-'.$manual.'-manual.png';copy(getenv('IMG'),$dir.'/'.$mf);$hash=hash_file('sha256',$dir.'/'.$mf);$now=gmdate('c');$db->prepare("INSERT INTO resource_asset_files(link_id,asset_kind,file_name,original_name,mime_type,byte_size,width,height,file_hash,created_at,updated_at) VALUES(?,'cover',?,'manual.png','image/png',?,120,180,?,?,?)")->execute([$manual,$mf,filesize($dir.'/'.$mf),$hash,$now,$now]);$manualCalls=0;$mc=new VfResourceCoverCache($db,function()use(&$manualCalls){$manualCalls++;throw new RuntimeException('manual should not fetch');});$m=$mc->refreshOne($manual);A($m['success']&&$m['source']==='manual'&&$manualCalls===0,'manual preserve');
$assets=$surface->allAssets(true);$map=[];foreach($assets as $a)$map[(int)$a['id']]=$a;A($map[$channel]['resource_kind']==='频道'&&$map[$channel]['provider_label']==='YouTube'&&!empty($map[$channel]['cover_url']),'channel projection');A($map[$watch]['resource_kind']==='电影'&&$map[$watch]['provider_label']==='爱一帆'&&!empty($map[$watch]['cover_url']),'watch projection');A(empty($map[$hydrate]['cover_url']),'hydrate must be empty');
file_put_contents(getenv('EVID').'/ids.json',json_encode(compact('channel','watch','pending','manual','hydrate'),JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE));
echo "TAXONOMY=PASS\nAUTO_COVER=PASS\nMANUAL_OVERRIDE=PASS\nCALLS=$calls\n";
