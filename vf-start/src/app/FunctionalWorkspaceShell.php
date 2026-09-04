<?php
declare(strict_types=1);
require_once __DIR__ . '/FunctionalWorkspaceCore.php';

function vf_fw_render_category_nodes(array $categories, array $counts, string $mode, int $selectedId, int $parentId = 0): void
{
    $children = vf_fw_category_children($categories);
    $map = vf_fw_category_map($categories);
    $selectedPath = vf_fw_selected_path($categories, $selectedId);
    foreach ($children[$parentId] ?? [] as $id) {
        $id = (int)$id;
        $category = $map[$id] ?? null;
        if (!$category) continue;
        $count = (int)($counts[$id] ?? 0);
        $childIds = $children[$id] ?? [];
        $hasVisibleChild = !empty($childIds);
        $name = (string)($category['name'] ?? '未命名分类');
        $active = $selectedId === $id;
        $href = vf_fw_link($mode, ['category' => $id]);
        $label = vf_fw_h($name);
        $nodeClass = 'vf-category-node' . ($active ? ' active' : '');
        if ($hasVisibleChild) {
            $open = isset($selectedPath[$id]) || $parentId === 0;
            echo '<details class="' . $nodeClass . '" data-category-node data-label="' . vf_fw_h(mb_strtolower($name, 'UTF-8')) . '"' . ($open ? ' open' : '') . '>';
            echo '<summary><span class="vf-category-caret">›</span><a href="' . $href . '"><span>' . $label . '</span><em>' . number_format($count) . '</em></a></summary>';
            echo '<div class="vf-category-children">';
            vf_fw_render_category_nodes($categories, $counts, $mode, $selectedId, $id);
            echo '</div></details>';
        } else {
            echo '<a class="' . $nodeClass . '" data-category-node data-label="' . vf_fw_h(mb_strtolower($name, 'UTF-8')) . '" href="' . $href . '"><span>' . $label . '</span><em>' . number_format($count) . '</em></a>';
        }
    }
}

function vf_fw_render_kind_nodes(array $counts, string $mode, string $selectedKind): void
{
    foreach ($counts as $name => $count) {
        $name = (string)$name;
        $display = vf_fw_kind_display_label($mode, $name);
        $active = $selectedKind === $name;
        $searchLabel = mb_strtolower(trim($display . ' ' . $name), 'UTF-8');
        echo '<a class="vf-category-node' . ($active ? ' active' : '') . '" data-category-node data-label="' . vf_fw_h($searchLabel) . '" href="' . vf_fw_link($mode, ['kind'=>$name]) . '"><span>' . vf_fw_h($display) . '</span><em>' . number_format((int)$count) . '</em></a>';
    }
}

function vf_fw_render_global_domain_nav(string $mode, bool $admin, string $scope): void
{
    $items = VfWorkspaceViewCatalog::entries($admin);
    ?>
<nav class="vf-global-domain-nav" aria-label="VF Start 资源域">
  <div class="vf-global-domain-nav-inner">
    <?php foreach($items as $item):
        $key = (string)$item['mode'];
        $label = (string)$item['label'];
        $href = $key === 'home' ? 'home.php' : vf_fw_route_link($key, $admin ? $scope : 'public', 0);
    ?><a class="<?=$mode===$key?'active':''?>" href="<?=$href?>" aria-current="<?=$mode===$key?'page':'false'?>"><?=vf_fw_h($label)?></a><?php endforeach; ?>
    <?php if($admin): ?><a href="#" class="vf-global-auth-action" data-vf-auth-logout>退出</a><?php else: ?><a href="#" class="vf-global-auth-action" data-vf-auth-login>登录</a><?php endif; ?>
  </div>
</nav>
<?php
}

