<?php
declare(strict_types=1);

require_once __DIR__ . '/bootstrap.php';
require_once __DIR__ . '/Repository.php';
require_once __DIR__ . '/SurfaceRepository.php';
require_once __DIR__ . '/SurfaceShell.php';
require_once __DIR__ . '/WorkspaceViewCatalog.php';

/**
 * P01 functional-first workspace renderer.
 *
 * Functional contract:
 * - one asset authority; resource domains do not share one classification tree
 * - Start/navigation keeps the legacy hierarchical category tree
 * - Channels/Watch/Topics use their own lightweight primary kind + tags/facets
 * - privacy and resource domain remain orthogonal
 * - UI may evolve, but these capabilities may not disappear
 */

function vf_fw_h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function vf_fw_mode(): string
{
    return VfWorkspaceViewCatalog::normalizeMode((string)($GLOBALS['vfWorkspaceMode'] ?? 'all'));
}

function vf_fw_scope(bool $admin): string
{
    if (!$admin) return 'public';
    $scope = strtolower(trim((string)($_GET['scope'] ?? 'all')));
    return in_array($scope, ['all', 'public', 'private'], true) ? $scope : 'all';
}

function vf_fw_is_private(array $asset): bool
{
    if (array_key_exists('effective_private', $asset)) return (int)$asset['effective_private'] === 1;
    if (array_key_exists('category_private', $asset) && (int)$asset['category_private'] === 1) return true;
    return (int)($asset['is_private'] ?? 0) === 1;
}

function vf_fw_filter_scope(array $assets, string $scope): array
{
    if ($scope === 'all') return array_values($assets);
    $wantPrivate = $scope === 'private';
    return array_values(array_filter($assets, static fn(array $asset): bool => vf_fw_is_private($asset) === $wantPrivate));
}

function vf_fw_category_map(array $categories): array
{
    $map = [];
    foreach ($categories as $category) {
        $id = (int)($category['id'] ?? 0);
        if ($id > 0) $map[$id] = $category;
    }
    return $map;
}

function vf_fw_category_children(array $categories): array
{
    $groups = [];
    $visibleCounts = $GLOBALS['vf_fw_category_visible_counts'] ?? null;
    foreach ($categories as $category) {
        $id = (int)($category['id'] ?? 0);
        if ($id <= 0) continue;
        // After subtree counts are known, daily navigation should not expose empty
        // classification shells. The category manager remains the maintenance UI.
        if (is_array($visibleCounts) && (int)($visibleCounts[$id] ?? 0) <= 0) continue;
        $parent = $category['parent_id'] === null ? 0 : (int)$category['parent_id'];
        $groups[$parent][] = $category;
    }
    foreach ($groups as &$siblings) {
        usort($siblings, static function(array $a, array $b): int {
            $sort = (int)($b['sort_order'] ?? 0) <=> (int)($a['sort_order'] ?? 0);
            if ($sort !== 0) return $sort;
            $legacy = (int)($a['legacy_position'] ?? 0) <=> (int)($b['legacy_position'] ?? 0);
            if ($legacy !== 0) return $legacy;
            return (int)($a['id'] ?? 0) <=> (int)($b['id'] ?? 0);
        });
        $siblings = array_map(static fn(array $category): int => (int)$category['id'], $siblings);
    }
    unset($siblings);
    return $groups;
}

function vf_fw_descendant_ids(array $categories, int $categoryId): array
{
    if ($categoryId <= 0) return [];
    $children = vf_fw_category_children($categories);
    $seen = [];
    $stack = [$categoryId];
    while ($stack) {
        $id = array_pop($stack);
        if ($id <= 0 || isset($seen[$id])) continue;
        $seen[$id] = true;
        foreach ($children[$id] ?? [] as $child) $stack[] = (int)$child;
    }
    return array_map('intval', array_keys($seen));
}

function vf_fw_filter_category(array $assets, array $categories, int $categoryId): array
{
    if ($categoryId <= 0) return array_values($assets);
    $allowed = array_fill_keys(vf_fw_descendant_ids($categories, $categoryId), true);
    return array_values(array_filter($assets, static fn(array $asset): bool => isset($allowed[(int)($asset['category_id'] ?? 0)])));
}

function vf_fw_category_subtree_counts(array $assets, array $categories): array
{
    $direct = [];
    foreach ($assets as $asset) {
        $id = (int)($asset['category_id'] ?? 0);
        if ($id > 0) $direct[$id] = ($direct[$id] ?? 0) + 1;
    }
    // Count against the complete active tree first. Only after the totals are
    // known do later rendering/selection calls hide zero-count branches.
    unset($GLOBALS['vf_fw_category_visible_counts']);
    $children = vf_fw_category_children($categories);
    $memo = [];
    $sum = function(int $id) use (&$sum, &$memo, $children, $direct): int {
        if (isset($memo[$id])) return $memo[$id];
        $total = (int)($direct[$id] ?? 0);
        foreach ($children[$id] ?? [] as $child) $total += $sum((int)$child);
        return $memo[$id] = $total;
    };
    foreach ($categories as $category) {
        $id = (int)($category['id'] ?? 0);
        if ($id > 0) $sum($id);
    }
    $GLOBALS['vf_fw_category_visible_counts'] = $memo;
    return $memo;
}

