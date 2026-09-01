<?php
declare(strict_types=1);
$root = getenv('P01_ROOT');
if (!$root) { fwrite(STDERR, "missing P01_ROOT\n"); exit(2); }
require $root . '/app/bootstrap.php';
require $root . '/app/SurfaceRepository.php';
$d = vf_db();
$r = new VfRepository($d);
$s = new VfSurfaceRepository($d);
$cat = $r->createCategory(['name'=>'公开测试分类','description'=>'','icon'=>'','is_private'=>0,'sort_order'=>0]);
$save = function(string $title, string $url) use ($r, $cat): int {
    return (int)$r->saveLink(null, ['category_id'=>$cat,'title'=>$title,'url'=>$url,'description'=>'用于匿名布局宽度验证','is_private'=>0], 'manual')['id'];
};
for ($i=1; $i<=8; $i++) $save('公开导航资源完整标题 '.$i, 'https://example.com/public-start-'.$i);
for ($i=1; $i<=6; $i++) {
    $id=$save('公开频道资源完整标题 '.$i, 'https://www.youtube.com/@public-channel-'.$i);
    $s->upsertProfile($id, ['surface'=>'channels','resource_kind'=>'频道']);
}
for ($i=1; $i<=4; $i++) {
    $id=$save('公开影视资源完整标题 '.$i, 'https://example.com/public-watch-'.$i);
    $s->upsertProfile($id, ['surface'=>'watch','resource_kind'=>'电影']);
}
for ($i=1; $i<=4; $i++) {
    $id=$save('公开专题资源完整标题 '.$i, 'https://example.com/public-topic-'.$i);
    $s->upsertProfile($id, ['surface'=>'topics','resource_kind'=>'专题']);
}
if (strtolower((string)$d->query('PRAGMA integrity_check')->fetchColumn()) !== 'ok') exit(11);
if ($d->query('PRAGMA foreign_key_check')->fetchAll(PDO::FETCH_ASSOC)) exit(12);
echo "P01_ANONYMOUS_GRID_SEED=PASS\n";