function vf_fw_render_sidebar(array $options): void
{
    $mode = (string)$options['mode'];
    $scope = (string)$options['scope'];
    $admin = (bool)$options['admin'];
    $surfaceCounts = (array)$options['surface_counts'];
    $scopeCounts = (array)$options['scope_counts'];
    $categories = (array)$options['categories'];
    $categoryCounts = (array)$options['category_counts'];
    $categoryId = (int)$options['category_id'];
    $kindCounts = (array)($options['kind_counts'] ?? []);
    $kind = (string)($options['kind'] ?? '');
    $pending = (int)$options['pending'];
    $categoryTotal = (int)($options['category_total'] ?? 0);
    $activeView = (string)$options['active_view'];
    $logoUrl = (string)$options['logo_url'];
    $brandHref = $admin ? 'home.php' : 'index.php';
    $primary = VfWorkspaceViewCatalog::entries($admin);
    ?>
<aside class="vf-app-sidebar vf-functional-sidebar" aria-label="VF Start 导航">
  <a class="vf-app-brand" href="<?=vf_fw_h($brandHref)?>" aria-label="VF Start 首页">
    <span class="vf-brand-mark<?= $logoUrl !== '' ? ' has-custom-logo' : '' ?>"><?php if($logoUrl !== ''): ?><img src="<?=vf_fw_h($logoUrl)?>" alt=""><?php else: ?>VF<?php endif; ?></span>
    <span><strong>VF Start</strong><small>P01 · 个人互联网资产</small></span>
  </a>
  <div class="vf-sidebar-scroll" data-functional-sidebar-scroll>
    <div class="vf-nav-section vf-nav-section-first"><span>资源</span></div>
    <nav class="vf-main-nav" aria-label="资源类型">
      <?php foreach($primary as $item):
          $key=(string)$item['mode'];$icon=(string)$item['icon'];$label=(string)$item['label'];
          $target=$key==='home'?'home.php':vf_fw_route_link($key,$admin?$scope:'public',$categoryId);
          $count=$key==='home'?null:(int)($surfaceCounts[$key]??0);
      ?><a class="<?=$mode===$key?'active':''?>" href="<?=$target?>"><span class="vf-nav-icon"><?=$icon?></span><b><?=$label?></b><?php if($count!==null): ?><em><?=number_format($count)?></em><?php endif; ?></a><?php endforeach; ?>
    </nav>

    <?php if($mode==='all'||$mode==='home'): ?>
    <div class="vf-nav-section"><span>快捷入口</span></div>
    <nav class="vf-secondary-nav vf-quick-nav" aria-label="快捷入口">
      <a class="<?=$mode==='all'&&$activeView==='all'?'active':''?>" href="<?=vf_fw_route_link('all',$admin?$scope:'public',0)?>"><span>▣</span><b>全部资源</b><em><?=number_format((int)($surfaceCounts['total']??0))?></em></a>
      <a class="<?=$mode==='all'&&$activeView==='favorite'?'active':''?>" href="<?=vf_fw_route_link('all',$admin?$scope:'public',0,['view'=>'favorite'])?>"><span>☆</span><b>我的收藏</b></a>
      <a class="<?=$mode==='all'&&$activeView==='recent'?'active':''?>" href="<?=vf_fw_route_link('all',$admin?$scope:'public',0,['view'=>'recent'])?>"><span>◷</span><b>最近使用</b></a>
      <?php if($admin): ?><a class="<?=$activeView==='inbox'?'active':''?>" href="surface-manager.php"><span>◇</span><b>待整理</b><?php if($pending>0): ?><em><?=number_format($pending)?></em><?php endif; ?></a><?php endif; ?>
      <a class="<?=$mode==='all'&&$activeView==='tags'?'active':''?>" href="<?=vf_fw_route_link('all',$admin?$scope:'public',0,['view'=>'tags'])?>"><span>#</span><b>标签</b></a>
      <a class="<?=$mode==='all'&&$activeView==='discover'?'active':''?>" href="<?=vf_fw_route_link('all',$admin?$scope:'public',0,['view'=>'discover'])?>"><span>✦</span><b>随机发现</b></a>
    </nav>
    <?php endif; ?>

    <?php if($admin): ?>
    <section class="vf-sidebar-scope-section" aria-label="可见范围">
      <div class="vf-nav-section"><span>可见范围</span></div>
      <div class="vf-sidebar-scope" role="tablist" aria-label="资源可见范围">
        <?php foreach(['all'=>'全部','public'=>'公开','private'=>'私人'] as $key=>$label): ?>
          <a class="<?=$scope===$key?'active':''?>" href="<?=vf_fw_link($mode,['scope'=>$key==='all'?null:$key])?>" role="tab" aria-selected="<?=$scope===$key?'true':'false'?>"><span><?=$label?></span><b><?=number_format((int)($scopeCounts[$key]??0))?></b></a>
        <?php endforeach; ?>
      </div>
    </section>
    <?php endif; ?>

    <?php if($mode==='start'): ?>
    <section class="vf-category-section" aria-label="导航分类">
      <div class="vf-category-title"><span>导航分类</span><?php if($categoryId>0): ?><a href="<?=vf_fw_link($mode,['category'=>null])?>">清除</a><?php endif; ?></div>
      <label class="vf-category-search"><span>⌕</span><input type="search" placeholder="筛选分类" data-category-search autocomplete="off"></label>
      <nav class="vf-category-tree" aria-label="导航分类树">
        <a class="vf-category-all<?=$categoryId===0?' active':''?>" href="<?=vf_fw_link($mode,['category'=>null])?>"><span>全部分类</span><em><?=number_format($categoryTotal)?></em></a>
        <?php vf_fw_render_category_nodes($categories,$categoryCounts,$mode,$categoryId,0); ?>
      </nav>
    </section>
    <?php elseif(in_array($mode,['channels','watch','topics','courses','projects','tools','software'],true)): ?>
    <section class="vf-category-section" aria-label="<?=vf_fw_h(vf_fw_kind_label($mode))?>">
      <div class="vf-category-title"><span><?=vf_fw_h(vf_fw_kind_label($mode))?></span><?php if($kind!==''): ?><a href="<?=vf_fw_link($mode,['kind'=>null])?>">清除</a><?php endif; ?></div>
      <?php if(count($kindCounts)>8): ?><label class="vf-category-search"><span>⌕</span><input type="search" placeholder="筛选分类" data-category-search autocomplete="off"></label><?php endif; ?>
      <nav class="vf-category-tree" aria-label="<?=vf_fw_h(vf_fw_kind_label($mode))?>">
        <a class="vf-category-all<?=$kind===''?' active':''?>" href="<?=vf_fw_link($mode,['kind'=>null])?>"><span>全部</span><em><?=number_format($categoryTotal)?></em></a>
        <?php vf_fw_render_kind_nodes($kindCounts,$mode,$kind); ?>
      </nav>
    </section>
    <?php endif; ?>
  </div>
  <div class="vf-sidebar-bottom">
    <?php if($admin): ?>
      <a href="recycle-bin.php">♲ <span>回收站</span></a>
      <a href="surface-manager.php?advanced=1">☷ <span>资源管理</span></a>
      <a href="settings.php">⚙ <span>设置</span></a>
      <a href="#" data-vf-auth-logout>↪ <span>退出</span></a>
    <?php else: ?>
      <a href="#" data-vf-auth-login>↪ <span>登录</span></a>
    <?php endif; ?>
    <small>VF Start · V<?=vf_fw_h(VF_VERSION)?></small>
  </div>
</aside>
<script src="<?=vf_fw_h(vf_asset_url('assets/auth-controls.js'))?>" defer></script>
<?php
}