function vf_fw_kind_counts(array $assets, string $mode = ''): array
{
    $counts = [];
    foreach ($assets as $asset) {
        $kind = VfWorkspaceViewCatalog::viewKind($asset, $mode);
        if ($kind === '') continue;
        $counts[$kind] = ($counts[$kind] ?? 0) + 1;
    }
    if ($counts) uksort($counts, 'strnatcasecmp');
    return $counts;
}

function vf_fw_kind_value(array $counts): string
{
    $kind = trim((string)($_GET['kind'] ?? ''));
    return $kind !== '' && isset($counts[$kind]) ? $kind : '';
}

function vf_fw_filter_kind(array $assets, string $kind, string $mode = ''): array
{
    if ($kind === '') return array_values($assets);
    return array_values(array_filter($assets, static fn(array $asset): bool => VfWorkspaceViewCatalog::viewKind($asset, $mode) === $kind));
}

function vf_fw_kind_label(string $mode): string
{
    return match ($mode) {
        'channels' => '频道分类',
        'watch' => '内容类型',
        'topics' => '专题分类',
        'courses' => '课程分类',
        'tools' => '使用场景',
        'software' => '软件用途',
        'projects' => '项目类型',
        default => '主分类',
    };
}

function vf_fw_kind_display_label(string $mode, string $kind): string
{
    $raw = trim($kind);
    if ($raw === '') return '';
    $key = strtolower($raw);
    $labels = match ($mode) {
        'channels' => [
            'youtube' => 'YouTube',
            'podcast' => '播客',
            'bilibili' => '哔哩哔哩',
        ],
        'watch' => [
            'movie' => '电影',
            'series' => '剧集',
            'documentary' => '纪录片',
            'variety' => '综艺',
            'anime' => '动漫',
        ],
        default => [],
    };
    return $labels[$key] ?? $raw;
}

function vf_fw_surface_counts(array $assets): array
{
    return VfWorkspaceViewCatalog::counts($assets);
}

function vf_fw_scope_counts(array $assets): array
{
    $out = ['all' => count($assets), 'public' => 0, 'private' => 0];
    foreach ($assets as $asset) $out[vf_fw_is_private($asset) ? 'private' : 'public']++;
    return $out;
}

function vf_fw_base_route(string $mode): string
{
    return match ($mode) {
        'start' => 'start.php',
        'channels' => 'channels.php',
        'watch' => 'watch.php',
        'topics' => 'topics.php',
        'books', 'courses' => 'courses.php',
        'tools' => 'tools.php',
        'software' => 'software.php',
        'home' => 'home.php',
        'projects' => 'projects.php',
        default => 'surfaces.php',
    };
}

function vf_fw_url(string $mode, array $changes = []): string
{
    $params = $_GET;
    unset($params['page'], $params['classic']);
    if ($mode !== 'start') unset($params['category']);
    if ($mode === 'start') unset($params['kind']);
    foreach ($changes as $key => $value) {
        if ($value === null || $value === '') unset($params[$key]);
        else $params[$key] = $value;
    }
    $query = http_build_query($params);
    return vf_fw_base_route($mode) . ($query !== '' ? '?' . $query : '');
}

function vf_fw_link(string $mode, array $changes = []): string
{
    return vf_fw_h(vf_fw_url($mode, $changes));
}

function vf_fw_route_link(string $mode, string $scope, int $categoryId = 0, array $extra = []): string
{
    $params = [];
    if ($scope !== 'all' && $scope !== '') $params['scope'] = $scope;
    if ($mode === 'start' && $categoryId > 0) $params['category'] = $categoryId;
    foreach ($extra as $key => $value) {
        if ($value !== null && $value !== '') $params[$key] = $value;
    }
    $query = http_build_query($params);
    return vf_fw_h(vf_fw_base_route($mode) . ($query !== '' ? '?' . $query : ''));
}

function vf_fw_initial(array $asset): string
{
    $title = trim((string)($asset['title'] ?? ''));
    return vf_fw_h($title !== '' ? mb_substr($title, 0, 1, 'UTF-8') : '•');
}

function vf_fw_image_attrs(bool $priority = false): string
{
    return $priority
        ? ' loading="eager" fetchpriority="high" decoding="async"'
        : ' loading="lazy" decoding="async"';
}

