<?php
declare(strict_types=1);

require_once __DIR__ . '/WorkspaceViewCatalog.php';

/**
 * P01 private workspace shell.
 * V2.29: Chinese resource-domain labels, distinct domain classification and compressed covers.
 */
function vf_surface_shell_begin(array $options = []): void
{
    $title = trim((string)($options['title'] ?? 'VF Start'));
    $active = trim((string)($options['active'] ?? 'all'));
    $admin = array_key_exists('admin',$options) ? (bool)$options['admin'] : vf_is_admin();
    $counts = is_array($options['counts'] ?? null) ? $options['counts'] : ['start'=>0,'channels'=>0,'watch'=>0,'topics'=>0,'books'=>0,'projects'=>0,'total'=>0];
    $pending = max(0,(int)($options['pending'] ?? 0));
    $q = trim((string)($options['q'] ?? ''));
    $bodyClass = trim((string)($options['body_class'] ?? ''));
    $scripts = is_array($options['scripts'] ?? null) ? $options['scripts'] : [];
    $styles = is_array($options['styles'] ?? null) ? $options['styles'] : [];
    $contextAction = (string)($options['context_action'] ?? '');
    $allowAdd = array_key_exists('allow_add',$options) ? (bool)$options['allow_add'] : $admin;

    $branding = ['logoUrl'=>''];
    try { $branding = (new VfRepository(vf_db()))->getBranding(); } catch (Throwable $ignored) {}
    $logoUrl = trim((string)($branding['logoUrl'] ?? ''));

    $primary = VfWorkspaceViewCatalog::entries($admin);
    $smart = [
        ['inbox','surface-manager.php','◇','待整理',$pending],
        ['favorite','surfaces.php?view=favorite','☆','我的收藏',null],
        ['tags','surfaces.php?view=tags','#','标签',null],
        ['recent','surfaces.php?view=recent','◷','最近使用',null],
        ['discover','surfaces.php?view=discover','✦','随机发现',null],
    ];
    ?>
<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="theme-color" content="#0f766e">
<title><?=htmlspecialchars($title,ENT_QUOTES,'UTF-8')?> · VF Start</title>
<link rel="stylesheet" href="<?=htmlspecialchars(vf_asset_url('assets/surfaces.css'),ENT_QUOTES,'UTF-8')?>">
<link rel="stylesheet" href="<?=htmlspecialchars(vf_asset_url('assets/surface-workspace.css'),ENT_QUOTES,'UTF-8')?>">
<link rel="stylesheet" href="<?=htmlspecialchars(vf_asset_url('assets/workspace-v228.css'),ENT_QUOTES,'UTF-8')?>">
<?php foreach($styles as $style): ?><link rel="stylesheet" href="<?=htmlspecialchars(vf_asset_url((string)$style),ENT_QUOTES,'UTF-8')?>"><?php endforeach; ?>
<script src="<?=htmlspecialchars(vf_asset_url('assets/surface-home.js'),ENT_QUOTES,'UTF-8')?>" defer></script>
<script src="<?=htmlspecialchars(vf_asset_url('assets/workspace.js'),ENT_QUOTES,'UTF-8')?>" defer></script>
<?php foreach($scripts as $script): ?><script src="<?=htmlspecialchars(vf_asset_url((string)$script),ENT_QUOTES,'UTF-8')?>" defer></script><?php endforeach; ?>
</head><body class="vf-surface-app <?=htmlspecialchars($bodyClass,ENT_QUOTES,'UTF-8')?>">
<aside class="vf-app-sidebar" aria-label="VF Start 导航">
  <a class="vf-app-brand" href="surfaces.php" aria-label="VF Start 全部资源">
    <span class="vf-brand-mark<?= $logoUrl !== '' ? ' has-custom-logo' : '' ?>"><?php if($logoUrl !== ''): ?><img src="<?=htmlspecialchars($logoUrl,ENT_QUOTES,'UTF-8')?>" alt=""><?php else: ?>VF<?php endif; ?></span>
    <span><strong>VF Start</strong><small>P01 · 个人互联网资产</small></span>
  </a>
  <nav class="vf-main-nav" aria-label="资源视图">
    <?php foreach($primary as $item): $key=(string)$item['mode'];$href=(string)$item['route'];$icon=(string)$item['icon'];$label=(string)$item['label'];$count=$key==='home'?null:(int)($counts[$key]??($key==='courses'?($counts['books']??0):0)); ?><a class="<?=$active===$key?'active':''?>" href="<?=$href?>"><span class="vf-nav-icon"><?=$icon?></span><b><?=$label?></b><?php if($count!==null): ?><em><?=number_format($count)?></em><?php endif; ?></a><?php endforeach; ?>
  </nav>
  <div class="vf-nav-section"><span>智能视图</span></div>
  <nav class="vf-secondary-nav" aria-label="智能视图">
    <?php foreach($smart as [$key,$href,$icon,$label,$count]): ?><a class="<?=$active===$key?'active':''?>" href="<?=$href?>"><span><?=$icon?></span><b><?=$label?></b><?php if($count!==null && (int)$count>0): ?><em><?=number_format((int)$count)?></em><?php endif; ?></a><?php endforeach; ?>
  </nav>
  <div class="vf-sidebar-bottom">
    <?php if($admin): ?><a href="surface-manager.php?advanced=1">☷ <span>资源管理</span></a><a href="settings.php">⚙ <span>设置</span></a><?php endif; ?>
    <small>VF Start · V<?=htmlspecialchars(VF_VERSION,ENT_QUOTES,'UTF-8')?></small>
  </div>
</aside>
<section class="vf-app-stage">
  <header class="vf-app-topbar">
    <form class="vf-global-search" action="surfaces.php" method="get"><span>⌕</span><input type="search" name="q" value="<?=htmlspecialchars($q,ENT_QUOTES,'UTF-8')?>" placeholder="搜索标题、网址、分类或标签" autocomplete="off"><kbd>⌘ K</kbd></form>
    <div class="vf-top-actions"><?=$contextAction?><?php if($allowAdd): ?><button type="button" class="vf-context-action vf-new-action" data-open-add><span>＋</span><b>添加</b></button><?php endif; ?><button type="button" class="vf-theme-toggle" data-theme-toggle aria-label="切换主题">◐</button></div>
  </header>
  <main class="vf-shell-main">
<?php }