function vf_fw_render_head(array $context): void
{
    $title = (string)$context['title'];
    $scope = (string)$context['scope'];
    $admin = (bool)$context['admin'];
    $categoryName = (string)$context['category_name'];
    $kind = (string)($context['kind'] ?? '');
    $kindLabel = (string)($context['kind_label'] ?? '主分类');
    $q = (string)$context['q'];
    $total = (int)$context['total'];
    $rangeStart = (int)$context['range_start'];
    $rangeEnd = (int)$context['range_end'];
    $mode = (string)($context['mode'] ?? vf_fw_mode());
    $categoryId = (int)($context['category_id'] ?? 0);
    ?>
<div class="vf-mobile-command-row" aria-label="移动端快速操作">
  <form class="vf-mobile-command-search" action="surfaces.php" method="get">
    <span aria-hidden="true">⌕</span><input type="search" name="q" value="<?=vf_fw_h($q)?>" placeholder="搜索我的互联网" autocomplete="off"><button type="submit">搜索</button>
  </form>
  <?php if($admin): ?><button type="button" class="vf-mobile-command-add" data-open-add>＋ 添加</button><?php endif; ?>
</div>
<section class="vf-workspace-head vf-functional-head">
  <div>
    <h1><?=vf_fw_h($title)?></h1>
    <p class="vf-workspace-count"><?php if($q!==''): ?>“<?=vf_fw_h($q)?>” · <?php endif; ?><?=number_format($total)?> 项<?php if($total>0): ?> · 当前 <?=$rangeStart?>–<?=$rangeEnd?><?php endif; ?></p>
    <div class="vf-context-chips" aria-label="当前筛选上下文">
      <?php if($admin&&$scope!=='all'): ?><span class="vf-context-chip <?=$scope==='private'?'private':''?>"><?=vf_fw_scope_label($scope)?></span><?php endif; ?>
      <?php if($categoryName!==''): ?><span class="vf-context-chip">导航分类：<?=vf_fw_h($categoryName)?></span><?php endif; ?>
      <?php if($kind!==''): ?><span class="vf-context-chip"><?=vf_fw_h($kindLabel)?>：<?=vf_fw_h(vf_fw_kind_display_label($mode,$kind))?></span><?php endif; ?>
    </div>
  </div>
</section>
<?php
}

function vf_fw_render_mobile_filters(string $mode, bool $admin, string $scope, array $categories, array $categoryCounts, int $categoryId, array $kindCounts = [], string $kind = ''): void
{
    ?>
<div class="vf-mobile-functional-filters" aria-label="移动端筛选">
  <?php if($admin): ?><select data-vf-location-select aria-label="可见范围"><option value="<?=vf_fw_link($mode,['scope'=>null])?>" <?=$scope==='all'?'selected':''?>>全部范围</option><option value="<?=vf_fw_link($mode,['scope'=>'public'])?>" <?=$scope==='public'?'selected':''?>>公开</option><option value="<?=vf_fw_link($mode,['scope'=>'private'])?>" <?=$scope==='private'?'selected':''?>>私人</option></select><?php endif; ?>
  <?php if($mode==='start'): ?><select data-vf-location-select aria-label="导航分类"><option value="<?=vf_fw_link($mode,['category'=>null])?>">全部分类</option><?php foreach($categories as $category): $id=(int)($category['id']??0); if($id<=0||(int)($categoryCounts[$id]??0)<=0)continue; ?><option value="<?=vf_fw_link($mode,['category'=>$id])?>" <?=$categoryId===$id?'selected':''?>><?=str_repeat('　',min(3,(int)($category['depth']??0)))?><?=vf_fw_h((string)($category['name']??''))?> · <?=number_format((int)$categoryCounts[$id])?></option><?php endforeach; ?></select><?php endif; ?>
  <?php if(in_array($mode,['channels','watch','topics','courses','projects','tools','software'],true)): ?><select data-vf-location-select aria-label="<?=vf_fw_h(vf_fw_kind_label($mode))?>"><option value="<?=vf_fw_link($mode,['kind'=>null])?>">全部<?=vf_fw_h(vf_fw_kind_label($mode))?></option><?php foreach($kindCounts as $name=>$count): ?><option value="<?=vf_fw_link($mode,['kind'=>$name])?>" <?=$kind===(string)$name?'selected':''?>><?=vf_fw_h(vf_fw_kind_display_label($mode,(string)$name))?> · <?=number_format((int)$count)?></option><?php endforeach; ?></select><?php endif; ?>
</div>
<?php
}

