<?php
declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/src/app/ResourceSearch.php';

$assets = [
    ['id'=>1,'title'=>'Google Search Console','url'=>'https://search.google.com/search-console','description'=>'SEO','category_name'=>'SEO','resource_kind'=>'','provider_label'=>'','tags'=>['站长'],'sort_order'=>2,'surface'=>'start','is_private'=>0],
    ['id'=>2,'title'=>'Google','url'=>'https://google.com','description'=>'搜索','category_name'=>'工具','resource_kind'=>'','provider_label'=>'','tags'=>[],'sort_order'=>1,'surface'=>'start','is_private'=>1],
    ['id'=>3,'title'=>'我的 Google 教程','url'=>'https://example.com/google','description'=>'Google 学习','category_name'=>'专题','resource_kind'=>'教程','provider_label'=>'','tags'=>['google'],'sort_order'=>3,'surface'=>'topics','is_private'=>0],
];

$result = VfResourceSearch::search($assets, 'google', 8);
if (count($result) !== 3) throw new RuntimeException('Expected three matches.');
if ((int)$result[0]['id'] !== 2) throw new RuntimeException('Exact title must rank first.');
if ((int)$result[1]['id'] !== 1) throw new RuntimeException('Title prefix must rank before title contains/tag match.');

$present = VfResourceSearch::present($result[0], true);
if (!is_array($present) || ($present['open_url'] ?? '') !== 'surface-open.php?id=2') throw new RuntimeException('Admin quick open must use tracked surface-open route.');
if (empty($present['private'])) throw new RuntimeException('Private projection missing.');

$hosted = VfResourceSearch::present([
    'id'=>9,'title'=>'Hosted Topic','url'=>'https://placeholder.invalid','html_url'=>'resource-html.php?id=9','surface'=>'topics','source_kind'=>'hosted_html','resource_kind'=>'专题','is_private'=>0
], false);
if (($hosted['open_url'] ?? '') !== 'resource-html.php?id=9') throw new RuntimeException('Public hosted topic must use hosted HTML route.');

if (VfResourceSearch::present(['id'=>10,'title'=>'No URL','url'=>'','surface'=>'projects'], true) !== null) throw new RuntimeException('URL-less resource must not appear in quick open results.');

$course = VfResourceSearch::present(['id'=>11,'title'=>'A1','url'=>'https://example.com/a1','surface'=>'books','resource_kind'=>'实战课程','is_private'=>0], true);
if (($course['surface_label'] ?? '') !== '课程') throw new RuntimeException('Quick Open must present books storage as Courses.');

echo "RESOURCE_SEARCH_CONTRACT_PASS\n";