function vf_workspace_payload(array $assets, array $categories, array $options = []): void
{
    if (!vf_is_admin()) return;
    $csrf = vf_csrf_token();
    $safeAssets = [];
    foreach ($assets as $asset) {
        $id = (int)($asset['id'] ?? 0);
        if ($id <= 0) continue;
        $domain = (string)(parse_url((string)($asset['url'] ?? ''), PHP_URL_HOST) ?: '');
        $safeAssets[(string)$id] = [
            'id'=>$id,
            'category_id'=>(int)($asset['category_id'] ?? 0),
            'category_name'=>(string)($asset['category_name'] ?? ''),
            'title'=>(string)($asset['title'] ?? ''),
            'url'=>(string)($asset['url'] ?? ''),
            'domain'=>$domain,
            'provider'=>(string)($asset['provider'] ?? ''),
            'provider_label'=>(string)($asset['provider_label'] ?? ''),
            'description'=>(string)($asset['description'] ?? ''),
            'tags'=>array_values(array_map('strval',(array)($asset['tags'] ?? []))),
            'surface'=>(string)($asset['surface'] ?? 'start'),
            'resource_kind'=>(string)($asset['resource_kind'] ?? ''),
            'source_kind'=>(string)($asset['source_kind'] ?? 'remote_url'),
            'source_ref'=>(string)($asset['source_ref'] ?? ''),
            'html_url'=>(string)($asset['html_url'] ?? ''),
            'html_name'=>(string)($asset['html_name'] ?? ''),
            'html_bytes'=>(int)($asset['html_bytes'] ?? 0),
            'media_year'=>$asset['media_year'] ?? null,
            'media_status'=>(string)($asset['media_status'] ?? ''),
            'surface_note'=>(string)($asset['surface_note'] ?? ''),
            'background_friendly'=>(int)($asset['background_friendly'] ?? 0),
            'last_surface_opened_at'=>(string)($asset['last_surface_opened_at'] ?? ''),
            'project_code'=>(string)($asset['project_code'] ?? ''),
            'project_status'=>(string)($asset['project_status'] ?? ''),
            'is_private'=>(int)($asset['is_private'] ?? 0),
            'is_favorite'=>(int)($asset['is_favorite'] ?? 0),
            'icon_cache_url'=>(string)($asset['icon_cache_url'] ?? ''),
            'cover_url'=>(string)($asset['cover_url'] ?? ''),
        ];
    }
    $safeCategories = [];
    foreach ($categories as $category) {
        $id=(int)($category['id'] ?? 0); if($id<=0) continue;
        $safeCategories[]=['id'=>$id,'name'=>(string)($category['name'] ?? ''),'depth'=>(int)($category['depth'] ?? 0)];
    }
    $payload = json_encode(['assets'=>$safeAssets,'categories'=>$safeCategories,'csrf'=>$csrf], JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT) ?: '{}';
    ?>
<script type="application/json" id="vf-workspace-data"><?=$payload?></script>
<div class="vf-workspace-overlay" data-workspace-overlay hidden>
  <section class="vf-workspace-dialog vf-add-dialog" data-panel="add" hidden role="dialog" aria-modal="true" aria-label="添加资源">
    <header><div><strong>添加资源</strong><small>在当前工作区完成，不跳转到管理后台。</small></div><button type="button" data-close-panel aria-label="关闭">×</button></header>
    <form data-add-form class="vf-workspace-form">
      <label class="vf-field vf-field-wide" data-url-field><span>网址</span><input type="url" name="url" required placeholder="https://"></label>
      <label class="vf-field vf-field-wide"><span>标题</span><input name="title" required maxlength="300" placeholder="资源标题"></label>
      <label class="vf-field" data-surface-field="start"><span>导航分类</span><select name="category_id" required><?php foreach($safeCategories as $c): ?><option value="<?=$c['id']?>"><?=str_repeat('　',min(3,(int)$c['depth']))?><?=htmlspecialchars($c['name'],ENT_QUOTES,'UTF-8')?></option><?php endforeach; ?></select></label>
      <label class="vf-field"><span>所属分组</span><select name="surface"><option value="start">导航</option><option value="channels">频道</option><option value="watch">影视</option><option value="topics">专题</option><option value="books">课程</option><option value="projects">项目</option></select></label>
      <label class="vf-field" data-surface-field="topics"><span>专题来源</span><select name="source_kind" data-source-kind><option value="remote_url">远程网址</option><option value="hosted_html">上传 HTML</option></select></label>
      <label class="vf-field vf-field-wide" data-html-field hidden><span>HTML 文件 <small>最大 2 MB · 原样保存并隔离运行</small></span><input type="file" name="html" accept=".html,.htm,text/html" data-html-input><small data-html-status></small></label>
      <label class="vf-field" data-surface-field="channels,watch,topics,books,projects"><span data-kind-label>主分类</span><input name="resource_kind" maxlength="80" placeholder="输入主分类"></label>
      <label class="vf-field" data-surface-field="projects"><span>项目编号</span><input name="project_code" maxlength="40" placeholder="例如 P01"></label>
      <label class="vf-field" data-surface-field="projects"><span>项目状态</span><select name="project_status"><option value="active">使用中</option><option value="optimizing">优化中</option><option value="sealed">已封版</option><option value="retired">已退役</option></select></label>
      <label class="vf-field vf-field-wide"><span>标签 / 次属性</span><input name="tags" placeholder="多个标签用逗号分隔"></label>
      <label class="vf-field vf-field-wide"><span>描述 / 备注</span><textarea name="description" rows="3"></textarea></label>
      <label class="vf-field vf-field-wide vf-cover-field" data-surface-field="channels,watch,topics,books,projects"><span>封面 <small>自动获取 · 可手工覆盖</small></span><input type="file" name="cover" accept="image/png,image/jpeg,image/webp" data-cover-input><span class="vf-cover-preview" data-cover-preview hidden></span></label>
      <label class="vf-field" data-surface-field="watch"><span>年份</span><input name="media_year" inputmode="numeric" placeholder="2026"></label>
      <label class="vf-field" data-surface-field="watch"><span>影视状态</span><select name="media_status"><option value="">未设置</option><option value="want">想看</option><option value="watching">在看</option><option value="watched">看过</option><option value="favorite">珍藏</option></select></label>
      <label class="vf-check" data-surface-field="channels"><input type="checkbox" name="background_friendly" value="1"> 适合后台听</label>
      <label class="vf-check"><input type="checkbox" name="is_private" value="1" checked> 私人</label>
      <label class="vf-check"><input type="checkbox" name="is_favorite" value="1"> 收藏</label>
      <footer><button type="button" class="vf-secondary-button" data-close-panel>取消</button><button type="submit" class="vf-primary-button">添加资源</button></footer>
    </form>
  </section>

  <aside class="vf-detail-drawer" data-panel="detail" hidden role="dialog" aria-modal="true" aria-label="资源详情">
    <header class="vf-detail-head"><span class="vf-detail-icon" data-detail-icon></span><div><strong data-detail-title>资源详情</strong><small data-detail-domain></small></div><a href="#" data-detail-open target="_blank" rel="noopener noreferrer">打开 ↗</a><button type="button" data-close-panel aria-label="关闭">×</button></header>
    <form data-detail-form class="vf-workspace-form vf-detail-form">
      <input type="hidden" name="id">
      <label class="vf-field vf-field-wide"><span>标题</span><input name="title" required maxlength="300"></label>
      <label class="vf-field vf-field-wide" data-url-field><span>网址</span><input type="url" name="url" required></label>
      <label class="vf-field" data-surface-field="start"><span>导航分类</span><select name="category_id" required></select></label>
      <label class="vf-field"><span>所属分组</span><select name="surface"><option value="start">导航</option><option value="channels">频道</option><option value="watch">影视</option><option value="topics">专题</option><option value="books">课程</option><option value="projects">项目</option></select></label>
      <label class="vf-field" data-surface-field="topics"><span>专题来源</span><select name="source_kind" data-source-kind><option value="remote_url">远程网址</option><option value="hosted_html">上传 HTML</option></select></label>
      <label class="vf-field vf-field-wide" data-html-field hidden><span>HTML 文件 <small>最大 2 MB · 可上传新文件替换</small></span><input type="file" name="html" accept=".html,.htm,text/html" data-html-input><small data-html-status></small></label>
      <label class="vf-field" data-surface-field="channels,watch,topics,books,projects"><span data-kind-label>主分类</span><input name="resource_kind" maxlength="80"></label>
      <label class="vf-field" data-surface-field="projects"><span>项目编号</span><input name="project_code" maxlength="40"></label>
      <label class="vf-field" data-surface-field="projects"><span>项目状态</span><select name="project_status"><option value="active">使用中</option><option value="optimizing">优化中</option><option value="sealed">已封版</option><option value="retired">已退役</option></select></label>
      <label class="vf-field vf-field-wide"><span>标签 / 次属性</span><input name="tags"></label>
      <label class="vf-field vf-field-wide"><span>描述</span><textarea name="description" rows="4"></textarea></label>
      <label class="vf-field vf-field-wide vf-cover-field" data-surface-field="channels,watch,topics,books,projects"><span>封面 <small>自动获取 · 可手工覆盖</small></span><input type="file" name="cover" accept="image/png,image/jpeg,image/webp" data-cover-input><span class="vf-cover-preview" data-cover-preview hidden></span><button type="button" class="vf-cover-delete" data-cover-delete hidden>删除封面</button></label>
      <label class="vf-field" data-surface-field="watch"><span>年份</span><input name="media_year" inputmode="numeric"></label>
      <label class="vf-field" data-surface-field="watch"><span>影视状态</span><select name="media_status"><option value="">未设置</option><option value="want">想看</option><option value="watching">在看</option><option value="watched">看过</option><option value="favorite">珍藏</option></select></label>
      <label class="vf-field vf-field-wide" data-surface-field="channels,watch,topics,books,projects"><span>私人备注</span><textarea name="surface_note" rows="3"></textarea></label>
      <label class="vf-check" data-surface-field="channels"><input type="checkbox" name="background_friendly" value="1"> 适合后台听</label>
      <label class="vf-check"><input type="checkbox" name="is_private" value="1"> 私人</label>
      <label class="vf-check"><input type="checkbox" name="is_favorite" value="1"> 收藏</label>
      <footer><button type="button" class="vf-secondary-button" data-close-panel>取消</button><button type="submit" class="vf-primary-button">保存修改</button></footer>
    </form>
  </aside>
</div>

<div class="vf-bulkbar" data-bulkbar hidden aria-live="polite">
  <strong><span data-selected-count>0</span> / <span data-page-count>0</span> 项已选择</strong>
  <select data-bulk-surface aria-label="批量移动分组"><option value="">移动到分组…</option><option value="start">导航</option><option value="channels">频道</option><option value="watch">影视</option><option value="topics">专题</option><option value="books">课程</option><option value="projects">项目</option></select>
  <select data-bulk-category aria-label="批量移动导航分类"><option value="">移动导航分类…</option><?php foreach($safeCategories as $c): ?><option value="<?=$c['id']?>"><?=str_repeat('　',min(3,(int)$c['depth']))?><?=htmlspecialchars($c['name'],ENT_QUOTES,'UTF-8')?></option><?php endforeach; ?></select>
  <button type="button" data-bulk-action="favorite">☆ 收藏</button>
  <button type="button" data-bulk-action="unfavorite">移除收藏</button>
  <button type="button" class="danger" data-bulk-action="delete">删除</button>
  <button type="button" class="vf-bulk-clear" data-bulk-clear title="也可按 Esc 清除选择">清除</button>
</div>
<?php }

function vf_surface_shell_end(): void { ?></main></section></body></html><?php }