function vf_fw_render_toolbar(array $context): void
{
    $mode=(string)$context['mode'];$view=(string)$context['view'];$sort=(string)$context['sort'];$per=(int)$context['per'];$density=(string)$context['density'];$layout=(string)$context['layout'];$admin=(bool)$context['admin'];$background=(bool)$context['background'];$discover=(bool)$context['discover'];$status=(string)$context['status'];$statusCounts=(array)$context['status_counts'];$favoriteCount=(int)$context['favorite_count'];$kind=(string)($context['kind']??'');$watchYear=(int)($context['watch_year']??0);$watchGenre=(string)($context['watch_genre']??'');$watchRating=(float)($context['watch_rating']??0);$watchYears=(array)($context['watch_years']??[]);$watchGenres=(array)($context['watch_genres']??[]);
    ?>
<section class="vf-workspace-toolbar" aria-label="当前视图筛选">
  <nav>
    <?php if($mode==='all'): ?>
      <a class="<?=$view==='all'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>null])?>">全部</a><a class="<?=$view==='favorite'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'favorite'])?>">收藏</a><a class="<?=$view==='recent'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'recent'])?>">最近</a><a class="<?=$view==='tags'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'tags'])?>">标签</a><a class="<?=$view==='discover'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'discover'])?>">随机</a>
    <?php elseif($mode==='start'): ?>
      <a class="<?=$view==='all'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>null,'sort'=>null])?>">全部</a><a class="<?=$view==='favorite'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'favorite'])?>">收藏 <small><?=number_format($favoriteCount)?></small></a><a class="<?=$view==='popular'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'popular','sort'=>'popular'])?>">常用</a>
    <?php elseif($mode==='channels'): ?>
      <a class="<?=(!$background&&!$discover)?'active':''?>" href="<?=vf_fw_link($mode,['background'=>null,'discover'=>null])?>">全部</a><?php if($admin): ?><a class="<?=$background?'active':''?>" href="<?=vf_fw_link($mode,['background'=>1,'discover'=>null])?>">后台听</a><a class="<?=$discover?'active':''?>" href="<?=vf_fw_link($mode,['discover'=>1,'background'=>null])?>">重新发现</a><?php endif; ?>
    <?php elseif($mode==='watch'): ?>
      <a class="<?=$status===''?'active':''?>" href="<?=vf_fw_link($mode,['status'=>null])?>">全部</a><?php if($admin): ?><?php foreach(['want'=>'想看','watching'=>'在看','watched'=>'看过','favorite'=>'珍藏'] as $key=>$label): ?><a class="<?=$status===$key?'active':''?>" href="<?=vf_fw_link($mode,['status'=>$key])?>"><?=$label?><?php if(($statusCounts[$key]??0)>0): ?> <small><?=number_format((int)$statusCounts[$key])?></small><?php endif; ?></a><?php endforeach; ?><?php endif; ?>
    <?php elseif($mode==='topics'): ?>
      <a class="<?=$kind===''?'active':''?>" href="<?=vf_fw_link($mode,['kind'=>null])?>">全部专题</a>
    <?php elseif($mode==='courses'): ?>
      <a class="<?=$kind===''?'active':''?>" href="<?=vf_fw_link($mode,['kind'=>null])?>">全部课程</a>
    <?php elseif($mode==='projects'): ?>
      <a class="<?=$kind===''?'active':''?>" href="<?=vf_fw_link($mode,['kind'=>null])?>">全部项目</a>
    <?php elseif($mode==='tools'||$mode==='software'): ?>
      <a class="<?=$view==='all'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>null])?>">全部</a><a class="<?=$view==='favorite'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'favorite'])?>">收藏<?php if($favoriteCount>0): ?> <small><?=number_format($favoriteCount)?></small><?php endif; ?></a><a class="<?=$view==='recent'?'active':''?>" href="<?=vf_fw_link($mode,['view'=>'recent'])?>">最近</a>
    <?php endif; ?>
  </nav>
  <div class="vf-toolbar-controls">
    <?php if($admin): ?><label class="vf-select-all-label"><input type="checkbox" data-select-all> 全选</label><?php endif; ?>
    <?php if($mode==='watch'): ?>
    <select data-vf-location-select aria-label="年份筛选"><option value="<?=vf_fw_link($mode,['year'=>null])?>">全部年份</option><?php foreach($watchYears as $year=>$count): ?><option value="<?=vf_fw_link($mode,['year'=>(int)$year])?>" <?=$watchYear===(int)$year?'selected':''?>><?=$year?> · <?=number_format((int)$count)?></option><?php endforeach; ?></select>
    <select data-vf-location-select aria-label="题材筛选"><option value="<?=vf_fw_link($mode,['genre'=>null])?>">全部题材</option><?php foreach($watchGenres as $genre=>$count): ?><option value="<?=vf_fw_link($mode,['genre'=>(string)$genre])?>" <?=$watchGenre===(string)$genre?'selected':''?>><?=vf_fw_h((string)$genre)?> · <?=number_format((int)$count)?></option><?php endforeach; ?></select>
    <select data-vf-location-select aria-label="评分筛选"><option value="<?=vf_fw_link($mode,['rating'=>null])?>">全部评分</option><?php foreach([9,8,7,6] as $rating): ?><option value="<?=vf_fw_link($mode,['rating'=>$rating])?>" <?=$watchRating===(float)$rating?'selected':''?>>★ <?=$rating?>+</option><?php endforeach; ?></select>
    <?php if($admin): ?><button type="button" class="vf-watch-enrich-button" data-watch-enrich>批量补全资料</button><?php endif; ?>
    <?php endif; ?>
    <select data-vf-location-select aria-label="排序"><option value="<?=vf_fw_link($mode,['sort'=>'default'])?>" <?=$sort==='default'?'selected':''?>>默认排序</option><option value="<?=vf_fw_link($mode,['sort'=>'title'])?>" <?=$sort==='title'?'selected':''?>>标题</option><?php if($mode==='all'||$mode==='start'): ?><option value="<?=vf_fw_link($mode,['sort'=>'popular'])?>" <?=$sort==='popular'?'selected':''?>>常用</option><?php endif; ?><option value="<?=vf_fw_link($mode,['sort'=>'recent'])?>" <?=$sort==='recent'?'selected':''?>>最近使用</option><?php if($mode==='watch'): ?><option value="<?=vf_fw_link($mode,['sort'=>'added'])?>" <?=$sort==='added'?'selected':''?>>最近添加</option><option value="<?=vf_fw_link($mode,['sort'=>'rating'])?>" <?=$sort==='rating'?'selected':''?>>评分最高</option><option value="<?=vf_fw_link($mode,['sort'=>'year_desc'])?>" <?=$sort==='year_desc'?'selected':''?>>年份最新</option><option value="<?=vf_fw_link($mode,['sort'=>'year_asc'])?>" <?=$sort==='year_asc'?'selected':''?>>年份最早</option><?php endif; ?></select>
    <?php if(!in_array($mode,['watch','topics','courses','projects'],true)): ?><a class="<?=$density==='compact'?'active':''?>" href="<?=vf_fw_link($mode,['density'=>$density==='compact'?'comfortable':'compact'])?>"><?=$density==='compact'?'舒适':'紧凑'?></a><?php endif; ?>
    <?php if($mode==='all'||$mode==='start'): ?><a class="<?=$layout==='cards'?'active':''?>" href="<?=vf_fw_link($mode,['layout'=>$layout==='cards'?'list':'cards'])?>"><?=$layout==='cards'?'列表':'卡片'?></a><?php endif; ?>
  </div>
</section>
<?php
}

