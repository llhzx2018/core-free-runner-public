<?php
declare(strict_types=1);
require_once __DIR__ . '/FunctionalWorkspaceShell.php';

function vf_render_functional_workspace(): void
{
    if (!vf_is_installed()) { header('Location: setup.php'); exit; }
    $mode=vf_fw_mode();$admin=vf_is_admin();
    vf_security_headers($admin);
    if ($admin) {
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('Cache-Control: no-store, private');
    } elseif ($mode === 'start') {
        header('Cache-Control: public, max-age=120, stale-while-revalidate=300');
    } else {
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('Cache-Control: public, max-age=120, stale-while-revalidate=300');
    }

    $scope=vf_fw_scope($admin);$db=vf_db();$baseRepo=new VfRepository($db);$surfaceRepo=new VfSurfaceRepository($db);$base=$baseRepo->bootstrap($admin);$pageSettings=(array)($base['settings']??[]);$per=(int)($pageSettings['pageSize']??20);if(!in_array($per,[10,15,20,30,50,100],true))$per=20;$categories=(array)$base['categories'];$allAssets=$surfaceRepo->allAssets($admin);
    $modeAll=vf_fw_mode_assets($allAssets,$mode);
    $scopeCounts=vf_fw_scope_counts($modeAll);
    $scopedMode=vf_fw_filter_scope($modeAll,$scope);
    $scopeGlobal=vf_fw_filter_scope($allAssets,$scope);
    $surfaceCounts=vf_fw_surface_counts($scopeGlobal);
    $categoryId=vf_fw_category_id($categories);
    $categoryCounts=$mode==='start'?vf_fw_category_subtree_counts($scopedMode,$categories):[];
    $categoryMap=vf_fw_category_map($categories);
    $categoryName=$categoryId>0?(string)($categoryMap[$categoryId]['name']??''):'';
    $kindCounts=in_array($mode,['channels','watch','topics','courses','projects','tools','software'],true)?vf_fw_kind_counts($scopedMode,$mode):[];
    $kind=vf_fw_kind_value($kindCounts);

    $q=trim((string)($_GET['q']??''));$view=trim((string)($_GET['view']??'all'));$background=$mode==='channels'&&(string)($_GET['background']??'')==='1';$discover=$mode==='channels'&&(string)($_GET['discover']??'')==='1';$status=$mode==='watch'?trim((string)($_GET['status']??'')):'';$watchYear=$mode==='watch'?max(0,(int)($_GET['year']??0)):0;$watchGenre=$mode==='watch'?trim((string)($_GET['genre']??'')):'';$watchRating=$mode==='watch'?max(0.0,min(10.0,(float)($_GET['rating']??0))):0.0;
    $allowedViews=$mode==='all'?['all','favorite','tags','recent','discover']:($mode==='start'?['all','favorite','popular']:(in_array($mode,['tools','software'],true)?['all','favorite','recent']:['all']));if(!in_array($view,$allowedViews,true))$view='all';
    $recentWindow=$mode==='all'&&$view==='recent'?trim((string)($_GET['recent_window']??'all')):'all';if(!in_array($recentWindow,['7','30','90','all'],true))$recentWindow='all';
    $statusLabels=['want'=>'想看','watching'=>'在看','watched'=>'看过','favorite'=>'珍藏'];if($status!==''&&!isset($statusLabels[$status]))$status='';
    $defaultSort=$mode==='watch'?'title':($view==='recent'?'recent':'default');$sort=trim((string)($_GET['sort']??$defaultSort));if($sort==='year')$sort='year_desc';if(!in_array($sort,['default','title','popular','recent','added','year_desc','year_asc','rating'],true))$sort='default';if(in_array($sort,['added','year_desc','year_asc','rating'],true)&&$mode!=='watch')$sort='default';if($sort==='default'&&$defaultSort!=='default')$sort=$defaultSort;
    $density=(string)($_GET['density']??'comfortable')==='compact'?'compact':'comfortable';$layout=(string)($_GET['layout']??'list')==='cards'?'cards':'list';$page=max(1,(int)($_GET['page']??1));

    $assets=$mode==='start'?vf_fw_filter_category($scopedMode,$categories,$categoryId):vf_fw_filter_kind($scopedMode,$kind,$mode);
    $needle=$q!==''?mb_strtolower($q,'UTF-8'):'';
    if($needle!==''){$assets=array_values(array_filter($assets,static function(array $asset)use($needle):bool{$haystack=mb_strtolower((string)($asset['title']??'').' '.(string)($asset['url']??'').' '.(string)($asset['description']??'').' '.(string)($asset['category_name']??'').' '.(string)($asset['resource_kind']??'').' '.(string)($asset['provider_label']??'').' '.implode(' ',(array)($asset['tags']??[])),'UTF-8');return mb_strpos($haystack,$needle,0,'UTF-8')!==false;}));}
    if($view==='favorite')$assets=array_values(array_filter($assets,static fn(array $x):bool=>(int)($x['is_favorite']??0)===1));
    if($view==='recent'){
        $assets=array_values(array_filter($assets,static fn(array $x):bool=>trim((string)($x['last_surface_opened_at']??''))!==''||(int)($x['click_count']??0)>0));
        if($recentWindow!=='all'){$cutoff=time()-((int)$recentWindow*86400);$assets=array_values(array_filter($assets,static function(array $x)use($cutoff):bool{$raw=trim((string)($x['last_surface_opened_at']??''));if($raw==='')return false;$opened=strtotime($raw);return $opened!==false&&$opened>=$cutoff;}));}
    }
    if($view==='discover'&&count($assets)>1)shuffle($assets);
    if($background&&$admin)$assets=array_values(array_filter($assets,static fn(array $x):bool=>!empty($x['background_friendly'])));
    if($discover&&$admin){$rediscovered=$surfaceRepo->rediscovery('channels',true,500);$ids=array_fill_keys(array_map(static fn(array $x):int=>(int)$x['id'],$assets),true);$assets=array_values(array_filter($rediscovered,static fn(array $x):bool=>isset($ids[(int)$x['id']])));}
    if($status!==''&&$admin)$assets=array_values(array_filter($assets,static fn(array $x):bool=>(string)($x['media_status']??'')===$status));
    $watchYears=[];$watchGenres=[];if($mode==='watch'){foreach($assets as $asset){$y=(int)($asset['media_year']??0);if($y>0)$watchYears[$y]=($watchYears[$y]??0)+1;foreach((array)($asset['tmdb_genres']??[]) as $genreName){$genreName=trim((string)$genreName);if($genreName!=='')$watchGenres[$genreName]=($watchGenres[$genreName]??0)+1;}}krsort($watchYears,SORT_NUMERIC);if($watchGenres)uksort($watchGenres,'strnatcasecmp');if($watchYear>0)$assets=array_values(array_filter($assets,static fn(array $x):bool=>(int)($x['media_year']??0)===$watchYear));if($watchGenre!=='')$assets=array_values(array_filter($assets,static fn(array $x):bool=>in_array($watchGenre,array_map('strval',(array)($x['tmdb_genres']??[])),true)));if($watchRating>0)$assets=array_values(array_filter($assets,static fn(array $x):bool=>(float)($x['tmdb_rating']??0)>=$watchRating));}

    if($view!=='discover'&&!$discover){usort($assets,static function(array $a,array $b)use($sort,$mode,$view,$needle):int{if($sort==='default'&&$needle!==''){
        $score=static function(array $asset)use($needle):int{
            $title=mb_strtolower(trim((string)($asset['title']??'')),'UTF-8');$url=mb_strtolower((string)($asset['url']??''),'UTF-8');$category=mb_strtolower((string)($asset['category_name']??''),'UTF-8');$description=mb_strtolower((string)($asset['description']??''),'UTF-8');$provider=mb_strtolower((string)($asset['provider_label']??''),'UTF-8');$kind=mb_strtolower((string)($asset['resource_kind']??''),'UTF-8');$tags=array_map(static fn($tag):string=>mb_strtolower(trim((string)$tag),'UTF-8'),(array)($asset['tags']??[]));
            $points=0;if($title===$needle)$points+=1000;elseif(str_starts_with($title,$needle))$points+=850;elseif(mb_strpos($title,$needle,0,'UTF-8')!==false)$points+=650;
            if(in_array($needle,$tags,true))$points+=500;elseif(implode(' ',$tags)!==''&&mb_strpos(implode(' ',$tags),$needle,0,'UTF-8')!==false)$points+=220;
            if(mb_strpos($url,$needle,0,'UTF-8')!==false)$points+=300;if(mb_strpos($category,$needle,0,'UTF-8')!==false)$points+=240;if(mb_strpos($provider,$needle,0,'UTF-8')!==false)$points+=160;if(mb_strpos($kind,$needle,0,'UTF-8')!==false)$points+=140;if(mb_strpos($description,$needle,0,'UTF-8')!==false)$points+=80;
            return $points;
        };
        $as=$score($a);$bs=$score($b);if($as!==$bs)return $bs<=>$as;$order=((int)($a['sort_order']??0)<=>(int)($b['sort_order']??0));if($order!==0)return $order;return strnatcasecmp((string)$a['title'],(string)$b['title']);
    }if($sort==='title')return strnatcasecmp((string)$a['title'],(string)$b['title']);if($sort==='popular')return ((int)($b['click_count']??0)<=>(int)($a['click_count']??0))?:strnatcasecmp((string)$a['title'],(string)$b['title']);if($sort==='recent'){$ad=(string)($a['last_surface_opened_at']??'');$bd=(string)($b['last_surface_opened_at']??'');if($ad!==$bd)return strcmp($bd,$ad);return strcmp((string)($b['updated_at']??''),(string)($a['updated_at']??''));}if($sort==='added'&&$mode==='watch')return strcmp((string)($b['created_at']??''),(string)($a['created_at']??''))?:strnatcasecmp((string)$a['title'],(string)$b['title']);if($sort==='rating'&&$mode==='watch')return ((float)($b['tmdb_rating']??0)<=>(float)($a['tmdb_rating']??0))?:((int)($b['tmdb_vote_count']??0)<=>(int)($a['tmdb_vote_count']??0))?:strnatcasecmp((string)$a['title'],(string)$b['title']);if($sort==='year_desc'&&$mode==='watch')return ((int)($b['media_year']??0)<=>(int)($a['media_year']??0))?:strnatcasecmp((string)$a['title'],(string)$b['title']);if($sort==='year_asc'&&$mode==='watch'){$ay=(int)($a['media_year']??0);$by=(int)($b['media_year']??0);if($ay<=0)return 1;if($by<=0)return -1;return ($ay<=>$by)?:strnatcasecmp((string)$a['title'],(string)$b['title']);}if($sort==='default'&&$view==='favorite'){$ar=(int)($a['favorite_rank']??0);$br=(int)($b['favorite_rank']??0);if($ar>0||$br>0){if($ar<=0)return 1;if($br<=0)return -1;if($ar!==$br)return $ar<=>$br;}$updated=strcmp((string)($b['updated_at']??''),(string)($a['updated_at']??''));if($updated!==0)return $updated;return strnatcasecmp((string)$a['title'],(string)$b['title']);}return ((int)($a['sort_order']??0)<=>(int)($b['sort_order']??0))?:strnatcasecmp((string)$a['title'],(string)$b['title']);});}

    $favoriteCount=count(array_filter($scopedMode,static fn(array $x):bool=>(int)($x['is_favorite']??0)===1));$statusCounts=['want'=>0,'watching'=>0,'watched'=>0,'favorite'=>0];if($mode==='watch'){foreach(vf_fw_filter_kind($scopedMode,$kind,$mode) as $asset){$key=(string)($asset['media_status']??'');if(isset($statusCounts[$key]))$statusCounts[$key]++;}}
    $tags=[];if($mode==='all'&&$view==='tags'){foreach($scopedMode as $asset){foreach((array)($asset['tags']??[])as $name){$name=trim((string)$name);if($name!=='')$tags[$name]=($tags[$name]??0)+1;}}if($tags)uksort($tags,'strnatcasecmp');$tag=trim((string)($_GET['tag']??''));if($tag!=='')$assets=array_values(array_filter($assets,static fn(array $x):bool=>in_array($tag,array_map('strval',(array)($x['tags']??[])),true)));}

    $total=count($assets);$pages=max(1,(int)ceil($total/$per));if($page>$pages)$page=$pages;$pageAssets=array_slice($assets,($page-1)*$per,$per);$rangeStart=$total>0?(($page-1)*$per+1):0;$rangeEnd=$total>0?min($page*$per,$total):0;$pageWindowStart=max(1,$page-2);$pageWindowEnd=min($pages,$page+2);
    $pending=$admin?count(array_filter($allAssets,static fn(array $asset):bool=>(int)($asset['is_pending']??0)===1)):0;
    $title=$q!==''?'搜索结果':vf_fw_mode_label($mode);if($mode==='all')$title=match($view){'favorite'=>'我的收藏','tags'=>'标签','recent'=>'最近使用','discover'=>'随机发现',default=>$title};
    $activeView=$mode==='all'?$view:$mode;
    $domainEmpty=count($modeAll)===0;
    $emptyTitle=$domainEmpty?match($mode){'start'=>'还没有导航资源','channels'=>'还没有频道','watch'=>'还没有影视内容','topics'=>'还没有专题','courses'=>'还没有课程','projects'=>'还没有项目','tools'=>'还没有匹配现有资源的工具','software'=>'还没有匹配现有资源的软件',default=>'资源库还是空的'}:'没有找到符合条件的内容';
    $emptyCopy=$domainEmpty?($admin?'从添加入口开始建立这个资源域。':'这个资源域暂时还没有可显示的内容。'):($q!==''?'换一个关键词，或调整可见范围、分类和筛选条件后再试。':'调整可见范围、分类或筛选条件继续查找。');
    $searchUrlCandidate='';
    if($admin&&$q!==''&&$mode==='all'&&$total===0){try{$searchUrlCandidate=vf_validate_url($q);}catch(Throwable $ignored){}}
    $branding=['logoUrl'=>''];try{$branding=$baseRepo->getBranding();}catch(Throwable $ignored){}$logoUrl=trim((string)($branding['logoUrl']??''));
    $legacyProjectHost=strtolower(trim((string)($_SERVER['HTTP_HOST']??'')));$legacyProjectHost=(string)preg_replace('/:\d+$/','',$legacyProjectHost);
    $legacyProjectImportAvailable=false;
    if($admin&&$mode==='projects'&&$legacyProjectHost==='start.kewaro.com'){
        try{$stmt=$db->prepare("SELECT setting_value FROM settings WHERE setting_key='projects_legacy_import_available'");$stmt->execute();$legacyProjectImportAvailable=(string)$stmt->fetchColumn()==='1';}catch(Throwable $ignored){}
    }
    $legacyProjectImportState=$mode==='projects'?trim((string)($_GET['legacy_import']??'')):'';
    $legacyProjectImportCreated=max(0,(int)($_GET['created']??0));
    $legacyProjectImportReused=max(0,(int)($_GET['reused']??0));
    $bookCatalogImportState=$mode==='courses'?trim((string)($_GET['catalog_import']??'')):'';
    $bookCatalogCreated=max(0,(int)($_GET['created']??0));
    $bookCatalogUpdated=max(0,(int)($_GET['updated']??0));
    $bookCatalogReused=max(0,(int)($_GET['reused']??0));
    $bookCatalogSkipped=max(0,(int)($_GET['skipped']??0));
    $bookCatalogTotal=max(0,(int)($_GET['total']??0));
    $publicStart = !$admin && $mode === 'start';
    $seoSettings = $publicStart ? $baseRepo->getSettings() : [];
    $seoEnabled = $publicStart && !empty($seoSettings['seoEnabled']);
    $seoBase = $publicStart ? rtrim(vf_seo_base_url(), '/') : '';
    $siteTitle = trim((string)(vf_config()['site_title'] ?? 'VF Start')) ?: 'VF Start';
    $seoTitle = $publicStart ? trim((string)($seoSettings['seoHomeTitle'] ?? '')) : '';
    if ($seoTitle === '') $seoTitle = $title . ' · VF Start';
    $seoDescription = $publicStart ? vf_seo_clean((string)($seoSettings['seoHomeDescription'] ?? '公开网址导航与实用工具目录，按真实工作用途整理。'), 180) : '';
    if ($seoEnabled && !is_file(VF_ROOT . '/sitemap.xml')) {
        try { vf_seo_rebuild($db, vf_config(), $seoSettings, $seoBase, VF_VERSION); } catch (Throwable $ignored) {}
    }

    ?><!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="theme-color" content="#0f766e">
<meta name="robots" content="<?=$seoEnabled?'index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1':'noindex,nofollow,noarchive'?>">
<?php if($publicStart): ?><meta name="description" content="<?=vf_fw_h($seoDescription)?>"><link rel="canonical" href="<?=vf_fw_h($seoBase . '/')?>"><meta property="og:title" content="<?=vf_fw_h($seoTitle)?>"><meta property="og:description" content="<?=vf_fw_h($seoDescription)?>"><meta property="og:url" content="<?=vf_fw_h($seoBase . '/')?>"><meta property="og:type" content="website"><meta name="twitter:card" content="summary"><?php if($seoEnabled): ?><script type="application/ld+json"><?=json_encode(['@context'=>'https://schema.org','@type'=>'WebSite','name'=>$siteTitle,'url'=>$seoBase . '/','description'=>$seoDescription],JSON_UNESCAPED_UNICODE|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT)?></script><?php endif; ?><?php endif; ?>
<title><?=vf_fw_h($publicStart?$seoTitle:($title . ' · VF Start'))?></title>
<link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/surfaces.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/surface-workspace.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/workspace-v228.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/workspace-rebaseline.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/resource-media.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/resource-actions.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/workspace-domain-nav.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/workspace-projects.css'))?>"><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/quick-open.css'))?>"><?php if($mode==='watch'): ?><link rel="stylesheet" href="<?=vf_fw_h(vf_asset_url('assets/watch-metadata.css'))?>"><?php endif; ?>
<script src="<?=vf_fw_h(vf_asset_url('assets/surface-home.js'))?>" defer></script><script src="<?=vf_fw_h(vf_asset_url('assets/quick-open.js'))?>" defer></script><script src="<?=vf_fw_h(vf_asset_url('assets/workspace.js'))?>" defer></script><script src="<?=vf_fw_h(vf_asset_url('assets/workspace-rebaseline.js'))?>" defer></script><script src="<?=vf_fw_h(vf_asset_url('assets/workspace-primary-open.js'))?>" defer></script><?php if($mode==='watch'&&$admin): ?><script src="<?=vf_fw_h(vf_asset_url('assets/watch-metadata.js'))?>" defer></script><?php endif; ?>
</head><body class="vf-surface-app vf-workspace-page vf-functional-workspace surface-<?=vf_fw_h($mode)?>" data-vf-scope="<?=vf_fw_h($scope)?>" data-vf-mode="<?=vf_fw_h($mode)?>">
<?php vf_fw_render_sidebar(['mode'=>$mode,'scope'=>$scope,'admin'=>$admin,'surface_counts'=>$surfaceCounts,'scope_counts'=>$scopeCounts,'categories'=>$categories,'category_counts'=>$categoryCounts,'category_id'=>$categoryId,'category_total'=>count($scopedMode),'kind_counts'=>$kindCounts,'kind'=>$kind,'pending'=>$pending,'active_view'=>$activeView,'logo_url'=>$logoUrl]); ?>
<section class="vf-app-stage"><?php vf_fw_render_global_domain_nav($mode,$admin,$scope); ?><header class="vf-app-topbar vf-domain-subbar"><form class="vf-global-search" action="surfaces.php" method="get"><span>⌕</span><input type="search" name="q" value="<?=vf_fw_h($q)?>" placeholder="搜索我的互联网" autocomplete="off"><kbd>⌘ K</kbd></form><div class="vf-top-actions"><?php if($admin): ?><button type="button" class="vf-context-action vf-new-action" data-open-add><span>＋</span><b>添加</b></button><?php endif; ?><button type="button" class="vf-theme-toggle" data-theme-toggle aria-label="切换主题">◐</button></div></header><main class="vf-shell-main">
<?php vf_fw_render_head(['mode'=>$mode,'title'=>$title,'scope'=>$scope,'admin'=>$admin,'category_id'=>$categoryId,'category_name'=>$categoryName,'kind'=>$kind,'kind_label'=>vf_fw_kind_label($mode),'q'=>$q,'total'=>$total,'range_start'=>$rangeStart,'range_end'=>$rangeEnd]); ?>
<?php if($admin&&$mode==='projects'&&$legacyProjectImportAvailable): ?>
<section class="vf-project-import-notice" aria-label="旧 Kewaro 项目迁移">
  <div><strong>迁移旧 Kewaro 项目入口</strong><span>把原来的 P01–P06 入口变成这里可编辑、可移动的项目资源。已有网址会复用，缺失项才创建；P03 / P06 保持已退役。</span></div>
  <form action="projects-kewaro-import.php" method="post"><input type="hidden" name="csrf" value="<?=vf_fw_h(vf_csrf_token())?>"><button type="submit">导入 P01–P06</button></form>