function vf_fw_cover_image_spec(string $context): array
{
    return match ($context) {
        'watch' => [320, [192, 320, 480], '(max-width:760px) calc(50vw - 18px), (max-width:1050px) calc((100vw - 240px)/4), 220px'],
        'topic' => [320, [192, 320, 480, 720], '(max-width:680px) calc(50vw - 16px), 300px'],
        'book' => [480, [320, 480, 720, 960], '(max-width:560px) calc(100vw - 44px), (max-width:820px) 34vw, 220px'],
        'project' => [720, [320, 480, 720, 960], '(max-width:560px) calc(100vw - 24px), (max-width:820px) calc(100vw - 48px), (max-width:1180px) calc((100vw - 270px)/2), 570px'],
        default => [96, [96, 192], '34px'],
    };
}

function vf_fw_cover_image(array $asset, bool $priority = false, string $context = 'row'): string
{
    $canonical = trim((string)($asset['cover_url'] ?? ''));
    if ($canonical === '') return '';
    [$defaultWidth, $widths, $sizes] = vf_fw_cover_image_spec($context);
    $sourceWidth = max(0, (int)($asset['cover_width'] ?? 0));
    $src = ($sourceWidth <= 0 || $defaultWidth < $sourceWidth)
        ? VfResourceCoverDerivative::urlForWidth($canonical, $defaultWidth)
        : $canonical;
    $srcset = VfResourceCoverDerivative::srcset($canonical, $sourceWidth, $widths);
    $responsive = $srcset !== ''
        ? ' srcset="' . vf_fw_h($srcset) . '" sizes="' . vf_fw_h($sizes) . '"'
        : '';
    return '<img src="' . vf_fw_h($src) . '" alt=""' . $responsive . vf_fw_image_attrs($priority) . '>';
}

function vf_fw_asset_image(array $asset, bool $priority = false, string $context = 'row'): string
{
    $surface = (string)($asset['surface'] ?? 'start');
    if ($surface !== 'start' && trim((string)($asset['cover_url'] ?? '')) !== '') {
        return vf_fw_cover_image($asset, $priority, $context);
    }
    $icon = trim((string)($asset['icon_cache_url'] ?? ''));
    return $icon !== '' ? '<img src="' . vf_fw_h($icon) . '" alt=""' . vf_fw_image_attrs($priority) . '>' : '';
}

function vf_fw_icon(array $asset, bool $priority = false): string
{
    $image = vf_fw_asset_image($asset, $priority, 'row');
    return $image !== '' ? $image : '<span>' . vf_fw_initial($asset) . '</span>';
}

function vf_fw_open_href(array $asset, bool $admin): string
{
    $hosted = (string)($asset['surface'] ?? '') === 'topics' && (string)($asset['source_kind'] ?? '') === 'hosted_html' && trim((string)($asset['html_url'] ?? '')) !== '';
    if ($hosted) return $admin ? 'surface-open.php?id=' . (int)$asset['id'] : vf_fw_h((string)$asset['html_url']);
    return $admin ? 'surface-open.php?id=' . (int)$asset['id'] : vf_fw_h((string)$asset['url']);
}

function vf_fw_mode_assets(array $allAssets, string $mode): array
{
    return VfWorkspaceViewCatalog::assets($allAssets, $mode);
}

function vf_fw_mode_label(string $mode): string
{
    return match ($mode) {
        'start' => '导航',
        'channels' => '频道',
        'watch' => '影视',
        'topics' => '专题',
        'books', 'courses' => '课程',
        'tools' => '工具',
        'software' => '软件',
        'projects' => '项目',
        default => '全部资源',
    };
}

function vf_fw_scope_label(string $scope): string
{
    return match ($scope) {
        'public' => '公开',
        'private' => '私人',
        default => '全部',
    };
}

function vf_fw_category_id(array $categories): int
{
    if (vf_fw_mode() !== 'start') return 0;
    $raw = trim((string)($_GET['category'] ?? ''));
    if ($raw === '') return 0;
    if (ctype_digit($raw)) {
        $id = (int)$raw;
        foreach ($categories as $category) if ((int)($category['id'] ?? 0) === $id) return $id;
        return 0;
    }
    foreach ($categories as $category) {
        if ((string)($category['name'] ?? '') === $raw) return (int)$category['id'];
    }
    return 0;
}

function vf_fw_selected_path(array $categories, int $selectedId): array
{
    if ($selectedId <= 0) return [];
    $map = vf_fw_category_map($categories);
    $path = [];
    $id = $selectedId;
    $guard = 0;
    while ($id > 0 && isset($map[$id]) && $guard++ < 32) {
        $path[$id] = true;
        $parent = $map[$id]['parent_id'] ?? null;
        $id = $parent === null ? 0 : (int)$parent;
    }
    return $path;
}