function vf_fw_render_row(array $asset, bool $admin, bool $showSurface = true, bool $priority = false): void
{
    $surface=(string)($asset['surface']??'start');$domain=(string)(parse_url((string)$asset['url'],PHP_URL_HOST)?:'');$provider=trim((string)($asset['provider_label']??''));$source=$surface==='start'?$domain:($provider!==''?$provider:$domain);$isFav=(int)($asset['is_favorite']??0)===1;$private=vf_fw_is_private($asset);$class=$surface==='start'?(string)($asset['category_name']??''):vf_fw_kind_display_label($surface,(string)($asset['resource_kind']??''));
    ?>
<article class="vf-asset-row" data-asset-row="<?=(int)$asset['id']?>">
  <?php if($admin): ?><label class="vf-asset-select"><input type="checkbox" value="<?=(int)$asset['id']?>" data-select-asset aria-label="选择 <?=vf_fw_h((string)$asset['title'])?>"></label><?php endif; ?>
  <span class="vf-asset-icon" data-edit-id="<?=(int)$asset['id']?>"><?=vf_fw_icon($asset,$priority)?></span>
  <span class="vf-asset-copy" data-edit-id="<?=(int)$asset['id']?>"><strong><?=vf_fw_h((string)$asset['title'])?></strong><small><?=vf_fw_h($source)?><?php if($class!==''): ?> · <?=vf_fw_h($class)?><?php endif; ?></small><?php if(!empty($asset['surface_note'])): ?><em><?=vf_fw_h(mb_substr((string)$asset['surface_note'],0,120,'UTF-8'))?></em><?php elseif(!empty($asset['description'])): ?><em><?=vf_fw_h(mb_substr((string)$asset['description'],0,120,'UTF-8'))?></em><?php endif; ?></span>
  <span class="vf-asset-meta"><?php if($admin&&$private): ?><i class="vf-chip private">私人</i><?php endif; ?><?php if($showSurface&&$surface!=='start'): ?><i class="vf-chip teal"><?=vf_fw_h(vf_fw_mode_label($surface))?></i><?php endif; ?><?php if(!empty($asset['background_friendly'])): ?><i class="vf-chip teal">后台听</i><?php endif; ?><?php foreach(array_slice((array)($asset['tags']??[]),0,2) as $tag): ?><small class="vf-chip">#<?=vf_fw_h((string)$tag)?></small><?php endforeach; ?><span class="vf-asset-actions"><?php if($admin): ?><button type="button" class="vf-icon-button <?=$isFav?'active':''?>" data-favorite-id="<?=(int)$asset['id']?>" data-favorite="<?=$isFav?'1':'0'?>" aria-label="<?=$isFav?'取消收藏':'收藏'?>" title="<?=$isFav?'取消收藏':'收藏'?>"><?=$isFav?'★':'☆'?></button><button type="button" class="vf-icon-button" data-edit-id="<?=(int)$asset['id']?>" aria-label="编辑" title="编辑">✎</button><?php endif; ?><a class="vf-icon-button" href="<?=vf_fw_open_href($asset,$admin)?>" target="_blank" rel="noopener noreferrer" aria-label="打开" title="打开">↗</a></span></span>
</article>
<?php
}