</section>
<?php elseif($admin&&$mode==='projects'&&$legacyProjectImportState==='done'): ?>
<div class="vf-project-import-result success">Kewaro 项目迁移完成：新建 <?=$legacyProjectImportCreated?> 项，复用 <?=$legacyProjectImportReused?> 项。</div>
<?php elseif($admin&&$mode==='projects'&&$legacyProjectImportState==='already'): ?>
<div class="vf-project-import-result">Kewaro 项目已经迁移过，没有重复创建。</div>
<?php elseif($admin&&$mode==='projects'&&$legacyProjectImportState==='error'): ?>
<div class="vf-project-import-result error">Kewaro 项目迁移未完成，数据已回滚；请检查系统日志后重试。</div>
<?php endif; ?>
<?php if($admin&&$mode==='courses'): ?>
<section class="vf-books-import-notice" aria-label="导入 Git 图书目录">
  <div><strong>导入 / 更新 Git 图书目录</strong><span>上传 BOOK_CATALOG.json。P01 只保存书籍信息和正式 Git 阅读入口，正文继续由原 Git 仓库维护；同一本书再次导入会原地更新，不会重复创建。</span></div>
  <form action="books-catalog-import.php" method="post" enctype="multipart/form-data">
    <input type="hidden" name="csrf" value="<?=vf_fw_h(vf_csrf_token())?>">
    <input type="file" name="catalog" accept=".json,application/json" required aria-label="选择 BOOK_CATALOG.json">
    <button type="submit">导入 / 更新</button>
  </form>
