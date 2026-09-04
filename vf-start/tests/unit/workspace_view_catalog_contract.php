<?php
declare(strict_types=1);
require_once dirname(__DIR__, 2) . '/src/app/WorkspaceViewCatalog.php';

$assets = [
    ['id'=>1,'surface'=>'books','title'=>'A1 一个人做出海网站','url'=>'https://example.test/course','description'=>'课程','category_name'=>'','resource_kind'=>'实战课程','tags'=>[]],
    ['id'=>2,'surface'=>'start','title'=>'WhatRuns','url'=>'https://example.test/stack','description'=>'分析网站技术栈','category_name'=>'开发工具与测试','resource_kind'=>'','tags'=>[]],
    ['id'=>3,'surface'=>'start','title'=>'v2rayN','url'=>'https://example.test/client','description'=>'Windows 代理客户端，支持分流和测速','category_name'=>'网络与路由','resource_kind'=>'','tags'=>[]],
    ['id'=>4,'surface'=>'start','title'=>'Ventoy','url'=>'https://example.test/rescue','description'=>'ISO 启动盘，重装和救援使用','category_name'=>'系统与装机','resource_kind'=>'','tags'=>[]],
    ['id'=>5,'surface'=>'topics','title'=>'SEO 指南','url'=>'https://example.test/topic','description'=>'教程','category_name'=>'','resource_kind'=>'指南','tags'=>[]],
    ['id'=>6,'surface'=>'start','title'=>'明确映射','url'=>'https://example.test/tagged','description'=>'','category_name'=>'','resource_kind'=>'','tags'=>['场景:内容生产','软件:开发 / 编程']],
    ['id'=>7,'surface'=>'start','title'=>'全自动 AI 短视频教程','url'=>'https://example.test/tutorial','description'=>'写作与翻译方法','category_name'=>'AI 内容创作','resource_kind'=>'','tags'=>[]],
    ['id'=>8,'surface'=>'start','title'=>'Canva','url'=>'https://example.test/canva','description'=>'模板设计','category_name'=>'内容创作 / 设计、视频与音频','resource_kind'=>'','tags'=>[]],
    ['id'=>9,'surface'=>'start','title'=>'Chrome 浏览器插件推荐（15个）','url'=>'https://example.test/extensions','description'=>'浏览器扩展清单','category_name'=>'工具与软件 / 浏览器与扩展','resource_kind'=>'','tags'=>[]],
];

$entries = VfWorkspaceViewCatalog::entries(true);
if (array_column($entries, 'mode') !== ['home','start','channels','watch','topics','courses','projects','tools','software']) throw new RuntimeException('Nine-entry order drifted.');
if (array_column(VfWorkspaceViewCatalog::entries(false), 'mode')[0] !== 'start') throw new RuntimeException('Anonymous navigation must not expose private Home.');
if (VfWorkspaceViewCatalog::normalizeMode('books') !== 'courses') throw new RuntimeException('Legacy books mode must normalize to courses.');
if (VfWorkspaceViewCatalog::storageDomain('courses') !== 'books') throw new RuntimeException('Courses must alias canonical books storage.');

$courses = VfWorkspaceViewCatalog::assets($assets, 'courses');
if (array_column($courses, 'id') !== [1]) throw new RuntimeException('Courses view must reuse books assets only.');

$tools = VfWorkspaceViewCatalog::assets($assets, 'tools');
$toolKinds = array_column($tools, '_vf_view_kind', 'id');
if (($toolKinds[2] ?? '') !== '做网站') throw new RuntimeException('Website analysis tool scene missing.');
if (($toolKinds[3] ?? '') !== '代理 / 账号环境') throw new RuntimeException('Proxy tool scene missing.');
if (($toolKinds[6] ?? '') !== '内容生产') throw new RuntimeException('Explicit tool tag must win.');
if (($toolKinds[8] ?? '') !== '内容生产') throw new RuntimeException('Real content-creation tools must stay in the eighth scene.');
if (isset($toolKinds[5]) || isset($toolKinds[7]) || isset($toolKinds[9])) throw new RuntimeException('Content/tutorial or recommendation resources must not leak into derived Tools.');

$software = VfWorkspaceViewCatalog::assets($assets, 'software');
$softwareKinds = array_column($software, '_vf_view_kind', 'id');
if (($softwareKinds[3] ?? '') !== '网络') throw new RuntimeException('Network software group missing.');
if (($softwareKinds[4] ?? '') !== '装机 / 救援') throw new RuntimeException('Rescue software group missing.');
if (($softwareKinds[6] ?? '') !== '开发 / 编程') throw new RuntimeException('Explicit software tag must win.');
if (isset($softwareKinds[7]) || isset($softwareKinds[9])) throw new RuntimeException('Tutorial or recommendation resources must not leak into derived Software.');

$counts = VfWorkspaceViewCatalog::counts($assets);
if (($counts['books'] ?? -1) !== 1 || ($counts['courses'] ?? -1) !== 1) throw new RuntimeException('Courses/books alias counts drifted.');
if (($counts['total'] ?? -1) !== count($assets)) throw new RuntimeException('Derived views must not inflate canonical total.');

echo "WORKSPACE_VIEW_CATALOG_CONTRACT_PASS\n";