function vf_fw_render_watch_card(array $asset, bool $admin, bool $priority = false): void
{
    $isFav=(int)($asset['is_favorite']??0)===1;$private=vf_fw_is_private($asset);$mediaStatus=(string)($asset['media_status']??'');$provider=trim((string)($asset['provider_label']??''));$labels=['want'=>'想看','watching'=>'在看','watched'=>'看过','favorite'=>'珍藏'];$visual=(string)($asset['cover_url']??'');if($visual==='')$visual=(string)($asset['icon_cache_url']??'');$rating=(float)($asset['tmdb_rating']??0);$genres=array_values(array_filter(array_map('strval',(array)($asset['tmdb_genres']??[]))));
    $detail=['title'=>(string)($asset['title']??''),'originalTitle'=>(string)($asset['tmdb_original_title']??''),'year'=>!empty($asset['media_year'])?(int)$asset['media_year']:null,'rating'=>$rating,'voteCount'=>(int)($asset['tmdb_vote_count']??0),'genres'=>$genres,'countries'=>array_values(array_filter(array_map('strval',(array)($asset['tmdb_countries']??[])))),'runtime'=>$asset['tmdb_runtime']!==null?(int)$asset['tmdb_runtime']:null,'overview'=>(string)($asset['tmdb_overview']??''),'kind'=>vf_fw_kind_display_label('watch',(string)($asset['resource_kind']??'')) ?: '影视','provider'=>$provider,'tmdbId'=>(int)($asset['tmdb_id']??0),'syncedAt'=>(string)($asset['tmdb_synced_at']??'')];
    $detailJson=json_encode($detail,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT) ?: '{}';
    ?>
<article class="vf-watch-card" data-asset-row="<?=(int)$asset['id']?>" data-watch-tmdb-id="<?=(int)($asset['tmdb_id']??0)?>" data-watch-created-at="<?=vf_fw_h((string)($asset['created_at']??''))?>" data-watch-detail="<?=vf_fw_h($detailJson)?>">
  <?php if($admin): ?><label class="vf-asset-select"><input type="checkbox" value="<?=(int)$asset['id']?>" data-select-asset aria-label="选择 <?=vf_fw_h((string)$asset['title'])?>"></label><?php endif; ?>
  <span class="vf-watch-poster" data-edit-id="<?=(int)$asset['id']?>"><?php if($visual!==''): ?><?=vf_fw_asset_image($asset,$priority,'watch')?><?php else: ?><b><?=vf_fw_initial($asset)?></b><?php endif; ?></span>
  <span class="vf-watch-copy" data-edit-id="<?=(int)$asset['id']?>"><strong><?=vf_fw_h((string)$asset['title'])?></strong><small><?php if(!empty($asset['media_year'])): ?><?=(int)$asset['media_year']?><?php endif; ?><?php if($rating>0): ?><?=!empty($asset['media_year'])?' · ':''?>★ <?=number_format($rating,1)?><?php endif; ?><?php if($genres): ?><?=(!empty($asset['media_year'])||$rating>0)?' · ':''?><?=vf_fw_h(implode(' / ',array_slice($genres,0,2)))?><?php elseif(empty($asset['media_year'])&&$rating<=0): ?><?=vf_fw_h(vf_fw_kind_display_label('watch',(string)($asset['resource_kind']??'')) ?: '电影')?><?php endif; ?></small><?php if($admin&&$private): ?><em class="vf-status-label private">私人</em><?php elseif($mediaStatus!==''&&isset($labels[$mediaStatus])): ?><em class="vf-status-label"><?=vf_fw_h($labels[$mediaStatus])?></em><?php endif; ?></span>
  <?php if($admin): ?><span class="vf-cover-diagnostic" data-cover-diagnostic hidden></span><?php endif; ?>
  <span class="vf-asset-actions"><?php if($admin): ?><?php if($visual===''): ?><button type="button" class="vf-icon-button" data-cover-refresh-id="<?=(int)$asset['id']?>" aria-label="重新抓封面" title="重新抓封面">↻</button><?php endif; ?><button type="button" class="vf-icon-button <?=$isFav?'active':''?>" data-favorite-id="<?=(int)$asset['id']?>" data-favorite="<?=$isFav?'1':'0'?>" aria-label="<?=$isFav?'取消收藏':'收藏'?>" title="<?=$isFav?'取消收藏':'收藏'?>"><?=$isFav?'★':'☆'?></button><button type="button" class="vf-icon-button" data-edit-id="<?=(int)$asset['id']?>" aria-label="编辑" title="编辑">✎</button><?php endif; ?><button type="button" class="vf-icon-button" data-watch-detail-open aria-label="影视详情" title="影视详情">ⓘ</button><a class="vf-icon-button" href="<?=vf_fw_open_href($asset,$admin)?>" target="_blank" rel="noopener noreferrer" aria-label="打开" title="打开">↗</a></span>
</article>
<?php
}

