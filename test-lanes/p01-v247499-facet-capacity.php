<?php
declare(strict_types=1);
// Isolated, synthetic-only projection benchmark; source is injected via the
// exact-candidate transient checkout, never persisted to public Git/Artifact.
$src=(string)getenv('P01_FACET_SOURCE');
if($src===''||!str_ends_with($src,'/src/app/WatchFacetContext.php')
   ||!is_file($src))throw new RuntimeException('Exact source fixture missing');
require $src;
function sample(int $count):array {
  $rows=[];
  for($i=0;$i<$count;$i++){
    $rows[]=[
      'id'=>$i+1,'media_status'=>($i%3===0?'want':($i%3===1?'watched':'')),
      'media_year'=>2010+($i%15),
      'tmdb_genres'=>[$i%2?'科幻':'剧情',$i%7?'动作':'悬疑'],
      'tmdb_rating'=>6.0+($i%4),
      'last_surface_opened_at'=>$i%4===0?'2026-11-05T08:00:00Z':''
    ];
  }
  return $rows;
}
$statuses=['want','watching','watched','favorite'];
$run=function(int $n)use($statuses):array{
  $items=sample($n);
  $start=hrtime(true);
  $lists=VfWatchFacetContext::forView($items,'lists',$statuses);
  $recent=VfWatchFacetContext::forView($items,'recent',$statuses);
  $listFacets=VfWatchFacetContext::build($lists,$statuses,'',0,'',0.0);
  $recentFacets=VfWatchFacetContext::build($recent,$statuses,'',0,'',0.0);
  if(count($lists)!==(int)floor(($n+2)/3)*2 && $n%3===0)throw new RuntimeException('Unexpected marked count');
  if(count($recent)!==(int)ceil($n/4))throw new RuntimeException('Unexpected recent count');
  if(count($listFacets['assets'])!==count($lists) || count($recentFacets['assets'])!==count($recent))
    throw new RuntimeException('Facet population drift');
  $sec=(hrtime(true)-$start)/1e9;
  unset($items,$lists,$recent,$listFacets,$recentFacets);
  return ['assets'=>$n,'seconds'=>round($sec,4),'mem_mib'=>round(memory_get_peak_usage(true)/1048576,1)];
};
$small=$run(2000);
$large=$run(20000);
if($large['seconds']>8.0 || $large['mem_mib']>192.0)
  throw new RuntimeException('Facet 20k bounded-capacity budget exceeded');
echo 'P01_FACET_CAPACITY='.json_encode(['small'=>$small,'large'=>$large],JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE)."\n";
echo "P01_WATCH_FACET_20K_BOUNDED=PASS\n";
