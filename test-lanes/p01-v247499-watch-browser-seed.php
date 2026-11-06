<?php
declare(strict_types=1);

// Synthetic disposable fixture for the registered Public Runner.
// Only an ephemeral localhost site root may be mutated; never Production.
$root=(string)getenv('P01_SITE_ROOT');
$output=(string)getenv('P01_FIXTURE_JSON');
if(!preg_match('#^/tmp/p01-v247499-watch-browser-[a-zA-Z0-9_-]+/site$#',$root)
    ||!str_starts_with($output,'/tmp/p01-v247499-watch-browser-')){
    fwrite(STDERR,"P01_WATCH_FIXTURE_LOCALHOST_SCOPE_REQUIRED\n");exit(60);
}
require $root.'/app/bootstrap.php';
$repo=new VfRepository(vf_db());
$cat=$repo->createCategory([
    'name'=>'Watch Browser Isolated Fixture','description'=>'','icon'=>'',
    'is_private'=>0,'sort_order'=>0
]);
$specs=[
    'publicMarked'=>['Public Marked Film',0,'want','电影'],
    'publicUnmarked'=>['Public Unmarked Film',0,'','纪录片'],
    'privateWatched'=>['Private Watched Film',1,'watched','电影'],
    'privateUnmarked'=>['Private Unmarked Film',1,'','剧集']
];
$ids=[];
$i=0;
foreach($specs as $key=>$row){
    $i++;
    [$title,$private,$status,$kind]=$row;
    $created=$repo->saveLink(null,[
        'surface'=>'watch','category_id'=>$cat,'title'=>$title,
        'url'=>'https://example.com/p01-watch-browser-'.$i,
        'description'=>'isolated synthetic Browser proof','tags'=>[],
        'is_private'=>$private,'is_pending'=>0,
        'source_kind'=>'remote_url','resource_kind'=>$kind,
        'media_status'=>$status,'media_year'=>2024
    ]);
    $id=(int)($created['id']??0);
    if($id<=0){fwrite(STDERR,"P01_WATCH_SEED_INVALID_ID\n");exit(61);}
    $ids[$key]=$id;
}
file_put_contents($output,json_encode($ids,JSON_THROW_ON_ERROR));
echo "P01_WATCH_BROWSER_SYNTHETIC_SEED=PASS\n";