function vf_fw_render_topic_card(array $asset, bool $admin, bool $priority = false): void
{
    $isFav=(int)($asset['is_favorite']??0)===1;$private=vf_fw_is_private($asset);$visual=(string)($asset['cover_url']??'');if($visual==='')$visual=(string)($asset['icon_cache_url']??'');
    ?>
<article class="vf-topic-card" data-asset-row="<?=(int)$asset['id']?>">
  <?php if($admin): ?><label class="vf-asset-select"><input type="checkbox" value="<?=(int)$asset['id']?>" data-select-asset aria-label="选择 <?=vf_fw_h((string)$asset['title'])?>"></label><?php endif; ?>
  <span class="vf-topic-cover" data-edit-id="<?=(int)$asset['id']?>"><?php if($visual!==''): ?><?=vf_fw_asset_image($asset,$priority,'topic')?><?php else: ?><b><?=vf_fw_initial($asset)?></b><?php endif; ?></span>
  <span class="vf-topic-copy" data-edit-id="<?=(int)$asset['id']?>"><strong><?=vf_fw_h((string)$asset['title'])?></strong><small><?=vf_fw_h(vf_fw_kind_display_label('topics',(string)($asset['resource_kind']??'')) ?: '未分类')?></small><?php if(!empty($asset['description'])): ?><em><?=vf_fw_h(mb_substr((string)$asset['description'],0,90,'UTF-8'))?></em><?php endif; ?></span>
  <span class="vf-topic-footer"><?php if($admin&&$private): ?><i class="vf-chip private">私人</i><?php endif; ?><span class="vf-asset-actions"><?php if($admin): ?><button type="button" class="vf-icon-button <?=$isFav?'active':''?>" data-favorite-id="<?=(int)$asset['id']?>" data-favorite="<?=$isFav?'1':'0'?>" aria-label="<?=$isFav?'取消收藏':'收藏'?>" title="<?=$isFav?'取消收藏':'收藏'?>"><?=$isFav?'★':'☆'?></button><button type="button" class="vf-icon-button" data-edit-id="<?=(int)$asset['id']?>" aria-label="编辑" title="编辑">✎</button><?php endif; ?><a class="vf-icon-button" href="<?=vf_fw_open_href($asset,$admin)?>" target="_blank" rel="noopener noreferrer" aria-label="打开" title="打开">↗</a></span></span>
</article>
<?php
}


function vf_fw_book_source_meta(array $asset): array
{
    $url=trim((string)($asset['url']??''));
    $tags=array_values(array_map('strval',(array)($asset['tags']??[])));
    $isCatalog=in_array('Git-Book',$tags,true);
    $repository='';$branch='';$sourcePath='';
    $parts=parse_url($url);
    $host=strtolower((string)($parts['host']??''));
    $path=(string)($parts['path']??'');
    if($host==='github.com'&&preg_match('#^/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$#',$path,$match)){
        $repository=rawurldecode($match[1]).'/'.rawurldecode($match[2]);
        $branch=rawurldecode($match[3]);
        $sourcePath=implode('/',array_map('rawurldecode',explode('/',$match[4])));
    }
    $bookId='';$version='';
    if($isCatalog){
        foreach($tags as $tag){
            $tag=trim($tag);if($tag===''||$tag==='Git-Book'||$tag===$repository)continue;
            if($version===''&&preg_match('/^v?\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9._-]+)?$/i',$tag)){$version=$tag;continue;}
            if($bookId===''&&preg_match('/^[A-Z0-9][A-Z0-9._-]{0,39}$/',$tag))$bookId=$tag;
        }
    }
    return [
        'is_catalog'=>$isCatalog,
        'repository'=>$repository,
        'repository_url'=>$repository!==''?'https://github.com/'.$repository:'',
        'branch'=>$branch,
        'source_path'=>$sourcePath,
        'book_id'=>$bookId,
        'version'=>$version,
    ];
}

function vf_fw_render_book_card(array $asset, bool $admin, bool $priority = false): void
{
    $isFav=(int)($asset['is_favorite']??0)===1;
    $private=vf_fw_is_private($asset);
    $visual=(string)($asset['cover_url']??'');if($visual==='')$visual=(string)($asset['icon_cache_url']??'');
    $kind=vf_fw_kind_display_label('books',(string)($asset['resource_kind']??''));
    $kind=$kind!==''?$kind:'书籍';
    $host=(string)(parse_url((string)($asset['url']??''),PHP_URL_HOST)?:'');
    $source=vf_fw_book_source_meta($asset);
    $description=trim((string)($asset['description']??''));
    $technicalDescription=!empty($source['is_catalog'])&&str_starts_with($description,'Git 图书目录');
    $readLabel=!empty($source['repository'])?'阅读正文 →':'打开 →';
    ?>
<article class="vf-book-card" data-asset-row="<?=(int)$asset['id']?>">
  <?php if($admin): ?><label class="vf-asset-select"><input type="checkbox" value="<?=(int)$asset['id']?>" data-select-asset aria-label="选择 <?=vf_fw_h((string)$asset['title'])?>"></label><?php endif; ?>
  <a class="vf-book-cover" href="<?=vf_fw_open_href($asset,$admin)?>" target="_blank" rel="noopener noreferrer" aria-label="打开 <?=vf_fw_h((string)$asset['title'])?>">
    <?php if($visual!==''): ?><?=vf_fw_asset_image($asset,$priority,'book')?><?php else: ?><b><?=vf_fw_initial($asset)?></b><?php endif; ?>
  </a>
  <div class="vf-book-body">
    <div class="vf-book-head"><span class="vf-book-meta-badges"><?php if((string)$source['book_id']!==''): ?><b><?=vf_fw_h((string)$source['book_id'])?></b><?php endif; ?><span class="vf-project-id"><?=vf_fw_h($kind)?></span><?php if((string)$source['version']!==''): ?><i><?=vf_fw_h((string)$source['version'])?></i><?php endif; ?></span><?php if($admin&&$private): ?><i class="vf-chip private">私人</i><?php endif; ?></div>
    <div class="vf-book-copy" data-edit-id="<?=(int)$asset['id']?>"><strong><?=vf_fw_h((string)$asset['title'])?></strong><?php if($description!==''&&!$technicalDescription): ?><p><?=vf_fw_h(mb_substr($description,0,150,'UTF-8'))?></p><?php endif; ?></div>
    <?php if((string)$source['repository']!==''): ?>
      <div class="vf-book-source" title="<?=vf_fw_h((string)$source['source_path'])?>"><span>GitHub · <b><?=vf_fw_h((string)$source['repository'])?></b></span><?php if((string)$source['source_path']!==''): ?><code><?=vf_fw_h((string)$source['source_path'])?></code><?php endif; ?></div>
    <?php endif; ?>
    <div class="vf-book-footer"><span><?php if((string)$source['branch']!==''): ?><?=vf_fw_h((string)$source['branch'])?> · 正式源<?php else: ?><?=vf_fw_h($host!==''?$host:'书籍资源')?><?php endif; ?></span><span class="vf-asset-actions"><?php if($admin): ?><button type="button" class="vf-icon-button <?=$isFav?'active':''?>" data-favorite-id="<?=(int)$asset['id']?>" data-favorite="<?=$isFav?'1':'0'?>" aria-label="<?=$isFav?'取消收藏':'收藏'?>" title="<?=$isFav?'取消收藏':'收藏'?>"><?=$isFav?'★':'☆'?></button><button type="button" class="vf-icon-button" data-edit-id="<?=(int)$asset['id']?>" aria-label="编辑" title="编辑">✎</button><?php endif; ?><?php if((string)$source['repository_url']!==''): ?><a class="vf-book-source-link" href="<?=vf_fw_h((string)$source['repository_url'])?>" target="_blank" rel="noopener noreferrer">Git 源</a><?php endif; ?><a class="vf-book-read-link" href="<?=vf_fw_open_href($asset,$admin)?>" target="_blank" rel="noopener noreferrer"><?=vf_fw_h($readLabel)?></a></span></div>
  </div>
</article>
<?php
}