</section>
<?php if($bookCatalogImportState==='done'): ?>
<div class="vf-books-import-result success">图书目录处理完成：目录 <?=$bookCatalogTotal?> 本 · 新建 <?=$bookCatalogCreated?> · 更新 <?=$bookCatalogUpdated?> · 复用 <?=$bookCatalogReused?><?php if($bookCatalogSkipped>0): ?> · 跳过 <?=$bookCatalogSkipped?><?php endif; ?>。</div>
<?php elseif($bookCatalogImportState==='error'): ?>
<div class="vf-books-import-result error">图书目录导入未完成，事务已回滚。请确认目录格式、Git 仓库信息和 source_path 后重试。</div>
<?php endif; ?>
<?php endif; ?>
<?php if($q!==''&&$mode==='all'&&$total===0): ?><div class="vf-search-fallback<?= $searchUrlCandidate!==''?' is-url-candidate':'' ?>"><span>个人资源里没有找到。</span><?php if($searchUrlCandidate!==''): ?><span class="vf-search-fallback-actions"><button type="button" data-open-add data-prefill-url="<?=vf_fw_h($searchUrlCandidate)?>">保存这个网址 →</button><a href="<?=vf_fw_h($searchUrlCandidate)?>" target="_blank" rel="noopener noreferrer">直接打开 ↗</a></span><?php else: ?><a href="https://www.google.com/search?q=<?=rawurlencode($q)?>" target="_blank" rel="noopener noreferrer">在 Google 搜索“<?=vf_fw_h($q)?>” →</a><?php endif; ?></div><?php endif; ?>
<?php vf_fw_render_mobile_filters($mode,$admin,$scope,$categories,$categoryCounts,$categoryId,$kindCounts,$kind); ?>
<?php if($admin&&$pending>0&&$mode==='all'&&$view==='all'&&$q===''): ?><a class="vf-workspace-notice" href="surface-manager.php"><span><b><?=$pending?></b> 条内容等待确认归属</span><em>去整理 →</em></a><?php endif; ?>
<?php vf_fw_render_toolbar(['mode'=>$mode,'view'=>$view,'sort'=>$sort,'per'=>$per,'density'=>$density,'layout'=>$layout,'admin'=>$admin,'background'=>$background,'discover'=>$discover,'status'=>$status,'status_counts'=>$statusCounts,'favorite_count'=>$favoriteCount,'kind'=>$kind,'watch_year'=>$watchYear,'watch_genre'=>$watchGenre,'watch_rating'=>$watchRating,'watch_years'=>$watchYears,'watch_genres'=>$watchGenres]); ?>
<?php if($mode==='all'&&$view==='recent'): ?><div class="vf-collection-filter" aria-label="最近使用时间范围"><span>时间范围</span><select aria-label="最近使用时间范围" data-vf-location-select><?php foreach(['7'=>'最近 7 天','30'=>'最近 30 天','90'=>'最近 90 天','all'=>'全部历史'] as $key=>$label): ?><option value="<?=vf_fw_link($mode,['recent_window'=>$key==='all'?null:$key,'page'=>null])?>" <?=$recentWindow===$key?'selected':''?>><?=vf_fw_h($label)?></option><?php endforeach; ?></select></div><?php endif; ?>
<?php if($mode==='all'&&$view==='tags'): ?><section class="vf-tag-cloud" aria-label="标签"><a class="<?=trim((string)($_GET['tag']??''))===''?'active':''?>" href="<?=vf_fw_link($mode,['tag'=>null])?>">全部</a><?php foreach($tags as $name=>$count): ?><a class="<?=trim((string)($_GET['tag']??''))===$name?'active':''?>" href="<?=vf_fw_link($mode,['tag'=>$name])?>">#<?=vf_fw_h((string)$name)?> <small><?=number_format((int)$count)?></small></a><?php endforeach; ?></section><?php endif; ?>
<?php if(!$pageAssets): ?><section class="vf-workspace-list"><div class="vf-workspace-empty"><strong><?=vf_fw_h($emptyTitle)?></strong><p><?=vf_fw_h($emptyCopy)?></p></div></section><?php elseif($mode==='watch'): ?><section class="vf-watch-grid" aria-label="影视"><?php foreach($pageAssets as $index=>$asset)vf_fw_render_watch_card($asset,$admin,$index<8); ?></section><?php elseif($mode==='topics'): ?><section class="vf-topic-grid" aria-label="专题"><?php foreach($pageAssets as $index=>$asset)vf_fw_render_topic_card($asset,$admin,$index<8); ?></section><?php elseif($mode==='courses'): ?><section class="vf-books-grid" aria-label="课程"><?php foreach($pageAssets as $index=>$asset)vf_fw_render_book_card($asset,$admin,$index<8); ?></section><?php elseif($mode==='projects'): ?><section class="vf-projects-grid" aria-label="项目"><?php foreach($pageAssets as $index=>$asset)vf_fw_render_project_card($asset,$admin,$index<8); ?></section><?php else: ?><section class="<?=$layout==='cards'&&($mode==='all'||$mode==='start')?'vf-card-grid':'vf-workspace-list '.$density?>" aria-label="资源列表"><?php foreach($pageAssets as $index=>$asset){if($layout==='cards'&&($mode==='all'||$mode==='start')){?><article class="vf-asset-card" data-asset-row="<?=(int)$asset['id']?>"><?php $cardFav=(int)($asset['is_favorite']??0)===1; if($admin): ?><label class="vf-asset-select"><input type="checkbox" value="<?=(int)$asset['id']?>" data-select-asset aria-label="选择 <?=vf_fw_h((string)$asset['title'])?>"></label><?php endif; ?><span class="vf-asset-icon" data-edit-id="<?=(int)$asset['id']?>"><?=vf_fw_icon($asset,$index<12)?></span><span class="vf-asset-copy" data-edit-id="<?=(int)$asset['id']?>"><strong><?=vf_fw_h((string)$asset['title'])?></strong><small><?=vf_fw_h((string)(((string)($asset['surface']??'start')==='start')?($asset['category_name']??''):($asset['resource_kind']??'')))?></small></span><span class="vf-asset-meta"><?php if($admin&&vf_fw_is_private($asset)): ?><i class="vf-chip private">私人</i><?php endif; ?><?php if((string)($asset['surface']??'start')!=='start'): ?><i class="vf-chip teal"><?=vf_fw_h(vf_fw_mode_label((string)$asset['surface']))?></i><?php endif; ?><span class="vf-asset-actions"><?php if($admin): ?><button type="button" class="vf-icon-button <?=$cardFav?'active':''?>" data-favorite-id="<?=(int)$asset['id']?>" data-favorite="<?=$cardFav?'1':'0'?>" aria-label="<?=$cardFav?'取消收藏':'收藏'?>" title="<?=$cardFav?'取消收藏':'收藏'?>"><?=$cardFav?'★':'☆'?></button><button type="button" class="vf-icon-button" data-edit-id="<?=(int)$asset['id']?>" aria-label="编辑" title="编辑">✎</button><?php endif; ?><a class="vf-icon-button" href="<?=vf_fw_open_href($asset,$admin)?>" target="_blank" rel="noopener noreferrer" aria-label="打开" title="打开">↗</a></span></span></article><?php }else vf_fw_render_row($asset,$admin,$mode==='all',$index<12);} ?></section><?php endif; ?>
<?php if($pages>1): ?><div class="vf-pagination"><span>第 <?=$rangeStart?>–<?=$rangeEnd?> 项 · 共 <?=number_format($total)?> 项 · <?=$pages?> 页</span><nav><?php if($page>1): ?><a href="<?=vf_fw_link($mode,['page'=>1])?>">«</a><a href="<?=vf_fw_link($mode,['page'=>$page-1])?>">‹</a><?php endif; ?><?php for($p=$pageWindowStart;$p<=$pageWindowEnd;$p++): ?><?php if($p===$page): ?><span class="page"><?=$p?></span><?php else: ?><a href="<?=vf_fw_link($mode,['page'=>$p])?>"><?=$p?></a><?php endif; ?><?php endfor; ?><?php if($page<$pages): ?><a href="<?=vf_fw_link($mode,['page'=>$page+1])?>">›</a><a href="<?=vf_fw_link($mode,['page'=>$pages])?>">»</a><?php endif; ?></nav></div><?php endif; ?>
<script type="application/json" id="vf-functional-context"><?=vf_fw_context_json($categories,$scope,$mode)?></script>
<?php if($admin)vf_workspace_payload($pageAssets,$categories); ?>
</main></section></body></html><?php
}
