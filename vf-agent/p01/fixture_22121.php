<?php
declare(strict_types=1);
require 'app/bootstrap.php';
$repo = new VfRepository(vf_db());
for ($i = 1; $i <= 12; $i++) {
    $root = $repo->createCategory([
        'name' => '一级分类 ' . $i,
        'description' => 'Root ' . $i,
        'parent_id' => null,
        'is_private' => false,
        'sort_order' => 100 - $i,
    ]);
    for ($j = 1; $j <= 3; $j++) {
        $name = $j === 1 ? '浏览器、设备与环境' : '二级分类 ' . $i . '-' . $j;
        $child = $repo->createCategory([
            'name' => $name,
            'description' => 'Child',
            'parent_id' => $root,
            'is_private' => false,
            'sort_order' => 10 - $j,
        ]);
        $repo->saveLink(null, [
            'category_id' => $child,
            'title' => 'Fixture ' . $i . '-' . $j,
            'url' => 'https://example.com/' . $i . '/' . $j,
            'description' => 'fixture',
            'is_private' => false,
            'is_pending' => false,
        ], 'manual');
    }
}
echo "P01_22121_FIXTURE_PASS\n";