function vf_fw_render_project_card(array $asset, bool $admin, bool $priority = false): void
{
    $isFav=(int)($asset['is_favorite']??0)===1;
    $private=vf_fw_is_private($asset);
    $visual=(string)($asset['cover_url']??'');if($visual==='')$visual=(string)($asset['icon_cache_url']??'');
    $status=(string)($asset['project_status']??'active');if($status==='')$status='active';
    $labels=['active'=>'使用中','optimizing'=>'优化中','sealed'=>'已封版','retired'=>'已退役'];
    $code=trim((string)($asset['project_code']??''));
    $host=(string)(parse_url((string)($asset['url']??''),PHP_URL_HOST)?:'');
    $canOpen=VfProjectResource::canOpen((string)($asset['url']??''));
    ?>
<article class="vf-project-card" data-asset-row="<?=(int)$asset['id']?>">
  <?php if($admin): ?><label class="vf-asset-select"><input type="checkbox" value="<?=(int)$asset['id']?>" data-select-asset aria-label="选择 <?=vf_fw_h((string)$asset['title'])?>"></label><?php endif; ?>
  <span class="vf-project-cover<?= $visual===''?' is-placeholder':'' ?>" data-edit-id="<?=(int)$asset['id']?>"><?php if($visual!==''): ?><?=vf_fw_asset_image($asset,$priority,'project')?><?php else: ?><b><?=vf_fw_initial($asset)?></b><?php endif; ?></span>
  <div class="vf-project-card-top">
    <span class="vf-project-id"><?=vf_fw_h($code!==''?$code:'PROJECT')?></span>
    <span class="vf-project-status <?=vf_fw_h($status)?>"><?=vf_fw_h($labels[$status]??$status)?></span>
  </div>
  <div class="vf-project-card-title" data-edit-id="<?=(int)$asset['id']?>">
    <div><strong><?=vf_fw_h((string)$asset['title'])?></strong><small><?=vf_fw_h((string)($asset['resource_kind']??'项目'))?></small></div>
  </div>
  <p><?=vf_fw_h(mb_substr((string)($asset['description']??''),0,120,'UTF-8'))?></p>
  <div class="vf-project-domain"><span><?=vf_fw_h($host!==''?$host:'无网址')?></span><span class="vf-asset-actions"><?php if($admin&&$private): ?><i class="vf-chip private">私人</i><?php endif; ?><?php if($admin): ?><button type="button" class="vf-icon-button <?=$isFav?'active':''?>" data-favorite-id="<?=(int)$asset['id']?>" data-favorite="<?=$isFav?'1':'0'?>" aria-label="<?=$isFav?'取消收藏':'收藏'?>" title="<?=$isFav?'取消收藏':'收藏'?>"><?=$isFav?'★':'☆'?></button><button type="button" class="vf-icon-button" data-edit-id="<?=(int)$asset['id']?>" aria-label="编辑" title="编辑">✎</button><?php endif; ?><?php if($canOpen): ?><a class="vf-icon-button" href="<?=vf_fw_open_href($asset,$admin)?>" target="_blank" rel="noopener noreferrer" aria-label="打开" title="打开">↗</a><?php endif; ?></span></div>
</article>
<?php
}

function vf_fw_context_json(array $categories, string $scope, string $mode): string
{
    $items=[];
    if($mode==='start'){foreach($categories as $category){$id=(int)($category['id']??0);if($id<=0)continue;$items[]=['id'=>$id,'parent_id'=>$category['parent_id']===null?null:(int)$category['parent_id'],'name'=>(string)($category['name']??''),'effective_private'=>(int)($category['effective_private']??$category['is_private']??0)];}}
    return json_encode(['scope'=>$scope,'mode'=>$mode,'categories'=>$items],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT) ?: '{}';
}
